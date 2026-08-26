import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.webhooks import router as webhook_router
from app.api.business_onboarding import router as business_router
from app.api.gateway_bridge import router as gateway_router
from app.api.admin_security import router as admin_router
from app.api.social_ingest import router as social_router
from app.services.knowledge_base import KnowledgeBaseService
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("rabta-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing RABTA AI Backend Services...")
    kb = KnowledgeBaseService()
    await kb.init_collection()  # Creates both text and image collections
    yield
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

# Mount static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(webhook_router)
app.include_router(business_router)
app.include_router(gateway_router)
app.include_router(admin_router)
app.include_router(social_router)


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
