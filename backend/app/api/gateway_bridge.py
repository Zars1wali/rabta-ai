import time
import uuid
import base64
import logging
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel
from fastapi import APIRouter

from app.services.conversation_store import conversation_store
from app.services.deepgram import DeepgramService
from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo
from app.db.repositories.tenant_repo import normalize_phone
from app.graph.builder import get_graph
from app.graph.checkpointer import make_thread_config
from app.graph.state import RabtaGraphState

deepgram_service = DeepgramService()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gateway", tags=["WhatsApp QR Gateway Bridge"])

# ---------------------------------------------------------------------------
# Catalog cache (60s TTL) + recent media cache (300s TTL) + metrics
# ---------------------------------------------------------------------------
_catalog_cache: Dict[str, Any] = {}
_recent_media_cache: Dict[str, Tuple[float, str]] = {}
_metrics = {
    "total_incoming": 0,
    "total_replies": 0,
    "total_errors": 0,
    "recent_failures": [],
}


def _record_failure(business_phone: str, customer_phone: str, error: str, request_id: str):
    _metrics["recent_failures"].append({
        "business": business_phone,
        "customer": customer_phone,
        "error": str(error)[:200],
        "request_id": request_id,
        "ts": time.time(),
    })
    _metrics["recent_failures"] = _metrics["recent_failures"][-50:]


def invalidate_catalog_cache(tenant_id: str):
    _catalog_cache.pop(tenant_id, None)


async def _get_cached_catalog(session, tenant_id: str) -> str:
    now = time.time()
    cached = _catalog_cache.get(tenant_id)
    if cached and cached["expires"] > now:
        return cached["text"]
    text = await catalog_repo.format_catalog_context_for_ai(session, tenant_id)
    _catalog_cache[tenant_id] = {"text": text, "expires": now + 60.0}
    return text


class GatewayMessagePayload(BaseModel):
    customer_phone: str
    business_phone: str
    message: str
    real_phone: Optional[str] = None
    push_name: Optional[str] = None
    sender_jid: Optional[str] = None
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime: Optional[str] = None
    platform: str = "baileys_qr"



@router.post("/process-message")
async def process_gateway_message(payload: GatewayMessagePayload):
    """
    Central message router for Rabta AI WhatsApp Gateway.
    All routing & state transitions are driven by LangGraph state machine.
    """
    _metrics["total_incoming"] += 1
    start_time = time.time()

    # --- Voice transcription ---
    effective_message = payload.message
    if payload.audio_base64:
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
            transcript = await deepgram_service.transcribe_audio_bytes(
                audio_bytes, payload.audio_mime or "audio/ogg; codecs=opus"
            )
            if transcript and transcript.strip():
                effective_message = transcript.strip()
        except Exception as e:
            logger.error("Deepgram transcription error: %s", e)

    logger.info("Inbound [%s]: %s", payload.customer_phone, effective_message[:80])

    try:
        async with AsyncSessionLocal() as session:
            tenant = await tenant_repo.get_tenant_by_phone(session, payload.business_phone)
            if not tenant:
                return _reply("Store setting up. Please try again shortly.")

            tenant_id = tenant.id
            biz_name = tenant.name
            industry = tenant.industry or "Retail"
            owner_phone = tenant.owner_phone or "+923169827188"
            active_takeover = tenant.active_takeover_customer_phone

            # ---------------------------------------------------------------
            # 1. OWNER / BOSS IDENTIFICATION
            # ---------------------------------------------------------------
            norm_from = normalize_phone(payload.customer_phone)
            norm_owner = normalize_phone(owner_phone)
            is_boss = bool(norm_from and norm_owner and norm_from == norm_owner)

            logger.info(
                "Routing message: from=%s owner=%s is_boss=%s",
                norm_from, norm_owner, is_boss
            )

            # ---------------------------------------------------------------
            # 2. HUMAN TAKEOVER
            # ---------------------------------------------------------------
            if not is_boss and active_takeover and normalize_phone(active_takeover) == norm_from:
                return {
                    "reply": "", "reply_chunks": [],
                    "forward_to_owner": owner_phone,
                    "forward_message": f"[Customer says]: {effective_message}",
                    "is_order": False, "business_name": biz_name,
                }

            # ---------------------------------------------------------------
            # 3. CONTEXT GATHERING
            # ---------------------------------------------------------------
            catalog_context = await _get_cached_catalog(session, str(tenant_id))
            history = await conversation_store.get_history_async(
                tenant_id, payload.customer_phone if not is_boss else norm_from, limit=10
            )

            # Preserve uploaded media across short follow-up messages (e.g. Turn 1: photo, Turn 2: "Add this" or "Price 700k")
            effective_image_b64 = payload.image_base64
            if payload.image_base64:
                _recent_media_cache[norm_from] = (time.time(), payload.image_base64)
            elif norm_from in _recent_media_cache:
                cached_ts, cached_b64 = _recent_media_cache[norm_from]
                if (time.time() - cached_ts) < 300:  # 5 minutes TTL
                    msg_l = effective_message.lower()
                    if any(kw in msg_l for kw in ["add", "photo", "image", "pic", "tasveer", "ye", "yeh", "isko", "is ko", "this", "kardo", "kar do", "rate", "price"]):
                        effective_image_b64 = cached_b64

            # ---------------------------------------------------------------
            # 4. LANGGRAPH INVOCATION
            # ---------------------------------------------------------------
            from app.graph.builder import get_graph_async
            graph = await get_graph_async()
            thread_config = make_thread_config(str(tenant_id), norm_from)

            # Detect real SIM phone
            detected_sim = payload.real_phone or (
                norm_from if len(norm_from) <= 12 and (norm_from.startswith("923") or norm_from.startswith("03") or norm_from.startswith("3"))
                else None
            )

            input_state: RabtaGraphState = {
                "tenant_id": str(tenant_id),
                "is_boss": is_boss,
                "sender_phone": norm_from,
                "owner_phone": owner_phone,
                "business_phone": payload.business_phone,
                "business_name": biz_name,
                "industry": industry,
                "raw_message": effective_message,
                "catalog_context": catalog_context,
                "image_base64": effective_image_b64,
                "conversation_history": history,
                "customer_sim_phone": detected_sim,
                "push_name": payload.push_name,
                # Reset turn-specific outputs explicitly so nothing bleeds from prior turns in checkpointer
                "reply_text": "",
                "reply_chunks": [],

                "media_url": None,
                "media_urls": None,
                "owner_alert": None,
                "forward_to_customer": None,
                "forward_message": None,
                "escalation_resolved_for": None,
                "escalation_resolved_id": None,
            }

            result_state = await graph.ainvoke(input_state, thread_config)

            reply_text = result_state.get("reply_text") or ""
            reply_chunks = result_state.get("reply_chunks") or ([reply_text] if reply_text else [])
            owner_alert = result_state.get("owner_alert")
            forward_to_customer = result_state.get("forward_to_customer")
            forward_message = result_state.get("forward_message")

            # Persist messages in DB
            if not is_boss:
                await conversation_store.add_message_async(
                    tenant_id, payload.customer_phone, "customer", effective_message
                )
                if reply_text:
                    await conversation_store.add_message_async(
                        tenant_id, payload.customer_phone, "assistant", reply_text
                    )
            else:
                await conversation_store.add_message_async(
                    tenant_id, norm_from, "customer", effective_message
                )
                if reply_text:
                    await conversation_store.add_message_async(
                        tenant_id, norm_from, "assistant", reply_text
                    )
                # If boss replied to an escalation, relay & save in customer thread
                if forward_to_customer and forward_message:
                    norm_cust = normalize_phone(forward_to_customer)
                    # Reset the customer's graph state to BROWSING
                    try:
                        cust_thread_config = make_thread_config(str(tenant_id), norm_cust)
                        await graph.aupdate_state(
                            cust_thread_config,
                            {"customer_state": "BROWSING", "escalation_id": None}
                        )
                    except Exception as esc_upd_err:
                        logger.warning("Could not reset customer thread state: %s", esc_upd_err)

                    await conversation_store.add_message_async(
                        tenant_id, forward_to_customer, "assistant", forward_message
                    )

            _metrics["total_replies"] += 1
            return {
                "reply": reply_text,
                "reply_chunks": reply_chunks,
                "media_url": result_state.get("media_url"),
                "media_urls": result_state.get("media_urls"),
                "is_order": False,
                "needs_escalation": bool(owner_alert),
                "owner_alert": owner_alert,
                "owner_phone": owner_phone,
                "forward_to_customer": forward_to_customer,
                "forward_message": forward_message,
                "business_name": biz_name,
                "latency_ms": int((time.time() - start_time) * 1000),
            }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[GATEWAY EXCEPTION] {e}\n{tb}", flush=True)
        logger.error("Gateway bridge error: %s\n%s", e, tb, exc_info=True)
        _metrics["total_errors"] += 1
        _record_failure(payload.business_phone, payload.customer_phone, str(e)[:200], str(start_time))
        # Global safeguard: Never leak internal python exception strings to user/owner
        return _reply("Maaf kijiye, system mein temporary technical issue aaya hai. Thori der mein dobara message karein.")


@router.get("/metrics")
async def gateway_metrics():
    """Operational dashboard for the WhatsApp QR gateway bridge."""
    return {
        "total_incoming": _metrics["total_incoming"],
        "total_replies": _metrics["total_replies"],
        "total_errors": _metrics["total_errors"],
        "recent_failures": _metrics["recent_failures"],
        "per_business": {},
        "avg_latency_ms": 0,
    }


class FollowUpTriggerPayload(BaseModel):
    idle_minutes: float = 10.0
    max_hours: float = 24.0
    tenant_id: Optional[str] = None
    force_conversation_id: Optional[str] = None


@router.post("/trigger-followups")
async def trigger_followups(payload: FollowUpTriggerPayload = FollowUpTriggerPayload()):
    """Manually trigger or test polite follow-up scan for idle conversations."""
    from app.services.followup_service import followup_service
    t_uuid = uuid.UUID(payload.tenant_id) if payload.tenant_id else None
    c_uuid = uuid.UUID(payload.force_conversation_id) if payload.force_conversation_id else None
    processed = await followup_service.scan_and_process_followups(
        idle_minutes=payload.idle_minutes,
        max_hours=payload.max_hours,
        tenant_id=t_uuid,
        force_conversation_id=c_uuid,
    )
    return {"status": "ok", "processed_count": len(processed), "followups": processed}


def _reply(text: str, biz_name: str = "Haider Arms") -> Dict[str, Any]:
    return {
        "reply": text,
        "reply_chunks": [text],
        "is_order": False,
        "business_name": biz_name,
    }
