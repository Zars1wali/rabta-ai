"""
NLU Node — the ONLY place in the system where Gemini is called for understanding.

Two responsibilities, strictly separated:
  1. Customer NLU: understand what the customer said and populate nlu_* fields
  2. Owner NLU: understand what the owner said and populate nlu_* fields

This node NEVER decides what happens next.
It fills fields. The graph's edge functions decide transitions based on those fields.

Gemini output format: strict JSON, low temperature.
Fallback: regex parser if Gemini call fails.
"""
from __future__ import annotations
import re
import json
import logging
import time
import asyncio
from typing import Optional, List, Dict, Tuple
from google import genai
from google.genai import types
from app.core.config import settings
from app.graph.state import RabtaGraphState

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Known entities (deterministic extraction fallback)
# --------------------------------------------------------------------------
_CITIES = [
    "lahore", "karachi", "islamabad", "rawalpindi", "peshawar", "quetta",
    "multan", "faisalabad", "sialkot", "gujranwala", "abbottabad", "mardan",
    "kohat", "dera", "hyderabad", "sukkur", "bahawalpur", "sargodha",
    "larkana", "rahim yar khan", "sahiwal", "sheikhupura", "gujrat",
]

# ---------------------------------------------------------------------------
# LIVE CATALOG CACHE — loaded from DB, refreshed every 5 minutes.
# This replaces the old static _PRODUCTS/_BRANDS lists which drifted out of
# sync whenever a new product was added to the DB.
# ---------------------------------------------------------------------------
_catalog_cache: List[str] = []          # lowercase product names from DB
_catalog_cache_ts: float = 0.0          # unix timestamp of last refresh
_CATALOG_TTL = 300                      # seconds between refreshes
_catalog_lock = asyncio.Lock()

async def _refresh_catalog_cache_if_needed() -> None:
    """Async: refresh the in-process catalog name cache from the DB."""
    global _catalog_cache, _catalog_cache_ts
    now = time.time()
    if now - _catalog_cache_ts < _CATALOG_TTL and _catalog_cache:
        return
    async with _catalog_lock:
        # double-check after acquiring lock
        if time.time() - _catalog_cache_ts < _CATALOG_TTL and _catalog_cache:
            return
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.database import CatalogItem
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                q = select(CatalogItem.name).distinct()
                res = await session.execute(q)
                names = [r[0] for r in res.all() if r[0]]
            _catalog_cache.clear()
            _catalog_cache.extend([str(n).lower() for n in names if n])
            _catalog_cache_ts = time.time()
            logger.info("[NLU] Catalog cache refreshed: %d products", len(_catalog_cache))
        except Exception as exc:
            logger.warning("[NLU] Failed to refresh catalog cache: %s", exc)


def get_catalog_cache() -> List[str]:
    return list(_catalog_cache)



def _extract_products_from_text(text: str, catalog_names: List[str]) -> List[str]:
    """
    Given lowercase message text and a list of lowercase catalog product names,
    return all product names (in original casing from DB) present in the text.
    Uses word-boundary matching sorted longest-first so 'Kral XPS Bullpup' wins over 'Kral XPS'.
    """
    t = (text or "").lower()
    found: List[str] = []
    seen_lower: set = set()
    for name_lower in sorted(catalog_names or [], key=len, reverse=True):
        if not name_lower or name_lower in seen_lower:
            continue
        # Use word-boundary regex for multi-word product names
        pat = re.escape(name_lower)
        if re.search(rf'\b{pat}\b', t):
            # Restore title-case from cache
            found.append(name_lower.title())
            seen_lower.add(name_lower)
    return found


# Keep backward-compatible _PRODUCTS/_BRANDS for owner.py and other callers.
# These are still useful as a brand->default_model mapping.
_PRODUCTS: List[str] = []  # populated lazily from DB; kept for compat

_BRANDS: Dict[str, str] = {
    "colt": "Colt M4",
    "sig sauer": "Sig Sauer M400",
    "sig": "Sig Sauer M400",
    "glock": "Glock 19 Gen 5",
    "canik": "Canik TP9 Sub Elite",
    "taurus": "Taurus PT92 AFS Black",
    "utas defense": "Utas Defense AR10",
    "utas": "Utas Defense AR10",
    "desert eagle": "Desert Eagle .44 Magnum",
    "cz": "CZ Shadow 2",
    "saiga": "Saiga MK",
    "beretta": "Beretta 92FS",
    "bellini": "Bellini Magnum",
    "kral": "Kral XPS",
    "stoeger": "Stoeger STR9",
    "norinco": "Norinco NP-7",
    "hs9": "HS9 Subcompact",
    "hk": "HK SFP9",
    "zigana": "Zigana PX9 Gen 3",
    "zig": "Zig 14",
    "girsan": "Girsan MC 1911",
    "kimber": "Kimber Rapide 1911",
    "ruger": "Ruger 5.7",
    "keltec": "Keltec RDB Bullpup",
    "diamondback": "Diamondback DB15",
    "scar": "Scar 17 .308",
    "smith": "Smith & Wesson 1911 Performance Center",
    "s&w": "Smith & Wesson 1911 Performance Center",
    "baikal": "Baikal Makarov 442",
    "akdas": "Akdas SA-9",
    "agaoglu": "Agaoglu FXS 9",
    "derya": "Derya DY9",
    "ermox": "ERMOX XP Pro Series",
    "vepr": "Vepr Molot Krenkove",
    "huglu": "Huglu Tactical Bolt Action",
    "mkа": "MKA",
    "mka": "MKA",
    "brg": "BRG9 Elite",
    "brg9": "BRG9 Elite",
}

# Photo-request keywords — ONLY explicit photo/image request words.
# NOTE: "dekhaye", "dikhao", "dekh", "show" are intentionally EXCLUDED because
# they mean "browse/show me options" not "send me a product photo".
# For photo detection, at least one of these explicit words must appear.
_PHOTO_WORDS = [
    "pic", "picture", "photo", "tasweer", "image", "tasvir",
]

# Browse/list request keywords — customer wants to SEE OPTIONS or ALTERNATIVES.
# e.g. "rifles dekhaye", "or options kya hain", "kuch aur dikhao"
_BROWSE_WORDS = [
    "dekhaye", "dikhao", "dikhayein", "dekh", "show", "options",
    "available", "list", "batao", "konse", "kaunse", "bata", "kya kya",
    "aur options", "or options", "kuch aur", "doosre", "dusre",
    "alternatives", "variety", "range", "models",
]

_CATEGORY_KEYWORDS = {
    "rifle": ["rifle", "rifles", "ak", "m4", "carbine", "assault", "ar", "bullpup"],
    "pistol": ["pistol", "pistols", "handgun", "sidearm"],
    "shotgun": ["shotgun", "shotguns", "12 bore", "gauge"],
    "sniper": ["sniper", "bolt action", "bolt-action"],
}

_CORRECTION_PATTERNS = [
    r'\b(?:galat|ghalat|wrong)\b',
    r'\bkuch (?:orr|aur)\b',
    r'\byeh? (?:to )?nahi\b',
    r'\bm[ae]ne\s+([a-zA-Z0-9\s.]+?)\s+ka\s+poocha',
    r'\bm[ae]ne\s+([a-zA-Z0-9\s.]+?)\s+manga',
    r'\b(?:dusri|doosri|sahi)\s+(?:pic|picture|photo|tasweer|image)\b',
]

_DELIVERY_WORDS = [
    "delivery", "deliver", "courier", "bhejdo", "bhej do", "bhejna",
    "charges", "shipping", "send karo", "mangwana",
]

_NAME_KEYWORDS = r'\b(?:mera naam|my name is|i am)\s+([a-zA-Z]{3,15})\b'
_NAME_BLACKLIST = {
    "delivery", "lahore", "karachi", "islamabad", "glock", "taurus",
    "hai", "bhai", "want", "need", "price", "peshawar", "pindi",
    "rawalpindi", "canik", "tisas", "beretta", "available", "brand",
    "nahi", "pata", "shop", "model", "firearm", "pistol", "gun",
    "cheez", "stoeger", "image", "photo", "pic", "kya", "konsa",
    "charges", "rates", "rate", "cost", "details",
    "asalam", "assalam", "salam", "slam", "aslam", "aoa", "walaikum", "walikum", "wassalam",
    "hello", "hi", "hey", "janab", "bro", "dear", "shukriya", "thanks", "ok", "theek",
    "acha", "ji", "jee", "customer", "process",
}

_ORIGINS = ["USA", "Austria", "Turkey", "Pakistan", "Brazil", "China", "Italy"]


def _regex_city(text: str) -> Optional[str]:
    t = text.lower()
    for city in _CITIES:
        if re.search(rf'\b{re.escape(city)}\b', t):
            return city.title()
    return None


def _regex_product(text: str) -> Optional[str]:
    t = text.lower()
    # 1. Exact model match
    for p in sorted(_PRODUCTS, key=len, reverse=True):
        if re.search(rf'\b{re.escape(p)}\b', t):
            return p.title()
    # 2. Brand match
    for brand, default_model in sorted(_BRANDS.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf'\b{re.escape(brand)}\b', t):
            return default_model
    return None


def _regex_name(text: str) -> Optional[str]:
    tl = (text or "").lower()
    if any(w in tl for w in ["nahi pata", "pata nahi", "maloom nahi", "brand"]):
        return None
    m = re.search(_NAME_KEYWORDS, tl)
    if m:
        cand = m.group(1).capitalize()
        if cand and cand.lower() not in _NAME_BLACKLIST:
            return cand
    return None

_LEGAL_PATTERNS = [
    r'\b(?:license|licence|licensing|permit|qanooni?|illegal|qanoon|nadra|all pakistan|punjab license|without license|bina license|allow(?:ed)?|ban(?:ned)?)\b',
    r'\b(?:rules?|req(?:uirement)?s?|procedure)\b.*?\b(?:buy|purchase|ownership|rakh(?:na)?)\b',
    r'\b(?:age limit|eligible|cnic)\b.*?\b(?:firearm|gun|pistol|rifle|weapon)\b',
]

def _has_legal_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(pat, t) for pat in _LEGAL_PATTERNS)


def _has_delivery_intent(text: str) -> bool:
    t = (text or "").lower()
    # Explicit photo requests, corrections, or product attributes must NEVER be treated as delivery intents
    ATTRIBUTE_WORDS = [
        "pic", "picture", "photo", "tasweer", "image", "dikhao", "dikhayein",
        "galat", "ghalat", "kuch orr", "kuch aur", "mene delivery ka nahi bola",
        "color", "colors", "colour", "colours", "variant", "variants",
        "specs", "specification", "specifications", "barrel", "weight", "finish",
        "caliber", "capacity", "action", "stock", "mag", "magazine"
    ]
    if any(p in t for p in ATTRIBUTE_WORDS):
        # Only true if customer explicitly also asked "delivery" or "courier"
        if not any(w in t for w in ["delivery", "deliver", "courier", "home delivery"]):
            return False
    return any(w in t for w in _DELIVERY_WORDS)


def _has_correction_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(pat, t) for pat in _CORRECTION_PATTERNS)


# --------------------------------------------------------------------------
# Customer NLU (Gemini 2.0 Flash Structured Classification + Regex Fallback)
# --------------------------------------------------------------------------
async def run_customer_nlu(state: RabtaGraphState) -> RabtaGraphState:
    """
    Populate customer NLU fields using genuine Gemini LLM classification:
    - nlu_delivery_intent: customer explicitly asking about delivery/courier/shipping
    - nlu_photo_intent: customer asking to see product picture/photo
    - nlu_correction_intent: customer pointing out wrong image/product
    - nlu_legal_intent: customer asking licensing, permits, NADRA, legal rules
    - nlu_extracted_city: normalized Pakistani city (e.g. Isb -> Islamabad, Rwp -> Rawalpindi)
    - nlu_extracted_product: firearm model/brand name
    - nlu_extracted_name: customer personal name if introduced
    """
    msg = (state.get("raw_message") or "").strip()
    msg_lower = msg.lower()
    biz_name = state.get("business_name", "Haider Arms")

    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    result = None

    # ── 1. High-Speed Deterministic Extraction (0.1ms, zero API calls, 100% reliable) ──
    city_fb = _regex_city(msg)
    product_fb = _regex_product(msg)
    name_fb = _regex_name(msg)
    legal_fb = _has_legal_intent(msg)
    correction_fb = _has_correction_intent(msg)
    photo_fb = correction_fb or any(w in msg_lower for w in _PHOTO_WORDS)
    browse_fb = any(w in msg_lower for w in _BROWSE_WORDS) and not photo_fb
    delivery_fb = _has_delivery_intent(msg) and not photo_fb and not legal_fb and not browse_fb
    cat_fb = None
    for cat, kws in _CATEGORY_KEYWORDS.items():
        if any(kw in msg_lower for kw in kws):
            cat_fb = cat
            break

    pure_greetings = {"salam", "assalam o alaikum", "assalam u alaikum", "assalamualaikum", "aoa", "hello", "hi", "hey"}
    is_greeting = msg_lower.strip() in pure_greetings

    # If any clean sales intent or entity is recognized, resolve instantly without burning LLM roundtrip
    if is_greeting or any([city_fb, product_fb, name_fb, legal_fb, correction_fb, photo_fb, browse_fb, delivery_fb, cat_fb]):
        result = {
            "is_delivery_intent": delivery_fb,
            "is_photo_intent": photo_fb,
            "is_browse_intent": browse_fb,
            "is_correction_intent": correction_fb,
            "is_legal_intent": legal_fb,
            "is_order_intent": False,
            "is_greeting": is_greeting,
            "extracted_city": city_fb,
            "extracted_product": product_fb,
            "extracted_products": [product_fb] if product_fb else [],
            "extracted_category": cat_fb,
            "extracted_name": name_fb,
        }

    # ── 2. LLM Fallback only for ambiguous/unrecognized messages ─────────────────────
    if client and msg and result is None:
        # Include brief history context if available
        history = state.get("conversation_history") or []
        recent_ctx = " | ".join([f"{h.get('role', 'user')}: {h.get('text', '')}" for h in history[-3:]])

        prompt = f"""You are the NLU intent classifier and entity extractor for customer messages sent to {biz_name} (a firearms dealer in Pakistan) on WhatsApp.
Customer Message: "{msg}"
Recent Context: "{recent_ctx}"

Task:
1. Classify customer intents:
   - "is_delivery_intent": true ONLY IF customer is explicitly asking to deliver/ship/courier an item, or asking delivery charges.
   - "is_photo_intent": true ONLY IF customer explicitly asks for a PHOTO/IMAGE/PICTURE of a SPECIFIC product.
   - "is_browse_intent": true IF customer is asking to see a CATEGORY or LIST of products, or asking for ALTERNATIVES.
   - "is_correction_intent": true IF customer says previous image/item sent was wrong.
   - "is_legal_intent": true IF customer is asking about gun licensing, permits, NADRA.
   - "is_order_intent": true IF customer explicitly expresses intent to buy/order.
   - "is_greeting": true IF simple greeting.

2. Extract entities:
   - "extracted_city": normalized Pakistani city name, or null.
   - "extracted_product": specific firearm model or brand, or null.
   - "extracted_category": category keyword (e.g. "rifle", "pistol", "shotgun"), or null.
   - "extracted_name": customer personal name ONLY IF explicitly introduced, or null.
   - "extracted_products": list of firearm models mentioned.

Return STRICT JSON only:
{{"is_delivery_intent": boolean, "is_photo_intent": boolean, "is_browse_intent": boolean, "is_correction_intent": boolean, "is_legal_intent": boolean, "is_order_intent": boolean, "is_greeting": boolean, "extracted_city": string|null, "extracted_product": string|null, "extracted_products": list, "extracted_category": string|null, "extracted_name": string|null}}"""

        model_pool = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest", settings.GEMINI_MODEL]
        seen_models = set()
        for attempt_model in model_pool:
            if not attempt_model or attempt_model in seen_models:
                continue
            seen_models.add(attempt_model)
            try:
                resp = await client.aio.models.generate_content(
                    model=attempt_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                raw = (resp.text or "").strip()
                result = json.loads(raw)
                break
            except Exception as exc:
                logger.warning("[NLU:customer] Model %s failed (%s), trying next", attempt_model, exc)

    # ── Fallback deterministic extraction if LLM unavailable ─────────────────
    if result is None:
        city_fb = _regex_city(msg)
        product_fb = _regex_product(msg)
        name_fb = _regex_name(msg)
        legal_fb = _has_legal_intent(msg)
        correction_fb = _has_correction_intent(msg)
        # Photo intent requires explicit photo keywords (not generic browse words)
        photo_fb = correction_fb or any(w in msg_lower for w in _PHOTO_WORDS)
        # Browse intent: category or alternatives request
        browse_fb = any(w in msg_lower for w in _BROWSE_WORDS) and not photo_fb
        delivery_fb = _has_delivery_intent(msg) and not photo_fb and not legal_fb and not browse_fb
        # Extract category
        cat_fb = None
        for cat, kws in _CATEGORY_KEYWORDS.items():
            if any(kw in msg_lower for kw in kws):
                cat_fb = cat
                break

        result = {
            "is_delivery_intent": delivery_fb,
            "is_photo_intent": photo_fb,
            "is_browse_intent": browse_fb,
            "is_correction_intent": correction_fb,
            "is_legal_intent": legal_fb,
            "is_order_intent": False,
            "is_greeting": False,
            "extracted_city": city_fb,
            "extracted_product": product_fb,
            "extracted_category": cat_fb,
            "extracted_name": name_fb,
        }

    delivery_intent = bool(result.get("is_delivery_intent"))
    photo_intent = bool(result.get("is_photo_intent")) or bool(result.get("is_correction_intent"))
    correction_intent = bool(result.get("is_correction_intent"))
    legal_intent = bool(result.get("is_legal_intent"))
    browse_intent = bool(result.get("is_browse_intent"))
    extracted_category = result.get("extracted_category")
    city = result.get("extracted_city")
    product = result.get("extracted_product")
    products_list = result.get("extracted_products") or []
    if not isinstance(products_list, list):
        products_list = []
    name = result.get("extracted_name")

    # If classified as browse AND no explicit photo keywords — strip photo intent to prevent image loop
    if browse_intent and not any(w in msg_lower for w in _PHOTO_WORDS):
        photo_intent = False

    # Anti-confusion guard: if photo, correction, color, or spec is asked, never classify as delivery!
    ATTRIBUTE_WORDS = [
        "pic", "picture", "photo", "tasweer", "image", "dikhao", "dikhayein",
        "galat", "ghalat", "kuch orr", "kuch aur", "mene delivery ka nahi bola",
        "color", "colors", "colour", "colours", "variant", "variants",
        "specs", "specification", "specifications", "barrel", "weight", "finish",
        "caliber", "capacity", "action", "stock", "mag", "magazine"
    ]
    if any(p in msg_lower for p in ATTRIBUTE_WORDS) and not any(w in msg_lower for w in ["delivery", "deliver", "courier", "home delivery"]):
        delivery_intent = False

    # Guard and normalize city against LLM hallucinations
    if city and isinstance(city, str):
        city_clean = city.strip().title()
        aliases = [city_clean.lower()]
        if city_clean.lower() == "islamabad":
            aliases.append("isb")
        elif city_clean.lower() in ["rawalpindi", "pindi"]:
            aliases.extend(["rwp", "pindi"])
        elif city_clean.lower() == "lahore":
            aliases.append("lhr")
        elif city_clean.lower() == "karachi":
            aliases.append("khi")
        elif city_clean.lower() == "faisalabad":
            aliases.append("fsd")
        elif city_clean.lower() == "peshawar":
            aliases.append("pew")

        # Only accept city if explicitly mentioned in raw message
        if any(re.search(rf"\b{re.escape(a)}\b", msg_lower) for a in aliases):
            city = city_clean
            if city.lower() in ["isb", "islamabad"]:
                city = "Islamabad"
            elif city.lower() in ["rwp", "pindi", "rawalpindi"]:
                city = "Rawalpindi"
            elif city.lower() in ["lhr", "lahore"]:
                city = "Lahore"
            elif city.lower() in ["khi", "karachi"]:
                city = "Karachi"
            elif city.lower() in ["fsd", "faisalabad"]:
                city = "Faisalabad"
            elif city.lower() in ["pew", "peshawar"]:
                city = "Peshawar"
        else:
            city = None

    # Guard name against hallucinations
    if name and isinstance(name, str):
        name_clean = name.strip().title()
        if not any(token.lower() in msg_lower for token in name_clean.split() if len(token) >= 3):
            name = None

    # Guard product against non-firearm conversational phrases (e.g. "apka shop kider", "ok payment process kia")
    NON_PRODUCT_WORDS = {
        "shop", "kider", "kidhar", "kahan", "address", "location", "dukaan", "payment",
        "process", "delivery", "charges", "rate", "price", "kitna", "kitne", "hai", "karo",
        "bhai", "ok", "yes", "no", "theek", "kia", "kya", "kar", "dein", "do", "salam", "showroom"
    }
    if product and isinstance(product, str):
        p_tokens = set(re.findall(r'[a-z0-9]+', product.lower()))
        if p_tokens.issubset(NON_PRODUCT_WORDS) or any(w in product.lower() for w in ["shop kider", "shop kidhar", "payment process", "process kia", "kya rate"]):
            product = None

    # Merge into session state (never overwrite a valid firearm with None or conversational garbage)
    merged_product = product or state.get("customer_product")
    merged_city = city or state.get("customer_city")
    merged_name = name or state.get("customer_name")

    logger.info(
        "[NLU:customer] delivery=%s photo=%s browse=%s legal=%s corr=%s city=%s prod=%s prods=%s cat=%s name=%s",
        delivery_intent, photo_intent, browse_intent, legal_intent, correction_intent, merged_city, merged_product, products_list, extracted_category, merged_name,
    )

    return {
        **state,
        "nlu_delivery_intent": delivery_intent,
        "nlu_photo_intent": photo_intent,
        "nlu_correction_intent": correction_intent,
        "nlu_legal_intent": legal_intent,
        "nlu_browse_intent": browse_intent,
        "nlu_extracted_category": extracted_category,
        "nlu_extracted_city": city,
        "nlu_extracted_product": product,
        "nlu_extracted_products": products_list,
        "nlu_extracted_name": name,
        # Merge into session state immediately
        "customer_city": merged_city,
        "customer_product": merged_product,
        "customer_name": merged_name,
        # Clear owner fields
        "nlu_is_price_update": False,
        "nlu_price_product": None,
        "nlu_price_amount": None,
        "nlu_price_origin": None,
        "nlu_is_add_product": False,
        "nlu_add_product_data": None,
    }



# --------------------------------------------------------------------------
# Owner NLU
# --------------------------------------------------------------------------
async def run_owner_nlu(state: RabtaGraphState) -> RabtaGraphState:
    """
    Determine the owner's intent using genuine Gemini LLM classification:
    - ADD_PRODUCT: adding a new catalog item (e.g. "ek new rifle add kar do: CZ Bren 2 .223 price 950k")
    - PRICE_UPDATE: setting/updating a price (e.g. "450k", "badal do 450000 kar do", "ab 450 hai", "price update glock 19")
    - RELAY_TO_CUSTOMER: answering a pending customer escalation (e.g. "dedo 400 mein", "Islamabad ka 1500 bol do")
    - INFO_REQUEST: asking about inventory or product photo (e.g. "colt ki pic hai?", "kya stock mein hai?")
    - GREETING / CASUAL_CHAT / COMMAND
    """
    msg = state.get("raw_message", "").strip()
    msg_lower = msg.lower()

    # Only skip NLU if owner is in active confirmation / disambiguation flow
    # AND the message looks like an actual confirmation reply (haan/cancel/number).
    # Never skip for fresh intent messages like "new product add karna hai".
    CONFIRM_SKIP_WORDS = ["haan", "han", "yes", "confirm", "bilkul", "cancel", "nahi", "no", "mat karo", "stop"]
    is_likely_confirmation = any(w in msg_lower for w in CONFIRM_SKIP_WORDS)
    FRESH_INTENT_PATTERNS = [
        "add product", "product add", "naya product", "new product", "item add", "add item",
        "new rifle", "naya item", "add new", "naya add", "price update", "rate update",
        "/", "delivery", "photo", "image", "salam", "hello",
    ]
    has_fresh_intent = any(kw in msg_lower for kw in FRESH_INTENT_PATTERNS)

    pending_price = state.get("price_pending_state")
    pending_prod = state.get("product_pending_state")
    if (pending_price or pending_prod) and is_likely_confirmation and not has_fresh_intent:
        return {
            **state,
            "nlu_is_price_update": False,
            "nlu_price_product": None,
            "nlu_price_amount": None,
            "nlu_price_origin": None,
            "nlu_is_add_product": pending_prod in ("AWAITING_DETAILS", "AWAITING_PRICE", "AWAITING_CONFIRMATION"),
            "nlu_add_product_data": None,
            "nlu_delivery_intent": False,
            "nlu_extracted_city": None,
            "nlu_extracted_product": None,
            "nlu_extracted_name": None,
        }

    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    result = None

    if client:
        prompt = f"""You are the intent classifier and entity extractor for the retail business owner (Haider bhai) communicating with his AI copilot via WhatsApp.
Analyze the owner's message: "{msg}"

Classify into one of these intents:
- "ADD_PRODUCT": owner wants to add a new inventory item (e.g. "add product", "naya product add karo", "ek new rifle add kardo: Smith & Wesson M&P15 .223 semi-auto 30 rounds price 850000 USA", "add item")
- "PRICE_UPDATE": owner wants to set, change, or update an existing item's price (e.g. "450k kar do", "badal do 450000 kar do", "ab 450 hai", "glock 19 price 420000", "price update colt m4 800k")
- "RELAY_TO_CUSTOMER": owner is responding to a customer inquiry/escalation (e.g. "dedo 400 mein", "haan 1500 delivery charges hain", "ko bolo kal milega")
- "INFO_REQUEST": owner asks if an item/photo exists (e.g. "colt ki photo hai?", "glock 19x kitne ki hai?")
- "GREETING": greeting like "salam", "kese ho"
- "CASUAL_CHAT": casual remark like "ok", "theek hai", "shukriya"
- "COMMAND": commands starting with /

Extract:
- "intent": string
- "product_name": name of the firearm model if mentioned, or null
- "category": "Pistols" | "Rifles" | "Shotguns" | "Ammunition" | "Accessories" | null
- "origin": country/brand origin if mentioned (e.g. USA, Turkey, Austria, Czech Republic, Pakistan, China, Italy), or null
- "caliber": caliber if mentioned (e.g. 9mm, .223 Rem, 7.62x39, 12 Gauge, 30 Bore), or null
- "capacity": magazine capacity (e.g. "15 rounds", "30 rounds"), or null
- "action": "Semi Auto" | "Full Auto" | "Bolt Action" | "Pump Action" | null
- "new_price": numeric price in PKR as float (parse 450k -> 450000, 3.8 lakh -> 380000, 450000 -> 450000), or null
- "description": summary of specs or description, or null
- "relay_text": message to relay to customer if RELAY_TO_CUSTOMER, or null

Return STRICT JSON only:
{{"intent": string, "product_name": string|null, "category": string|null, "origin": string|null, "caliber": string|null, "capacity": string|null, "action": string|null, "new_price": number|null, "description": string|null, "relay_text": string|null}}"""

        model_pool = [settings.GEMINI_MODEL, "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]
        seen_models = set()
        for attempt_model in model_pool:
            if not attempt_model or attempt_model in seen_models:
                continue
            seen_models.add(attempt_model)
            try:
                resp = await client.aio.models.generate_content(
                    model=attempt_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                raw = (resp.text or "").strip()
                data = json.loads(raw)
                result = data
                if attempt_model != settings.GEMINI_MODEL:
                    logger.info("[NLU:owner] Succeeded with model %s", attempt_model)
                break
            except Exception as exc:
                logger.warning("[NLU:owner] Model %s failed (%s), trying next", attempt_model, exc)

    if result is None:
        add_match = re.search(r'\b(?:add\s+(?:product|item|rifle|pistol|gun)|naya\s+(?:product|item))\b', msg_lower)
        if add_match:
            price_val = 0.0
            p_match = re.search(r'(\d+(?:\.\d+)?)\s*(k|lakh|lac)?', msg_lower)
            if p_match:
                raw_v = float(p_match.group(1))
                u = (p_match.group(2) or "").lower()
                price_val = raw_v * 1000 if u == "k" else (raw_v * 100000 if u in ["lakh", "lac"] else raw_v)
            clean_name = re.sub(r'^(?:add\s+(?:product|item|rifle|pistol|gun)|naya\s+item|ek\s+new\s+(?:rifle|pistol|item)\s+add\s+kar\s+do)[:\s]*', '', msg, flags=re.IGNORECASE).strip()
            result = {
                "intent": "ADD_PRODUCT",
                "product_name": clean_name or "New Firearm",
                "category": "Rifles" if "rifle" in msg_lower else ("Shotguns" if "shotgun" in msg_lower else "Pistols"),
                "new_price": price_val,
            }
        else:
            price_fallback = _regex_price_fallback(msg)
            if price_fallback and price_fallback.get("new_price"):
                result = {
                    "intent": "PRICE_UPDATE",
                    "product_name": price_fallback.get("product_name"),
                    "origin": price_fallback.get("origin"),
                    "new_price": price_fallback.get("new_price"),
                }
            else:
                result = {"intent": "CASUAL_CHAT"}

    intent = result.get("intent", "CASUAL_CHAT")
    CANCEL_WORDS = ["cancel", "nahi", "no", "mat karo", "stop", "band", "chhoro", "rehne do", "add nahi", "chutiye", "pagal"]
    is_cancel = any(w in msg_lower for w in CANCEL_WORDS)
    is_add_keyword = any(kw in msg_lower for kw in ["add product", "product add", "naya product", "new product", "item add", "add item", "new rifle", "naya item"])
    has_price_val = bool(re.search(r'\b\d+(?:\.\d+)?\s*(?:k|lakh|lac)?\b', msg_lower))

    # Only remain in add flow if user is actually providing price/details and didn't cancel/ask something else
    in_add_flow = (
        state.get("product_pending_state") in ("AWAITING_DETAILS", "AWAITING_PRICE")
        and not is_cancel
        and has_price_val
        and intent not in ("INFO_REQUEST", "CASUAL_CHAT")
    )
    is_add_product = (intent == "ADD_PRODUCT" or is_add_keyword or in_add_flow) and not is_cancel
    is_price_update = (intent == "PRICE_UPDATE" and bool(result.get("new_price")) and not is_add_product)
    
    CATALOG_INFO_KEYWORDS = [
        "image", "photo", "pic", "tasveer", "tasvir", "dekao", "dikhao", "dikhana", "bhejo", "send",
        "price", "rate", "rates", "cost", "current price", "kitne ka", "kitne ki", "kya rate", "kia rate",
        "kya price", "kia price", "bhao", "specs", "spec", "specification", "specifications", "detail", "details",
        "maloomat", "stock", "available", "parha hai", "parhi hai", "pari hai", "para hai"
    ]
    is_info_request = (intent == "INFO_REQUEST") or any(kw in msg_lower for kw in CATALOG_INFO_KEYWORDS)

    logger.info(
        "[NLU:owner] intent=%s product=%s price=%s is_add=%s is_price_upd=%s is_info_req=%s in_add_flow=%s",
        intent, result.get("product_name"), result.get("new_price"), is_add_product, is_price_update, is_info_request, in_add_flow
    )

    return {
        **state,
        "nlu_is_price_update": is_price_update,
        "nlu_price_product": result.get("product_name"),
        "nlu_price_amount": float(result.get("new_price", 0)) if result.get("new_price") else None,
        "nlu_price_origin": result.get("origin"),
        "nlu_is_add_product": is_add_product,
        "nlu_add_product_data": result if is_add_product else None,
        "nlu_is_owner_info_request": is_info_request,
        "nlu_extracted_product": result.get("product_name"),
        # Clear customer fields on owner turn
        "nlu_delivery_intent": False,
        "nlu_legal_intent": False,
        "nlu_extracted_city": None,
        "nlu_extracted_name": None,
    }


def _regex_price_fallback(text: str) -> Optional[dict]:
    candidates = list(re.finditer(
        r'(?:pkr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(k|lakh|lac)?',
        text, re.IGNORECASE
    ))
    if not candidates:
        return None

    def _price(m) -> float:
        raw_val = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit == "k":
            return raw_val * 1000
        if unit in ["lakh", "lac"]:
            return raw_val * 100000
        return raw_val

    # Product names often contain model digits (e.g. "Glock 19X"), so a price
    # candidate must be a plausible PKR value. Prefer the last number that is
    # >= 1000, falling back to the last candidate overall.
    chosen = next((m for m in reversed(candidates) if _price(m) >= 1000), candidates[-1])
    price = _price(chosen)

    prod_text = text[:chosen.start()].strip()
    prod_text = re.sub(r'^(?:update|change|set|price of)\s+', '', prod_text, flags=re.IGNORECASE).strip()
    if not prod_text or price < 1000:
        return None

    origin = None
    for org in _ORIGINS:
        if re.search(rf'\b{org}\b', text, re.IGNORECASE):
            origin = org.title()
            break

    return {"is_price_update": True, "product_name": prod_text, "origin": origin, "new_price": price}
