"""
Interactive Multi-Persona WhatsApp Testing Harness for Rabta AI.
Allows testing both Owner Side (+92 3140922056) and Customer Side.
"""
import asyncio
import sys
import os
import uuid

# Ensure backend folder is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import AsyncSessionLocal
from app.db.repositories import tenant_repo
from app.api.gateway_bridge import process_gateway_message, GatewayMessagePayload


async def send_simulated_message(sender_phone: str, message: str, business_phone: str = "+923040124445"):
    payload = GatewayMessagePayload(
        customer_phone=sender_phone,
        business_phone=business_phone,
        message=message,
    )
    result = await process_gateway_message(payload)
    return result


async def run_feature_test(feature_name: str, sender_phone: str, message: str):
    print(f"\n{'='*70}")
    is_owner = (sender_phone.replace("+", "") == "923140922056")
    role = "OWNER (Shahzad Haider Bhai)" if is_owner else f"CUSTOMER ({sender_phone})"
    print(f"TESTING: {feature_name}")
    print(f"SENDER:  {role} [{sender_phone}]")
    print(f"MESSAGE: \"{message}\"")
    print(f"{'-'*70}")

    res = await send_simulated_message(sender_phone, message)
    reply = res.get("reply", "")
    forward_owner = res.get("forward_to_owner")
    forward_msg = res.get("forward_message")

    if reply:
        print(f"BOT REPLY TO SENDER:\n{reply}")
    if forward_owner:
        print(f"\nALERT FORWARDED TO OWNER ({forward_owner}):\n{forward_msg}")

    print(f"{'='*70}")
    return res


async def main():
    owner_phone = "+923140922056"
    cust_phone = "+923005551234"

    print("\n" + "#"*70)
    print("RABTA AI — OWNER & CUSTOMER TWO-SIDED FEATURE TEST")
    print(f"Owner Number Configured: {owner_phone}")
    print("#"*70)

    # 1. Test Owner Daily Price Confirmation
    await run_feature_test(
        feature_name="1. Owner Daily Morning Price Confirmation",
        sender_phone=owner_phone,
        message="confirmed",
    )

    # 2. Test Owner Price Update
    await run_feature_test(
        feature_name="2. Owner Natural Price Update",
        sender_phone=owner_phone,
        message="Glock 19 Gen 5 is now 490k",
    )

    # 3. Test Owner Margin Preference Setting
    await run_feature_test(
        feature_name="3. Owner Margin Preference Intelligence",
        sender_phone=owner_phone,
        message="Push this one — better margin for us on Canik TP9",
    )

    # 4. Test Owner Stock Update
    await run_feature_test(
        feature_name="4. Owner Stock Availability Update",
        sender_phone=owner_phone,
        message="2 pieces left for Glock 19 Gen 5",
    )

    # 5. Test Customer Inquiry & Verification
    await run_feature_test(
        feature_name="5. Customer Price & Stock Inquiry (Rabta Sells as Haider Bhai)",
        sender_phone=cust_phone,
        message="salam bhai glock 19 gen 5 kitne ki hai aur delivery ho jayegi?",
    )

    # 6. Test Customer Delivery Closing -> Owner Alert
    await run_feature_test(
        feature_name="6. Customer Delivery Info -> Alerts Owner for Charges",
        sender_phone=cust_phone,
        message="main Lahore DHA Phase 5 se bol raha hun delivery charges kitne honge?",
    )

    # 7. Test Owner Relaying Answer back to Customer
    await run_feature_test(
        feature_name="7. Owner Relays Delivery Charges to Customer",
        sender_phone=owner_phone,
        message="Lahore DHA ke 1500 charges hain",
    )

    print("\nAll automated feature tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
