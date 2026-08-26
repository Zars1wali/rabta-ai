import uuid
import asyncio
import logging
from fastapi import APIRouter, Request, Query, Response, BackgroundTasks, HTTPException
from app.core.config import settings
from app.services.whatsapp import WhatsAppService
from app.services.deepgram import DeepgramService
from app.services.owner_copilot import OwnerCopilotService
from app.services.store_agent import WhatsAppStoreAgent
from app.services.conversation_store import conversation_store
from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo, catalog_repo, conversation_repo
from app.db.repositories.tenant_repo import normalize_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])

whatsapp_service = WhatsAppService()
deepgram_service = DeepgramService()
owner_copilot = OwnerCopilotService()
store_agent = WhatsAppStoreAgent()

# In-process failure counters for monitoring
_webhook_metrics = {
    "messages_received": 0,
    "messages_replied": 0,
    "messages_failed": 0,
    "send_failures": 0,
}


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("WhatsApp webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


async def _send_with_retry(to_phone: str, message: str, request_id: str, max_retries: int = 1) -> bool:
    """Send a WhatsApp message with one retry on failure. Returns True on success."""
    for attempt in range(max_retries + 1):
        sent = await whatsapp_service.send_text_message(to_phone=to_phone, message=message)
        if sent:
            return True
        if attempt < max_retries:
            logger.warning("[%s] Send attempt %d failed to %s, retrying in 2s...", request_id, attempt + 1, to_phone)
            await asyncio.sleep(2)
    _webhook_metrics["send_failures"] += 1
    logger.error("[%s] All send attempts failed to %s", request_id, to_phone)
    return False


async def _send_chunks_with_delays(to_phone: str, chunks: list, request_id: str) -> bool:
    """Send reply as multiple short messages with natural typing delays. Returns True if at least one chunk sent."""
    if not chunks:
        return False
    any_sent = False
    for i, chunk in enumerate(chunks):
        if i > 0:
            await asyncio.sleep(1.2)  # natural typing delay between message bursts
        sent = await _send_with_retry(to_phone, chunk, request_id)
        if sent:
            any_sent = True
        else:
            logger.error("[%s] Failed to send chunk %d/%d to %s", request_id, i + 1, len(chunks), to_phone)
    return any_sent


async def process_inbound_message(message_data: dict, business_phone_id: str):
    """Processes inbound WhatsApp messages via PostgreSQL queries — fully tenant-isolated."""
    request_id = str(uuid.uuid4())[:8]
    from_phone = message_data.get("from")
    msg_type = message_data.get("type")

    logger.info("[%s] Inbound msg from=%s type=%s via=%s", request_id, from_phone, msg_type, business_phone_id)

    try:
        customer_text = ""

        if msg_type == "text":
            customer_text = message_data.get("text", {}).get("body", "")
        elif msg_type == "audio":
            audio_id = message_data.get("audio", {}).get("id")
            if audio_id:
                media_url = await whatsapp_service.get_media_url(audio_id)
                if media_url:
                    transcript = await deepgram_service.transcribe_audio_url(media_url)
                    customer_text = transcript or "[Voice Note Received]"
        elif msg_type == "image":
            caption = message_data.get("image", {}).get("caption", "")
            customer_text = f"[Image sent] {caption}" if caption else "[Image sent]"

        if not customer_text:
            logger.debug("[%s] No extractable text — skipping.", request_id)
            return

        async with AsyncSessionLocal() as session:
            # 1. Look up tenant in PostgreSQL
            tenant = await tenant_repo.get_tenant_by_phone(session, business_phone_id)
            if not tenant:
                logger.error("[%s] No tenant found in DB for phone=%s", request_id, business_phone_id)
                return

            tenant_id = tenant.id
            biz_name = tenant.name
            industry = tenant.industry or "Retail"
            owner_phone = tenant.owner_phone
            active_takeover = tenant.active_takeover_customer_phone

            # 2. Check if sender is Business Owner
            norm_from = normalize_phone(from_phone)
            norm_owner = normalize_phone(owner_phone) if owner_phone else ""

            if norm_owner and norm_from and norm_from == norm_owner:
                logger.info("[%s] Message from owner (%s): %s", request_id, from_phone, customer_text[:80])

                if owner_copilot.is_owner_command(customer_text):
                    result = await owner_copilot.handle_command(
                        command_text=customer_text,
                        business_name=biz_name,
                        active_customer=active_takeover,
                    )
                    if result["action"] == "pause_ai":
                        await tenant_repo.set_human_takeover(session, tenant_id, result.get("customer_phone"))
                    elif result["action"] == "resume_ai":
                        await tenant_repo.set_human_takeover(session, tenant_id, None)
                    elif result["action"] == "add_catalog_item":
                        await catalog_repo.add_catalog_item(
                            session=session,
                            tenant_id=tenant_id,
                            name=result.get("item_name", result.get("raw_text")),
                            price=float(result.get("price", 0)),
                            description="Added via WhatsApp by store owner",
                        )

                    await _send_with_retry(to_phone=from_phone, message=result["message"], request_id=request_id)
                    return

                # Owner types normal text while in takeover mode — forward to customer
                if active_takeover:
                    await _send_with_retry(to_phone=active_takeover, message=customer_text, request_id=request_id)
                    logger.info("[%s] Forwarded owner reply to customer %s", request_id, active_takeover)
                    return

            # 3. Check if customer is in active Human Takeover mode
            if active_takeover and normalize_phone(active_takeover) == norm_from:
                logger.info("[%s] Customer %s in takeover mode — forwarding to owner.", request_id, from_phone)
                if owner_phone:
                    forward_msg = f"Customer ({from_phone}):\n\"{customer_text}\"\n\n(Type your reply directly to respond)"
                    await _send_with_retry(to_phone=owner_phone, message=forward_msg, request_id=request_id)
                return

            # 4. Normal Customer Path — Scoped catalog & conversation from DB
            catalog_context = await catalog_repo.format_catalog_context_for_ai(session, tenant_id)
            policies = (tenant.ai_persona_config or {}).get("policies", "")
            if policies:
                catalog_context += f"\n\nStore Policies:\n{policies}"

            # Load recent conversation history from PostgreSQL
            history = await conversation_store.get_history_async(tenant_id, from_phone, limit=15)

            logger.info("[%s] AI handling customer=%s tenant=%s (history=%d msgs)", request_id, from_phone, biz_name, len(history))

            interaction = await store_agent.handle_customer_interaction(
                customer_message=customer_text,
                business_name=biz_name,
                industry=industry,
                catalog_context=catalog_context,
                conversation_history=history if history else None,
            )

            ai_reply = interaction["reply_text"]
            reply_chunks = interaction.get("reply_chunks") or [ai_reply]
            is_order = interaction["is_order_intent"]

            # Persist customer message & AI response to PostgreSQL
            await conversation_store.add_message_async(tenant_id, from_phone, "customer", customer_text)
            await conversation_store.add_message_async(tenant_id, from_phone, "assistant", ai_reply)

            # 5. Send AI reply
            reply_sent = await _send_chunks_with_delays(from_phone, reply_chunks, request_id)
            if not reply_sent:
                fallback_msg = "Maaf kijiye, abhi technical issue hai. Thori der mein dobara try karein."
                await _send_with_retry(to_phone=from_phone, message=fallback_msg, request_id=request_id, max_retries=2)

            _webhook_metrics["messages_replied" if reply_sent else "messages_failed"] += 1

            # 6. Notify owner on orders/leads
            if owner_phone and reply_sent and is_order:
                try:
                    alert_text = owner_copilot.format_lead_alert(
                        customer_phone=from_phone,
                        customer_message=customer_text,
                        ai_reply=ai_reply,
                        reason="NEW ORDER / LEAD",
                    )
                    await _send_with_retry(to_phone=owner_phone, message=alert_text, request_id=request_id)
                except Exception as owner_err:
                    logger.warning("[%s] Owner notification failed: %s", request_id, owner_err)

    except Exception as e:
        logger.error("[%s] UNHANDLED error in process_inbound_message: %s", request_id, e, exc_info=True)
        _webhook_metrics["messages_failed"] += 1
        try:
            if from_phone:
                fallback = "Maaf kijiye, technical issue aa gaya hai. Thori der mein dobara try karein ya owner se baat karein."
                await _send_with_retry(to_phone=from_phone, message=fallback, request_id=request_id, max_retries=2)
        except Exception as fallback_err:
            logger.error("[%s] Emergency fallback failed for %s: %s", request_id, from_phone, fallback_err)


@router.get("/webhook-metrics")
async def get_webhook_metrics():
    """Monitoring endpoint for Cloud API webhook path."""
    total_in = _webhook_metrics["messages_received"]
    total_out = _webhook_metrics["messages_replied"]
    total_err = _webhook_metrics["messages_failed"]
    return {
        "messages_received": total_in,
        "messages_replied": total_out,
        "messages_failed": total_err,
        "send_failures": _webhook_metrics["send_failures"],
        "success_rate_pct": round((total_out / total_in * 100) if total_in else 0, 1),
    }


@router.post("")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives incoming event notifications from WhatsApp Cloud API."""
    body = await request.json()
    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                metadata = value.get("metadata", {})
                business_phone_id = metadata.get("phone_number_id")

                for message in messages:
                    _webhook_metrics["messages_received"] += 1
                    background_tasks.add_task(process_inbound_message, message, business_phone_id)

        return {"status": "ok"}
    except Exception as e:
        logger.error("Error parsing incoming webhook: %s", e, exc_info=True)
        return {"status": "error"}
