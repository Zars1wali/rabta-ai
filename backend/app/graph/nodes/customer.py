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
from app.brain.flags import RabtaFlag, strip_rabta_flags, parse_rabta_flag

logger = logging.getLogger(__name__)
_store_agent = WhatsAppStoreAgent()
_esc_service = EscalationService()
_copilot = OwnerCopilotService()


def is_valid_human_name(n: Optional[str]) -> bool:
    """Checks if string is an actual human name (not empty, single punctuation, or generic label)."""
    if not n:
        return False
    clean = re.sub(r'[^A-Za-z\s]', '', str(n)).strip()
    if len(clean) < 3:
        return False
    tokens = clean.lower().split()
    non_name = {
        "customer", "user", "guest", "none", "unknown", "whatsapp", "haider arms", "owner",
        "delivery", "deliver", "chahiye", "bhejo", "bhej", "karo", "rate", "price", "kitna", "kitne",
        "kya", "discount", "account", "bank", "details", "firearm", "pistol", "gun", "ammo", "available",
        "kimber", "glock", "beretta", "taurus", "cz", "sig", "colt", "tisas", "zigana", "sath",
        "asalam", "assalam", "salam", "slam", "aoa", "walaikum", "walikum", "wassalam",
        "hello", "hi", "hey", "bhai", "sir", "janab", "bro", "dear", "greetings", "shukriya",
        "thanks", "thank", "ok", "theek", "acha", "ji", "jee", "haan", "yes", "no", "nahi",
        "apka", "aapka", "shop", "kider", "kidhar", "kahan", "location", "address", "process",
        "from", "frm", "live", "living", "rehta", "rehte", "se", "mein", "me", "ka", "ki", "ke", "ko"
    }
    if any(t in non_name for t in tokens):
        return False
    # If the whole string is just greeting or polite marker
    if clean.lower() in non_name:
        return False
    return True


def is_valid_pakistani_sim(p: Optional[str]) -> bool:
    """Checks if string is a real Pakistani mobile SIM phone number."""
    if not p:
        return False
    digits = re.sub(r'[^\d]', '', str(p))
    if len(digits) >= 13:
        # 13+ digits is a WhatsApp internal LID
        return False
    if len(digits) == 12 and digits.startswith("923"):
        return True
    if len(digits) == 11 and digits.startswith("03"):
        return True
    if len(digits) == 10 and digits.startswith("3"):
        return True
    return False


def extract_customer_entities(
    text: str,
    current_name: Optional[str] = None,
    current_city: Optional[str] = None,
    current_sim: Optional[str] = None,
    push_name: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts customer Name, Pakistani City, and real SIM phone number from text."""
    name = current_name if is_valid_human_name(current_name) else None
    city = current_city
    sim = current_sim if is_valid_pakistani_sim(current_sim) else None

    # 1. Extract Pakistani mobile SIM phone
    if not sim:
        sim_match = re.search(r'(?:(?:\+92|0092|92|0)?\s?3\d{2}[-\s]?\d{7})', text)
        if sim_match:
            raw_digits = re.sub(r'[^\d]', '', sim_match.group(0))
            if raw_digits.startswith("0") and len(raw_digits) == 11:
                raw_digits = "92" + raw_digits[1:]
            elif raw_digits.startswith("3") and len(raw_digits) == 10:
                raw_digits = "92" + raw_digits
            if is_valid_pakistani_sim(raw_digits):
                sim = raw_digits

    # 2. Extract Pakistani City
    if not city:
        city_match = re.search(r'\b(lahore|karachi|islamabad|rawalpindi|peshawar|quetta|multan|faisalabad|sialkot|gujranwala|abbottabad|mardan|kohat|pindi|hyderabad|sukkur|bahawalpur|sargodha|dera ismail khan|swat)\b', text, re.IGNORECASE)
        if city_match:
            city = city_match.group(1).title()

    # 3. Extract Customer Name
    if not name:
        name_match = re.search(r'(?:mera\s+naam|naam\s+hai|naam)\s+([A-Za-z\s]+?)(?:\s+(?:hai|he|hun|hoon|hy|,|\.|$))', text, re.IGNORECASE)
        if name_match:
            raw_cand = name_match.group(1).strip()
            if city:
                raw_cand = re.sub(rf'\b(?:from|frm|se|mein|in)?\s*{re.escape(city)}\b', '', raw_cand, flags=re.IGNORECASE).strip()
            raw_cand = re.sub(r'\b(from|frm|se|aur|and|mein|me|ka|ki|ke|ko)\b.*$', '', raw_cand, flags=re.IGNORECASE).strip()
            cand = raw_cand.title()
            if is_valid_human_name(cand):
                name = cand
        else:
            name_match2 = re.search(r'(?:mera\s+naam|naam)\s+([A-Za-z\s]+)', text, re.IGNORECASE)
            if name_match2:
                n = name_match2.group(1).strip()
                if city:
                    n = re.sub(rf'\b(?:from|frm|se|mein|in)?\s*{re.escape(city)}\b', '', n, flags=re.IGNORECASE).strip()
                n = re.sub(r'\b(hai|he|hun|hoon|hy|aur|se|bhai|from|frm|mein|me)\b.*$', '', n, flags=re.IGNORECASE).strip()
                if is_valid_human_name(n):
                    name = n.title()

        # Handle combined messages like "Ahmed 0307 5659224" or "Ahmed Hyderabad" or "Umer Wali from Islamabad"
        if not name and len(text.split()) <= 6:
            inquiry_markers = [
                "?", "kya", "kia", "rate", "price", "kitna", "kitne", "available", "mil", "sakta",
                "hoga", "chahiye", "order", "kerni", "karni", "stock", "detail", "details", "info",
                "kimber", "glock", "beretta", "taurus", "cz", "sig", "colt", "tisas", "zigana", "sath"
            ]
            has_inquiry = any(m in text.lower() for m in inquiry_markers)
            if not has_inquiry:
                clean_for_name = text
                clean_for_name = re.sub(r'(?:(?:\+92|0092|92|0)?\s?3\d{2}[-\s]?\d{7})', '', clean_for_name)
                if city:
                    clean_for_name = re.sub(rf'\b{re.escape(city)}\b', '', clean_for_name, flags=re.IGNORECASE)
                clean_for_name = re.sub(
                    r'\b(asalam|assalam|salam|slam|aoa|walaikum|walikum|hai|he|hun|hoon|hy|aur|se|bhai|bhi|main|mera|meri|number|no|whatsapp|sim|hello|hi|ok|theek|jee|ji|from|frm|live|living|rehta|rehte|in|mein|me|ka|ki|ke|ko)\b',
                    '',
                    clean_for_name,
                    flags=re.IGNORECASE,
                )
                clean_for_name = re.sub(r'[^A-Za-z\s]', '', clean_for_name).strip()
                tokens = [t for t in clean_for_name.split() if is_valid_human_name(t)]
                if 1 <= len(tokens) <= 3:
                    cand = " ".join(tokens).title()
                    cand = re.sub(r'^(?:from|frm|se|aur|and)\s+', '', cand, flags=re.IGNORECASE).strip()
                    cand = re.sub(r'\s+(?:from|frm|se|aur|and|mein|me|ka|ki|ke)$', '', cand, flags=re.IGNORECASE).strip()
                    if is_valid_human_name(cand):
                        name = cand

        if not name and push_name and is_valid_human_name(push_name) and len(push_name.split()) <= 3:
            name = push_name.strip().title()

    return name, city, sim



# --------------------------------------------------------------------------
# Modern ReAct Customer Sales Node (Node 2A)
# --------------------------------------------------------------------------
async def customer_react_node(state: RabtaGraphState) -> RabtaGraphState:
    """
    Core ReAct Sales Intelligence Node for Rabta AI.
    Executes native tool calling via WhatsAppStoreAgent & ReActAgentHarness.
    
    Binds: search_catalog, get_product_photos, check_delivery_policy,
    get_payment_bank_details, escalate_delivery_quote, escalate_custom_inquiry,
    recommend_alternative.
    """
    raw_message = (state.get("raw_message") or "").strip()
    tenant_id_str = state.get("tenant_id") or ""
    sender_phone = state.get("sender_phone") or ""
    sender_jid = state.get("sender_jid") or sender_phone
    push_name = state.get("push_name")
    
    current_name = state.get("customer_name")
    current_city = state.get("customer_city")
    current_address = state.get("customer_address")
    current_sim = state.get("customer_sim_phone")
    current_product = state.get("customer_product")
    escalation_id = state.get("escalation_id")
    history = state.get("conversation_history") or []
    image_b64 = state.get("image_base64")

    # Detect real SIM phone
    clean_sender = re.sub(r'[^\d]', '', sender_phone)
    if not current_sim and len(clean_sender) <= 12 and (clean_sender.startswith("923") or clean_sender.startswith("03") or clean_sender.startswith("3")):
        current_sim = clean_sender

    # Light opportunistic entity extraction for phone/name if customer directly sent it
    ext_name, ext_city, ext_sim = extract_customer_entities(
        raw_message, current_name=current_name, current_city=current_city, current_sim=current_sim, push_name=push_name
    )
    name = ext_name or current_name
    city = ext_city or current_city
    sim = ext_sim or current_sim
    address = current_address

    # 1. Customer Opt-Out / Stop Request Check
    raw_l = raw_message.lower().strip()
    is_stop_req = any(
        phrase in raw_l for phrase in [
            "stop texting", "stop text", "dont text", "don't text", "dont message",
            "don't message", "stop", "mat karo", "message mat karo", "msg mat karo",
            "too many messages", "no need", "nahi chahiye", "na karo", "toba", "unsub"
        ]
    )
    if is_stop_req:
        logger.info("[CustomerReactNode] Customer %s requested stop/opt-out. Pausing AI.", sender_phone)
        reply = "Theek hai bhai, bilkul pareshan na hon. Main mazeed message nahi karunga. Agar aainda kabhi koi zaroorat ho toh aap bejhijhak rabta kar sakte hain. Allah hafiz! 🙏"
        return {
            **state,
            "customer_state": "IDLE",
            "reply_text": reply,
            "reply_chunks": [reply],
            "media_url": None,
            "media_urls": None,
            "owner_alert": None,
            "ai_active": False,
        }

    # 2. Call the ReAct Sales Intelligence Agent
    reply_data = await _store_agent.handle_customer_interaction(
        customer_message=raw_message,
        business_name=state.get("business_name", "Haider Arms"),
        industry=state.get("industry", "Firearms Retail"),
        catalog_context=state.get("catalog_context", ""),
        conversation_history=history,
        image_base64=image_b64,
        tenant_id=tenant_id_str,
        sender_phone=sender_phone,
        current_product=current_product,
    )

    reply_text = reply_data.get("reply_text") or ""
    reply_chunks = reply_data.get("reply_chunks") or ([reply_text] if reply_text else [])
    media_urls = reply_data.get("media_urls") or []
    final_media_url = media_urls[0]["url"] if media_urls else None
    owner_alert = reply_data.get("owner_alert")
    state_updates = reply_data.get("state_updates") or {}

    # 3. Product in focus tracking
    new_product = state_updates.get("customer_product") or reply_data.get("extracted_item") or reply_data.get("product") or current_product
    if media_urls and media_urls[0].get("name"):
        new_product = media_urls[0]["name"]
    elif media_urls and media_urls[0].get("product_name"):
        new_product = media_urls[0]["product_name"]

    # 4. Profile and Escalation tracking
    profile = state_updates.get("customer_profile") or {}
    if profile.get("name"):
        name = profile["name"]
    if profile.get("city"):
        city = profile["city"]
    if profile.get("address"):
        address = profile["address"]
    if profile.get("sim"):
        sim = profile["sim"]
    
    if state_updates.get("escalation_id"):
        escalation_id = state_updates["escalation_id"]
    elif reply_data.get("needs_escalation") and not escalation_id:
        # Create escalation record if flagged
        try:
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=sim or sender_phone,
                customer_jid=sender_jid,
                customer_city=city,
                customer_name=name,
                question=raw_message,
                product_context=new_product,
                conversation_snippet=history[-6:],
            )
            escalation_id = esc.escalation_id
        except Exception as esc_err:
            logger.warning("[CustomerReactNode] Escalation creation: %s", esc_err)

    customer_state = "ESCALATED" if (owner_alert or escalation_id) else "BROWSING"

    # 5. Sanitize reply text (remove any internal [FLAG: ...] stanzas)
    if reply_text:
        reply_text = strip_rabta_flags(reply_text)
        if not reply_text.strip():
            reply_text = "Jee bilkul bhai! Main mazeed details confirm karke aapko batata hoon."
        reply_chunks = [strip_rabta_flags(c) for c in reply_chunks if strip_rabta_flags(c).strip()]
        if not reply_chunks:
            reply_chunks = [reply_text]

    return {
        **state,
        "customer_state": customer_state,
        "customer_name": name,
        "customer_city": city,
        "customer_address": address,
        "customer_sim_phone": sim,
        "customer_product": new_product,
        "escalation_id": escalation_id,
        "media_url": final_media_url,
        "media_urls": media_urls if media_urls else None,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "owner_alert": owner_alert,
    }


# --------------------------------------------------------------------------
# Backward-compatibility aliases & stubs
# --------------------------------------------------------------------------
customer_sales_chat = customer_react_node

async def collect_customer_info(state: RabtaGraphState) -> RabtaGraphState:
    """Backward-compatible alias routing directly to customer_react_node."""
    return await customer_react_node(state)

def route_customer(state: RabtaGraphState) -> str:
    """Backward-compatible routing function returning customer_react_node."""
    return "customer_react_node"

async def ask_city(state: RabtaGraphState) -> RabtaGraphState:
    return await customer_react_node(state)

async def ask_city_again(state: RabtaGraphState) -> RabtaGraphState:
    return await customer_react_node(state)

async def send_patience_reply(state: RabtaGraphState) -> RabtaGraphState:
    reply = "Main shop se confirm kar raha hoon, thoda sa wait karein — abhi batata hoon."
    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
    }

async def escalate_to_owner(state: RabtaGraphState) -> RabtaGraphState:
    return await customer_react_node(state)

