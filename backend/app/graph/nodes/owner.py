"""
Rabta AI — Enterprise ReAct Owner Intelligence Node
===================================================
Replaces the brittle 46KB regex/IVR state machine with a modern,
enterprise-grade ReAct Agent powered by Native Gemini Tool Calling.

Zero JSON regex parsing. Deterministic tool execution against PostgreSQL.
"""
from __future__ import annotations
import logging
import base64
from typing import Dict, Any, List, Optional

from app.graph.state import RabtaGraphState
from app.brain.prompts_owner import OWNER_INTELLIGENCE_SYSTEM_PROMPT
from app.services.agent_harness import react_agent_harness

logger = logging.getLogger(__name__)


async def owner_react_node(state: RabtaGraphState) -> RabtaGraphState:
    """
    Core ReAct Agent node for Store Owner communications.
    Natively calls tools: search_catalog, get_product_photos, update_price,
    update_stock_status, add_catalog_item, relay_to_customer, get_pending_escalations.
    """
    import re
    import uuid
    from app.services.owner_copilot import owner_copilot
    from app.services.escalation_service import escalation_service

    raw_message = state.get("raw_message", "").strip()
    tenant_id = state.get("tenant_id", "")
    sender_phone = state.get("sender_phone", "")
    history = state.get("conversation_history") or []
    image_b64 = state.get("image_base64")

    logger.info("[OwnerReActNode] Turn from %s: '%s'", sender_phone, raw_message[:60])

    try:
        t_uuid = uuid.UUID(tenant_id) if tenant_id else uuid.uuid4()
    except Exception:
        t_uuid = uuid.uuid4()

    # 1. Deterministic Slash Commands
    if raw_message.startswith("/"):
        cmd_res = await owner_copilot.handle_command(raw_message, state.get("business_name", "Haider Arms"))
        return {
            **state,
            "reply_text": cmd_res["message"],
            "reply_chunks": [cmd_res["message"]],
            "media_url": None,
            "media_urls": None,
            "owner_alert": None,
        }

    # 2. Intelligent Fast-Path for Pending Customer Inquiries
    # If owner sends a bare number (e.g. "3500"), price, delivery answer, or "customer ko batao..."
    pending_list = escalation_service.get_pending_for_tenant(t_uuid)
    lower_msg = raw_message.lower()

    is_bare_number = bool(re.match(r'^(?:rs\.?|pkr)?\s*(\d+[\d,.]*)\s*(?:pkr|rs|hazar|k)?$', lower_msg.strip()))
    is_relay_command = any(kw in lower_msg for kw in [
        "ko bolo", "ko batao", "ko batado", "ko kaho", "ko keh do", "ko bhej do",
        "wale customer", "wali delivery", "customer ko", "delivery charges"
    ])
    is_payment_approval = any(kw in lower_msg for kw in [
        "account number bhej do", "account details share", "bank details bhej do", "share kardo", "share kar do"
    ])

    if pending_list and (is_bare_number or is_relay_command or is_payment_approval):
        esc, clean_ans = escalation_service.find_target_escalation(t_uuid, raw_message)
        if esc:
            cust_name = esc.customer_name or "Customer"
            name_prefix = f"Jee {cust_name} bhai! " if esc.customer_name else "Jee bhai! "
            
            # Format customer response text
            num_match = re.search(r'(\d+[\d,.]*)', raw_message)
            if "delivery" in esc.customer_question.lower() or "charges" in esc.customer_question.lower() or "delivery" in lower_msg:
                amount_str = num_match.group(1) if num_match else clean_ans
                cust_reply = f"{name_prefix}Shop owner se confirm kar liya hai. {esc.customer_city or 'Delivery'} ke liye delivery charges Rs. {amount_str} hain."
            elif is_payment_approval:
                cust_reply = f"{name_prefix}Shop owner ne approval de di hai. Humari payment details share ki ja rahi hain."
            else:
                cust_reply = f"{name_prefix}Shop owner se confirm kar liya hai: {clean_ans}"

            escalation_service.resolve_escalation(esc.escalation_id, cust_reply)
            target_dest = esc.customer_jid or esc.customer_phone

            # Also try direct gateway delivery
            try:
                import httpx
                for gw_url in ["http://rabta_gateway:3001/api/send-message", "http://localhost:3001/api/send-message", "http://127.0.0.1:3001/api/send-message"]:
                    try:
                        async with httpx.AsyncClient(timeout=4.0) as client:
                            resp = await client.post(gw_url, json={"to": target_dest, "message": cust_reply})
                            if resp.status_code == 200:
                                break
                    except Exception:
                        pass
            except Exception:
                pass

            owner_confirm = f"Jee Haider bhai, {cust_name} ({esc.customer_city or 'inquiry'}) ko message deliver kar diya hai: '{cust_reply}'"
            return {
                **state,
                "reply_text": owner_confirm,
                "reply_chunks": [owner_confirm],
                "forward_to_customer": target_dest,
                "forward_message": cust_reply,
                "escalation_resolved_id": esc.escalation_id,
                "media_url": None,
                "media_urls": None,
                "owner_alert": None,
            }

    # Decode image bytes if owner sent an image
    image_bytes = None
    if image_b64:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as e:
            logger.warning("[OwnerReActNode] Failed to decode image: %s", e)

    execution_context = {
        "tenant_id": str(t_uuid),
        "sender_phone": sender_phone,
        "is_boss": True,
        "pending_image_url": state.get("media_url"),
    }

    # Inject dynamic pending inquiries summary into the ReAct prompt
    pending_summary = escalation_service.format_pending_escalations_summary(t_uuid)
    dynamic_instruction = OWNER_INTELLIGENCE_SYSTEM_PROMPT
    if pending_summary:
        dynamic_instruction = f"{OWNER_INTELLIGENCE_SYSTEM_PROMPT}\n\n{pending_summary}"

    # Execute ReAct conversational turn
    result = await react_agent_harness.run_turn(
        system_instruction=dynamic_instruction,
        user_message=raw_message,
        conversation_history=history,
        role="owner",
        execution_context=execution_context,
        image_bytes=image_bytes,
    )

    reply_text = result.get("reply_text", "")
    reply_chunks = result.get("reply_chunks") or [reply_text]
    media_urls = result.get("media_urls") or []
    media_url = media_urls[0]["url"] if media_urls else None
    fwd_cust = result.get("forward_to_customer")
    fwd_msg = result.get("forward_message")
    esc_res_id = result.get("escalation_resolved_id")

    logger.info(
        "[OwnerReActNode] Completed turn. Tools: %s. Reply: '%s' | Media: %d | Forward: %s",
        result.get("tool_calls_executed"),
        reply_text[:60],
        len(media_urls),
        fwd_cust,
    )

    return {
        **state,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "media_url": media_url,
        "media_urls": media_urls if media_urls else None,
        "forward_to_customer": fwd_cust,
        "forward_message": fwd_msg,
        "escalation_resolved_id": esc_res_id,
        "owner_alert": None,
    }


# --------------------------------------------------------------------------
# Backward-compatibility stubs for graph routing or legacy tests
# --------------------------------------------------------------------------
async def handle_owner_command(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_owner_add_product(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def extract_and_match_price(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_disambiguation(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_confirmation(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def relay_owner_answer(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_owner_greeting(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_owner_info_request(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def handle_owner_inquiry_clarification(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

async def owner_fallback(state: RabtaGraphState) -> RabtaGraphState:
    return await owner_react_node(state)

def route_owner(state: RabtaGraphState) -> str:
    """Dispatches all owner messages directly to the ReAct agent node."""
    return "owner_react_node"
