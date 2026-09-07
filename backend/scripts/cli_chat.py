"""
Interactive WhatsApp Terminal Simulator for Rabta AI.
Allows switching seamlessly between Owner mode (+92 3169827188) and Customer mode.
"""
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.gateway_bridge import process_gateway_message, GatewayMessagePayload


async def main():
    owner_phone = "+923140922056"
    cust_phone = "+923001234567"
    biz_phone = "+923040124445"

    current_role = "owner"  # "owner" or "customer"

    print("=" * 70)
    print("  RABTA AI — INTERACTIVE WHATSAPP SIMULATOR")
    print(f"  Configured Owner Number: {owner_phone}")
    print(f"  Configured Customer Number: {cust_phone}")
    print("=" * 70)
    print("Commands:")
    print("  /role owner     -> Switch to chatting as the Owner (+92 3140922056)")
    print("  /role customer  -> Switch to chatting as a Customer (+92 300 1234567)")
    print("  exit or quit    -> Quit simulator")
    print("=" * 70)

    while True:
        prompt_label = f"[{'OWNER' if current_role == 'owner' else 'CUSTOMER'}]: "
        try:
            user_input = input(f"\n{prompt_label}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Exiting simulator.")
            break

        if user_input.startswith("/role"):
            parts = user_input.split()
            if len(parts) > 1 and parts[1].lower() in ("owner", "customer"):
                current_role = parts[1].lower()
                print(f"Switched role to: {current_role.upper()}")
            else:
                print("Usage: /role owner OR /role customer")
            continue

        active_sender = owner_phone if current_role == "owner" else cust_phone

        payload = GatewayMessagePayload(
            customer_phone=active_sender,
            business_phone=biz_phone,
            message=user_input,
        )

        res = await process_gateway_message(payload)
        reply = res.get("reply", "")
        fwd_owner = res.get("forward_to_owner")
        fwd_msg = res.get("forward_message")

        if reply:
            print(f"\n[BOT]: {reply}")
        if fwd_owner:
            print(f"\n[ALERT TO OWNER {fwd_owner}]:\n{fwd_msg}")


if __name__ == "__main__":
    asyncio.run(main())
