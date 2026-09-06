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
from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo
from app.db.repositories.tenant_repo import format_pakistani_phone_display
from app.brain.prompts_owner import build_owner_inquiry_alert
from app.services.store_agent import WhatsAppStoreAgent
from app.services.escalation_service import EscalationService
from app.services.owner_copilot import OwnerCopilotService
from app.services.catalog_tools import get_product_photos
from app.brain.flags import RabtaFlag

logger = logging.getLogger(__name__)
_store_agent = WhatsAppStoreAgent()
_esc_service = EscalationService()
_copilot = OwnerCopilotService()


def extract_customer_entities(
    text: str,
    current_name: Optional[str] = None,
    current_city: Optional[str] = None,
    current_sim: Optional[str] = None,
    push_name: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts customer Name, Pakistani City, and real SIM phone number from text."""
    name = current_name
    city = current_city
    sim = current_sim

    if not name:
        name_match = re.search(r'(?:mera\s+naam|naam\s+hai|naam)\s+([A-Za-z\s]+)', text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().title()
        elif push_name and len(push_name.split()) <= 3 and not any(w in push_name.lower() for w in ["whatsapp", "user", "guest"]):
            name = push_name.strip().title()

    if not city:
        city_match = re.search(r'\b(lahore|karachi|islamabad|rawalpindi|peshawar|quetta|multan|faisalabad|sialkot|gujranwala|abbottabad|mardan|kohat|pindi|hyderabad|sukkur|bahawalpur|sargodha|dera ismail khan|swat)\b', text, re.IGNORECASE)
        if city_match:
            city = city_match.group(1).title()

    if not sim:
        sim_match = re.search(r'(?:(?:\+92|0092|92|0)?\s?3\d{2}[-\s]?\d{7})', text)
        if sim_match:
            raw_digits = re.sub(r'[^\d]', '', sim_match.group(0))
            if raw_digits.startswith("0") and len(raw_digits) == 11:
                raw_digits = "92" + raw_digits[1:]
            sim = raw_digits

    return name, city, sim



# --------------------------------------------------------------------------
# customer_router — edge function
# --------------------------------------------------------------------------
def route_customer(state: RabtaGraphState) -> str:
    """
    Evaluates current conversation state to route between ongoing info collection
    and dynamic Sales Intelligence chat.
    """
    cs = state.get("customer_state", "BROWSING")
    msg = (state.get("raw_message") or "").lower()

    # If in active info collection, continue unless customer changes topic
    if cs in ("COLLECTING_INFO", "DELIVERY_ASKED"):
        return "collect_customer_info"

    # Delivery intent initiates info collection (name -> city -> address)
    if any(w in msg for w in ["delivery", "deliver", "bhejo", "bhej do"]):
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
    Progressively collects Name -> City -> WhatsApp SIM / Address when delivery
    or bank details payment is chosen, then executes relay or alerts owner.
    """
    msg = (state.get("raw_message") or "").strip()
    phone = state.get("sender_phone", "unknown")
    name = state.get("customer_name")
    city = state.get("customer_city")
    address = state.get("customer_address")
    sim = state.get("customer_sim_phone")
    product = state.get("customer_product", "requested firearm")
    step = state.get("info_collection_step")
    esc_type = state.get("escalation_type")
    tenant_id_str = state.get("tenant_id", "")

    # Check if sender phone is already a real Pakistani SIM phone
    clean_sender = re.sub(r'[^\d]', '', phone)
    if not sim and len(clean_sender) <= 12 and (clean_sender.startswith("923") or clean_sender.startswith("03") or clean_sender.startswith("3")):
        sim = clean_sender

    # Entity extraction
    extracted_name, extracted_city, extracted_sim = extract_customer_entities(
        msg, current_name=name, current_city=city, current_sim=sim, push_name=state.get("push_name")
    )
    name = extracted_name or name
    city = extracted_city or city
    sim = extracted_sim or sim

    if not name and step == "name" and len(msg.split()) <= 3 and not any(w in msg.lower() for w in ["lahore", "karachi", "delivery", "payment"]):
        name = msg.strip().title()

    if not city and step == "city" and len(msg.split()) <= 3:
        city = msg.strip().title()

    if not address and city:
        if any(w in msg.lower() for w in ["road", "street", "gali", "phase", "sector", "block", "house", "dha", "town", "chowk"]):
            address = msg
        elif step == "address":
            address = msg

    effective_sim = sim or phone

    # ── WORKFLOW A: Payment & Bank Details Collection ─────────────────────────
    if step == "payment_details" or esc_type == "payment":
        if not name:
            reply = "Jee bilkul bhai! Payment aur bank account details provide kar dete hain. Kindly apna Naam share kar dein taake invoice record generate ho sake."
            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "info_collection_step": "payment_details",
                "escalation_type": "payment",
                "customer_name": None,
                "reply_text": reply,
                "reply_chunks": [reply],
                "owner_alert": None,
            }

        if not city:
            reply = f"Jee {name}, kis city se hain aap?"
            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "info_collection_step": "payment_details",
                "escalation_type": "payment",
                "customer_name": name,
                "customer_city": None,
                "reply_text": reply,
                "reply_chunks": [reply],
                "owner_alert": None,
            }

        if not sim and len(clean_sender) >= 13:
            reply = f"Jee {name}, apna WhatsApp SIM contact number share kar dein taake official order slip aur payment verification book ho sake."
            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "info_collection_step": "payment_details",
                "escalation_type": "payment",
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": None,
                "reply_text": reply,
                "reply_chunks": [reply],
                "owner_alert": None,
            }

        # Complete payment details collected! Check database accounts
        async with AsyncSessionLocal() as session:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else None
            accounts = await tenant_repo.get_payment_accounts(session, t_uuid) if t_uuid else []
            auto_share = await tenant_repo.is_payment_auto_share_enabled(session, t_uuid) if t_uuid else True

        if accounts and auto_share:
            reply = tenant_repo.format_payment_accounts_text(accounts, name)
            owner_alert = build_owner_inquiry_alert(
                customer_name=name,
                customer_phone=effective_sim,
                product=product,
                city=city,
                inquiry_type="payment_share_alert",
            )
            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "info_collection_step": "receipt_awaited",
                "escalation_type": None,
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": effective_sim,
                "reply_text": reply,
                "reply_chunks": [reply],
                "owner_alert": owner_alert,
            }
        else:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc_record = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=effective_sim,
                question=f"Bank details requested by {name} from {city} for {product}",
                product_context=product,
                customer_name=name,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            owner_alert = build_owner_inquiry_alert(
                customer_name=name,
                customer_phone=effective_sim,
                product=product,
                city=city,
                question="Customer ne bank account details maangi hain — please provide bank details",
                inquiry_type="payment",
            )
            reply = f"Theek hai {name} bhai, main shop se verified bank account details confirm karke aapko foran share karta hoon."
            return {
                **state,
                "customer_state": "ESCALATED",
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": effective_sim,
                "escalation_id": esc_record.escalation_id,
                "info_collection_step": None,
                "escalation_type": None,
                "reply_text": reply,
                "reply_chunks": [reply],
                "owner_alert": owner_alert,
            }

    # ── WORKFLOW B: Delivery Address Collection ───────────────────────────────
    if not name:
        reply = "Delivery bilkul ho sakti hai. Aapka naam kya hai?"
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "info_collection_step": "name",
            "escalation_type": "delivery",
            "customer_name": None,
            "reply_text": reply,
            "reply_chunks": [reply],
            "owner_alert": None,
        }

    if not city:
        reply = f"Jee {name}, kis city mein delivery chahiye?"
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "info_collection_step": "city",
            "escalation_type": "delivery",
            "customer_name": name,
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
            "escalation_type": "delivery",
            "customer_name": name,
            "customer_city": city,
            "reply_text": reply,
            "reply_chunks": [reply],
            "owner_alert": None,
        }

    # Complete delivery info collected — notify owner for charges
    try:
        tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
    except (ValueError, AttributeError):
        tenant_id = uuid.uuid4()

    esc_record = _esc_service.create_escalation(
        tenant_id=tenant_id,
        customer_phone=effective_sim,
        question=f"Delivery to {city} ({address}) for {product}",
        product_context=product,
        customer_name=name,
        conversation_snippet=(state.get("conversation_history") or [])[-6:],
    )

    owner_alert = build_owner_inquiry_alert(
        customer_name=name,
        customer_phone=effective_sim,
        product=product,
        city=city,
        address=address,
        inquiry_type="delivery",
    )

    reply = f"Theek hai bhai, main shop se {city} ke liye {product} ke delivery charges confirm karke aapko foran batata hoon."
    return {
        **state,
        "customer_state": "ESCALATED",
        "customer_name": name,
        "customer_city": city,
        "customer_address": address,
        "customer_sim_phone": effective_sim,
        "escalation_id": esc_record.escalation_id,
        "info_collection_step": None,
        "escalation_type": None,
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
    Enforces customer detail collection before payment escalation and clean SIM alerts.
    """
    raw_message = state.get("raw_message", "")
    tenant_id_str = state.get("tenant_id", "")
    sender_phone = state.get("sender_phone", "")
    current_name = state.get("customer_name")
    current_city = state.get("customer_city")
    current_sim = state.get("customer_sim_phone")

    # Detect real SIM phone
    clean_sender = re.sub(r'[^\d]', '', sender_phone)
    if not current_sim and len(clean_sender) <= 12 and (clean_sender.startswith("923") or clean_sender.startswith("03") or clean_sender.startswith("3")):
        current_sim = clean_sender

    # Entity extraction from current turn
    ext_name, ext_city, ext_sim = extract_customer_entities(
        raw_message, current_name=current_name, current_city=current_city, current_sim=current_sim, push_name=state.get("push_name")
    )
    name = ext_name or current_name
    city = ext_city or current_city
    sim = ext_sim or current_sim
    effective_sim = sim or sender_phone

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
    media_urls = reply_data.get("media_urls") or None
    media_url = media_urls[0]["url"] if media_urls else None
    customer_state = state.get("customer_state", "BROWSING")
    escalation_id = state.get("escalation_id")
    product = reply_data.get("extracted_item") or reply_data.get("product") or state.get("customer_product")

    # Check if this interaction is asking for payment / bank account details
    raw_l = raw_message.lower()
    flag_payload_l = (flag.payload or "").lower() if flag else ""
    is_payment_inquiry = any(w in raw_l for w in ["bank", "account", "jazzcash", "easypaisa", "raast", "payment details", "paise transfer", "online payment", "advance payment", "bank details", "a/c", "khata"]) or (
        flag and flag.flag_type == "OWNER_QUERY" and any(w in flag_payload_l for w in ["bank", "account", "payment", "jazzcash", "easypaisa"])
    )

    # ── CASE 1: Payment & Bank Details Inquiries ─────────────────────────────
    if is_payment_inquiry:
        # If customer details (Name, City, SIM) are missing, gate the escalation
        if not name or not city or (len(clean_sender) >= 13 and not sim):
            if not name and not city:
                prompt_reply = "Jee bilkul bhai! Payment aur bank account details provide kar dete hain. Kindly apna Naam, City aur WhatsApp contact number share kar dein taake aapka order aur invoice record mein register ho sake."
            elif not name:
                prompt_reply = "Jee bilkul bhai! Payment aur bank details share karne ke liye aapka shubh naam kya hai?"
            elif not city:
                prompt_reply = f"Jee {name} bhai! Kis city se hain aap taake invoice record ban sake?"
            else:
                prompt_reply = f"Jee {name} bhai! Apna WhatsApp SIM contact number share kar dein taake official order slip book ho sake."

            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": sim,
                "customer_product": product,
                "info_collection_step": "payment_details",
                "escalation_type": "payment",
                "reply_text": prompt_reply,
                "reply_chunks": [prompt_reply],
                "owner_alert": None,
            }

        # Customer details ARE present! Check tenant payment accounts
        async with AsyncSessionLocal() as session:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else None
            accounts = await tenant_repo.get_payment_accounts(session, t_uuid) if t_uuid else []
            auto_share = await tenant_repo.is_payment_auto_share_enabled(session, t_uuid) if t_uuid else True

        if accounts and auto_share:
            pay_reply = tenant_repo.format_payment_accounts_text(accounts, name)
            owner_alert = build_owner_inquiry_alert(
                customer_name=name,
                customer_phone=effective_sim,
                product=product,
                city=city,
                inquiry_type="payment_share_alert",
            )
            return {
                **state,
                "customer_state": "COLLECTING_INFO",
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": effective_sim,
                "customer_product": product,
                "info_collection_step": "receipt_awaited",
                "reply_text": pay_reply,
                "reply_chunks": [pay_reply],
                "owner_alert": owner_alert,
            }
        else:
            # Need owner confirmation or owner to provide bank details
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=effective_sim,
                customer_name=name,
                question=f"Customer ne payment ke liye bank details maangi hain ({product or 'general'})",
                product_context=product,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            owner_alert = build_owner_inquiry_alert(
                customer_name=name,
                customer_phone=effective_sim,
                product=product,
                city=city,
                question="Customer ne bank account details maangi hain — please provide bank details",
                inquiry_type="payment",
            )
            wait_reply = f"Jee {name} bhai, shop se verified bank account details confirm karke abhi share karte hain, thoda sa wait karein."
            return {
                **state,
                "customer_state": "ESCALATED",
                "customer_name": name,
                "customer_city": city,
                "customer_sim_phone": effective_sim,
                "customer_product": product,
                "escalation_id": esc.escalation_id,
                "info_collection_step": None,
                "reply_text": wait_reply,
                "reply_chunks": [wait_reply],
                "owner_alert": owner_alert,
            }

    # 1. Handle Native Media or Legacy IMAGE_REQUEST Flag
    if not media_urls and flag and flag.flag_type == "IMAGE_REQUEST":
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
        reply_text = ""
        reply_chunks = []
        customer_state = "ESCALATED"
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=effective_sim,
                customer_name=name,
                question=flag.payload or raw_message,
                product_context=product,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            escalation_id = esc.escalation_id
            owner_alert = (
                f"🚨 [URGENT ESCALATION]\n"
                f"Customer {name or ''} (WhatsApp SIM: {format_pakistani_phone_display(effective_sim)}) ne serious issue report kiya hai:\n"
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
                customer_phone=effective_sim,
                customer_name=name,
                question=flag.payload or raw_message,
                product_context=product,
                conversation_snippet=(state.get("conversation_history") or [])[-6:],
            )
            escalation_id = esc.escalation_id
            owner_alert = build_owner_inquiry_alert(
                customer_name=name,
                customer_phone=effective_sim,
                product=product,
                city=city,
                question=flag.payload or raw_message,
                inquiry_type="inquiry",
            )
        except Exception as e:
            logger.error("[Node:customer_sales_chat] Failed creating owner query: %s", e)

    # 4. Handle BULK_LEAD Flag (Section A.21)
    elif flag and flag.flag_type == "BULK_LEAD":
        customer_state = "ESCALATED"
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=effective_sim,
                customer_name=name,
                question=f"BULK LEAD: {flag.payload}",
                product_context=flag.product,
            )
            escalation_id = esc.escalation_id
            owner_alert = (
                f"💼 [BULK BUYER LEAD]\n"
                f"Customer {name or ''} (WhatsApp SIM: {format_pakistani_phone_display(effective_sim)}) wants {flag.quantity or 'bulk'} of {flag.product or 'firearms'}.\n"
                f"Serious buyer lag raha hai — aap khud baat karein ya main rate quote karun?"
            )
        except Exception as e:
            logger.error("[Node:customer_sales_chat] Failed creating bulk lead: %s", e)

    return {
        **state,
        "customer_state": customer_state,
        "customer_name": name,
        "customer_city": city,
        "customer_sim_phone": sim,
        "customer_product": product,
        "escalation_id": escalation_id,
        "media_url": media_url,
        "media_urls": media_urls,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "owner_alert": owner_alert,
    }

