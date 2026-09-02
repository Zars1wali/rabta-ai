import re
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.price_update_service import PriceUpdateService
from app.services.escalation_service import EscalationService, EscalationRecord
from app.db.repositories import tenant_repo, price_log_repo

logger = logging.getLogger(__name__)


class OwnerCopilotService:
    """Personal Digital Executive Assistant for the Business Owner (Haider bhai) on WhatsApp.
    
    Speaks to the owner casually like a real person to their boss on WhatsApp:
    Short. Casual. No formatting. No subject lines. No bullet points.
    """

    def __init__(self):
        self.price_service = PriceUpdateService()
        self.escalation_service = EscalationService(
            reminder1_secs=1800.0,  # 30 minutes
            reminder2_secs=3600.0,  # 60 minutes
            timeout_secs=7200.0
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
        cmd_parts = command_text.strip().split()
        main_cmd = cmd_parts[0].lower()

        if main_cmd == "/help":
            return {
                "action": "reply_owner",
                "message": "Commands: /status, /pause [number], /resume [number], /prices. Ya direct mujhse baat karein rate update ya customer replies ke liye."
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

        else:
            return {
                "action": "reply_owner",
                "message": "Bhai samajh nahi aaya. Rate update karna hai toh jaise 'Glock 19 USA 450000' likhein.",
            }

    async def handle_owner_natural_message(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        owner_phone: str,
        message_text: str,
        on_cache_invalidate: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Routes natural messages from Haider bhai."""
        # 1. Price Updates
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

        # 2. Answering an open customer inquiry
        target_esc, clean_answer = self.escalation_service.find_target_escalation(tenant_id, message_text)
        if target_esc:
            resolved_esc = self.escalation_service.resolve_escalation(target_esc.escalation_id, clean_answer)
            if resolved_esc:
                # Direct answer pass: do not rephrase, pass straight
                return {
                    "action": "relay_escalation_to_customer",
                    "customer_phone": resolved_esc.customer_phone,
                    "customer_reply": clean_answer,
                    "escalation_id": resolved_esc.escalation_id,
                    "owner_confirmation": "Done bhai. Customer ko convey kar diya.",
                }

        # 3. Fallback
        return {
            "action": "reply_owner",
            "message": "Jee bhai note kar liya.",
        }

    def format_escalation_alert(
        self,
        customer_phone: str,
        customer_question: str,
        customer_name: Optional[str] = None,
        extracted_item: Optional[str] = None,
        extracted_city: Optional[str] = None,
        customer_address: Optional[str] = None,
        inquiry_type: str = "delivery",
    ) -> str:
        """Short, casual, one-line message to Haider bhai on WhatsApp."""
        INVALID_NAMES = {
            "nahi", "brand", "pata", "naam", "firearm", "pistol", "gun",
            "delivery", "lahore", "karachi", "islamabad", "rawalpindi", "peshawar",
            "unknown", "none", "customer", "bhai", "sir", "batao", "price", "rate",
        }

        # Clean and format phone number properly (preserves international & local numbers)
        phone_raw = str(customer_phone or "").strip()
        digits = re.sub(r'[^\d]', '', phone_raw)
        if digits.startswith("92") and len(digits) == 12:
            phone_display = f"+92 {digits[2:5]} {digits[5:]}"
        elif digits.startswith("03") and len(digits) == 11:
            phone_display = f"+92 {digits[1:4]} {digits[4:]}"
        elif digits:
            phone_display = f"+{digits}"
        else:
            phone_display = phone_raw

        # 1. Clean Customer Identifier
        if customer_name and isinstance(customer_name, str):
            c_name = customer_name.strip().title()
            if c_name.lower() not in INVALID_NAMES and len(c_name) >= 3 and not re.search(r'\d', c_name):
                identifier = c_name
            else:
                short = digits[-4:] if len(digits) >= 4 else (digits or "0000")
                identifier = f"customer (...{short})"
        else:
            short = digits[-4:] if len(digits) >= 4 else (digits or "0000")
            identifier = f"customer (...{short})"

        identifier_full = f"{identifier} ({phone_display})"

        # 2. Clean Product
        product = extracted_item.strip() if (extracted_item and extracted_item.lower() not in ["firearm", "gun", "pistol", "unknown", "product"]) else None
        city = extracted_city.strip() if extracted_city else None
        q_lower = customer_question.lower()

        # 3. Final Price / Discount Inquiries
        if inquiry_type == "discount" or any(w in q_lower for w in ["final", "discount", "kam", "akhri", "concession", "gunjaish", "kam rate"]):
            if product:
                return f"Haider bhai, {identifier_full} {product} ka final price / discount pooch raha hai. Kitna de sakte hain?"
            return f"Haider bhai, {identifier_full} final price / discount maang raha hai. Kitna discount de sakte hain?"

        # 4. Delivery Charges Inquiries
        if inquiry_type == "delivery" or any(w in q_lower for w in ["deliver", "charges", "bhej", "shipping", "courier"]):
            # Build location string: "Lahore, DHA Phase 5 Street 7" or just "Lahore"
            loc_parts = []
            if city:
                loc_parts.append(city)
            if customer_address and customer_address.lower() != (city or "").lower():
                loc_parts.append(customer_address)
            location = ", ".join(loc_parts) if loc_parts else "Not specified"

            if location and product:
                return (f"Haider bhai, {identifier_full}\n"
                        f"Address: {location}\n"
                        f"Product: {product}\n"
                        f"Delivery charges kya hain?")
            elif location:
                return (f"Haider bhai, {identifier_full}\n"
                        f"Address: {location}\n"
                        f"Delivery charges pooch raha hai.")
            elif product:
                return (f"Haider bhai, {identifier_full} {product} ke liye delivery charges pooch raha hai. "
                        f"Charges kya hain?")
            else:
                return f"Haider bhai, {identifier_full} delivery charges pooch raha hai: \"{customer_question}\""

        # 5. Price / Rate Inquiries
        if any(w in q_lower for w in ["price", "rate", "kitne ka", "cost"]):
            if product:
                return f"Haider bhai, {identifier} {product} ka price pooch raha hai. Aaj ka rate kya hai?"
            return f"Haider bhai, {identifier} rate pooch raha hai: \"{customer_question}\""

        # 6. Availability Inquiries
        if any(w in q_lower for w in ["available", "stock", "hai ya nahi", "mil jayegi", "parhi hai"]):
            if product:
                return f"Haider bhai, {identifier} {product} maang raha hai. Available hai? Aur price kya hai?"
            return f"Haider bhai, {identifier} stock availability pooch raha hai: \"{customer_question}\""

        # 7. Bulk Inquiries
        if any(w in q_lower for w in ["bulk", "quantity", "zyada", "5 piece", "10 piece", "wholesale"]):
            if product:
                return f"Haider bhai, {identifier} {product} bulk mein maang raha hai. Yeh serious lag raha hai — aap khud baat karein ya main rate quote karun?"

        # 8. General Inquiry Fallback
        if product:
            return f"Haider bhai, {identifier} {product} ke baray mein pooch raha hai: \"{customer_question}\". Kya jawab dun?"
        return f"Haider bhai, {identifier} ne poochha: \"{customer_question}\". Kya jawab dun?"
