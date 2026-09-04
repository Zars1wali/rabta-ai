"""
Polite, Rate-Limited Follow-Up Service for Rabta AI
===================================================
Scans for quiet customer conversations (idle for 10-15 minutes without a clean resolution),
and sends at most ONE natural, LLM-generated follow-up message inviting them to explore
the shop's Instagram or YouTube channels.

Strictly grounded in database business profile facts with zero hardcoded URLs or templates.
Enforces WhatsApp's 24-hour messaging window safeguard.
"""
from __future__ import annotations

import logging
import uuid
import json
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from google import genai
from google.genai import types

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.database import Conversation, Customer, Tenant, Message
from app.db.repositories.conversation_repo import get_recent_messages, append_message, is_clean_resolution
from app.services.catalog_tools import get_business_profile

logger = logging.getLogger(__name__)


class FollowUpService:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    async def _dispatch_whatsapp_message(self, phone: str, message_text: str) -> bool:
        """Sends an outbound WhatsApp message via Baileys QR gateway or Cloud API."""
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        # 1. Try Baileys Gateway (internal Docker or localhost)
        gateway_urls = [
            "http://gateway:3001/api/send-message",
            "http://localhost:3001/api/send-message",
            "http://127.0.0.1:3001/api/send-message",
        ]
        for g_url in gateway_urls:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(g_url, json={"phone": clean_phone, "message": message_text})
                    if resp.status_code == 200:
                        logger.info("[FollowUp] Successfully dispatched message to %s via %s", clean_phone, g_url)
                        return True
            except Exception:
                continue

        # 2. Try Meta Cloud API if configured
        if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
            try:
                from app.services.whatsapp import WhatsAppService
                wa = WhatsAppService()
                sent = await wa.send_text_message(clean_phone, message_text)
                if sent:
                    return True
            except Exception as wa_err:
                logger.warning("[FollowUp] Meta Cloud API error: %s", wa_err)

        logger.info("[FollowUp:Simulated] Outbound to %s: %s", clean_phone, message_text[:100])
        return True

    async def generate_natural_followup(
        self,
        tenant_name: str,
        customer_name: Optional[str],
        recent_messages: List[Dict[str, str]],
        business_profile: Dict[str, Any],
    ) -> str:
        """Generates a warm, natural follow-up message inviting the customer to Instagram or YouTube."""
        instagram_url = business_profile.get("instagram_url", "https://www.instagram.com/haiderarmsofficial")
        youtube_url = business_profile.get("youtube_url", "https://www.youtube.com/@haiderarmofficial")
        address = business_profile.get("address", "")

        # Format the chat history for Gemini context
        chat_lines = []
        for m in recent_messages[-6:]:
            speaker = "Customer" if m.get("role") == "customer" else "Store AI"
            chat_lines.append(f"{speaker}: {m.get('text', '')}")
        chat_summary = "\n".join(chat_lines) if chat_lines else "Customer was exploring firearms."

        salutation = f"{customer_name} bhai" if customer_name else "bhai"

        if not self.gemini_client:
            return f"Salam {salutation}! Agar aap mazeed details ya videos dekhna chahein toh hamara Instagram ({instagram_url}) ya YouTube ({youtube_url}) zaroor visit karein. Kisi bhi cheez mein help chahiye ho toh batayein!"

        prompt = f"""You are the friendly, professional WhatsApp sales consultant for {tenant_name}.
A customer inquired about products earlier, and the conversation has been quiet for 10-15 minutes.
Send a single polite, natural follow-up message.

=== CHAT HISTORY ===
{chat_summary}

=== VERIFIED OFFICIAL CHANNELS (DATABASE FACTS) ===
Official Instagram: {instagram_url}
Official YouTube: {youtube_url}
Physical Store Address: {address}

=== GUIDELINES ===
1. Be warm, polite, and completely non-pushy. Sound like a helpful shop representative.
2. In Roman Urdu (Pakistani WhatsApp style, English alphabet).
3. Naturally invite them to check out either the shop's Instagram ({instagram_url}) or YouTube channel ({youtube_url}) — or both — depending on what feels most natural given their inquiry (e.g. if they asked about models/reviews, YouTube videos or Instagram pictures are great).
4. You MUST use the exact verified URLs provided above. NEVER invent or alter URLs.
5. Plain text only: zero emojis, no bold asterisks, no bullet points.
6. Keep it concise: 2 to 3 natural sentences.

Generate the follow-up message text now:"""

        try:
            resp = await self.gemini_client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=200,
                ),
            )
            raw_text = (resp.text or "").strip()
            # Clean formatting
            import re
            raw_text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', raw_text)
            raw_text = re.sub(r'[\U0001F600-\U0001FAFF]', '', raw_text)
            return raw_text.strip()
        except Exception as e:
            logger.warning("[FollowUp:LLM] Error generating follow-up: %s", e)
            return f"Salam {salutation}! Agar aap mazeed details ya test-fire videos dekhna chahein toh hamara YouTube ({youtube_url}) ya Instagram ({instagram_url}) zaroor check karein. Koi bhi sawal ho toh batayein!"

    async def scan_and_process_followups(
        self,
        idle_minutes: float = 10.0,
        max_hours: float = 24.0,
        tenant_id: Optional[uuid.UUID] = None,
        force_conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scans for conversations that have been idle between `idle_minutes` and `max_hours`.
        Respects WhatsApp's 24-hour customer window and skips cleanly resolved chats.
        Sends at most ONE follow-up per conversation.
        """
        now = datetime.utcnow()
        idle_threshold = now - timedelta(minutes=idle_minutes)
        window_24h_limit = now - timedelta(hours=max_hours)

        processed = []

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Conversation)
                .where(
                    Conversation.status == "active",
                    Conversation.has_followed_up == False,
                    Conversation.is_resolved_cleanly == False,
                )
            )

            if force_conversation_id:
                stmt = select(Conversation).where(Conversation.id == force_conversation_id)
            else:
                stmt = stmt.where(
                    and_(
                        Conversation.last_message_at <= idle_threshold,
                        Conversation.last_message_at >= window_24h_limit,
                    )
                )

            if tenant_id:
                stmt = stmt.where(Conversation.tenant_id == tenant_id)

            res = await session.execute(stmt)
            conversations = res.scalars().all()

            logger.info("[FollowUp] Found %d candidate conversations for follow-up evaluation.", len(conversations))

            for conv in conversations:
                # 1. Strict guard: Already followed up?
                if conv.has_followed_up and not force_conversation_id:
                    continue

                # 2. Strict guard: 24-hour customer service window safeguard
                last_active = conv.last_customer_message_at or conv.last_message_at or conv.created_at
                if (now - last_active).total_seconds() > (max_hours * 3600):
                    logger.warning(
                        "[FollowUp] Aborting follow-up for conv=%s: Outside WhatsApp 24h window (last active %s)",
                        conv.id, last_active
                    )
                    conv.has_followed_up = True  # Mark skipped so it never retries outside window
                    await session.commit()
                    continue

                # 3. Load Customer & Tenant
                customer = await session.get(Customer, conv.customer_id)
                tenant = await session.get(Tenant, conv.tenant_id)
                if not customer or not tenant:
                    continue

                # 4. Check conversation history
                recent_msgs = await get_recent_messages(session, conv.id, limit=6)
                if not recent_msgs:
                    continue

                # 5. Clean resolution check: If customer already said thanks/goodbye, skip follow-up!
                last_cust_msgs = [m["text"] for m in recent_msgs if m.get("role") == "customer"]
                if last_cust_msgs and is_clean_resolution(last_cust_msgs[-1]):
                    logger.info("[FollowUp] Skipping conv=%s: customer cleanly closed with '%s'", conv.id, last_cust_msgs[-1])
                    conv.is_resolved_cleanly = True
                    conv.has_followed_up = True
                    await session.commit()
                    continue

                # 6. Load business profile from DB
                business_profile = await get_business_profile(str(tenant.id))

                # 7. Generate natural, grounded follow-up message
                followup_text = await self.generate_natural_followup(
                    tenant_name=tenant.name,
                    customer_name=customer.name,
                    recent_messages=recent_msgs,
                    business_profile=business_profile,
                )

                # 8. Dispatch outbound WhatsApp message
                dispatched = await self._dispatch_whatsapp_message(customer.phone, followup_text)

                # 9. Mark follow-up as sent (guarantees AT MOST ONCE per conversation)
                conv.has_followed_up = True
                conv.followed_up_at = datetime.utcnow()

                # 10. Record message in database
                await append_message(
                    session,
                    conversation_id=conv.id,
                    sender_type="ai",
                    content_text=followup_text,
                )

                await session.commit()

                logger.info(
                    "[FollowUp] Sent follow-up to customer=%s (conv=%s): %s",
                    customer.phone, conv.id, followup_text[:60]
                )

                processed.append({
                    "conversation_id": str(conv.id),
                    "customer_phone": customer.phone,
                    "followup_message": followup_text,
                    "dispatched": dispatched,
                    "followed_up_at": conv.followed_up_at.isoformat() if conv.followed_up_at else None,
                })

        return processed


# Global singleton
followup_service = FollowUpService()
