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

    async def _understand_owner_intent_agi(
        self,
        message_text: str,
        open_inquiries: List[EscalationRecord],
    ) -> Dict[str, Any]:
        """
        Uses Gemini 3.5 Flash-Lite to understand natural owner texts:
        - daily_confirm: owner confirming today's prices
        - relay_to_customer: owner replying to an open customer inquiry
        - margin_preference: owner instructing to prioritize / push a product
        - stock_update: owner updating stock status (sold out, available count)
        - price_update: owner providing a new rate for an item
        - general_chat: conversational acknowledgment
        """
        if not self.client:
            return {"intent": "general"}

        inquiries_summary = []
        for e in open_inquiries:
            inquiries_summary.append({
                "id": str(e.escalation_id),
                "customer": e.customer_phone,
                "question": e.customer_question,
                "product": e.product_context,
            })

        prompt = f"""You are the Owner Intelligence Agent for Haider Arms (Pakistan firearms dealership).
The owner (Shahzad Haider Bhai) just sent this WhatsApp message:
"{message_text}"

Current Open Customer Inquiries waiting for owner answer:
{json.dumps(inquiries_summary, indent=2)}

Determine the owner's exact intent:
1. "daily_confirm": Owner confirming daily prices (e.g. "confirmed", "theek hai sab", "prices ok")
2. "relay_to_customer": Owner answering one of the open customer inquiries (e.g. "dedo 480 me", "1500 delivery charges", "available hai", "tell him out of stock")
3. "margin_preference": Owner setting priority/push rule (e.g. "push this one - good margin", "give priority to canik")
4. "stock_update": Owner updating inventory availability (e.g. "sold out", "2 pieces left", "we don't sell this anymore")
5. "price_update": Owner updating permanent catalog price (e.g. "Glock 19 Gen 5 is 485k", "price changed to 510")
6. "chat": General greeting or conversation

Return STRICT JSON only:
{{
  "intent": "daily_confirm" | "relay_to_customer" | "margin_preference" | "stock_update" | "price_update" | "chat",
  "target_escalation_id": string or null,
  "clean_relay_answer": string or null,
  "product_name": string or null,
  "new_price": number or null,
  "stock_count": number or null,
  "is_sold_out": boolean or null,
  "preference_reason": string or null,
  "reply_to_owner": string (short natural Pakistani Roman Urdu response like a capable employee, e.g. "Got it. Updated." or "Done bhai, customer ko convey kar diya.")
}}"""

        try:
            resp = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            raw = (resp.text or "").strip()
            return json.loads(raw)
        except Exception as err:
            logger.warning("[OwnerCopilot:AGI] Intent understanding failed: %s", err)
            return {"intent": "general"}

    async def handle_owner_natural_message(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        owner_phone: str,
        message_text: str,
        on_cache_invalidate: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Processes natural WhatsApp communication from Shahzad Haider Bhai.
        Implements Section 3, 5, 12, 13, 19 of Rabta Owner Intelligence Agent v2.0.
        """
        msg_clean = message_text.strip()
        open_inquiries = self.escalation_service.get_pending_for_tenant(tenant_id)

        # 1. Run AGI Cognitive Understanding
        intel = await self._understand_owner_intent_agi(msg_clean, open_inquiries)
        intent = intel.get("intent", "general")

        # 2. Daily Morning Price Confirmation (Section 13)
        if intent == "daily_confirm" or msg_clean.lower() in ("confirmed", "confirm", "sab theek hai", "theek hai"):
            stmt_t = select(Tenant).where(Tenant.id == tenant_id)
            res_t = await session.execute(stmt_t)
            t = res_t.scalar_one_or_none()
            if t:
                cfg = dict(t.ai_persona_config or {})
                cfg["prices_confirmed_today"] = True
                cfg["prices_confirmed_date"] = date.today().isoformat()
                t.ai_persona_config = cfg
                await session.commit()
                if on_cache_invalidate:
                    await on_cache_invalidate()
                return {
                    "action": "reply_owner",
                    "message": "Got it bhai. Aaj ke prices confirmed mark ho gaye hain. Rabta confident quote karega.",
                }

        # 3. Relay answer to open customer inquiry / escalation (Section 14 & 19)
        if intent == "relay_to_customer" or (open_inquiries and not intent == "price_update"):
            target_id_str = intel.get("target_escalation_id")
            target_esc = None
            if target_id_str:
                for e in open_inquiries:
                    if str(e.escalation_id) == target_id_str:
                        target_esc = e
                        break
            if not target_esc and open_inquiries:
                target_esc = open_inquiries[0]

            if target_esc:
                clean_ans = intel.get("clean_relay_answer") or msg_clean
                resolved = self.escalation_service.resolve_escalation(target_esc.escalation_id, clean_ans)
                if resolved:
                    reply_owner = intel.get("reply_to_owner") or "Done bhai. Customer ko convey kar diya."
                    return {
                        "action": "relay_escalation_to_customer",
                        "customer_phone": resolved.customer_phone,
                        "customer_reply": clean_ans,
                        "escalation_id": resolved.escalation_id,
                        "owner_confirmation": reply_owner,
                    }

        # 4. Margin & Owner Preference Rule (Section 5)
        if intent == "margin_preference" or "margin" in msg_clean.lower() or "push" in msg_clean.lower():
            p_name = intel.get("product_name") or "preferred firearm"
            reason = intel.get("preference_reason") or msg_clean
            stmt_t = select(Tenant).where(Tenant.id == tenant_id)
            res_t = await session.execute(stmt_t)
            t = res_t.scalar_one_or_none()
            if t:
                cfg = dict(t.ai_persona_config or {})
                prefs = dict(cfg.get("owner_preferred_products", {}))
                prefs[p_name] = {
                    "type": "margin",
                    "reason": reason,
                    "date_set": datetime.utcnow().isoformat(),
                }
                cfg["owner_preferred_products"] = prefs
                t.ai_persona_config = cfg
                await session.commit()
                return {
                    "action": "reply_owner",
                    "message": f"Got it. {p_name} priority recorded. Customer requirement match hone par Rabta lead karega.",
                }

        # 5. Stock Update (Section 17 & 19)
        if intent == "stock_update":
            p_name = intel.get("product_name")
            is_sold = intel.get("is_sold_out", False)
            if p_name:
                items = await catalog_repo.get_catalog_for_tenant(session, tenant_id)
                for it in items:
                    if p_name.lower() in it.name.lower():
                        it.in_stock = not is_sold
                        await session.commit()
                        status_str = "Sold out" if is_sold else "In stock"
                        return {
                            "action": "reply_owner",
                            "message": f"Got it. {it.name} ab {status_str} mark ho gaya.",
                        }

        # 6. Price Update (Section 12 & 16)
        price_res = await self.price_service.process_owner_price_message(
            session=session,
            tenant_id=tenant_id,
            owner_phone=owner_phone,
            message_text=message_text,
            on_cache_invalidate=on_cache_invalidate,
        )
        if price_res is not None:
            return {
                "action": "reply_owner",
                "message": price_res["reply"],
                "is_price_updated": price_res.get("is_price_updated", False),
            }

        # 7. Catalog Inquiry Grounding Fallback
        items = await catalog_repo.get_catalog_for_tenant(session, tenant_id)
        from app.graph.nodes.owner import _smart_match_catalog_products
        matched = _smart_match_catalog_products(message_text, items)
        if matched:
            if len(matched) > 1:
                lines = ["Haider bhai, catalog ke mutabiq details yeh hain:"]
                for it in matched:
                    stk = "In stock" if it.in_stock else "Out of stock"
                    lines.append(f"• {it.name}: PKR {int(it.price):,} ({stk})")
                return {"action": "reply_owner", "message": "\n".join(lines)}
            else:
                it = matched[0]
                stk = "In stock" if it.in_stock else "Out of stock"
                return {"action": "reply_owner", "message": f"Jee Haider bhai, {it.name} stock mein available hai ({stk}), price PKR {int(it.price):,} hai."}

        # 8. Fallback Human Reply
        reply_to_owner = intel.get("reply_to_owner") or "Jee bhai note kar liya."
        return {
            "action": "reply_owner",
            "message": reply_to_owner,
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
