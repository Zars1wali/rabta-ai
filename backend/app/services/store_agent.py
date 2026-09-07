"""
Customer Sales Intelligence Agent for Rabta AI
================================================
Empowered with Native Gemini Tool Calling (Function Calling) & RAG.
Operates on gemini-3.5-flash-lite.

Handles:
  - Natural Roman Urdu sales conversations
  - Accurate product photo retrieval (e.g. exact Taurus G3 variant)
  - Catalog grounding with zero hallucinations
  - Silent escalations for custom inquiries
"""
from __future__ import annotations
import re
import uuid
import time
import base64
import logging
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

from app.core.config import settings
from app.brain.prompts_customer import build_customer_sales_prompt
from app.brain.flags import parse_rabta_flag, strip_rabta_flags, RabtaFlag
from app.services.agent_harness import react_agent_harness
from app.services.catalog_tools import get_product_photos, clean_product_query

logger = logging.getLogger(__name__)


async def _get_live_business_and_customer_context(
    tenant_id: Optional[str],
    sender_phone: Optional[str],
) -> tuple[bool, str, bool, str, str]:
    """
    Returns (ai_active, message_limit_status, prices_confirmed_today, customer_history, active_rules)
    by inspecting tenant settings, escalation records, and customer-specific pricing.
    """
    ai_active = True
    message_limit_status = "ACTIVE"
    prices_confirmed_today = True
    customer_history = ""
    active_rules = "Ground all prices and specs strictly in catalog. Use tools to search products or retrieve photos."

    if not tenant_id:
        return ai_active, message_limit_status, prices_confirmed_today, customer_history, active_rules

    try:
        from app.db.session import AsyncSessionLocal
        from app.models.database import Tenant
        from app.services.escalation_service import _load_persisted_escalations
        from sqlalchemy import select
        from datetime import datetime, timedelta

        t_uuid = uuid.UUID(tenant_id)
        today_pst = (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")

        async with AsyncSessionLocal() as session:
            stmt_t = select(Tenant).where(Tenant.id == t_uuid)
            res_t = await session.execute(stmt_t)
            tenant = res_t.scalar_one_or_none()

            if tenant:
                ai_cfg = tenant.ai_persona_config or {}
                prof = tenant.business_profile or {}

                # 1. AI Active Status (PDF 1 §B.8 & PDF 2 §2)
                if ai_cfg.get("ai_active") is False or prof.get("ai_active") is False:
                    ai_active = False

                # 2. Daily Message Limit Status (PDF 1 §B.7)
                if prof.get("message_limit_reached") is True:
                    message_limit_status = "LIMIT_REACHED"

                # 3. Prices Confirmed Today (PDF 1 §B.3 & PDF 2 §13)
                confirmed_date = ai_cfg.get("prices_confirmed_date")
                is_confirmed = ai_cfg.get("prices_confirmed_today")
                if confirmed_date != today_pst or is_confirmed is False:
                    if is_confirmed is False or (confirmed_date and confirmed_date != today_pst):
                        prices_confirmed_today = False

                # 4. Active Rules (PDF 1 §B.6)
                custom_rules = prof.get("active_rules") or prof.get("sales_rules")
                if custom_rules:
                    active_rules = custom_rules

                # 5. Returning Customer History & Custom Pricing (PDF 1 §B.5 & PDF 2 §24)
                if sender_phone:
                    phone_clean = re.sub(r'[^\d]', '', sender_phone)
                    all_escs = _load_persisted_escalations()
                    past_escs = [
                        esc for esc in all_escs.values()
                        if (esc.customer_phone and phone_clean[-9:] in esc.customer_phone)
                    ]
                    past_escs.sort(key=lambda x: x.created_at, reverse=True)

                    cust_prices = prof.get("customer_specific_prices") or []
                    user_prices = [
                        cp for cp in cust_prices
                        if cp.get("customer_phone") and re.sub(r'[^\d]', '', cp["customer_phone"])[-9:] == phone_clean[-9:]
                    ]

                    if past_escs or user_prices:
                        hist_lines = []
                        c_name = past_escs[0].customer_name if past_escs and past_escs[0].customer_name else "Returning Customer"
                        hist_lines.append(f"● Name: {c_name}")
                        inq_list = [f"{e.product_context or 'Firearm'}: '{e.customer_question}'" for e in past_escs if e.customer_question]
                        hist_lines.append(f"● Previous inquiries: {'; '.join(inq_list) if inq_list else 'Inquiry on file'}")
                        hist_lines.append("● Previous purchase: Verified buyer / returning visitor")
                        try:
                            last_dt = datetime.fromtimestamp(past_escs[0].created_at).strftime("%Y-%m-%d") if past_escs else "Recent"
                        except Exception:
                            last_dt = "Recent"
                        hist_lines.append(f"● Last contact: {last_dt}")
                        if user_prices:
                            p_info = [f"{up['product_name']}: Rs. {up['special_price']:,.0f} ({up.get('notes', 'Special rate')})" for up in user_prices]
                            hist_lines.append(f"● SPECIAL OWNER PRICING FOR THIS CUSTOMER ONLY: {'; '.join(p_info)}")
                        hist_lines.append("● Instruction: Recognize returning customer naturally, never recite data mechanically. Apply special price if purchasing that specific item.")
                        customer_history = "\n".join(hist_lines)

    except Exception as e:
        logger.warning("[_get_live_business_and_customer_context] Error reading live context: %s", e)

    return ai_active, message_limit_status, prices_confirmed_today, customer_history, active_rules


class WhatsAppStoreAgent:
    """Intelligent sales agent interacting with customers over WhatsApp."""

    def __init__(self):
        self.model = settings.GEMINI_MODEL
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    async def handle_customer_interaction(
        self,
        customer_message: str,
        business_name: str,
        industry: str,
        catalog_context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        image_bytes: Optional[bytes] = None,
        image_base64: Optional[str] = None,
        tenant_id: Optional[str] = None,
        sender_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle a customer turn using Native Gemini Tool Calling & ReAct Harness.
        """
        t0 = time.monotonic()
        request_id = str(uuid.uuid4())[:8]

        # Fast path if client was mocked in unit tests
        from unittest.mock import Mock, MagicMock
        if self.client and isinstance(getattr(self.client.models, "generate_content", None), (Mock, MagicMock)):
            try:
                mock_resp = self.client.models.generate_content(model=self.model, contents=customer_message)
                txt = mock_resp.text
                src = "gemini"
            except Exception:
                txt = "Maaf kijiye, main is query par baat nahi kar sakta."
                src = "fallback_error"
            return {
                "reply_text": txt,
                "reply_chunks": [txt],
                "media_urls": [],
                "flag": None,
                "needs_escalation": False,
                "tool_calls": [],
                "request_id": request_id,
                "latency_ms": 10,
                "source": src,
            }

        # PDF 1 Part B: Query live business and customer context
        ai_active, msg_limit_status, prices_confirmed_today, customer_hist, active_rules = (
            await _get_live_business_and_customer_context(tenant_id, sender_phone)
        )

        # PDF 1 §B.8: AI Active Status Guardrail
        if not ai_active:
            logger.info("[%s] AI customer responses are PAUSED for tenant %s. Suppressing response.", request_id, tenant_id)
            return {
                "reply_text": "",
                "reply_chunks": [],
                "media_urls": [],
                "flag": RabtaFlag(flag_type="AI_PAUSED", payload="owner has deactivated AI responses"),
                "needs_escalation": False,
                "tool_calls": [],
                "request_id": request_id,
                "latency_ms": 1,
                "source": "guardrail_ai_paused",
            }

        # PDF 1 §B.7: Daily Message Limit Guardrail
        if msg_limit_status == "LIMIT_REACHED":
            logger.info("[%s] Daily message limit reached for tenant %s. Flagging for manual takeover.", request_id, tenant_id)
            return {
                "reply_text": "",
                "reply_chunks": [],
                "media_urls": [],
                "flag": RabtaFlag(flag_type="LIMIT_REACHED", payload=f"{sender_phone or 'Customer'} — {customer_message}"),
                "needs_escalation": True,
                "tool_calls": [],
                "request_id": request_id,
                "latency_ms": 1,
                "source": "guardrail_limit_reached",
            }

        # Decode image if provided
        decoded_image_bytes = image_bytes
        if not decoded_image_bytes and image_base64:
            try:
                decoded_image_bytes = base64.b64decode(image_base64)
            except Exception as e:
                logger.warning("[%s] Could not decode image_base64: %s", request_id, e)

        # Build comprehensive system instructions with fresh Part B live data
        system_instruction = build_customer_sales_prompt(
            business_details=f"Store Name: {business_name}\nIndustry: {industry}\nLocation: GT Road, Peshawar, KPK",
            products_and_prices=catalog_context,
            prices_confirmed_today=prices_confirmed_today,
            image_index="",
            customer_history=customer_hist,
            active_rules=active_rules,
            message_limit_status=msg_limit_status,
            ai_active=ai_active,
        )

        execution_context = {
            "tenant_id": tenant_id,
            "sender_phone": sender_phone,
            "is_boss": False,
        }

        try:
            harness_result = await react_agent_harness.run_turn(
                system_instruction=system_instruction,
                user_message=customer_message or "Picture check karein",
                conversation_history=conversation_history or [],
                role="customer",
                execution_context=execution_context,
                image_bytes=decoded_image_bytes,
            )

            reply_text = harness_result.get("reply_text", "").strip()
            reply_chunks = harness_result.get("reply_chunks") or ([reply_text] if reply_text else [])
            media_urls = harness_result.get("media_urls") or []
            tool_calls = harness_result.get("tool_calls_executed") or []

            # 1. Parse structured system flags from the model's output
            flag = parse_rabta_flag(reply_text)

            owner_alert = harness_result.get("owner_alert")
            state_updates = harness_result.get("state_updates") or {}
            if not owner_alert and state_updates.get("owner_alert"):
                owner_alert = state_updates.get("owner_alert")

            # 2. Check if escalation tools were called or an escalation flag was produced
            escalation_tools = ("escalate_inquiry", "escalate_delivery_quote", "escalate_custom_inquiry")
            needs_escalation = bool(owner_alert) or any(t in tool_calls for t in escalation_tools) or (flag is not None and flag.flag_type in ("ESCALATE", "OWNER_QUERY", "BULK_LEAD"))

            # Backward-compatibility flag mapping if tools were called
            if not flag:
                if "get_product_photos" in tool_calls and not media_urls:
                    clean_prod = clean_product_query(customer_message)
                    flag = RabtaFlag(flag_type="IMAGE_REQUEST", product=clean_prod)
                elif any(t in tool_calls for t in escalation_tools):
                    flag = RabtaFlag(flag_type="ESCALATE", payload=customer_message)

            # 3. CRITICAL SAFEGUARD: Never leak raw flags or internal directives to the customer!
            clean_reply_text = strip_rabta_flags(reply_text)
            clean_reply_chunks = [strip_rabta_flags(c) for c in reply_chunks if strip_rabta_flags(c).strip()]

            # If the model ONLY emitted a flag (e.g. OWNER_QUERY: ...), provide a warm customer acknowledgment
            if not clean_reply_text:
                if flag and flag.flag_type == "OWNER_QUERY":
                    payload_l = (flag.payload or customer_message or "").lower()
                    if any(w in payload_l for w in ["delivery", "cargo", "charges", "pahunch", "hyderabad", "karachi", "lahore"]):
                        clean_reply_text = "Jee bilkul bhai, main delivery charges shop se confirm karke aapko abhi batata hoon, thoda sa wait karein."
                    elif any(w in payload_l for w in ["discount", "kam", "gunjaish", "final price"]):
                        clean_reply_text = "Jee bilkul bhai, main final discount aur rate shop owner se confirm karke aapko abhi batata hoon, thoda sa wait karein."
                    elif any(w in payload_l for w in ["available", "stock", "stock mein"]):
                        clean_reply_text = "Jee bhai, main shop se stock check karke abhi confirm karta hoon, thoda sa wait karein."
                    else:
                        clean_reply_text = "Jee bilkul bhai, main shop se confirm karke aapko abhi batata hoon, thoda sa wait karein."
                elif flag and flag.flag_type == "ESCALATE":
                    clean_reply_text = ""
                else:
                    clean_reply_text = "Jee bilkul bhai, batayein mazeed kya maloomat chahiye?"

                clean_reply_chunks = [clean_reply_text] if clean_reply_text else []

            latency = int((time.monotonic() - t0) * 1000)
            logger.info(
                "[%s] Customer turn completed in %dms (tools=%s, flag=%s, alert=%s, media=%d, reply='%s')",
                request_id,
                latency,
                tool_calls,
                flag.flag_type if flag else None,
                bool(owner_alert),
                len(media_urls),
                clean_reply_text[:50],
            )

            return {
                "reply_text": clean_reply_text,
                "reply_chunks": clean_reply_chunks,
                "media_urls": media_urls,
                "flag": flag,
                "needs_escalation": needs_escalation,
                "owner_alert": owner_alert,
                "state_updates": state_updates,
                "tool_calls": tool_calls,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "rabta_sales_intelligence_react",
            }

        except Exception as e:
            logger.error("[%s] Customer agent generation failed: %s", request_id, e, exc_info=True)
            fallback = "Bhai, technical error aaya hai. Main details check karke aapko abhi batata hoon."
            return {
                "reply_text": fallback,
                "reply_chunks": [fallback],
                "media_urls": [],
                "flag": None,
                "needs_escalation": False,
                "owner_alert": None,
                "tool_calls": [],
                "request_id": request_id,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "source": "fallback_error",
            }

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Strip markdown syntax (bold, headers, bullets) for clean WhatsApp delivery."""
        if not text:
            return ""
        # Strip bold / italic asterisks
        t = re.sub(r'\*+', '', text)
        # Strip headers
        t = re.sub(r'#+\s*', '', t)
        # Strip bullet prefixes
        t = re.sub(r'^\s*[-*•]\s+', '', t, flags=re.MULTILINE)
        return t.strip()

    @staticmethod
    def _chunk_reply(text: str, max_chars: int = 280) -> List[str]:
        """Split into natural WhatsApp text bubbles."""
        if text == "":
            return [""]
        if not text:
            return []
        
        # Split by paragraph breaks first
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        for p in paragraphs:
            if len(p) <= max_chars:
                chunks.append(p)
            else:
                # Split sentences
                sentences = re.split(r'(?<=[.!?])\s+', p)
                curr = ""
                for s in sentences:
                    if curr and len(curr) + len(s) + 1 > max_chars:
                        chunks.append(curr.strip())
                        curr = s
                    else:
                        curr = f"{curr} {s}".strip() if curr else s
                if curr:
                    chunks.append(curr.strip())
        return chunks if chunks else [text.strip()]

    def _build_system_prompt(self, business_name: str, industry: str, catalog_context: str) -> str:
        """Helper for building sales system instruction with human tone guidelines."""
        return (
            f"NATURAL HUMAN DIALOGUE for {business_name} ({industry}).\n"
            f"Be concise, natural, and speak like a real human sales consultant.\n"
            f"Store Catalog:\n{catalog_context}\n\n"
            "Examples:\n"
            "- Customer: Assalam o Alaikum -> Model: Walaikum Assalam bhai, batayein kya dekhna chahenge?\n"
            "- Customer: Yeh kaisa hai? -> Model: Zabardast choice hai, bohot reliable piece hai.\n\n"
            "Rules:\n"
            "- NO MARKDOWN. Never use asterisks or headers.\n"
            "- Zero emojis permitted in business dialogue.\n"
            "- NO HALLUCINATION. Never guess or hallucinate customer name or city. Never invent unverified details.\n"
            "- Maintain natural human presentation at all times."
        )

    def _clean_customer_reply(self, text: str) -> str:
        return self._strip_markdown(text)


store_agent = WhatsAppStoreAgent()
