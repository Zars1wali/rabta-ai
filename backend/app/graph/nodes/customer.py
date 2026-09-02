"""
Customer-facing graph nodes.

All state transitions for customer conversations are decided here —
deterministically, based on the current customer_state and nlu_* fields.
Gemini is called ONLY in customer_sales_chat, and only for language generation.

Node execution order for a customer message:
  run_customer_nlu → customer_router → (one of the nodes below) → END
"""
from __future__ import annotations
import re
import logging
import uuid
from typing import Any
from app.graph.state import RabtaGraphState
from app.services.store_agent import WhatsAppStoreAgent
from app.services.escalation_service import EscalationService

logger = logging.getLogger(__name__)
_store_agent = WhatsAppStoreAgent()
_esc_service = EscalationService()


# --------------------------------------------------------------------------
# customer_router — edge function (not a node, called by builder edges)
# --------------------------------------------------------------------------
def route_customer(state: RabtaGraphState) -> str:
    """
    Pure function. Returns the name of the next node based on current state.
    This is the only place customer conversation flow decisions are made.
    """
    # 1. Visual product query (incoming image) or photo request — always sales chat
    if state.get("image_base64") or state.get("nlu_photo_intent") or state.get("nlu_legal_intent"):
        return "customer_sales_chat"

    cs = state.get("customer_state", "BROWSING")
    raw_msg_lower = state.get("raw_message", "").lower()

    # If customer asks a product attribute, spec, color, or disclaims delivery — ALWAYS sales chat!
    is_attr_or_disclaimer = any(
        kw in raw_msg_lower for kw in [
            "color", "colors", "colour", "colours", "variant", "variants",
            "specs", "spec", "specification", "barrel", "weight", "finish",
            "twist", "caliber", "capacity", "action", "stock", "mag",
            "mene delivery", "delivery ka nahi", "delivery nahi"
        ]
    )
    if is_attr_or_disclaimer:
        return "customer_sales_chat"

    # If customer asks a new product/catalog/inventory question, always route to sales chat!
    from app.graph.nodes.nlu import _catalog_cache, _BRANDS
    is_catalog_inquiry = any(
        kw in raw_msg_lower for kw in [
            "rifles", "rifle", "pistol", "pistols", "shotgun", "gun", "arms", "category",
            "options", "konse", "kaunse", "konsi", "kaunsi", "available", "stock",
        ]
    ) or any(b in raw_msg_lower for b in _BRANDS) or any(p in raw_msg_lower for p in _catalog_cache)
    if is_catalog_inquiry:
        return "customer_sales_chat"

    # 2. Info collection in progress — continue collecting ONLY if not switching topic
    if cs == "COLLECTING_INFO":
        return "collect_customer_info"

    # 3. Legacy DELIVERY_ASKED state (city-only flow, kept for backward compat)
    if cs == "DELIVERY_ASKED":
        city = state.get("customer_city")
        if city:
            return "collect_customer_info"  # re-route through collection
        return "ask_city_again"

    # 4. If new explicit delivery intent detected without city — start collection
    # 5. All other conversational messages go to dynamic sales chat!
    return "customer_sales_chat"


# --------------------------------------------------------------------------
# Helper: Grounded LLM Response Generator for Customer Nodes
# --------------------------------------------------------------------------
async def _generate_grounded_customer_reply(
    scenario: str,
    raw_message: str,
    missing_field: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_city: Optional[str] = None,
    customer_product: Optional[str] = None,
    business_name: str = "Haider Arms",
    history: Optional[list] = None,
    fallback: str = "",
) -> str:
    """Generate natural, contextual Pakistani Roman Urdu reply grounded in specific state."""
    from google import genai
    from google.genai import types
    from app.core.config import settings

    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    if not client:
        return fallback

    prompt = f"""You are the friendly WhatsApp sales assistant for {business_name} (a firearms dealer in Pakistan).
Customer's current message: "{raw_message}"
Context:
- Customer Name: {customer_name or 'Not provided'}
- Product of interest: {customer_product or 'firearm'}
- Target City: {customer_city or 'Not provided'}
- Scenario: {scenario}
- Missing detail to ask for: {missing_field or 'None'}

Rules:
1. Write in natural Pakistani Roman Urdu (English alphabet).
2. Keep it warm, concise, and helpful (1-2 sentences, under 25 words).
3. Plain text only: zero emojis, no asterisks, no bullet points.
4. If the customer made a side-comment or objection (e.g. asking for charges estimate before giving address, or expressing urgency), acknowledge it politely and explain naturally why the missing detail is needed.
5. Never invent or hallucinate facts not given above.

Generate the exact WhatsApp message to send:"""

    try:
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=60,
            ),
        )
        text = (resp.text or "").strip()
        # Clean formatting
        text = re.sub(r'[\*\#\_`]', '', text)
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text, flags=re.UNICODE).strip()
        return text if text else fallback
    except Exception as exc:
        logger.warning("[CustomerNode:LLM] Generation fallback: %s", exc)
        return fallback


# --------------------------------------------------------------------------
# Node: ask_city
# Transition: BROWSING → DELIVERY_ASKED
# --------------------------------------------------------------------------
async def ask_city(state: RabtaGraphState) -> RabtaGraphState:
    """Customer asked about delivery but hasn't given a city yet — LLM grounded reply."""
    raw_msg = state.get("raw_message", "")
    prod = state.get("customer_product")
    name = state.get("customer_name")
    biz = state.get("business_name", "Haider Arms")

    fallback = "Delivery bilkul ho sakti hai. Aap kis city mein mangwana chahte hain?"
    reply = await _generate_grounded_customer_reply(
        scenario="Customer asked about delivery options or delivery feasibility.",
        raw_message=raw_msg,
        missing_field="destination city for delivery",
        customer_name=name,
        customer_product=prod,
        business_name=biz,
        fallback=fallback,
    )

    logger.info("[Node:ask_city] phone=%s reply=%s", state.get("sender_phone"), reply)
    return {
        **state,
        "customer_state": "DELIVERY_ASKED",
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
        "forward_to_customer": None,
        "forward_message": None,
    }


# --------------------------------------------------------------------------
# Node: ask_city_again
# State stays: DELIVERY_ASKED (customer didn't provide city yet)
# --------------------------------------------------------------------------
async def ask_city_again(state: RabtaGraphState) -> RabtaGraphState:
    """Customer is in DELIVERY_ASKED but their reply had no city — LLM grounded reply."""
    raw_msg = state.get("raw_message", "")
    prod = state.get("customer_product")
    name = state.get("customer_name")
    biz = state.get("business_name", "Haider Arms")

    fallback = "Bhai please city batayein — kis city mein delivery chahiye?"
    reply = await _generate_grounded_customer_reply(
        scenario="Customer replied in delivery flow but has not yet specified which city they want delivery in.",
        raw_message=raw_msg,
        missing_field="city name",
        customer_name=name,
        customer_product=prod,
        business_name=biz,
        fallback=fallback,
    )

    logger.info("[Node:ask_city_again] phone=%s reply=%s", state.get("sender_phone"), reply)
    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
        "forward_to_customer": None,
        "forward_message": None,
    }


# --------------------------------------------------------------------------
# Node: send_patience_reply
# State stays: ESCALATED (waiting for owner answer)
# --------------------------------------------------------------------------
async def send_patience_reply(state: RabtaGraphState) -> RabtaGraphState:
    """Customer messaged while waiting for owner reply — LLM grounded reassurance."""
    raw_msg = state.get("raw_message", "")
    prod = state.get("customer_product")
    name = state.get("customer_name")
    biz = state.get("business_name", "Haider Arms")

    fallback = "Main abhi bhi shop se confirm kar raha hoon, thori si sabr karein."
    reply = await _generate_grounded_customer_reply(
        scenario="Customer is asking for status or following up while an inquiry is actively pending with the shop owner.",
        raw_message=raw_msg,
        customer_name=name,
        customer_product=prod,
        business_name=biz,
        fallback=fallback,
    )

    logger.info("[Node:send_patience_reply] phone=%s reply=%s", state.get("sender_phone"), reply)
    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": None,
        "forward_to_customer": None,
        "forward_message": None,
    }


def sanitize_customer_name(name: Optional[str]) -> Optional[str]:
    """Sanitize customer name against known blacklist and word patterns."""
    if not name or not isinstance(name, str):
        return None
    name_clean = name.strip()
    if len(name_clean) < 3 or len(name_clean) > 20:
        return None
    if re.search(r'[\d\W_]', name_clean):
        return None
    BAD_NAMES = {
        "nahi", "nahin", "brand", "pata", "naam", "firearm", "pistol", "gun", "rifle",
        "delivery", "lahore", "karachi", "islamabad", "rawalpindi", "peshawar", "quetta",
        "multan", "faisalabad", "sialkot", "gujranwala", "abbottabad", "mardan", "kohat",
        "glock", "taurus", "canik", "tisas", "beretta", "sig", "sauer", "utas", "saiga",
        "hai", "bhai", "want", "need", "price", "pindi", "unknown", "none", "customer",
        "sir", "jee", "ji", "kya", "konsa", "charges", "rate", "rates", "cost", "details",
        "road", "mall", "dha", "phase", "street", "gali", "mohalla", "house", "shop",
        "haider", "arms", "theek", "ok", "haan", "ha"
    }
    if name_clean.lower() in BAD_NAMES:
        return None
    return name_clean.title()


# --------------------------------------------------------------------------
# Node: collect_customer_info (LLM-Grounded Intelligence + Strict State Transitions)
# Transition: BROWSING/DELIVERY_ASKED → COLLECTING_INFO → ESCALATED
# --------------------------------------------------------------------------
async def collect_customer_info(state: RabtaGraphState) -> RabtaGraphState:
    """
    Progressively collect name, city, and address before owner escalation.
    State transitions and escalation creation remain 100% deterministic,
    while language generation is dynamically generated by Gemini based on
    the customer's exact phrasing, objections, or side-questions.
    """
    from app.services.escalation_service import EscalationService
    from app.services.owner_copilot import OwnerCopilotService

    msg = state.get("raw_message", "").strip()
    msg_lower = msg.lower()
    biz_name = state.get("business_name", "Haider Arms")
    
    # Re-evaluate delivery intent dynamically
    is_delivery_intent = any(
        kw in msg_lower
        for kw in ["delivery", "deliver", "charges", "courier", "bhej", "order", "kharidna", "mangwana", "address", "mall road", "parcel"]
    )
    esc_type = "delivery" if (is_delivery_intent or state.get("escalation_type") == "delivery") else "inquiry"
    step = state.get("info_collection_step")
    is_delivery = esc_type == "delivery"

    phone = state.get("sender_phone", "unknown")
    name = sanitize_customer_name(state.get("customer_name"))
    city = state.get("customer_city")
    address = state.get("customer_address")
    product = state.get("customer_product", "requested firearm")
    tenant_id_str = state.get("tenant_id", "")

    # ── Detect refusal / skip attempt ────────────────────────────────────────
    REFUSAL_WORDS = ["nahi batana", "nahi bataunga", "skip", "no name", "bata nahi",
                     "kya zaroorat", "kyon batao", "privacy", "chor do", "mat poocho"]
    is_refusing = any(r in msg_lower for r in REFUSAL_WORDS)

    # ── Try to extract name/city/address from current message ────────────────
    if not name:
        name_m = re.search(r'\b(?:mera naam|my name is|naam hai|i am|main|mein)\s+([A-Za-z]{2,15})\b', msg_lower)
        if name_m:
            cand = sanitize_customer_name(name_m.group(1))
            if cand:
                name = cand
        elif step == "name" and not is_refusing:
            cand = sanitize_customer_name(msg.strip())
            if cand:
                name = cand

    if not city:
        for c in ["lahore", "karachi", "islamabad", "rawalpindi", "peshawar",
                  "quetta", "multan", "faisalabad", "sialkot", "gujranwala",
                  "abbottabad", "mardan", "kohat", "pindi", "isb", "rwp", "khi", "lhr"]:
            if re.search(rf'\b{c}\b', msg_lower):
                c_title = c.title()
                if c_title in ["Pindi", "Rwp"]:
                    c_title = "Rawalpindi"
                elif c_title == "Isb":
                    c_title = "Islamabad"
                elif c_title == "Khi":
                    c_title = "Karachi"
                elif c_title == "Lhr":
                    c_title = "Lahore"
                city = c_title
                break

    if not address and not is_refusing:
        if any(w in msg_lower for w in ["road", "street", "gali", "mohalla", "phase", "sector", "block", "house", "dha", "bahria", "town", "mall", "bypass", "chowk"]):
            address = msg.strip()
        elif step == "address" and len(msg.split()) >= 1 and not is_refusing:
            address = msg.strip()

    # ── Determine missing fields ─────────────────────────────────────────────
    need_name = not name
    need_city = is_delivery and not city
    need_address = is_delivery and not address

    logger.info(
        "[Node:collect_customer_info] step=%s esc_type=%s name=%s city=%s address=%s refusing=%s",
        step, esc_type, name, city, address, is_refusing
    )

    # ── Ask for name if still missing ────────────────────────────────────────
    if need_name:
        fallback = "Zaroor! Pehle aapka naam bata dein?"
        reply = await _generate_grounded_customer_reply(
            scenario="Need customer's name to register their inquiry and check with management.",
            raw_message=msg,
            missing_field="customer's first name",
            customer_product=product,
            business_name=biz_name,
            fallback=fallback,
        )
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "customer_name": name,
            "info_collection_step": "name",
            "escalation_type": esc_type,
            "reply_text": reply,
            "reply_chunks": [reply],
            "media_url": None,
            "media_urls": None,
            "owner_alert": None,
            "forward_to_customer": None,
            "forward_message": None,
        }

    # ── Ask for city if still missing (delivery only) ─────────────────────────
    if need_city:
        fallback = f"Shukriya {name}! Aur kis city mein delivery chahiye?"
        reply = await _generate_grounded_customer_reply(
            scenario="Need destination city to calculate delivery charges and courier availability.",
            raw_message=msg,
            missing_field="delivery destination city",
            customer_name=name,
            customer_product=product,
            business_name=biz_name,
            fallback=fallback,
        )
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "customer_name": name,
            "customer_city": city,
            "info_collection_step": "city",
            "escalation_type": esc_type,
            "reply_text": reply,
            "reply_chunks": [reply],
            "media_url": None,
            "media_urls": None,
            "owner_alert": None,
            "forward_to_customer": None,
            "forward_message": None,
        }

    # ── Ask for address if still missing (delivery only) ──────────────────────
    if need_address:
        fallback = f"{city} mein delivery address batayein — mohalla, area ya street number?"
        reply = await _generate_grounded_customer_reply(
            scenario=f"Customer is in {city}. Need local street address / area / mohalla to arrange courier delivery.",
            raw_message=msg,
            missing_field="street / area / mohalla address in " + (city or ""),
            customer_name=name,
            customer_city=city,
            customer_product=product,
            business_name=biz_name,
            fallback=fallback,
        )
        return {
            **state,
            "customer_state": "COLLECTING_INFO",
            "customer_name": name,
            "customer_city": city,
            "customer_address": address,
            "info_collection_step": "address",
            "escalation_type": esc_type,
            "reply_text": reply,
            "reply_chunks": [reply],
            "media_url": None,
            "media_urls": None,
            "owner_alert": None,
            "forward_to_customer": None,
            "forward_message": None,
        }

    # ── All required info collected — escalate to owner ───────────────────────
    esc_service = EscalationService()
    copilot = OwnerCopilotService()
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, AttributeError):
        tenant_id = uuid.uuid4()

    esc_record = esc_service.create_escalation(
        tenant_id=tenant_id,
        customer_phone=phone,
        question=state.get("raw_message", ""),
        product_context=product,
    )

    owner_alert = copilot.format_escalation_alert(
        customer_phone=phone,
        customer_question=state.get("raw_message", ""),
        customer_name=name,
        extracted_item=product,
        extracted_city=city,
        customer_address=address,
        inquiry_type=esc_type,
    )

    name_salutation = f"{name}" if name else "bhai"
    fallback_confirm = (
        f"Theek hai {name_salutation}, main shop se {city or ''} ke liye {product} delivery charges "
        f"confirm karke aapko foran batata hoon."
    ) if is_delivery else f"Theek hai {name_salutation}, main shop se confirm karke aapko foran update karta hoon."

    customer_reply = await _generate_grounded_customer_reply(
        scenario=f"All details collected ({name}, {city}, {address}). Reassure the customer that shop management is being contacted right now to confirm delivery charges and details for {product}.",
        raw_message=msg,
        customer_name=name,
        customer_city=city,
        customer_product=product,
        business_name=biz_name,
        fallback=fallback_confirm,
    )

    logger.info(
        "[Node:collect_customer_info] ESCALATED — phone=%s name=%s city=%s address=%s product=%s",
        phone, name, city, address, product
    )

    return {
        **state,
        "customer_state": "ESCALATED",
        "customer_name": name,
        "customer_city": city,
        "customer_address": address,
        "escalation_id": esc_record.escalation_id,
        "info_collection_step": None,
        "escalation_type": esc_type,
        "reply_text": customer_reply,
        "reply_chunks": [customer_reply],
        "media_url": None,
        "media_urls": None,
        "owner_alert": owner_alert,
        "forward_to_customer": None,
        "forward_message": None,
    }


# --------------------------------------------------------------------------
# Node: escalate_to_owner  (legacy — kept for direct city-only escalations)
# --------------------------------------------------------------------------
async def escalate_to_owner(state: RabtaGraphState) -> RabtaGraphState:
    """Legacy direct escalation used only when city already known from NLU.
    Redirects through collect_customer_info for consistent info gathering."""
    nlu_city = state.get("nlu_extracted_city")
    merged = {**state}
    if nlu_city and not merged.get("customer_city"):
        merged["customer_city"] = nlu_city
    merged["escalation_type"] = "delivery"
    merged["customer_state"] = "COLLECTING_INFO"
    return await collect_customer_info(merged)


# --------------------------------------------------------------------------
# Node: customer_sales_chat
# State: BROWSING or transitions to ESCALATED if unanswerable question
# --------------------------------------------------------------------------
async def customer_sales_chat(state: RabtaGraphState) -> RabtaGraphState:
    """
    Product & sales chat. Calls Gemini for language generation.
    If Gemini signals an unanswerable inquiry / escalation, creates the
    escalation record and formats the alert for Haider bhai.
    """
    # If a new image is received, reset old inquiry/delivery context so the new gun starts fresh
    if state.get("image_base64"):
        state["customer_address"] = None
        state["escalation_id"] = None
        state["escalation_type"] = None
        state["info_collection_step"] = None
        state["customer_state"] = "BROWSING"

    reply_data = await _store_agent.handle_customer_interaction(
        customer_message=state.get("raw_message", ""),
        business_name=state.get("business_name", "Haider Arms"),
        industry=state.get("industry", "Firearms Retail"),
        catalog_context=state.get("catalog_context", ""),
        conversation_history=state.get("conversation_history") or [],
        image_base64=state.get("image_base64"),
    )

    reply_text = reply_data.get("reply_text", "")
    reply_chunks = reply_data.get("reply_chunks") or [reply_text]
    needs_escalation = bool(reply_data.get("needs_escalation")) or any(
        kw in reply_text.lower() for kw in ["confirm karke", "shop se pata karke", "management se confirm"]
    )

    owner_alert = None
    customer_state = "BROWSING"
    escalation_id = state.get("escalation_id")

    current_product = reply_data.get("extracted_item") or state.get("customer_product")
    current_city = reply_data.get("extracted_city") or state.get("customer_city")
    current_name = sanitize_customer_name(reply_data.get("extracted_name") or state.get("customer_name"))

    # ── Photo / picture request handling ─────────────────────────────────────
    # This runs BEFORE the escalation block so a photo request can never be
    # mis-routed into info-collection.
    media_url = None
    raw_msg_lower = state.get("raw_message", "").lower()
    
    is_correction = bool(state.get("nlu_correction_intent")) or any(
        re.search(pat, raw_msg_lower) for pat in [
            r'\b(?:galat|ghalat|wrong)\b',
            r'\bkuch (?:orr|aur)\b',
            r'\byeh? (?:to )?nahi\b',
            r'\bm[ae]ne\s+([a-zA-Z0-9\s.]+?)\s+ka\s+poocha',
            r'\b(?:dusri|doosri|sahi)\s+(?:pic|picture|photo|tasweer|image)\b',
        ]
    )

    # Photo intent: trust NLU classification DIRECTLY.
    # CRITICAL: When Deepgram transcribes voice in Urdu Arabic script (e.g. پکچر شیئر کریں),
    # raw keyword matching ("pic", "photo", etc.) will FAIL because those words are in Arabic
    # script, not Latin. NLU Gemini reads the Arabic correctly and sets nlu_photo_intent=True.
    # We must trust NLU here, not raw text keywords.
    _EXPLICIT_PHOTO_WORDS = ["pic", "picture", "photo", "tasweer", "image", "bhejo", "share karein", "share keren"]
    has_explicit_photo_keyword = any(kw in raw_msg_lower for kw in _EXPLICIT_PHOTO_WORDS)

    # Browse intent: customer asking to see a category or alternatives
    is_browse_intent = bool(state.get("nlu_browse_intent"))

    is_photo_requested = (
        bool(state.get("nlu_photo_intent"))   # ← NLU already handled Arabic script correctly
        or is_correction
        or has_explicit_photo_keyword          # fallback: plain text "pic"/"photo" keywords
    )

    # Contextual product resolution:
    # Check if customer wants photos for multiple items ("dono", "all", "both")
    from app.graph.nodes.nlu import (
        _BRANDS, _refresh_catalog_cache_if_needed,
        _extract_products_from_text, _catalog_cache,
    )
    # Multi-requested: explicit words OR NLU detected multiple products in one message (e.g. voice listing guns)
    _nlu_multi = (state.get("nlu_extracted_products") or [])
    is_multi_requested = (
        any(w in raw_msg_lower for w in ["dono", "both", "all", "teeno", "sab", "inke"])
        or len(_nlu_multi) > 1
    )
    media_urls = None

    # Refresh DB-backed catalog cache (no-op if < 5 min old)
    await _refresh_catalog_cache_if_needed()
    live_catalog = _catalog_cache  # list of lowercase product names from DB

    matched_products = []

    # ── STEP 0: NLU product injection (HIGHEST PRIORITY for photo requests) ──
    # When NLU says photo=True AND extracted a product name (works for Arabic script voice),
    # inject it FIRST before any raw-text matching.
    if is_photo_requested and not is_browse_intent:
        nlu_prods = state.get("nlu_extracted_products") or []
        if nlu_prods:
            matched_products = list(nlu_prods)
        elif state.get("nlu_extracted_product"):
            matched_products.append(state.get("nlu_extracted_product"))

    # ── STEP 1: Search CURRENT raw_message using LIVE CATALOG (Latin-text messages) ──
    if not matched_products:
        matched_products = _extract_products_from_text(raw_msg_lower, live_catalog)

    # Brand-keyword fallback for current message (e.g. "bellini", "kral")
    if not matched_products:
        for brand, default_model in sorted(_BRANDS.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf'\b{re.escape(brand)}\b', raw_msg_lower):
                if default_model not in matched_products:
                    matched_products.append(default_model)

    # ── STEP 2: Only if current message has NO product/brand at all AND                 ──
    # ──         it's NOT a browse/alternatives request (to prevent re-sending same item) ──
    # NOTE: History scan is intentionally LIMITED to the LAST BOT TURN only (not all history)
    # to avoid picking up wrong products from a rifle-list reply when user asked about a pistol.
    if not matched_products and not is_browse_intent:
        history = state.get("conversation_history") or []
        # Only check the most recent assistant turn — don't scan further back
        for h in reversed(history):
            if h.get("role") in ("assistant", "bot"):
                h_text = h.get("text", "").lower()
                history_matches = _extract_products_from_text(h_text, live_catalog)
                if len(history_matches) == 1:
                    # Only use history match if it's UNAMBIGUOUS (exactly one product found)
                    matched_products = history_matches
                # Never pick from a list of 2+ items from history — too ambiguous
                break  # Only check the single most-recent bot turn

    # ── STEP 3: Fallback to current_product ONLY if not a browse request ───
    if not matched_products and not is_browse_intent:
        fallback_p = current_product
        if fallback_p:
            matched_products.append(fallback_p)

    search_term = matched_products[0] if matched_products else None
    if search_term and not is_browse_intent:
        current_product = search_term

    if is_photo_requested:
        if matched_products:
            try:
                from app.services.catalog_tools import get_product_photos

                tenant_id_val = state.get("tenant_id")
                found_items_with_images = []

                targets_to_fetch = matched_products if is_multi_requested else [matched_products[0]]
                for target_p in targets_to_fetch:
                    photos = await get_product_photos(
                        tenant_id=tenant_id_val,
                        product_name=target_p,
                        allow_multiple=is_multi_requested,
                    )
                    for photo in photos:
                        found_items_with_images.append({
                            "name": photo["product_name"],
                            "url": photo["url"],
                            "caption": photo["caption"],
                        })

                if len(found_items_with_images) > 1:
                    media_urls = found_items_with_images
                    media_url = found_items_with_images[0]["url"]
                    reply_text = f"Jee bilkul, yeh lijiye {' aur '.join(x['name'] for x in found_items_with_images)} ki pictures."
                    reply_chunks = [reply_text]
                    needs_escalation = False
                    logger.info("[Node:customer_sales_chat] Sending multiple images (%d items)", len(media_urls))
                elif len(found_items_with_images) == 1:
                    single_item = found_items_with_images[0]
                    media_url = single_item["url"]
                    media_urls = [single_item]
                    current_product = single_item["name"]
                    if is_correction:
                        reply_text = f"Maafi chahta hoon ghalat picture chali gayi thi! Yeh lijiye sahi {single_item['name']} ki picture."
                    else:
                        reply_text = f"Jee bilkul, yeh lijiye {single_item['name']} ki picture."
                    reply_chunks = [reply_text]
                    needs_escalation = False
                    logger.info("[Node:customer_sales_chat] Sending image for %s -> %s", single_item["name"], media_url)
                else:
                    target_name = matched_products[0]
                    if is_correction:
                        reply_text = f"Maafi chahta hoon! {target_name} ki photo abhi catalog mein available nahi hai. Aap shop visit karke dekh sakte hain ya specs pooch sakte hain."
                    else:
                        reply_text = f"Bhai {target_name} ki photo abhi upload nahi hui, sorry. Jaldi available ho gi — aap price ya specs pooch sakte hain."
                    reply_chunks = [reply_text]
                    media_url = None
                    media_urls = None
                    needs_escalation = False
                    logger.info("[Node:customer_sales_chat] No image found for %s", target_name)
            except Exception as img_err:
                logger.warning("[Node:customer_sales_chat] Image lookup error: %s", img_err)
        else:
            reply_text = "Bhai pehle batayein konsi firearm ki picture chahiye, phir main bhejta hoon!"
            reply_chunks = [reply_text]
            needs_escalation = False

    # ── HARD CODE-LEVEL RULE: NO LYING / HALLUCINATING SENT IMAGES ───────────
    # If media_url is None, the AI is STRICTLY FORBIDDEN from saying "yeh check karein tasweer"
    if not media_url:
        FALSE_CLAIM_PATTERNS = [
            r'yeh\s+(?:check\s+karein|lijiye|dekhein)[^.]*?(?:tasweer|picture|photo|pic|image)[^.]*?\.',
            r'(?:tasweer|picture|photo|pic|image)\s+(?:bhej\s+di|send\s+kar\s+di|share\s+kar\s+di|check\s+karein)[^.]*?\.',
            r'maafi\s+chahta\s+hoon[^.]*?(?:tasweer|picture|photo)[^.]*?\.',
        ]
        for pat in FALSE_CLAIM_PATTERNS:
            if re.search(pat, reply_text, flags=re.IGNORECASE):
                logger.warning("[Node:customer_sales_chat] Blocked false image claim from AI text: %r", reply_text)
                if is_photo_requested and search_term:
                    reply_text = f"Bhai {search_term} ki photo abhi available nahi hai. Aap shop visit karke check kar sakte hain ya specs pooch sakte hain."
                else:
                    reply_text = re.sub(pat, '', reply_text, flags=re.IGNORECASE).strip()
                    if not reply_text:
                        reply_text = "Jee batayein, kis model ke baare mein janna chahte hain?"
                reply_chunks = [reply_text]

    is_legal_inquiry = bool(state.get("nlu_legal_intent")) or any(
        kw in raw_msg_lower for kw in ["license", "licence", "permit", "qanoon", "qanooni", "nadra", "without license", "bina license"]
    )

    if is_legal_inquiry:
        reply_text = "Firearms purchase ke liye valid license aur legal requirements zaroori hain. Iski exact procedure aur verification ke liye main shop management se confirm karke aapko update karta hoon."
        reply_chunks = [reply_text]
        needs_escalation = True
        try:
            tenant_id_str = state.get("tenant_id", "")
            t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
            esc = _esc_service.create_escalation(
                tenant_id=t_uuid,
                customer_phone=state.get("sender_phone", ""),
                question=raw_msg_lower,
                product_context=current_product,
            )
            escalation_id = esc.escalation_id
            owner_alert = (
                f"🚨 [LEGAL / LICENSING INQUIRY]\n"
                f"Customer {current_name or ''} ({state.get('sender_phone')}) ne license requirement / procedure ke baare mein poochha hai:\n"
                f"\"{raw_msg_lower}\"\n"
                f"Firearm: {current_product or 'General'}\n"
                f"Please verify karein aur reply karein."
            )
            logger.info("[Node:customer_sales_chat] HIGH-PRIORITY Legal escalation created: %s", escalation_id)
        except Exception as e:
            logger.warning("[Node:customer_sales_chat] Failed creating legal escalation: %s", e)

    elif needs_escalation and customer_state not in ("COLLECTING_INFO", "ESCALATED") and not is_photo_requested:
        # STRICT DELIVERY CHECK: Requires explicit delivery words and NOT color/spec questions
        is_delivery = any(
            kw in raw_msg_lower for kw in ["delivery", "deliver", "courier", "home delivery", "mangwana", "bhejwai", "bhejna"]
        ) and not any(
            att in raw_msg_lower for att in ["color", "colour", "variant", "specs", "spec", "barrel", "finish"]
        )
        
        # Only enter address collection if explicitly asking for delivery
        if is_delivery:
            esc_type = "delivery"
            customer_state = "COLLECTING_INFO"
            logger.info(
                "[Node:customer_sales_chat] COLLECTING_INFO triggered for %s esc_type=%s product=%s",
                state.get("sender_phone"), esc_type, current_product
            )

            collection_state = {
                **state,
                "customer_state": "COLLECTING_INFO",
                "customer_product": current_product,
                "customer_city": current_city,
                "customer_name": current_name,
                "escalation_type": esc_type,
                "info_collection_step": None,
                "reply_text": reply_text,
                "reply_chunks": reply_chunks,
                "owner_alert": None,
                "forward_to_customer": None,
                "forward_message": None,
            }
            return await collect_customer_info(collection_state)
        else:
            # Discount or custom inquiry — create escalation alert directly without trapping in delivery collection
            esc_type = "inquiry"
            try:
                tenant_id_str = state.get("tenant_id", "")
                t_uuid = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()
                esc = _esc_service.create_escalation(
                    tenant_id=t_uuid,
                    customer_phone=state.get("sender_phone", ""),
                    question=raw_msg_lower,
                    product_context=current_product,
                )
                escalation_id = esc.escalation_id
                owner_alert = (
                    f"Haider bhai, {current_name or 'Customer'} ({state.get('sender_phone')}) {current_product or 'item'} ke baare mein pooch raha hai:\n"
                    f"\"{raw_msg_lower}\"\n"
                    f"Aap jo reply karein ge customer ko convey ho jaye ga."
                )
            except Exception as e:
                logger.warning("[Node:customer_sales_chat] Failed creating inquiry escalation: %s", e)

    logger.info(
        "[Node:customer_sales_chat] phone=%s chunks=%d escalate=%s product=%s media_url=%s",
        state.get("sender_phone"), len(reply_chunks), needs_escalation, current_product, media_url
    )

    return {
        **state,
        "customer_state": customer_state,
        "customer_product": current_product,
        "customer_city": current_city,
        "customer_name": current_name,
        "escalation_id": escalation_id,
        "media_url": media_url,
        "media_urls": media_urls,
        "reply_text": reply_text,
        "reply_chunks": reply_chunks,
        "owner_alert": owner_alert,
        "forward_to_customer": None,
        "forward_message": None,
    }


