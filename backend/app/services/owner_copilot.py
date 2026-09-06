"""
RABTA OWNER INTELLIGENCE AGENT (VERSION 3.0 — PRODUCTION READY)
==============================================================
Human-Like Owner Communication & Business Knowledge Engine
Powered by Native Gemini Tool Calling and ReAct Harness.
"""
from __future__ import annotations
import re
import uuid
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from google import genai

from app.core.config import settings
from app.services.agent_harness import react_agent_harness
from app.services.escalation_service import EscalationService
from app.brain.prompts_owner import (
    OWNER_INTELLIGENCE_SYSTEM_PROMPT,
    build_owner_inquiry_alert,
)

logger = logging.getLogger(__name__)


class OwnerCopilotService:
    """
    Owner Intelligence Agent for Haider Arms (Shahzad Haider Bhai).
    Acts as the intelligent employee bridge between Rabta and the owner.
    """

    def __init__(self):
        self.escalation_service = EscalationService()

    def is_owner_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    async def handle_command(
        self,
        command_text: str,
        business_name: str,
        active_customer: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Handles optional slash commands as quick shortcuts."""
        cmd_parts = command_text.strip().split()
        main_cmd = cmd_parts[0].lower()

        if main_cmd == "/help":
            return {
                "action": "reply_owner",
                "message": "Bhai aap mujhse natural baat kar sakte hain (jaise 'Glock 19 is 485', 'sold out', 'push this one'). Commands: /status, /pause [number], /resume [number], /prices.",
            }

        elif main_cmd == "/status":
            return {
                "action": "reply_owner",
                "message": "Sab clear hai bhai. Filhal koi pending customer inquiry nahi hai.",
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
                "message": "AI resumed successfully.",
            }

        return {
            "action": "reply_owner",
            "message": "Command process ho gaya hai.",
        }

    async def handle_natural_message(
        self,
        owner_message: str,
        tenant_id: uuid.UUID,
        owner_phone: str,
        session: AsyncSession,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_cache_invalidate=None,
    ) -> Dict[str, Any]:
        """
        Processes natural Roman Urdu WhatsApp message from owner using Native Gemini Tool Calling.
        """
        execution_context = {
            "tenant_id": str(tenant_id),
            "sender_phone": owner_phone,
            "is_boss": True,
        }

        harness_result = await react_agent_harness.run_turn(
            system_instruction=OWNER_INTELLIGENCE_SYSTEM_PROMPT,
            user_message=owner_message,
            conversation_history=conversation_history or [],
            role="owner",
            execution_context=execution_context,
        )

        reply_text = harness_result.get("reply_text", "")
        media_urls = harness_result.get("media_urls") or []
        media_url = media_urls[0]["url"] if media_urls else None

        return {
            "action": "reply_owner",
            "message": reply_text,
            "media_url": media_url,
            "media_urls": media_urls,
            "forward_to_customer": None,
            "forward_message": None,
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
        """Formats alert for owner when customer requires human intervention."""
        return build_owner_inquiry_alert(
            customer_name=customer_name,
            customer_phone=customer_phone,
            product=extracted_item,
            city=extracted_city,
            address=customer_address,
            question=customer_question,
            inquiry_type=inquiry_type,
        )

    def format_lead_alert(
        self,
        customer_phone: str,
        customer_message: str,
        ai_reply: str,
        product_name: Optional[str] = None,
        order_amount: Optional[float] = None,
    ) -> str:
        """Formats lead notification for owner on prospective purchases."""
        amount_str = f"Rs. {order_amount:,.0f}" if order_amount else "Discussing price"
        return (
            f"🎯 *[NEW LEAD ALERT]*\n"
            f"Customer: {customer_phone}\n"
            f"Product: {product_name or 'Inquiry'}\n"
            f"Value: {amount_str}\n"
            f"Message: \"{customer_message}\"\n"
            f"AI Response: \"{ai_reply[:120]}...\""
        )


owner_copilot = OwnerCopilotService()
