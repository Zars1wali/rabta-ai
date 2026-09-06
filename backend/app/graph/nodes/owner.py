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
    from app.services.owner_copilot import owner_copilot
    from app.services.escalation_service import escalation_service

    raw_message = state.get("raw_message", "").strip()
    tenant_id = state.get("tenant_id", "")
    sender_phone = state.get("sender_phone", "")
    history = state.get("conversation_history") or []
    image_b64 = state.get("image_base64")

    logger.info("[OwnerReActNode] Turn from %s: '%s'", sender_phone, raw_message[:60])

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

    # 2. Deterministic Relay Intent ("+923... ko bolo delivery charges 1000 hain")
    relay_match = re.search(r'(\+?\d{10,14})\s+ko\s+(?:bolo|batado|kaho|bhej do)\s+(.*)', raw_message, re.IGNORECASE)
    if relay_match:
        target_cust = relay_match.group(1)
        clean_msg = relay_match.group(2).strip()
        
        # Resolve any active escalation
        esc = escalation_service.resolve_escalation_by_phone(target_cust, clean_msg) if hasattr(escalation_service, "resolve_escalation_by_phone") else None
        esc_id = esc.escalation_id if esc else None

        done_reply = "Done bhai. Customer ko convey kar diya."
        return {
            **state,
            "reply_text": done_reply,
            "reply_chunks": [done_reply],
            "forward_to_customer": target_cust,
            "forward_message": clean_msg,
            "escalation_resolved_id": esc_id,
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
        "tenant_id": tenant_id,
        "sender_phone": sender_phone,
        "is_boss": True,
        "pending_image_url": state.get("media_url"),
    }

    # Execute ReAct conversational turn
    result = await react_agent_harness.run_turn(
        system_instruction=OWNER_INTELLIGENCE_SYSTEM_PROMPT,
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

    logger.info(
        "[OwnerReActNode] Completed turn. Tools: %s. Reply: '%s' | Media: %d",
        result.get("tool_calls_executed"),
        reply_text[:60],
        len(media_urls),
    )

    return {
        **state,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "media_url": media_url,
        "media_urls": media_urls if media_urls else None,
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
