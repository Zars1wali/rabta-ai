import re
import time
import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types
from app.core.config import settings
from app.brain.prompts_customer import build_customer_sales_prompt
from app.brain.context_builder import build_part_b_live_data
from app.brain.flags import parse_rabta_flag, RabtaFlag

logger = logging.getLogger(__name__)


class WhatsAppStoreAgent:
    """
    Enterprise sales intelligence engine for Rabta AI — Haider Arms.
    Implements Master Sales Intelligence Prompt v2.0 powered by Gemini 3.5 Flash-Lite.
    Acts as Haider Bhai (the owner's authoritative, calm voice).
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    @staticmethod
    def _clean_customer_reply(text: str) -> str:
        """Sanitizes generated text while respecting Section A.6, A.7, and A.8 tone rules."""
        if not text:
            return ""

        # Remove markdown formatting (*bold*, # headers, bullet lists)
        cleaned = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
        cleaned = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', cleaned)
        cleaned = re.sub(r'^#{1,3}\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^[-*•]\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'`{1,3}[^`]*`{1,3}', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        # Ensure no multiple exclamation marks (Confidence does not shout - Section A.8)
        cleaned = re.sub(r'!{2,}', '!', cleaned)

        return cleaned.strip()

    @staticmethod
    def _chunk_reply(text: str, max_chars: int = 300) -> List[str]:
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]

        chunks: List[str] = []
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_chars:
                current = f"{current}\n{para}" if current else para
            else:
                if current:
                    chunks.append(current)
                if len(para) <= max_chars:
                    current = para
                else:
                    sentences = re.split(r'([.!?]\s+)', para)
                    s_current = ""
                    for s in sentences:
                        if len(s_current) + len(s) <= max_chars:
                            s_current += s
                        else:
                            if s_current.strip():
                                chunks.append(s_current.strip())
                            s_current = s
                    current = s_current.strip()

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text]

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
        business_profile: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
        sender_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes Rabta AI sales dialogue turn with full Master Sales Intelligence v2.0.
        """
        request_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()

        # Build dynamic Part B context from database
        part_b_data = None
        if session and tenant_id:
            try:
                t_uuid = uuid.UUID(tenant_id)
                part_b_data = await build_part_b_live_data(session, t_uuid, customer_phone=sender_phone)
            except Exception as b_err:
                logger.warning("[%s] Could not build dynamic Part B: %s", request_id, b_err)

        if not part_b_data:
            # Fallback Part B assembly
            prof = business_profile or {}
            biz_details = (
                f"Business Name: {business_name}\n"
                f"Owner: {prof.get('owner_name', 'Shahzad Haider Bhai')}\n"
                f"Location: {prof.get('address', 'GT Road, Peshawar, KPK, Pakistan')}\n"
                f"Hours: Physical shop 10:00 AM - 7:00 PM (Mon-Sat). AI: 24/7\n"
                f"Instagram: {prof.get('instagram_url', 'https://www.instagram.com/haiderarmsofficial')}\n"
                f"YouTube: {prof.get('youtube_url', 'https://www.youtube.com/@haiderarmofficial')}"
            )
            part_b_data = {
                "business_details": biz_details,
                "products_and_prices": catalog_context or "Verified inventory available on request.",
                "prices_confirmed_today": True,
                "image_index": "",
                "customer_history": None,
                "active_rules": "Standard dealership rules active.",
                "message_limit_status": "ACTIVE",
                "ai_active": True,
            }

        # Check for technical spec queries that require spec research
        spec_context = ""
        is_spec_query = any(w in customer_message.lower() for w in ["specs", "spec", "barrel", "weight", "length", "twist", "dimension", "material"])
        if is_spec_query:
            try:
                from app.services.spec_search import search_product_specs
                from app.graph.nodes.nlu import _BRANDS, _catalog_cache, _refresh_catalog_cache_if_needed
                await _refresh_catalog_cache_if_needed()
                cand_p = None
                cm_lower = customer_message.lower()
                for p_name in sorted(_catalog_cache, key=len, reverse=True):
                    if p_name in cm_lower:
                        cand_p = p_name.title()
                        break
                if cand_p:
                    spec_context = await search_product_specs(cand_p, customer_message)
                    if spec_context:
                        part_b_data["business_details"] += f"\n\nRESEARCHED SPECS FOR {cand_p}:\n{spec_context}"
            except Exception as spec_err:
                logger.warning("[%s] Spec search error: %s", request_id, spec_err)

        system_instruction = build_customer_sales_prompt(
            business_details=part_b_data["business_details"],
            products_and_prices=part_b_data["products_and_prices"],
            prices_confirmed_today=part_b_data["prices_confirmed_today"],
            image_index=part_b_data["image_index"],
            customer_history=part_b_data["customer_history"],
            active_rules=part_b_data["active_rules"],
            message_limit_status=part_b_data["message_limit_status"],
            ai_active=part_b_data["ai_active"],
        )

        # Assemble conversation turns
        contents = []
        fresh_history = (conversation_history or [])[-8:]
        for item in fresh_history:
            role = "user" if item.get("role") in ("customer", "user") else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=item["text"])],
                )
            )

        user_text = customer_message or "Yeh pic check karein."
        user_parts = []

        if image_bytes:
            user_parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        elif image_base64:
            try:
                import base64
                decoded_bytes = base64.b64decode(image_base64)
                user_parts.append(types.Part.from_bytes(data=decoded_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning("[%s] Could not decode image_base64: %s", request_id, e)

        user_parts.append(types.Part.from_text(text=user_text))
        contents.append(types.Content(role="user", parts=user_parts))

        # Enforce alternating turns
        sanitized_contents: List[types.Content] = []
        for c in contents:
            if sanitized_contents and sanitized_contents[-1].role == c.role:
                sanitized_contents[-1].parts.extend(c.parts)
            else:
                sanitized_contents.append(c)

        while sanitized_contents and sanitized_contents[0].role != "user":
            sanitized_contents.pop(0)

        try:
            import asyncio
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=sanitized_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3,
                        max_output_tokens=300,
                    ),
                ),
                timeout=35.0,
            )

            raw_output = response.text.strip() if (response and response.text) else ""
            flag = parse_rabta_flag(raw_output)

            reply_text = ""
            reply_chunks = []
            needs_escalation = False
            image_product = None
            bulk_lead = None
            owner_query = None

            if flag:
                logger.info("[%s] Detected Rabta Flag: %s (%s)", request_id, flag.flag_type, flag.payload)
                if flag.flag_type == "ESCALATE":
                    # Section A.28: ONE — Reply nothing to the customer. Complete silence.
                    needs_escalation = True
                    reply_text = ""
                    reply_chunks = []
                elif flag.flag_type == "OWNER_QUERY":
                    # Section A.29: Go silent on specific detail until owner responds
                    needs_escalation = True
                    owner_query = flag.payload
                    reply_text = ""
                    reply_chunks = []
                elif flag.flag_type == "IMAGE_REQUEST":
                    # Section A.24: System handles image delivery automatically
                    image_product = flag.product
                    reply_text = ""
                    reply_chunks = []
                elif flag.flag_type == "BULK_LEAD":
                    # Section A.21: Alert owner for B2B negotiation
                    needs_escalation = True
                    bulk_lead = {"product": flag.product, "quantity": flag.quantity}
                    reply_text = "Bhai aapki requirement note kar li hai — quantity aur bulk rate ke liye main details finalize karke batata hun."
                    reply_chunks = [reply_text]
                elif flag.flag_type in ("AI_PAUSED", "LIMIT_REACHED", "SYSTEM_ERROR"):
                    needs_escalation = True
                    reply_text = ""
                    reply_chunks = []
            else:
                reply_text = self._clean_customer_reply(raw_output)
                reply_chunks = self._chunk_reply(reply_text)

            latency = int((time.monotonic() - t0) * 1000)
            logger.info("[%s] Turn processed in %dms (flag=%s, chunks=%d)", request_id, latency, flag.flag_type if flag else None, len(reply_chunks))

            return {
                "reply_text": reply_text,
                "reply_chunks": reply_chunks,
                "flag": flag,
                "needs_escalation": needs_escalation,
                "image_product": image_product,
                "bulk_lead": bulk_lead,
                "owner_query": owner_query,
                "request_id": request_id,
                "latency_ms": latency,
                "source": "rabta_sales_intelligence_v2",
            }

        except Exception as e:
            logger.error("[%s] Customer agent generation failed: %s", request_id, e, exc_info=True)
            fallback = "Jee bhai, Haider Arms se rabta karne ka shukriya. Batayein kis firearm ya product ke baare mein maloomat chahiye?"
            return {
                "reply_text": fallback,
                "reply_chunks": [fallback],
                "flag": None,
                "needs_escalation": False,
                "image_product": None,
                "bulk_lead": None,
                "owner_query": None,
                "request_id": request_id,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "source": "fallback",
            }
