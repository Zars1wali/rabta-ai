import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OwnerCopilotService:
    """Handles owner alerts, human handoffs, and WhatsApp slash commands."""

    COMMANDS_HELP = """*RABTA AI -- Owner Control Panel*

Commands:
* /pause [number] - Stop AI for this customer and chat directly.
* /resume [number] - Hand customer back to AI.
* /status - View active chats & AI status.
* /add [Item Name] PKR [Price] - Quick-add item to catalog.
* /help - View available commands.
"""

    def is_owner_command(self, text: str) -> bool:
        """Checks if a message from owner starts with a slash command."""
        return text.strip().startswith("/")

    async def handle_command(
        self,
        command_text: str,
        business_name: str,
        active_customer: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes owner WhatsApp commands and returns action dict."""
        cmd_parts = command_text.strip().split()
        main_cmd = cmd_parts[0].lower()

        if main_cmd == "/help":
            return {"action": "reply_owner", "message": self.COMMANDS_HELP}

        elif main_cmd == "/pause":
            target_phone = cmd_parts[1] if len(cmd_parts) > 1 else active_customer
            if not target_phone:
                return {
                    "action": "reply_owner",
                    "message": "[!] Please specify customer phone: /pause +923001234567",
                }
            return {
                "action": "pause_ai",
                "customer_phone": target_phone,
                "message": f"[*] AI Paused for customer {target_phone}.\nYour next messages will be forwarded directly to the customer!\nType /resume when finished.",
            }

        elif main_cmd == "/resume":
            target_phone = cmd_parts[1] if len(cmd_parts) > 1 else active_customer
            return {
                "action": "resume_ai",
                "customer_phone": target_phone,
                "message": f"[*] AI Resumed! AI will now respond to customer {target_phone or 'all'}.",
            }

        elif main_cmd == "/status":
            return {
                "action": "reply_owner",
                "message": f"[*] {business_name} -- Status Report\n- AI Status: Active (Ready to Sell)\n- Active Takeover: {active_customer or 'None'}\n- All systems running smoothly.",
            }

        elif main_cmd == "/add":
            item_data = " ".join(cmd_parts[1:])
            if not item_data:
                return {
                    "action": "reply_owner",
                    "message": "[!] Please specify item details: /add Lawn Kurti PKR 2500",
                }

            price = 0.0
            item_name = item_data
            # Extract price if present at the end or preceded by PKR / Rs / price
            match = re.search(r'(?:pkr|rs\.?|price)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*$', item_data, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    price = float(price_str)
                    item_name = item_data[:match.start()].strip(" -:|")
                except ValueError:
                    pass

            return {
                "action": "add_catalog_item",
                "item_name": item_name or item_data,
                "price": price,
                "raw_text": item_data,
                "message": f"[*] Product Added to AI Brain!\nItem: {item_name or item_data}\nPrice: PKR {price:,.0f}\nAI will now recommend this to customers.",
            }

        else:
            return {
                "action": "reply_owner",
                "message": "[?] Unknown command. Type /help for available commands.",
            }

    def format_lead_alert(
        self,
        customer_phone: str,
        customer_message: str,
        ai_reply: str,
        reason: str = "New Inquiry"
    ) -> str:
        """Formats a clean notification to send to the owner's personal WhatsApp."""
        return f"""[!] *{reason} Alert -- Rabta AI*

[Customer]: {customer_phone}
[Customer Said]: "{customer_message}"
[AI Replied]: "{ai_reply}"

-> To chat directly with customer, reply: /pause {customer_phone}
"""

