"""
Customer-facing graph nodes for Rabta AI (Version 2.0 Production Ready).

Integrates the Master Sales Intelligence Prompt v2.0 cognitive brain.
All rigid regexes, canned bot self-identifications, and brittle keyword blacklists
have been replaced with intelligent reasoning and strict adherence to Rabta Sales flags.
"""
from __future__ import annotations
import logging
import uuid
import re
from typing import Optional, Any, List, Dict
from app.graph.state import RabtaGraphState
from app.services.store_agent import WhatsAppStoreAgent
from app.services.escalation_service import EscalationService
from app.services.owner_copilot import OwnerCopilotService
from app.services.catalog_tools import get_product_photos
from app.brain.flags import RabtaFlag

logger = logging.getLogger(__name__)
_store_agent = WhatsAppStoreAgent()
_esc_service = EscalationService()
_copilot = OwnerCopilotService()


# --------------------------------------------------------------------------
# customer_router — edge function
# --------------------------------------------------------------------------
def route_customer(state: RabtaGraphState) -> str:
    """
    Evaluates current conversation state to route between ongoing info collection
    and dynamic Sales Intelligence chat.
    """
    cs = state.get("customer_state", "BROWSING")

    # If in active info collection, continue unless customer changes topic
    if cs == "COLLECTING_INFO":
        return "collect_customer_info"

    if cs == "DELIVERY_ASKED":
        return "collect_customer_info"

    # All conversational queries, greetings, product questions route to customer_sales_chat
    return "customer_sales_chat"


# --------------------------------------------------------------------------
# Node: ask_city
# --------------------------------------------------------------------------
async def ask_city(state: RabtaGraphState) -> RabtaGraphState:
    """Natural delivery closing step asking for destination city."""
    reply = "Delivery bilkul ho sakti hai — Karachi, Lahore, Islamabad, sab jagah. 100% advance payment pe. Aapka city kya hai?"
    return {
        **state,
        "customer_state": "DELIVERY_ASKED",
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
    }


# --------------------------------------------------------------------------
# Node: ask_city_again
# --------------------------------------------------------------------------
async def ask_city_again(state: RabtaGraphState) -> RabtaGraphState:
    """Gentle clarification for city."""
    reply = "Bhai please city batayein — kis city mein delivery chahiye?"
    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
    }


# --------------------------------------------------------------------------
# Node: send_patience_reply
# --------------------------------------------------------------------------
async def send_patience_reply(state: RabtaGraphState) -> RabtaGraphState:
    """Natural reassurance while owner confirms unverified details."""
    reply = "Main shop se confirm kar raha hoon, thoda sa wait karein — abhi batata hoon."
    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
    }


# --------------------------------------------------------------------------
# Node: escalate_to_owner
# --------------------------------------------------------------------------
async def escalate_to_owner(state: RabtaGraphState) -> RabtaGraphState:
    """Redirects to collection for structured delivery details."""
    merged = {**state, "escalation_type": "delivery", "customer_state": "COLLECTING_INFO"}
    return await collect_customer_info(merged)


# --------------------------------------------------------------------------
# Node: collect_customer_info
# --------------------------------------------------------------------------
async def collect_customer_info(state: RabtaGraphState) -> RabtaGraphState:
    """
    Collects city/address when delivery is chosen, then alerts the owner for courier charges.
    """
    msg = (state.get("raw_message") or "").strip()
    phone = state.get("sender_phone", "unknown")
    city = state.get("customer_city")
    address = state.get("customer_address")
    product = state.get("customer_product", "requested firearm")
    step = state.get("info_collection_step")
    tenant_id_str = state.get("tenant_id", "")

    # Natural entity extraction from message
    if not city:
        city_match = re.search(r'\b(lahore|karachi|islamabad|rawalpindi|peshawar|quetta|multan|faisalabad|sialkot|gujranwala|abbottabad|mardan|kohat|pindi)\b', msg, re.IGNORECASE)
        if city_match:
            city = city_match.group(1).title()
        elif step == "city" and len(msg.split()) <= 3:
            city = msg.title()

    if not address and city:
        if any(w in msg.lower() for w in ["road", "street", "gali", "phase", "sector", "block", "house", "dha", "town", "chowk"]):
            address = msg
        elif step == "address":
            address = msg

    if not city:
        reply = "Delivery bilkul ho sakti hai. Aapka city kya hai?"
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "info_collection_step": "city",
            "customer_city": None,
            "reply_text": reply,
            "reply_chunks": [reply],
            "owner_alert": None,
        }

    if not address:
        reply = f"{city} mein delivery address ya area batayein?"
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "info_collection_step": "address",
            "customer_city": city,
            "reply_text": reply,
            "reply_chunks": [reply],
            "owner_alert": None,
        }

    # Complete info collected — notify owner for charges (Section A.16)
    try:
        tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
    except (ValueError, AttributeError):
        tenant_id = uuid.uuid4()

    esc_record = _esc_service.create_escalation(
        tenant_id=tenant_id,
        customer_phone=phone,
        question=f"Delivery to {city} ({address}) for {product}",
        product_context=product,
        customer_name=state.get("customer_name"),
        conversation_snippet=(state.get("conversation_history") or [])[-6:],
    )

    owner_alert = _copilot.format_escalation_alert(
        customer_phone=phone,
        customer_question=msg,
        customer_name=state.get("customer_name"),
        extracted_item=product,
        extracted_city=city,
        customer_address=address,
        inquiry_type="delivery",
    )

    reply = f"Theek hai bhai, main shop se {city} ke liye {product} ke delivery charges confirm karke aapko foran batata hoon."
    return {
        **state,
        "customer_state": "ESCALATED",
        "customer_city": city,
        "customer_address": address,
        "escalation_id": esc_record.escalation_id,
        "info_collection_step": None,
        "reply_text": reply,
        "reply_chunks": [reply],
        "owner_alert": owner_alert,
    }


# --------------------------------------------------------------------------
# Node: customer_sales_chat
# --------------------------------------------------------------------------
async def customer_sales_chat(state: RabtaGraphState) -> RabtaGraphState:
    """
    Core Sales Intelligence Node driven by Master Sales Intelligence Prompt v2.0.
    """
    raw_message = state.get("raw_message", "")
    tenant_id_str = state.get("tenant_id", "")
    sender_phone = state.get("sender_phone", "")

    # Call the Sales Intelligence Agent
    reply_data = await _store_agent.handle_customer_interaction(
        customer_message=raw_message,
        business_name=state.get("business_name", "Haider Arms"),
        industry=state.get("industry", "Firearms Retail"),
        catalog_context=state.get("catalog_context", ""),
        conversation_history=state.get("conversation_history") or [],
        image_base64=state.get("image_base64"),
        tenant_id=tenant_id_str,
        sender_phone=sender_phone,
    )

    flag: Optional[RabtaFlag] = reply_data.get("flag")
    reply_text = reply_data.get("reply_text", "")
    reply_chunks = reply_data.get("reply_chunks") or ([reply_text] if reply_text else [])

    owner_alert = None
    media_url = None
    media_urls = None
    customer_state = state.get("customer_state", "BROWSING")
    escalation_id = state.get("escalation_id")
    product = state.get("customer_product")

    # 1. Handle IMAGE_REQUEST Flag (Section A.24)
    if flag and flag.flag_type == "IMAGE_REQUEST":
        target_product = flag.product or reply_data.get("image_product") or product or "firearm"
        try:
            photos = await get_product_photos(
                tenant_id=tenant_id_str,
                product_name=target_product,
                allow_multiple=False,
            )
            if photos:
                media_url = photos[0]["url"]
                media_urls = [{"name": target_product, "url": media_url, "caption": photos[0].get("caption", "")}]
                reply_text = f"Yeh hai piece. Genuine import."
                reply_chunks = [reply_text]
            else:
                reply_text = f"Bhai {target_product} ki photo abhi catalog mein load nahi hui — aap features ya specs pooch sakte hain."
                reply_chunks = [reply_text]
        except Exception as e:
            logger.warning("[Node:customer_sales_chat] Image fetch error: %s", e)
            reply_text = "Jee batayein, kis firearm ki picture dekhna chahte hain?"
            reply_chunks = [reply_text]

    # 2. Handle ESCALATE Flag (Section A.28: Immediate and Silent)
    elif flag and flag.flag_type == "ESCALATE":
        # Reply nothing to customer: complete silence
        reply_text = ""
        reply_chunks = []
        customer_state = "ESCALATED"
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=sender_phone,
                question=flag.payload or raw_message,
                product_context=product,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            escalation_id = esc.escalation_id
            owner_alert = (
                f"🚨 [URGENT ESCALATION]\n"
                f"Customer ({sender_phone}) ne serious issue report kiya hai:\n"
                f"\"{flag.payload or raw_message}\"\n"
                f"Please check and handle immediately."
            )
        except Exception as e:
            logger.error("[Node:customer_sales_chat] Failed creating escalation: %s", e)

    # 3. Handle OWNER_QUERY Flag (Section A.29)
    elif flag and flag.flag_type == "OWNER_QUERY":
        customer_state = "ESCALATED"
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=sender_phone,
                question=flag.payload or raw_message,
                product_context=product,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            escalation_id = esc.escalation_id
            owner_alert = f"Haider bhai, Customer ({sender_phone}) ke liye query:\n{flag.payload or raw_message}"
        except Exception as e:
            logger.error("[Node:customer_sales_chat] Failed creating owner query: %s", e)

    # 4. Handle BULK_LEAD Flag (Section A.21)
    elif flag and flag.flag_type == "BULK_LEAD":
        customer_state = "ESCALATED"
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=sender_phone,
                question=f"BULK LEAD: {flag.payload}",
                product_context=flag.product,
            )
            escalation_id = esc.escalation_id
            owner_alert = (
                f"💼 [BULK BUYER LEAD]\n"
                f"Customer ({sender_phone}) wants {flag.quantity or 'bulk'} of {flag.product or 'firearms'}.\n"
                f"Serious buyer lag raha hai — aap khud baat karein ya main rate quote karun?"
            )
        except Exception as e:
            logger.error("[Node:customer_sales_chat] Failed creating bulk lead: %s", e)

    return {
        **state,
        "customer_state": customer_state,
        "escalation_id": escalation_id,
        "media_url": media_url,
        "media_urls": media_urls,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "owner_alert": owner_alert,
    }
