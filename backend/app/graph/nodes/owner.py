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

    # 2. Check Pending Photo Confirmation (Option 1: Replace vs Option 2: Keep Both)
    from app.services.catalog_tools import (
        get_pending_photo_confirmation,
        resolve_pending_photo_confirmation,
        clear_pending_photo_confirmation,
    )
    pending_photo = get_pending_photo_confirmation(str(t_uuid))
    if pending_photo:
        raw_l = raw_message.strip().lower()
        choice_action = None

        # Option 1: Replace / Delete Old
        if raw_l in ["1", "one", "first", "option 1", "pehla", "pehli", "replace", "delete"]:
            choice_action = "replace"
        elif any(kw in raw_l for kw in ["replace", "purani delete", "old delete", "hata do", "hata dein", "delete kardo", "delete kar do", "badal do"]):
            choice_action = "replace"
        elif re.search(r'\b1\b', raw_l) and not re.search(r'\b2\b', raw_l):
            choice_action = "replace"

        # Option 2: Keep Both / Dono
        elif raw_l in ["2", "two", "second", "option 2", "doosra", "doosri", "dono", "keep", "both", "all", "saari"]:
            choice_action = "keep_both"
        elif any(kw in raw_l for kw in ["dono", "keep", "both", "saari", "sari", "purani bhi", "old bhi", "add kardo", "add kar do", "rakhein", "rakh lo", "rakhlo"]):
            choice_action = "keep_both"
        elif re.search(r'\b2\b', raw_l) and not re.search(r'\b1\b', raw_l):
            choice_action = "keep_both"

        # Cancel
        elif any(kw in raw_l for kw in ["cancel", "rehnay do", "rehnde", "chhoro", "no"]):
            choice_action = "cancel"

        if choice_action:
            res = await resolve_pending_photo_confirmation(str(t_uuid), choice_action)
            reply = res.get("message") or "Photo confirmation updated."
            return {
                **state,
                "reply_text": reply,
                "reply_chunks": [reply],
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
        "sender_aliases": state.get("sender_aliases") or [sender_phone],
        "sender_jid": state.get("sender_jid"),
        "customer_sim_phone": state.get("customer_sim_phone"),
        "pending_image_url": state.get("image_url") or state.get("media_url"),
        "image_url": state.get("image_url"),
        "image_urls": state.get("image_urls") or ([state.get("image_url")] if state.get("image_url") else []),
        "image_bytes": image_bytes,
        "image_base64": image_b64,
    }

    # If owner is directly answering a pending customer escalation, execute _tool_relay_to_customer
    pending_list = escalation_service.get_pending_for_tenant(t_uuid)
    if pending_list:
        esc, clean_ans = escalation_service.find_target_escalation(t_uuid, raw_message)
        has_num = bool(re.search(r'\d+', raw_message))
        is_reply = has_num or any(kw in raw_message.lower() for kw in ["batao", "bolo", "kaho", "bhej do", "share", "charges", "rate", "available", "yes", "haan", "nahi", "no", "ok", "theek"])
        if esc and is_reply:
            from app.services.catalog_tools import _tool_relay_to_customer
            relay_res = await _tool_relay_to_customer(str(t_uuid), {"escalation_id": esc.escalation_id, "reply_message": raw_message}, execution_context)
            if relay_res.get("status") == "success":
                confirm_msg = relay_res.get("message") or f"Jee Haider bhai, customer ko message deliver kar diya hai: '{relay_res.get('formatted_reply')}'"
                return {
                    **state,
                    "reply_text": confirm_msg,
                    "reply_chunks": [confirm_msg],
                    "forward_to_customer": relay_res.get("customer_jid") or relay_res.get("customer_phone"),
                    "forward_message": relay_res.get("formatted_reply"),
                    "escalation_resolved_id": esc.escalation_id,
                    "media_url": None,
                    "media_urls": None,
                    "owner_alert": None,
                }
        elif not esc and len(pending_list) > 1 and is_reply:
            from app.services.catalog_tools import _tool_relay_to_customer
            relay_res = await _tool_relay_to_customer(str(t_uuid), {"reply_message": raw_message}, execution_context)
            if relay_res.get("status") == "ambiguous":
                clarify_msg = relay_res.get("message")
                return {
                    **state,
                    "reply_text": clarify_msg,
                    "reply_chunks": [clarify_msg],
                    "forward_to_customer": None,
                    "forward_message": None,
                    "media_url": None,
                    "media_urls": None,
                    "owner_alert": None,
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
