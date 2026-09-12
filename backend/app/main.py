import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI

# psycopg3 (used by the LangGraph checkpointer) cannot run on Windows'
# default ProactorEventLoop. Force the selector loop before any loop is created.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass  # Python 3.16+ removed the policy API — loop_factory is preferred there

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.webhooks import router as webhook_router
from app.api.business_onboarding import router as business_router
from app.api.gateway_bridge import router as gateway_router
from app.api.admin_security import router as admin_router
from app.api.social_ingest import router as social_router
from app.api.catalog_import import router as catalog_import_router
from app.api.visual_search_api import router as visual_search_router
from app.services.knowledge_base import KnowledgeBaseService
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("rabta-api")


async def _conversation_cleanup_loop():
    """Background task: purge messages and close conversations inactive for 48+ hours.
    Runs every 6 hours so the AI always has a fresh, unbiased context window.
    """
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import text
    CLEANUP_INTERVAL_SECONDS = 6 * 3600  # run every 6 hours
    STALE_HOURS = 48

    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            logger.info("[Cleanup] Starting 48h conversation history purge...")
            async with AsyncSessionLocal() as session:
                # Delete messages from conversations that have had no activity in 48h
                del_msgs = await session.execute(text(
                    f"""
                    DELETE FROM messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations
                        WHERE COALESCE(last_message_at, created_at) < NOW() - INTERVAL '{STALE_HOURS} hours'
                        AND status = 'active'
                    )
                    """
                ))
                # Close those stale conversations (marks them inactive for next session)
                close_convs = await session.execute(text(
                    f"""
                    UPDATE conversations
                    SET status = 'closed'
                    WHERE COALESCE(last_message_at, created_at) < NOW() - INTERVAL '{STALE_HOURS} hours'
                    AND status = 'active'
                    """
                ))
                await session.commit()
                logger.info(
                    "[Cleanup] Purge complete: %s messages deleted, %s conversations closed.",
                    del_msgs.rowcount, close_convs.rowcount,
                )
        except asyncio.CancelledError:
            logger.info("[Cleanup] Conversation cleanup task cancelled.")
            break
        except Exception as exc:
            logger.error("[Cleanup] Error during conversation cleanup: %s", exc, exc_info=True)


async def _polite_followup_loop():
    """Background worker: periodically scans for quiet conversations (idle 10-15 mins)
    and sends a single polite, grounded follow-up message with official social channels.
    Runs every 60 seconds.
    """
    from app.services.followup_service import followup_service
    FOLLOWUP_SCAN_INTERVAL = 60  # seconds

    while True:
        try:
            await asyncio.sleep(FOLLOWUP_SCAN_INTERVAL)
            await followup_service.scan_and_process_followups(idle_minutes=10.0, max_hours=24.0)
        except asyncio.CancelledError:
            logger.info("[FollowUp] Follow-up scheduler cancelled.")
            break
        except Exception as exc:
            logger.error("[FollowUp] Error in follow-up worker loop: %s", exc, exc_info=True)


_scheduler_lock_file = None


def _acquire_scheduler_leader() -> bool:
    """Acquire non-blocking flock to ensure only ONE worker process runs background cron loops."""
    global _scheduler_lock_file
    try:
        import fcntl
        _scheduler_lock_file = open("/tmp/rabta_scheduler.lock", "w")
        fcntl.flock(_scheduler_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, AttributeError):
        # Fallback for environments without fcntl (e.g. Windows dev)
        return True
    except (IOError, BlockingIOError):
        return False


def _release_scheduler_leader():
    global _scheduler_lock_file
    if _scheduler_lock_file:
        try:
            import fcntl
            fcntl.flock(_scheduler_lock_file, fcntl.LOCK_UN)
            _scheduler_lock_file.close()
        except Exception:
            pass
        _scheduler_lock_file = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing RABTA AI Backend Services...")
    kb = KnowledgeBaseService()
    await kb.init_collection()  # Creates both text and image collections

    # Initialize LangGraph conversation engine with PostgreSQL checkpointer
    try:
        from app.graph.builder import init_graph
        await init_graph()
        logger.info("[Graph] LangGraph conversation engine initialized successfully.")
    except Exception as exc:
        logger.error("[Graph] Failed to initialize LangGraph: %s", exc, exc_info=True)

    is_leader = _acquire_scheduler_leader()
    cleanup_task = None
    followup_task = None

    if is_leader:
        logger.info("[SchedulerLeader] This worker acquired leader lock. Starting background workers...")
        cleanup_task = asyncio.create_task(_conversation_cleanup_loop())
        # Outbound automated follow-ups disabled: only respond when customer messages or owner explicitly relays
        followup_task = None
        try:
            from app.services.scheduler_agent import scheduler_agent
            await scheduler_agent.start()
            logger.info("[SchedulerAgent] Autonomous scheduler agent started on leader worker.")
        except Exception as exc:
            logger.error("[SchedulerAgent] Failed to start scheduler agent: %s", exc, exc_info=True)
    else:
        logger.info("[SchedulerLeader] Another worker is already the scheduler leader. Background tasks skipped on this worker.")

    yield

    try:
        from app.graph.checkpointer import close_checkpointer
        await close_checkpointer()
    except Exception:
        pass

    if is_leader:
        try:
            from app.services.scheduler_agent import scheduler_agent
            await scheduler_agent.stop()
        except Exception:
            pass

        if cleanup_task:
            cleanup_task.cancel()
        if followup_task:
            followup_task.cancel()
        try:
            if cleanup_task:
                await cleanup_task
            if followup_task:
                await followup_task
        except asyncio.CancelledError:
            pass
        _release_scheduler_leader()

    logger.info("Shutting down RABTA AI Backend...")


app = FastAPI(
    title="RABTA AI — Core API Engine",
    description="Omnichannel AI Employee SaaS for Pakistani Businesses",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: locked to production domain in prod, permissive in dev
_allowed_origins = (
    [settings.ALLOWED_ORIGINS] if getattr(settings, "ALLOWED_ORIGINS", None) and settings.ENVIRONMENT == "production"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder — includes catalog_images subdirectory
static_dir = os.path.join(os.path.dirname(__file__), "static")
catalog_images_dir = os.path.join(static_dir, "catalog_images")
os.makedirs(catalog_images_dir, exist_ok=True)
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(webhook_router)
app.include_router(business_router)
app.include_router(gateway_router)
app.include_router(admin_router)
app.include_router(social_router)
app.include_router(catalog_import_router)
app.include_router(visual_search_router)


@app.get("/", response_class=HTMLResponse)
async def serve_landing_page():
    """Serves the Rabta AI marketing and landing page."""
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Landing page not found</h1>", status_code=404)


@app.get("/onboard", response_class=HTMLResponse)
async def serve_onboarding_page():
    """Serves the interactive business onboarding web UI."""
    html_path = os.path.join(static_dir, "onboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Onboarding page not found</h1>", status_code=404)


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_page():
    """Serves the merchant management dashboard UI."""
    html_path = os.path.join(static_dir, "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Dashboard page not found</h1>", status_code=404)


@app.get("/api/info")
async def api_info():
    return {
        "status": "online",
        "service": "RABTA AI Core Engine",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health():
    """Health check endpoint used by Docker and uptime monitors."""
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "ok"}
    except Exception as e:
        return {"status": "degraded", "db": "error", "detail": str(e)}
