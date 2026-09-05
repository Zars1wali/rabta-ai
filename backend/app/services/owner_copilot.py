import re
import uuid
import logging
import json
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from google import genai
from google.genai import types
from app.core.config import settings
from app.services.price_update_service import PriceUpdateService
from app.services.escalation_service import EscalationService, EscalationRecord
from app.db.repositories import tenant_repo, price_log_repo, catalog_repo
from app.models.database import Tenant, CatalogItem
from app.brain.prompts_owner import (
    OWNER_INTELLIGENCE_SYSTEM_PROMPT,
    build_owner_inquiry_alert,
)

logger = logging.getLogger(__name__)


class OwnerCopilotService:
    """
    RABTA OWNER INTELLIGENCE AGENT (VERSION 2.0 — PRODUCTION READY)
    The Human-Like Owner Communication & Business Knowledge Engine.
    Acts as the intelligent employee bridge between Rabta sales engine and Shahzad Haider Bhai.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        self.price_service = PriceUpdateService()
        # Section 15 Timing: Inquiries 30m / 60m
        self.escalation_service = EscalationService(
            reminder1_secs=1800.0,  # 30 minutes
            reminder2_secs=3600.0,  # 60 minutes
            timeout_secs=7200.0,
        )

    def is_owner_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    async def handle_command(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        command_text: str,
        business_name: str,
        active_customer: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handles optional slash commands as quick shortcuts."""
        cmd_parts = command_text.strip().split()
        main_cmd = cmd_parts[0].lower()

        if main_cmd == "/help":
            return {
                "action": "reply_owner",
                "message": "Bhai aap mujhse natural baat kar sakte hain (jaise 'Glock 19 is 485', 'sold out', 'push this one'). Commands: /status, /pause [number], /resume [number], /prices."
            }

        elif main_cmd == "/pause":
            target_phone = cmd_parts[1] if len(cmd_parts) > 1 else active_customer
            if not target_phone:
                return {
                    "action": "reply_owner",
                    "message": "Bhai customer number batayein: /pause 03001234567",
                }
            return {
                "action": "pause_ai",
                "customer_phone": target_phone,
                "message": f"AI paused for {target_phone}. Aap directly baat karein, finish hone par /resume likhein.",
            }

        elif main_cmd == "/resume":
            target_phone = cmd_parts[1] if len(cmd_parts) > 1 else active_customer
            return {
                "action": "resume_ai",
                "customer_phone": target_phone,
                "message": f"AI resumed for {target_phone or 'all'}.",
            }

        elif main_cmd == "/status":
            pending_esc = self.escalation_service.get_pending_for_tenant(tenant_id)
            if pending_esc:
                esc_desc = ", ".join([f"{e.customer_phone}: {e.customer_question[:30]}" for e in pending_esc])
                return {
                    "action": "reply_owner",
                    "message": f"AI active hai. Open inquiries ({len(pending_esc)}): {esc_desc}",
                }
            return {
                "action": "reply_owner",
                "message": "Sab clear hai bhai, koi pending inquiry nahi hai.",
            }

        elif main_cmd == "/prices":
            history = await price_log_repo.get_price_history(session, tenant_id, limit=5)
            if not history:
                return {
                    "action": "reply_owner",
                    "message": "Bhai koi recent price updates nahi hain.",
                }
            lines = ["Recent price changes:"]
            for h in history:
                t_str = h.confirmed_at.strftime("%d %b %H:%M")
                lines.append(f"{h.item_name}: PKR {int(h.new_price):,} ({t_str})")
            return {
                "action": "reply_owner",
                "message": "\n".join(lines),
            }

        return {
            "action": "reply_owner",
            "message": "Bhai command samajh nahi aayi. Natural batayein kya update karna hai.",
        }

    async def handle_owner_natural_message(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        owner_phone: str,
        message_text: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        image_base64: Optional[str] = None,
        on_cache_invalidate: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Master Owner Intelligence Agent (Version 2.0).
        Cognitive business partner for Shahzad Haider Bhai with full context,
        free thoughts, natural Urdu-English fluency, and reliable action execution.
        """
        msg_clean = message_text.strip()
        open_inquiries = self.escalation_service.get_pending_for_tenant(tenant_id)
        items = await catalog_repo.get_catalog_for_tenant(session, tenant_id)

        # 1. Fetch store status & preferences
        stmt_t = select(Tenant).where(Tenant.id == tenant_id)
        res_t = await session.execute(stmt_t)
        tenant_obj = res_t.scalar_one_or_none()
        cfg = dict(tenant_obj.ai_persona_config or {}) if tenant_obj else {}

        # 2. Build live catalog context
        catalog_lines = []
        for it in items:
            stk = "In stock" if it.in_stock else "Sold out"
            meta = it.metadata_json or {}
            specs = []
            if meta.get("origin"): specs.append(str(meta["origin"]))
            if meta.get("caliber"): specs.append(str(meta["caliber"]))
            if meta.get("action"): specs.append(str(meta["action"]))
            if meta.get("capacity"): specs.append(f"{meta['capacity']} rds")
            specs_str = " | ".join(specs) if specs else (it.description or "Standard")
            has_pic = "Has photo" if it.images else "No photo"
            catalog_lines.append(f"- {it.name} | PKR {int(it.price):,} | {stk} | {specs_str} | {has_pic}")
        catalog_text = "\n".join(catalog_lines)

        # 3. Build active inquiries context
        inquiries_lines = []
        for e in open_inquiries:
            inquiries_lines.append(
                f"- ESC-{str(e.escalation_id)[:8]}: Customer {e.customer_name or 'Buyer'} ({e.customer_phone}) | Product: {e.product_context or 'Firearm'} | Question: \"{e.customer_question}\""
            )
        inquiries_text = "\n".join(inquiries_lines) if inquiries_lines else "None. All customer queries are currently resolved."

        # 4. Build store status context
        status_lines = [
            f"- AI Status: {'PAUSED for all' if tenant_obj and tenant_obj.is_ai_paused else ('PAUSED for ' + tenant_obj.active_takeover_customer_phone if tenant_obj and tenant_obj.active_takeover_customer_phone else 'ACTIVE')}",
            f"- Today Prices Confirmed: {'YES' if cfg.get('prices_confirmed_today') else 'NO'}",
        ]
        preferred = cfg.get("owner_preferred_products", {})
        if preferred:
            pref_strs = [f"{p} ({d.get('reason', 'Margin push')})" for p, d in preferred.items()]
            status_lines.append(f"- Active Push/Margin Priorities: {', '.join(pref_strs)}")
        status_text = "\n".join(status_lines)

        # 5. Build recent conversation history
        hist_turns = []
        for h in (conversation_history or [])[-8:]:
            spk = "Haider bhai" if h.get("role") in ("customer", "owner", "user") else "Assistant"
            hist_turns.append(f"{spk}: {h.get('text', '')}")
        hist_text = "\n".join(hist_turns) if hist_turns else "None (start of session)."

        # 6. Master Cognitive Prompt for Owner Intelligence Agent
        prompt = f"""You are the Owner Intelligence Agent for Haider Arms (Peshawar, Pakistan).
You are the personal AI executive assistant, store manager, and inventory copilot for Shahzad Haider Bhai (the store owner) on WhatsApp.
You function like an exceptionally capable, respectful, sharp employee texting your boss:
- Tone: Highly intelligent, capable, respectful, conversational, and loyal. Address him as "Jee Haider bhai", "Done bhai", "Theek hai bhai".
- Language: Natural Pakistani Roman Urdu mixed with clear English firearm/business terms.
- Cognitive Freedom: You have free thoughts and true business intelligence. You understand guns, pricing, customer negotiation, stock availability, and shop operations deeply.
- Zero robotic templates, zero markdown asterisks (*), zero emojis.
- Never make hollow promises like "main check karke batata hoon". You have the full live catalog and store data below, so answer directly with actual facts.

=== LIVE INVENTORY CATALOG ===
{catalog_text}

=== ACTIVE CUSTOMER INQUIRIES / ESCALATIONS ===
{inquiries_text}

=== STORE & SYSTEM STATUS ===
{status_text}

=== RECENT CONVERSATION HISTORY WITH HAIDER BHAI ===
{hist_text}

=== HAIDER BHAI'S LATEST MESSAGE ===
"{msg_clean}"

═══════════════════════════════════════════════════════
DECIDE AND RESPOND:
Analyze Haider bhai's message in context of the conversation and store state.
Determine if any operational action is needed:
1. "SEND_PHOTO": Owner asks for photo/pic of a product (e.g. "taurus g3 ki pic dekhana", "photo bhejo").
   Provide product_name.
2. "PRICE_UPDATE": Owner instructs to change or update a catalog price (e.g. "Glock 19 Gen 5 ab 490k kar do", "Taurus G3 160000").
   Provide product_name, new_price (as numeric PKR).
3. "STOCK_UPDATE": Owner updates inventory availability (e.g. "Taurus G3 sold out", "2 pieces left", "available hai").
   Provide product_name, is_in_stock (boolean).
4. "MARGIN_PREFERENCE": Owner wants to push a firearm for better margin (e.g. "Canik ko push karo acha margin hai").
   Provide product_name, preference_reason.
5. "RELAY_TO_CUSTOMER": Owner is answering an escalated customer question or giving a discount (e.g. "dedo 400 mein", "customer ko bolo 5k discount mil jayega").
   Provide target_escalation_id (or null), customer_reply (sanitized polite message for customer in Roman Urdu).
6. "PAUSE_AI": Owner wants to pause AI for a customer or store.
   Provide target_customer_phone (or null for all).
7. "RESUME_AI": Owner wants to resume AI.
   Provide target_customer_phone (or null for all).
8. "DAILY_CONFIRM": Owner confirms morning prices (e.g. "confirmed", "sab theek hai").
9. "NONE": Conversational reply, status check, price inquiry, specs inquiry, advice, greetings, discussion.

Return STRICT JSON only:
{{
  "thought": "<internal reasoning analyzing Haider bhai's intent, firearms discussed, and required action>",
  "reply": "<natural, respectful, conversational Roman Urdu response addressed to Haider bhai>",
  "action": "SEND_PHOTO" | "PRICE_UPDATE" | "STOCK_UPDATE" | "MARGIN_PREFERENCE" | "RELAY_TO_CUSTOMER" | "PAUSE_AI" | "RESUME_AI" | "DAILY_CONFIRM" | "NONE",
  "product_name": string or null,
  "new_price": number or null,
  "is_in_stock": boolean or null,
  "preference_reason": string or null,
  "customer_reply": string or null,
  "target_escalation_id": string or null,
  "target_customer_phone": string or null
}}"""

        data = {}
        if self.client:
            try:
                resp = await self.client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=450,
                        response_mime_type="application/json",
                    ),
                )
                raw = (resp.text or "").strip()
                data = json.loads(raw)
            except Exception as err:
                logger.warning("[OwnerCopilot:AGI] Generation error: %s", err)

        action = data.get("action", "NONE")
        reply_text = data.get("reply") or "Jee Haider bhai note kar liya."
        reply_text = re.sub(r'[\*\#\_`]', '', reply_text)
        reply_text = re.sub(r'[\U00010000-\U0010ffff]', '', reply_text, flags=re.UNICODE).strip()

        media_url = None
        forward_to_customer = None
        forward_message = None

        # --- ACTION 1: SEND_PHOTO ---
        if action == "SEND_PHOTO" or any(kw in msg_clean.lower() for kw in ["pic", "photo", "tasveer", "image", "tasvir"]):
            p_cand = data.get("product_name")
            matched_item = None
            if p_cand:
                for it in items:
                    if p_cand.lower() in it.name.lower():
                        matched_item = it
                        break
            if not matched_item:
                m_list = self._smart_match_catalog_products(msg_clean, items, history=conversation_history)
                if m_list:
                    matched_item = m_list[0]
            if matched_item and matched_item.images:
                raw_img = matched_item.images[0]
                media_url = f"http://65.20.90.130{raw_img}" if raw_img.startswith("/") else raw_img

        # --- ACTION 2: PRICE_UPDATE ---
        elif action == "PRICE_UPDATE":
            p_name = data.get("product_name")
            new_p = data.get("new_price")
            if p_name and new_p and float(new_p) > 0:
                matched_item = None
                for it in items:
                    if p_name.lower() in it.name.lower():
                        matched_item = it
                        break
                if matched_item:
                    from app.models.database import PriceChangeLog
                    old_p = float(matched_item.price)
                    matched_item.price = float(new_p)
                    log_entry = PriceChangeLog(
                        tenant_id=tenant_id,
                        catalog_item_id=matched_item.id,
                        item_name=matched_item.name,
                        old_price=old_p,
                        new_price=float(new_p),
                        changed_by_phone=owner_phone,
                        confirmed_at=datetime.utcnow(),
                        metadata_json=matched_item.metadata_json or {},
                    )
                    session.add(log_entry)
                    await session.commit()
                    if on_cache_invalidate:
                        await on_cache_invalidate()

        # --- ACTION 3: STOCK_UPDATE ---
        elif action == "STOCK_UPDATE":
            p_name = data.get("product_name")
            is_stk = data.get("is_in_stock", False)
            if p_name:
                for it in items:
                    if p_name.lower() in it.name.lower():
                        it.in_stock = bool(is_stk)
                        await session.commit()
                        if on_cache_invalidate:
                            await on_cache_invalidate()
                        break

        # --- ACTION 4: MARGIN_PREFERENCE ---
        elif action == "MARGIN_PREFERENCE":
            p_name = data.get("product_name") or "preferred item"
            reason = data.get("preference_reason") or msg_clean
            if tenant_obj:
                prefs = dict(cfg.get("owner_preferred_products", {}))
                prefs[p_name] = {
                    "type": "margin",
                    "reason": reason,
                    "date_set": datetime.utcnow().isoformat(),
                }
                cfg["owner_preferred_products"] = prefs
                tenant_obj.ai_persona_config = cfg
                await session.commit()

        # --- ACTION 5: RELAY_TO_CUSTOMER ---
        elif action == "RELAY_TO_CUSTOMER":
            clean_ans = data.get("customer_reply") or msg_clean
            target_esc = None
            t_id = data.get("target_escalation_id")
            if t_id:
                for e in open_inquiries:
                    if t_id in str(e.escalation_id):
                        target_esc = e
                        break
            if not target_esc and open_inquiries:
                target_esc = open_inquiries[0]
            if target_esc:
                resolved = self.escalation_service.resolve_escalation(target_esc.escalation_id, clean_ans)
                if resolved:
                    forward_to_customer = resolved.customer_phone
                    forward_message = clean_ans

        # --- ACTION 6: PAUSE_AI ---
        elif action == "PAUSE_AI":
            target_cust = data.get("target_customer_phone")
            await tenant_repo.set_human_takeover(session, tenant_id, target_cust)

        # --- ACTION 7: RESUME_AI ---
        elif action == "RESUME_AI":
            await tenant_repo.set_human_takeover(session, tenant_id, None)

        # --- ACTION 8: DAILY_CONFIRM ---
        elif action == "DAILY_CONFIRM":
            if tenant_obj:
                cfg["prices_confirmed_today"] = True
                cfg["prices_confirmed_date"] = date.today().isoformat()
                tenant_obj.ai_persona_config = cfg
                await session.commit()
                if on_cache_invalidate:
                    await on_cache_invalidate()

        return {
            "action": action,
            "message": reply_text,
            "media_url": media_url,
            "forward_to_customer": forward_to_customer,
            "forward_message": forward_message,
        }

    def format_escalation_alert(
        self,
        customer_phone: str,
        customer_question: str,
        customer_name: Optional[str] = None,
        extracted_item: Optional[str] = None,
        extracted_city: Optional[str] = None,
        customer_address: Optional[str] = None,
        inquiry_type: str = "inquiry",
    ) -> str:
        """
        Formats alert for Shahzad Haider Bhai following Section 3 of Owner Intelligence Agent.
        """
        return build_owner_inquiry_alert(
            customer_name=customer_name,
            customer_phone=customer_phone,
            product=extracted_item,
            city=extracted_city,
            address=customer_address,
            question=customer_question,
            inquiry_type=inquiry_type,
        )

    @staticmethod
    def _smart_match_catalog_products(text: str, catalog_items: list, history: list = None) -> list:
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

        # 2. Brand-context matching
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

        # 3. Model-only matching without brand
        if not matched:
            for item in sorted(catalog_items, key=lambda x: len(x.name), reverse=True):
                parts = item.name.split()
                if len(parts) > 1:
                    model_part = " ".join(parts[1:]).lower()
                    if len(model_part) >= 2 and re.search(r'\b' + re.escape(model_part) + r'\b', t):
                        add_match(item)

        # 4. History fallback
        if not matched and history:
            for turn in reversed(history):
                h_text = turn.get("text", "")
                if h_text and h_text != text:
                    h_matched = OwnerCopilotService._smart_match_catalog_products(h_text, catalog_items, history=None)
                    if h_matched:
                        return h_matched

        # 5. Brand-only fallback
        if not matched:
            for brand, b_items in brands.items():
                if re.search(r'\b' + re.escape(brand) + r'\b', t):
                    for item in b_items:
                        add_match(item)

        return matched
