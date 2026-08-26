import time
import uuid
import base64
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter
from app.services.store_agent import WhatsAppStoreAgent
from app.services.owner_copilot import OwnerCopilotService
from app.services.conversation_store import conversation_store
from app.services.deepgram import DeepgramService
from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo
from app.db.repositories.tenant_repo import normalize_phone

owner_copilot = OwnerCopilotService()
deepgram_service = DeepgramService()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gateway", tags=["WhatsApp QR Gateway Bridge"])
store_agent = WhatsAppStoreAgent()

# ---------------------------------------------------------------------------
# In-process metrics with timestamps for latency/failure tracking
# ---------------------------------------------------------------------------
_metrics = {
    "total_incoming": 0,
    "total_replies": 0,
    "total_errors": 0,
    "total_gemini_ms": 0,
    "total_send_failures": 0,
    "per_business": {},
    "recent_failures": [],
}


def _track(phone: str, event: str, latency_ms: int = 0):
    key = "total_incoming" if event == "in" else "total_replies" if event == "out" else "total_errors"
    _metrics[key] += 1
    if latency_ms and event == "out":
        _metrics["total_gemini_ms"] += latency_ms
    biz = _metrics["per_business"].setdefault(phone, {"in": 0, "out": 0, "err": 0, "total_latency_ms": 0})
    if event in biz:
        biz[event] += 1
    if event == "out" and latency_ms:
        biz["total_latency_ms"] = biz.get("total_latency_ms", 0) + latency_ms


def _record_failure(phone: str, customer_phone: str, error: str, request_id: str = "?"):
    _metrics["total_send_failures"] += 1
    entry = {"phone": phone, "customer": customer_phone, "error": str(error)[:200], "request_id": request_id, "ts": time.time()}
    _metrics["recent_failures"].append(entry)
    if len(_metrics["recent_failures"]) > 50:
        _metrics["recent_failures"] = _metrics["recent_failures"][-50:]


class GatewayMessagePayload(BaseModel):
    customer_phone: str
    business_phone: str
    message: str
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None   # raw voice note bytes as base64
    audio_mime: Optional[str] = None     # e.g. "audio/ogg; codecs=opus"
    platform: str = "baileys_qr"


@router.post("/process-message")
async def process_gateway_message(payload: GatewayMessagePayload):
    """Receives incoming WhatsApp messages from the Baileys QR gateway,
    runs the Gemini store agent using isolated PostgreSQL data, and returns
    the reply split into natural WhatsApp message chunks.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    _track(payload.business_phone, "in")

    # --- Voice Note: Transcribe with Deepgram BEFORE anything else ---
    effective_message = payload.message
    is_voice_note = bool(payload.audio_base64)
    if is_voice_note:
        logger.info("[%s] Voice note received (%d bytes) — transcribing with Deepgram",
                    request_id, len(payload.audio_base64))
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
            mime = payload.audio_mime or "audio/ogg; codecs=opus"
            transcript = await deepgram_service.transcribe_audio_bytes(audio_bytes, mime)
            if transcript and transcript.strip():
                effective_message = transcript.strip()
                logger.info("[%s] Deepgram transcript: %s", request_id, effective_message[:120])
            else:
                effective_message = "Customer ne voice note bheja, lekin transcript nahi mila."
                logger.warning("[%s] Deepgram returned empty transcript", request_id)
        except Exception as e:
            logger.error("[%s] Deepgram transcription failed: %s", request_id, e)
            effective_message = "Customer ne voice message bheja."

    logger.info(
        "[%s] Inbound gateway message from customer %s for business %s: %s (has_image=%s, is_voice=%s)",
        request_id, payload.customer_phone, payload.business_phone,
        effective_message[:60], bool(payload.image_base64), is_voice_note
    )

    try:
        async with AsyncSessionLocal() as session:
            # 1. Resolve tenant from PostgreSQL
            tenant = await tenant_repo.get_tenant_by_phone(session, payload.business_phone)
            if not tenant:
                logger.warning("[%s] No tenant found in DB for %s", request_id, payload.business_phone)
                return {
                    "reply": "Store is currently setting up. Please try again shortly.",
                    "reply_chunks": ["Store is currently setting up. Please try again shortly."],
                    "is_order": False,
                    "business_name": "Rabta Store",
                }

            tenant_id = tenant.id
            biz_name = tenant.name
            industry = tenant.industry or "Retail"
            owner_phone = tenant.owner_phone
            active_takeover = tenant.active_takeover_customer_phone

            # 2. Check if sender is Store Owner
            norm_from = normalize_phone(payload.customer_phone)
            norm_owner = normalize_phone(owner_phone) if owner_phone else ""

            if norm_owner and norm_from and norm_from == norm_owner:
                logger.info("[%s] Gateway message is from OWNER (%s): %s", request_id, payload.customer_phone, effective_message[:60])

                if owner_copilot.is_owner_command(effective_message):
                    cmd_res = await owner_copilot.handle_command(
                        command_text=payload.message,
                        business_name=biz_name,
                        active_customer=active_takeover,
                    )
                    if cmd_res["action"] == "pause_ai":
                        await tenant_repo.set_human_takeover(session, tenant_id, cmd_res.get("customer_phone"))
                    elif cmd_res["action"] == "resume_ai":
                        await tenant_repo.set_human_takeover(session, tenant_id, None)
                    elif cmd_res["action"] == "add_catalog_item":
                        await catalog_repo.add_catalog_item(
                            session=session,
                            tenant_id=tenant_id,
                            name=cmd_res.get("item_name", cmd_res.get("raw_text")),
                            price=float(cmd_res.get("price", 0)),
                            description="Added via WhatsApp by store owner",
                        )

                    return {
                        "reply": cmd_res["message"],
                        "reply_chunks": [cmd_res["message"]],
                        "is_order": False,
                        "is_owner_command": True,
                        "business_name": biz_name,
                    }

                # Owner typed normal message while in takeover
                if active_takeover:
                    return {
                        "reply": payload.message,
                        "reply_chunks": [payload.message],
                        "is_order": False,
                        "forward_to_customer": active_takeover,
                        "business_name": biz_name,
                    }

            # 3. Check if customer is in Human Takeover mode
            if active_takeover and normalize_phone(active_takeover) == norm_from:
                logger.info("[%s] Customer %s in human takeover mode — forwarding to owner.", request_id, payload.customer_phone)
                return {
                    "reply": "",
                    "reply_chunks": [],
                    "is_order": False,
                    "in_human_takeover": True,
                    "forward_to_owner": owner_phone,
                    "business_name": biz_name,
                }

            # 4. Scoped catalog context and conversation history from DB
            catalog_context = await catalog_repo.format_catalog_context_for_ai(session, tenant_id)
            policies = (tenant.ai_persona_config or {}).get("policies", "")
            if policies:
                catalog_context += f"\n\nStore Policies:\n{policies}"

            history = await conversation_store.get_history_async(tenant_id, payload.customer_phone, limit=15)

            gemini_start = time.time()
            interaction = await store_agent.handle_customer_interaction(
                customer_message=effective_message,
                business_name=biz_name,
                industry=industry,
                catalog_context=catalog_context,
                conversation_history=history if history else None,
                image_base64=payload.image_base64,
            )
            gemini_latency = int((time.time() - gemini_start) * 1000)

            reply_text = interaction.get("reply_text", "")
            reply_chunks = interaction.get("reply_chunks") or [reply_text]
            is_order = interaction.get("is_order_intent", False)

            # Persist to DB — store the effective (transcribed) message
            await conversation_store.add_message_async(tenant_id, payload.customer_phone, "customer", effective_message)
            await conversation_store.add_message_async(tenant_id, payload.customer_phone, "assistant", reply_text)

            total_latency = int((time.time() - start_time) * 1000)
            _track(payload.business_phone, "out", gemini_latency)

            logger.info(
                "[%s] AI reply generated in %dms (gemini=%dms, chunks=%d): %s",
                request_id, total_latency, gemini_latency, len(reply_chunks), reply_text[:60]
            )

            return {
                "reply": reply_text,
                "reply_chunks": reply_chunks,
                "is_order": is_order,
                "business_name": biz_name,
                "latency_ms": total_latency,
                "gemini_ms": gemini_latency,
                "owner_alert": owner_copilot.format_lead_alert(
                    customer_phone=payload.customer_phone,
                    customer_message=payload.message,
                    ai_reply=reply_text,
                    reason="NEW ORDER / LEAD" if is_order else "Inquiry"
                ) if is_order and owner_phone else None,
                "owner_phone": owner_phone if is_order else None,
            }

    except Exception as e:
        total_latency = int((time.time() - start_time) * 1000)
        _track(payload.business_phone, "err")
        _record_failure(payload.business_phone, payload.customer_phone, str(e), request_id)
        logger.error("[%s] Gateway processing failed after %dms: %s", request_id, total_latency, e, exc_info=True)

        return {
            "reply": "Maaf kijiye, technical issue aa gaya hai. Thori der mein dobara try karein ya owner se baat karein.",
            "reply_chunks": ["Maaf kijiye, technical issue aa gaya hai. Thori der mein dobara try karein ya owner se baat karein."],
            "is_order": False,
            "business_name": "Store",
            "error": str(e),
        }


@router.get("/metrics")
async def get_gateway_metrics():
    """Returns gateway performance metrics."""
    avg_latency = 0
    if _metrics["total_replies"] > 0:
        avg_latency = int(_metrics["total_gemini_ms"] / _metrics["total_replies"])

    return {
        "total_incoming": _metrics["total_incoming"],
        "total_replies": _metrics["total_replies"],
        "total_errors": _metrics["total_errors"],
        "total_send_failures": _metrics["total_send_failures"],
        "avg_gemini_latency_ms": avg_latency,
        "per_business": _metrics["per_business"],
        "recent_failures_count": len(_metrics["recent_failures"]),
        "recent_failures": _metrics["recent_failures"][-10:],
    }
