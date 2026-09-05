"""
Owner-facing graph nodes.

All state transitions for owner (Haider bhai) conversations.
The owner is the boss — he gets a different set of nodes entirely.

Node execution order for an owner message:
  run_owner_nlu → owner_router → (one of the nodes below) → END

The owner is NEVER shown error formatting, bullet points, or AI-speak.
All replies are casual Urdu-English mix.
"""
from __future__ import annotations
import re
import json
import uuid
import logging
from app.graph.state import RabtaGraphState
from app.services.price_update_service import PriceUpdateService
from app.services.escalation_service import EscalationService

logger = logging.getLogger(__name__)
_price_service = PriceUpdateService()
_esc_service = EscalationService()


# --------------------------------------------------------------------------
# owner_router — edge function (called by builder edges)
# --------------------------------------------------------------------------
def route_owner(state: RabtaGraphState) -> str:
    """
    Pure router function for owner messages.
    Routes commands to slash handler, active staged add-product flow to product handler,
    and all natural owner messages directly to the Master Owner Intelligence Copilot.
    """
    msg = (state.get("raw_message") or "").strip().lower()
    ps = state.get("price_pending_state")

    # 1. Slash command
    if msg.startswith("/"):
        return "handle_owner_command"

    # 2. Confirmation replies in pending flows
    CONFIRM_WORDS = ["haan", "han", "yes", "confirm", "add kardo", "add kar do", "bilkul", "zaroor"]
    CANCEL_WORDS = ["cancel", "nahi", "no", "mat karo", "stop", "band"]
    is_confirmation_reply = any(w in msg for w in CONFIRM_WORDS + CANCEL_WORDS)
    if state.get("product_pending_state") == "AWAITING_CONFIRMATION" and is_confirmation_reply:
        return "handle_confirmation"
    if state.get("product_pending_state") in ("AWAITING_PRICE", "AWAITING_DETAILS"):
        return "handle_owner_add_product"
    if ps == "AWAITING_DISAMBIGUATION":
        return "handle_disambiguation"
    if ps == "AWAITING_CONFIRMATION" and is_confirmation_reply:
        return "handle_confirmation"

    # 3. Direct photo vision intake (if owner sent an image without text, or with explicit add intent)
    if state.get("image_base64") and (not msg or state.get("nlu_is_add_product")):
        return "handle_owner_add_product"

    # 4. Explicit Add Product intent
    if state.get("nlu_is_add_product"):
        return "handle_owner_add_product"

    # 5. ALL OTHER NATURAL OWNER INTERACTIONS:
    # Greetings, catalog inquiries, stock checks, photo requests, pricing inquiries,
    # price updates, margin preferences, escalation responses, AI pause/resume,
    # casual conversation, and operational questions:
    # Handled with full cognitive reasoning by the Master Owner Intelligence Copilot!
    return "owner_fallback"


# --------------------------------------------------------------------------
# Node: handle_owner_command
# --------------------------------------------------------------------------
async def handle_owner_command(state: RabtaGraphState) -> RabtaGraphState:
    """Handle slash commands: /status, /pause, /resume, /prices, /help"""
    from app.db.session import AsyncSessionLocal
    from app.db.repositories import price_log_repo
    from app.db.repositories import tenant_repo

    msg = state.get("raw_message", "").strip()
    cmd_parts = msg.split()
    cmd = cmd_parts[0].lower()

    try:
        tenant_id = uuid.UUID(state.get("tenant_id", ""))
    except (ValueError, AttributeError):
        reply = "Bhai tenant ID mismatch. System check karo."
        return {**state, "reply_text": reply, "reply_chunks": [reply]}

    if cmd == "/help":
        reply = "Commands: /status, /pause [number], /resume [number], /prices"

    elif cmd == "/status":
        pending = _esc_service.get_pending_for_tenant(tenant_id)
        if pending:
            desc = ", ".join([f"{e.customer_phone[-7:]}: {e.customer_question[:25]}" for e in pending])
            reply = f"AI active hai. Open inquiries ({len(pending)}): {desc}"
        else:
            reply = "Sab clear hai bhai, koi pending inquiry nahi."

    elif cmd == "/pause":
        raw_target = " ".join(cmd_parts[1:]) if len(cmd_parts) > 1 else state.get("active_takeover_customer_phone")
        target = tenant_repo.normalize_phone(raw_target) if raw_target else None
        if not target:
            reply = "Bhai customer number batayein: /pause 03001234567"
        else:
            async with AsyncSessionLocal() as session:
                await tenant_repo.set_human_takeover(session, tenant_id, target)
            reply = f"AI paused for {target}. Aap khud baat karein. Baad mein /resume likhein."

    elif cmd == "/resume":
        raw_target = " ".join(cmd_parts[1:]) if len(cmd_parts) > 1 else None
        target = tenant_repo.normalize_phone(raw_target) if raw_target else None
        async with AsyncSessionLocal() as session:
            await tenant_repo.set_human_takeover(session, tenant_id, None)
        reply = f"AI resumed{f' for {target}' if target else ' for all'}."

    elif cmd == "/prices":
        async with AsyncSessionLocal() as session:
            history = await price_log_repo.get_price_history(session, tenant_id, limit=5)
        if not history:
            reply = "Bhai koi recent price updates nahi hain."
        else:
            lines = []
            for h in history:
                t_str = h.confirmed_at.strftime("%d %b %H:%M")
                lines.append(f"{h.item_name}: PKR {int(h.new_price):,} ({t_str})")
            reply = "\n".join(lines)
    else:
        reply = "Bhai samajh nahi aaya. Rate update ke liye jaise: 'Glock 19 USA 450000' likhein."

    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "owner_alert": None,
        "forward_to_customer": None,
        "forward_message": None,
    }


# --------------------------------------------------------------------------
# Helper: Grounded LLM Response Generator for Owner Copilot Nodes
# --------------------------------------------------------------------------
async def _generate_grounded_owner_reply(
    scenario: str,
    raw_message: str,
    context_details: Optional[dict] = None,
    fallback: str = "",
) -> str:
    """Generate natural, respectful, intelligent Urdu-English copilot message for Haider bhai."""
    from google import genai
    from google.genai import types
    from app.core.config import settings

    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    if not client:
        return fallback

    ctx_str = json.dumps(context_details or {}, indent=2)
    prompt = f"""You are the personal AI executive assistant & inventory copilot for the store owner (Haider bhai) on WhatsApp.
Owner's message: "{raw_message}"
Context / State Data:
{ctx_str}
Scenario: {scenario}

Rules:
1. Address the owner respectfully and conversationally like a sharp employee on WhatsApp (e.g. "Jee Haider bhai...", "Done bhai...", "Theek hai bhai...").
2. Language: Natural Pakistani Roman Urdu mixed with clear English terms.
3. Be clear, direct, and helpful. Avoid overly robotic phrases.
4. Zero emojis, zero markdown asterisks, zero bullet points.
5. Strictly adhere to the facts provided in Context / State Data above.

Generate the exact WhatsApp message to send to Haider bhai:"""

    try:
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=250,
            ),
        )
        text = (resp.text or "").strip()
        text = re.sub(r'[\*\#\_`]', '', text)
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text, flags=re.UNICODE).strip()
        return text if text else fallback
    except Exception as exc:
        logger.warning("[OwnerNode:LLM] Generation fallback: %s", exc)
        return fallback


# --------------------------------------------------------------------------
# Node: extract_and_match_price
# New price update intent — find matching catalog items
# --------------------------------------------------------------------------
async def extract_and_match_price(state: RabtaGraphState) -> RabtaGraphState:
    """Match NLU-extracted product against catalog. Set up pending state."""
    from app.db.session import AsyncSessionLocal

    product_name = state.get("nlu_price_product", "")
    new_price = state.get("nlu_price_amount", 0.0)
    origin = state.get("nlu_price_origin")

    try:
        tenant_id = uuid.UUID(state.get("tenant_id", ""))
    except (ValueError, AttributeError):
        reply = "Bhai system error — tenant mismatch."
        return {**state, "reply_text": reply, "reply_chunks": [reply]}

    async with AsyncSessionLocal() as session:
        matches = await _price_service.match_catalog_items(session, tenant_id, product_name, origin=origin)

    if not matches:
        # If there is an active pending escalation, treat this message as the owner's answer!
        pending = _esc_service.get_pending_for_tenant(tenant_id)
        if pending:
            return await relay_owner_answer(state)

        fallback = f"Catalog mein '{product_name}' nahi mila. Sahi model naam batayein."
        reply = await _generate_grounded_owner_reply(
            scenario=f"Product '{product_name}' not found in catalog.",
            raw_message=state.get("raw_message", ""),
            fallback=fallback,
        )
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "price_pending_state": None,
        }

    snaps = [_price_service._snapshot_item(m) for m in matches]

    if len(snaps) > 1:
        # Multiple matches — need disambiguation
        lines = [f"{len(snaps)} matches mile '{product_name}' ke liye:"]
        for i, s in enumerate(snaps, 1):
            org = f"{s['origin']} — " if s.get("origin") else ""
            lines.append(f"({i}) {s['name']} {org}PKR {int(s['price']):,}")
        lines.append(f"Konsa? 1 se {len(snaps)} number ya description reply karein.")
        reply = "\n".join(lines)
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "price_pending_state": "AWAITING_DISAMBIGUATION",
            "price_pending_matches": snaps,
            "price_pending_proposed": new_price,
            "price_pending_selected": None,
        }

    # Single match — go straight to confirmation
    snap = snaps[0]
    org_str = f" ({snap['origin']})" if snap.get("origin") else ""
    reply = (
        f"Confirm: {snap['name']}{org_str} PKR {int(snap['price']):,} "
        f"se PKR {int(new_price):,} kar dun?\n\nHaan / cancel"
    )
    return {
        **state,
        "reply_text": reply, "reply_chunks": [reply],
        "price_pending_state": "AWAITING_CONFIRMATION",
        "price_pending_matches": snaps,
        "price_pending_proposed": new_price,
        "price_pending_selected": snap,
    }


# --------------------------------------------------------------------------
# Node: handle_disambiguation (Conversational LLM Mapping + Regex Fallback)
# --------------------------------------------------------------------------
async def handle_disambiguation(state: RabtaGraphState) -> RabtaGraphState:
    """
    Intelligently map the owner's response (e.g. 'jo sab se mehengi wali hai',
    'kaali wali', 'doosri wali', 'USA wali', or numbers) to the correct candidate item.
    """
    msg = state.get("raw_message", "").strip()
    msg_lower = msg.lower()
    matches = state.get("price_pending_matches") or []
    new_price = state.get("price_pending_proposed", 0.0)

    if any(w in msg_lower for w in ["cancel", "no", "nahi", "mat karo", "stop", "chor do"]):
        return {
            **state,
            "reply_text": "Price update cancel kar diya.",
            "reply_chunks": ["Price update cancel kar diya."],
            "price_pending_state": None,
            "price_pending_matches": None,
            "price_pending_proposed": None,
            "price_pending_selected": None,
        }

    selected = None
    selected_idx = None

    # 1. LLM Conversational Disambiguation Mapper
    from google import genai
    from google.genai import types
    from app.core.config import settings
    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    if client and matches:
        matches_summary = [
            {"index": i, "name": m.get("name"), "origin": m.get("origin"), "current_price": m.get("price"), "category": m.get("category")}
            for i, m in enumerate(matches)
        ]
        prompt = f"""You are an intelligent entity matcher for store owner responses.
The store owner was asked to disambiguate which item to update from this list:
{json.dumps(matches_summary, indent=2)}

Owner's response: "{msg}"

Task:
Determine which index (0 to {len(matches)-1}) the owner selected.
Interpret natural descriptions, rankings, colors, origins, or ordinals:
- "jo sab se mehengi wali hai" / "expensive one" -> highest price item
- "jo sasti hai" -> lowest price item
- "kaali wali" / "black" -> item with Black finish/name
- "doosri wali" / "second" / "2" -> index 1
- "pehli wali" / "first" / "1" -> index 0
- "USA wali" / "austrian" -> match by origin
- "cancel" / "no" / "nahi" -> is_cancel: true

Return STRICT JSON only:
{{"selected_index": number|null, "is_cancel": boolean}}"""

        try:
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
            )
            raw = json.loads((resp.text or "").strip())
            if raw.get("is_cancel"):
                return {
                    **state,
                    "reply_text": "Price update cancel kar diya.",
                    "reply_chunks": ["Price update cancel kar diya."],
                    "price_pending_state": None,
                    "price_pending_matches": None,
                    "price_pending_proposed": None,
                    "price_pending_selected": None,
                }
            s_idx = raw.get("selected_index")
            if isinstance(s_idx, int) and 0 <= s_idx < len(matches):
                selected_idx = s_idx
                selected = matches[s_idx]
        except Exception as exc:
            logger.warning("[Disambiguation:LLM] Mapper error: %s", exc)

    # 2. Deterministic Fallback if LLM didn't resolve
    if not selected:
        num_m = re.search(r'\b([1-9])\b', msg_lower)
        if num_m:
            idx = int(num_m.group(1)) - 1
            if 0 <= idx < len(matches):
                selected = matches[idx]

    if not selected:
        for m in matches:
            org = (m.get("origin") or "").lower()
            if org and org in msg_lower:
                selected = m
                break

    if not selected:
        fallback = f"Samajh nahi aaya. 1 se {len(matches)} number reply karein ya 'cancel'."
        reply = await _generate_grounded_owner_reply(
            scenario=f"Owner response was unclear for disambiguating {len(matches)} items. Ask politely to pick by number or description.",
            raw_message=msg,
            fallback=fallback,
        )
        return {**state, "reply_text": reply, "reply_chunks": [reply]}

    org_str = f" ({selected['origin']})" if selected.get("origin") else ""
    reply = (
        f"Confirm: {selected['name']}{org_str} PKR {int(selected['price']):,} "
        f"se PKR {int(new_price):,} kar dun?\n\nHaan / cancel"
    )
    return {
        **state,
        "reply_text": reply, "reply_chunks": [reply],
        "price_pending_state": "AWAITING_CONFIRMATION",
        "price_pending_selected": selected,
    }


# --------------------------------------------------------------------------
# Node: handle_owner_add_product (Grounded Natural Prompts + Vision Intake)
# --------------------------------------------------------------------------
async def handle_owner_add_product(state: RabtaGraphState) -> RabtaGraphState:
    """Owner wants to add a new inventory item — handles full text, photos, or multi-turn flow."""
    in_genuine_add_flow = state.get("product_pending_state") in ("AWAITING_DETAILS", "AWAITING_PRICE")
    prev_staged = state.get("product_pending_item") if in_genuine_add_flow else {}
    data = state.get("nlu_add_product_data") or {}
    raw_msg = (state.get("raw_message") or "").strip()
    raw_lower = raw_msg.lower()

    # 1. Parse fields
    name_from_data = data.get("product_name") if data.get("intent") == "ADD_PRODUCT" else None
    name_from_price = state.get("nlu_price_product")
    staged_name = prev_staged.get("name") if prev_staged.get("name") not in [None, "", "New Item", "New Product", "Naya Item"] else None
    name = (name_from_data or name_from_price or staged_name or "").title()

    category = data.get("category") or prev_staged.get("category")
    origin = data.get("origin") or state.get("nlu_price_origin") or prev_staged.get("origin") or "Imported"
    caliber = data.get("caliber") or prev_staged.get("caliber") or "Standard"
    capacity = data.get("capacity") or prev_staged.get("capacity") or "Standard"
    action = data.get("action") or prev_staged.get("action") or "Semi Auto"

    price = float(data.get("new_price") or state.get("nlu_price_amount") or prev_staged.get("price") or 0.0)
    if price == 0.0:
        p_match = re.search(r'(\d+(?:\.\d+)?)\s*(k|lakh|lac)\b', raw_lower)
        if p_match:
            raw_v = float(p_match.group(1))
            u = (p_match.group(2) or "").lower()
            price = raw_v * 1000 if u == "k" else (raw_v * 100000 if u in ["lakh", "lac"] else raw_v)

    img_b64 = state.get("image_base64")
    images = prev_staged.get("images") or []

    # 2. Image save and Gemini Vision identification
    if img_b64:
        try:
            import base64, os
            clean_tag = re.sub(r'[^a-zA-Z0-9_]', '_', str(name or "firearm").lower())
            clean_fname = f"{clean_tag}_{uuid.uuid4().hex[:6]}.jpg"
            img_dir = "/app/app/static/catalog_images"
            if not os.path.exists(img_dir):
                os.makedirs(img_dir, exist_ok=True)
            img_path = os.path.join(img_dir, clean_fname)
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            images.append(f"/static/catalog_images/{clean_fname}")

            if not name or name in ["New Item", "New Product", "Naya Item"]:
                try:
                    from google import genai
                    from google.genai import types
                    from app.core.config import settings
                    client = genai.Client(api_key=settings.GEMINI_API_KEY)
                    resp = await client.aio.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=[
                            types.Part.from_bytes(data=base64.b64decode(img_b64), mime_type="image/jpeg"),
                            types.Part.from_text(text="Identify this exact firearm model from the image. Return strict JSON with keys: name (e.g. Glock 19 Gen 4), category (Pistols/Rifles/Shotguns), origin (e.g. Austria), caliber (e.g. 9mm).")
                        ],
                        config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
                    )
                    v_data = json.loads(resp.text or "{}")
                    if v_data.get("name"):
                        name = str(v_data["name"]).title()
                        category = v_data.get("category") or category
                        origin = v_data.get("origin") or origin
                        caliber = v_data.get("caliber") or caliber
                except Exception as v_err:
                    logger.warning("[Node:handle_owner_add_product] Vision identification error: %s", v_err)
        except Exception as e:
            logger.warning("[Node:handle_owner_add_product] Image saving error: %s", e)

    name_str = str(name or "")
    category = category or ("Rifles" if "rifle" in name_str.lower() else ("Shotguns" if "shotgun" in name_str.lower() else "Pistols"))
    cat_prefix = "RIF" if category == "Rifles" else ("SHG" if category == "Shotguns" else "PST")
    sku = prev_staged.get("sku") or f"HA-{cat_prefix}-{uuid.uuid4().hex[:4].upper()}"
    desc = data.get("description") or prev_staged.get("description") or f"{origin} {caliber} {action} {capacity}"

    staged = {
        "name": name,
        "category": category,
        "origin": origin,
        "caliber": caliber,
        "capacity": capacity,
        "action": action,
        "price": price,
        "description": desc,
        "images": images,
        "sku": sku,
    }

    # 3. If price or name missing, generate natural grounded prompt
    if not name or name in ["New Item", "New Product", "Naya Item"]:
        fallback = "Jee Haider bhai! Naya firearm add karne ke liye model name aur price batayein (jaise: 'CZ Bren 2 .223 semi-auto price 950k') ya photo bhej dein."
        reply = await _generate_grounded_owner_reply(
            scenario="Owner wants to add a product but model name is missing.",
            raw_message=raw_msg,
            fallback=fallback,
        )
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "product_pending_state": "AWAITING_DETAILS",
            "product_pending_item": staged,
        }

    if price <= 0:
        fallback = f"Haider bhai, {name} ({origin} {caliber}) ki price batayein (jaise: '450k' ya 'price 450000') taake catalog mein add kar doon."
        reply = await _generate_grounded_owner_reply(
            scenario=f"Name ({name}) and specs known, need price to add item to catalog.",
            raw_message=raw_msg,
            context_details={"name": name, "origin": origin, "caliber": caliber},
            fallback=fallback,
        )
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "product_pending_state": "AWAITING_PRICE",
            "product_pending_item": staged,
        }

    # 4. Both available — formatted confirmation
    reply = (
        f"Confirm: Naya Item Catalog mein Add kar doon?\n\n"
        f"• Name: {name}\n"
        f"• Category: {category}\n"
        f"• Origin: {origin}\n"
        f"• Caliber: {caliber}\n"
        f"• Price: PKR {int(price):,}\n"
        f"• SKU: {sku}\n\n"
        f"Haan / cancel"
    )

    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "product_pending_state": "AWAITING_CONFIRMATION",
        "product_pending_item": staged,
    }


# --------------------------------------------------------------------------
# Node: handle_confirmation
# --------------------------------------------------------------------------
async def handle_confirmation(state: RabtaGraphState) -> RabtaGraphState:
    from app.db.session import AsyncSessionLocal
    from app.db.repositories import catalog_repo, price_log_repo

    msg = state.get("raw_message", "").lower().strip()
    YES_WORDS = {"haan", "yes", "confirm", "theek hai", "ok", "kardo", "krdo", "done", "jee", "add karo", "add kardo"}
    NO_WORDS = {"no", "nahi", "cancel", "mat karo", "stop"}

    is_yes = any(w in msg for w in YES_WORDS)
    is_no = any(w in msg for w in NO_WORDS)

    # 1. Product addition confirmation flow
    if state.get("product_pending_state") == "AWAITING_CONFIRMATION":
        if is_no or (not is_yes):
            reply = "Cancel kar diya. Item catalog mein add nahi hua." if is_no else "Please 'haan' ya 'cancel' reply karein."
            return {
                **state,
                "reply_text": reply, "reply_chunks": [reply],
                "product_pending_state": None if is_no else state.get("product_pending_state"),
                "product_pending_item": None if is_no else state.get("product_pending_item"),
            }

        staged = state.get("product_pending_item") or {}
        try:
            tenant_id = uuid.UUID(state.get("tenant_id", ""))
        except (ValueError, KeyError):
            reply = "Bhai system error — tenant ID mismatch."
            return {**state, "reply_text": reply, "reply_chunks": [reply]}

        async with AsyncSessionLocal() as session:
            new_item = await catalog_repo.add_catalog_item(
                session=session,
                tenant_id=tenant_id,
                name=staged.get("name", "New Item"),
                price=float(staged.get("price", 0.0)),
                description=staged.get("description"),
                category=staged.get("category"),
                images=staged.get("images") or [],
                metadata_json={
                    "origin": staged.get("origin"),
                    "caliber": staged.get("caliber"),
                    "capacity": staged.get("capacity"),
                    "action": staged.get("action"),
                    "sku": staged.get("sku"),
                }
            )

        from app.api.gateway_bridge import invalidate_catalog_cache
        from app.graph.nodes import nlu
        invalidate_catalog_cache(str(tenant_id))
        nlu._catalog_cache_ts = 0.0
        await nlu._refresh_catalog_cache_if_needed()

        reply = f"Done bhai! {staged.get('name')} catalog mein add ho gaya hai (PKR {int(staged.get('price', 0)):,}) aur ab customer chats mein live hai."
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "product_pending_state": None,
            "product_pending_item": None,
        }

    # 2. Price update confirmation flow
    snap = state.get("price_pending_selected") or {}
    new_price = state.get("price_pending_proposed", 0.0)

    if is_no or (not is_yes):
        reply = "Cancel kar diya." if is_no else "Please 'haan' ya 'cancel' reply karein."
        return {
            **state,
            "reply_text": reply, "reply_chunks": [reply],
            "price_pending_state": None if is_no else state.get("price_pending_state"),
        }

    try:
        item_id = uuid.UUID(snap["id"])
        tenant_id = uuid.UUID(state.get("tenant_id", ""))
    except (ValueError, KeyError):
        reply = "Bhai system error — ID mismatch. Dobara try karein."
        return {**state, "reply_text": reply, "reply_chunks": [reply]}

    async with AsyncSessionLocal() as session:
        item = await catalog_repo.get_item_by_id(session, item_id)
        if not item:
            return {**state, "reply_text": "Item nahi mila DB mein.", "reply_chunks": ["Item nahi mila DB mein."]}
        item.price = new_price

        from app.models.database import PriceChangeLog
        from datetime import datetime
        log_entry = PriceChangeLog(
            tenant_id=tenant_id,
            catalog_item_id=item_id,
            item_name=snap.get("name", ""),
            old_price=snap.get("price", 0),
            new_price=new_price,
            changed_by_phone=state.get("sender_phone", ""),
            confirmed_at=datetime.utcnow(),
            metadata_json=snap.get("metadata_json", {}),
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(item)

    from app.api.gateway_bridge import invalidate_catalog_cache
    invalidate_catalog_cache(str(tenant_id))

    org_str = f" ({snap['origin']})" if snap.get("origin") else ""
    reply = f"Updated bhai. {snap['name']}{org_str} ab PKR {int(new_price):,} ho gaya."

    return {
        **state,
        "reply_text": reply, "reply_chunks": [reply],
        "price_pending_state": None,
        "price_pending_matches": None,
        "price_pending_proposed": None,
        "price_pending_selected": None,
    }


# --------------------------------------------------------------------------
# Node: relay_owner_answer (LLM Sanitization & Private-Note Separation)
# --------------------------------------------------------------------------
async def relay_owner_answer(state: RabtaGraphState) -> RabtaGraphState:
    """Relays owner answer to pending customer inquiry with LLM private-note filtering."""
    msg = state.get("raw_message", "")

    try:
        tenant_id = uuid.UUID(state.get("tenant_id", ""))
    except (ValueError, AttributeError):
        return {**state, "reply_text": "Jee bhai note kar liya.", "reply_chunks": ["Jee bhai note kar liya."]}

    target_esc, clean_answer = _esc_service.find_target_escalation(tenant_id, msg)
    if not target_esc:
        return {**state, "reply_text": "Jee bhai note kar liya.", "reply_chunks": ["Jee bhai note kar liya."]}

    # LLM Sanitizer: Distinguish private notes to the AI from customer-facing answers
    from google import genai
    from google.genai import types
    from app.core.config import settings
    client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    final_customer_msg = clean_answer
    owner_confirm = "Done bhai. Customer ko convey kar diya."

    if client:
        prompt = f"""You are a WhatsApp relay cleaner for a firearms store.
The store owner (Haider bhai) is answering an escalated customer question:
Customer Question: "{target_esc.customer_question}"
Product Context: "{target_esc.product_context or 'Firearm'}"
Owner's incoming message: "{msg}"

Task:
1. Extract the actual answer/price/details meant for the customer (in polite Pakistani Roman Urdu).
2. Filter out any internal instructions to the AI or personal side-notes (e.g. "customer ko bolo...", "ye rate batao aur mere liye ek box rakhna", etc.).
3. Generate a concise confirmation for the owner.

Return STRICT JSON only:
{{"customer_reply": string, "owner_confirmation": string}}"""

        try:
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
            )
            data = json.loads((resp.text or "").strip())
            if data.get("customer_reply"):
                final_customer_msg = data["customer_reply"]
            if data.get("owner_confirmation"):
                owner_confirm = data["owner_confirmation"]
        except Exception as err:
            logger.warning("[Relay:LLM] Sanitization error: %s", err)

    resolved = _esc_service.resolve_escalation(target_esc.escalation_id, final_customer_msg)
    if not resolved:
        return {**state, "reply_text": "Jee bhai note kar liya.", "reply_chunks": ["Jee bhai note kar liya."]}

    logger.info(
        "[Node:relay_owner_answer] ESC=%s customer=%s answer=%s",
        resolved.escalation_id, resolved.customer_phone, final_customer_msg[:40],
    )

    return {
        **state,
        "reply_text": owner_confirm,
        "reply_chunks": [owner_confirm],
        "forward_to_customer": resolved.customer_phone,
        "forward_message": final_customer_msg,
        "owner_alert": None,
        "escalation_resolved_for": resolved.customer_phone,
        "escalation_resolved_id": resolved.escalation_id,
    }


# --------------------------------------------------------------------------
# Node: handle_owner_greeting
# --------------------------------------------------------------------------
async def handle_owner_greeting(state: RabtaGraphState) -> RabtaGraphState:
    fallback = "Jee Haider bhai, salam! Batayein koi update ya price change karni hai?"
    reply = await _generate_grounded_owner_reply(
        scenario="Owner greeted the assistant.",
        raw_message=state.get("raw_message", ""),
        fallback=fallback,
    )
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


def _smart_match_catalog_products(text: str, catalog_items: list, history: list = None) -> list:
    """
    Match products in catalog given user text.
    Handles:
    - Full contiguous name matches (e.g. "Taurus G3 Tactical", "Taurus G3")
    - Brand-shared multi-model matches (e.g. "Taurus G3 and G3C and G3 Tactical")
    - Model-only mentions (e.g. "G3 Tactical", "G3C", "G3", "PT92")
    - Conversation history context (e.g. "pic or specs" preceded by "taurus G3")
    - Brand-only mentions (e.g. "taurus", "glock") -> returns all variants of that brand
    Returns list of CatalogItem instances in order of specificity.
    """
    t = (text or "").lower()
    matched = []
    seen_ids = set()

    def add_match(item):
        if item.id not in seen_ids:
            matched.append(item)
            seen_ids.add(item.id)

    # 1. Direct full name match (longest first)
    for item in sorted(catalog_items, key=lambda x: len(x.name), reverse=True):
        pat = re.escape(item.name.lower())
        if re.search(r'\b' + pat + r'\b', t):
            add_match(item)

    # 2. Brand-context matching: if brand is present, check sub-models
    brands = {}
    for item in catalog_items:
        brand = item.name.split()[0].lower()
        brands.setdefault(brand, []).append(item)

    for brand, b_items in brands.items():
        if re.search(r'\b' + re.escape(brand) + r'\b', t):
            for item in sorted(b_items, key=lambda x: len(x.name), reverse=True):
                model_part = item.name[len(brand):].strip().lower()
                if model_part and re.search(r'\b' + re.escape(model_part) + r'\b', t):
                    add_match(item)

    # 3. Model-only matching without brand (e.g. 'g3 tactical', 'g3c', 'pt92', 'tp9')
    if not matched:
        for item in sorted(catalog_items, key=lambda x: len(x.name), reverse=True):
            parts = item.name.split()
            if len(parts) > 1:
                model_part = " ".join(parts[1:]).lower()
                if len(model_part) >= 2 and re.search(r'\b' + re.escape(model_part) + r'\b', t):
                    add_match(item)

    # 4. History fallback: if no product matched in current turn, check conversation history
    if not matched and history:
        for turn in reversed(history):
            h_text = turn.get("text", "")
            if h_text and h_text != text:
                h_matched = _smart_match_catalog_products(h_text, catalog_items, history=None)
                if h_matched:
                    return h_matched

    # 5. Brand-only match: if user only said 'taurus', return all taurus items
    if not matched:
        for brand, b_items in brands.items():
            if re.search(r'\b' + re.escape(brand) + r'\b', t):
                for item in b_items:
                    add_match(item)

    return matched


# --------------------------------------------------------------------------
# Node: handle_owner_info_request
# --------------------------------------------------------------------------
async def handle_owner_info_request(state: RabtaGraphState) -> RabtaGraphState:
    from app.db.session import AsyncSessionLocal
    from app.models.database import CatalogItem
    from sqlalchemy import select

    try:
        tenant_id = uuid.UUID(state.get("tenant_id", ""))
    except (ValueError, AttributeError):
        tenant_id = uuid.uuid4()

    raw_msg = state.get("raw_message", "")
    history = state.get("conversation_history") or []
    media_url = None

    try:
        async with AsyncSessionLocal() as session:
            q = select(CatalogItem).where(CatalogItem.tenant_id == tenant_id)
            res = await session.execute(q)
            all_items = list(res.scalars().all())
    except Exception as db_err:
        logger.warning("[Node:handle_owner_info_request] DB load failed: %s", db_err)
        all_items = []

    matched_items = _smart_match_catalog_products(raw_msg, all_items, history=history)

    if matched_items:
        if len(matched_items) > 1:
            # Multiple items matched (e.g. multi-product price inquiry or brand list)
            lines = ["Haider bhai, catalog ke mutabiq details yeh hain:"]
            for it in matched_items:
                stk = "In stock" if it.in_stock else "Out of stock"
                lines.append(f"• {it.name}: PKR {int(it.price):,} ({stk})")
            reply = "\n".join(lines)
        else:
            # Single exact item matched
            it = matched_items[0]
            imgs = it.images or []
            if imgs:
                raw_img = imgs[0]
                media_url = f"http://65.20.90.130{raw_img}" if raw_img.startswith("/") else raw_img

            meta = it.metadata_json or {}
            specs_parts = []
            if meta.get("origin"):
                specs_parts.append(str(meta["origin"]))
            if meta.get("caliber"):
                specs_parts.append(str(meta["caliber"]))
            if meta.get("action"):
                specs_parts.append(str(meta["action"]))
            if meta.get("capacity"):
                specs_parts.append(str(meta["capacity"]))
            specs_str = f"\nSpecs: {' | '.join(specs_parts)}" if specs_parts else (f"\nDetails: {it.description}" if it.description else "")

            stk = "In stock" if it.in_stock else "Out of stock"
            has_photo_str = " aur tasweer bhej raha hoon" if media_url else ""
            reply = f"Jee Haider bhai, {it.name} stock mein available hai ({stk}), price PKR {int(it.price):,}{has_photo_str}.{specs_str}"
    else:
        pending_escs = _esc_service.get_pending_for_tenant(tenant_id)
        if pending_escs:
            esc = pending_escs[-1]
            prod_desc = f" ({esc.product_context})" if esc.product_context else ""
            reply = (
                f"Bhai open inquiry {esc.customer_phone} se hai{prod_desc}.\n"
                f"Customer ne poochha: \"{esc.customer_question}\"\n"
                f"Aap jo answer likhein ge wo customer ko relay ho jaye ga."
            )
        else:
            fallback = "Haider bhai, batayein kis firearm ya catalog item ki details ya photo chahiye?"
            reply = await _generate_grounded_owner_reply(
                scenario="Owner asked general info query without naming a specific product or active escalation.",
                raw_message=raw_msg,
                fallback=fallback,
            )

    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": media_url,
        "media_urls": None,
        "owner_alert": None,
        "forward_to_customer": None,
        "forward_message": None,
    }


# --------------------------------------------------------------------------
# Node: handle_owner_inquiry_clarification
# --------------------------------------------------------------------------
async def handle_owner_inquiry_clarification(state: RabtaGraphState) -> RabtaGraphState:
    """Owner asked a clarifying question about an active escalation."""
    tenant_id_str = state.get("tenant_id", "")
    try:
        tenant_id = uuid.UUID(tenant_id_str)
        pending_escs = _esc_service.get_pending_for_tenant(tenant_id)
    except (ValueError, AttributeError):
        pending_escs = []

    if not pending_escs:
        fallback = "Bhai abhi koi pending customer inquiry nahi hai."
        reply = await _generate_grounded_owner_reply(
            scenario="Owner asking about inquiries, but none are currently pending.",
            raw_message=state.get("raw_message", ""),
            fallback=fallback,
        )
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

    latest_esc = pending_escs[-1]
    cust_phone = str(latest_esc.customer_phone or "").strip()
    digits = re.sub(r'[^\d]', '', cust_phone)
    if digits.startswith("92") and len(digits) == 12:
        phone_display = f"+92 {digits[2:5]} {digits[5:]}"
    elif digits.startswith("03") and len(digits) == 11:
        phone_display = f"+92 {digits[1:4]} {digits[4:]}"
    elif digits:
        phone_display = f"+{digits}"
    else:
        phone_display = cust_phone

    cust_name = latest_esc.customer_name or ""
    product = latest_esc.product_context or "firearm"
    question = latest_esc.customer_question
    snippet = latest_esc.conversation_snippet or []

    # Format dialogue turns
    dialogue_lines = []
    for turn in snippet:
        speaker = "Customer" if turn.get("role") == "customer" else "Store AI"
        text = turn.get("text", "").strip()
        dialogue_lines.append(f"{speaker}: {text}")
    formatted_transcript = "\n".join(dialogue_lines) if dialogue_lines else f"Customer: {question}"

    fallback = (
        f"Haider bhai, customer {cust_name} ({phone_display}) ne {product} ke baray mein poochha tha: \"{question}\". "
        f"Aap jo rate ya discount batayein ge main customer ko relay kar doonga."
    )

    scenario_context = (
        f"Owner (Haider bhai) is asking a question about a pending customer inquiry.\n"
        f"Customer: {cust_name or 'Buyer'} ({phone_display})\n"
        f"Product Inquired: {product}\n"
        f"Customer's Inquiry: '{question}'\n\n"
        f"=== ACTUAL STORE CHAT TRANSCRIPT WITH CUSTOMER ===\n"
        f"{formatted_transcript}\n"
        f"==================================================\n"
        f"TASK:\n"
        f"Answer Haider bhai's exact question accurately using the chat transcript above.\n"
        f"- If he asks what price was quoted ('apne kia price dia / bataya'), state the exact PKR price told to the customer.\n"
        f"- If he asks which 3 guns/weapons were discussed ('kin teeno me / konse models'), list the exact models shown in the transcript.\n"
        f"- If he asks whether you gave a discount ('apne discount dia'), clarify that you told the customer you'd confirm with shop management.\n"
        f"Keep the reply concise, natural, and helpful in polite Pakistani Roman Urdu."
    )

    reply = await _generate_grounded_owner_reply(
        scenario=scenario_context,
        raw_message=state.get("raw_message", ""),
        fallback=fallback,
    )
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
# Node: owner_fallback (Driven by Rabta Owner Intelligence Agent v2.0)
# --------------------------------------------------------------------------
async def owner_fallback(state: RabtaGraphState) -> RabtaGraphState:
    """Natural language interpretation of owner messages via Rabta Owner Intelligence Brain."""
    from app.db.session import AsyncSessionLocal
    from app.services.owner_copilot import OwnerCopilotService
    copilot = OwnerCopilotService()
    tenant_id_str = state.get("tenant_id", "")
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, AttributeError):
        tenant_id = uuid.uuid4()

    async def _invalidate():
        from app.api.gateway_bridge import invalidate_catalog_cache
        invalidate_catalog_cache(tenant_id_str)

    async with AsyncSessionLocal() as session:
        res = await copilot.handle_owner_natural_message(
            session=session,
            tenant_id=tenant_id,
            owner_phone=state.get("sender_phone", ""),
            message_text=state.get("raw_message", ""),
            conversation_history=state.get("conversation_history") or [],
            image_base64=state.get("image_base64"),
            on_cache_invalidate=_invalidate,
        )

    reply = res.get("message") or "Jee Haider bhai, hukum karein. Sab update hai."
    media_url = res.get("media_url")
    forward_to_customer = res.get("forward_to_customer")
    forward_message = res.get("forward_message")

    return {
        **state,
        "reply_text": reply,
        "reply_chunks": [reply],
        "media_url": media_url,
        "media_urls": [media_url] if media_url else None,
        "owner_alert": None,
        "forward_to_customer": forward_to_customer,
        "forward_message": forward_message,
    }

