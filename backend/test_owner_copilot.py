import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.owner_copilot import OwnerCopilotService

async def main():
    print("=" * 60)
    print("TESTING: Owner WhatsApp Copilot & Slash Commands")
    print("=" * 60)

    copilot = OwnerCopilotService()
    business_name = "Al-Rehman Textiles"
    active_customer = None

    # Test 1: Lead Alert Formatting
    print("\n--- 1. Testing Lead Notification Sent to Owner's Personal WhatsApp ---")
    alert = copilot.format_lead_alert(
        customer_phone="+923009876543",
        customer_message="Assalam o alaikum, 5 suits chahiye wholesale rate kya hai?",
        ai_reply="Walaikum Assalam! Wholesale rates 5 suits par PKR 4,000 per suit hain...",
        reason="Hot Wholesale Lead"
    )
    print(alert)

    # Test 2: Owner sends /pause to take over chat
    print("\n--- 2. Owner replies with '/pause +923009876543' ---")
    res = await copilot.handle_command("/pause +923009876543", business_name, active_customer)
    print(f"Action: {res['action']}")
    print(f"WhatsApp message to Owner:\n{res['message']}")
    active_customer = res.get("customer_phone")

    # Test 3: Owner checks status
    print("\n--- 3. Owner checks status with '/status' ---")
    res = await copilot.handle_command("/status", business_name, active_customer)
    print(f"WhatsApp message to Owner:\n{res['message']}")

    # Test 4: Owner resumes AI
    print("\n--- 4. Owner hands chat back to AI with '/resume' ---")
    res = await copilot.handle_command("/resume", business_name, active_customer)
    print(f"Action: {res['action']}")
    print(f"WhatsApp message to Owner:\n{res['message']}")

    # Test 5: Owner adds a new item directly from WhatsApp
    print("\n--- 5. Owner adds new item with '/add Chiffon Saree PKR 8500' ---")
    res = await copilot.handle_command("/add Chiffon Saree PKR 8500", business_name, None)
    print(f"Action: {res['action']}")
    print(f"WhatsApp message to Owner:\n{res['message']}")

if __name__ == "__main__":
    asyncio.run(main())
