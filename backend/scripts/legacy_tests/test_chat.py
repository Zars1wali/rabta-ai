import asyncio
import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.store_agent import WhatsAppStoreAgent

from app.services.store_agent import WhatsAppStoreAgent

async def main():
    print("=" * 70)
    print("RABTA AI - Conversational Flow & Intro Styles Test")
    print("=" * 70)

    agent = WhatsAppStoreAgent()

    haider_catalog = """
    Products & Inventory:
    - Canik METE SFx 9mm Pistol: PKR 185,000 (Imported Turkish 9mm pistol)
    - Beretta 92FS 9mm Pistol: PKR 260,000 (Italian classic 9mm pistol)
    - Tisas PX-9 Gen 3 9mm Pistol: PKR 140,000 (Polymer frame 9mm)
    - Custom Kydex IWB Concealed Holster: PKR 6,500
    - Heavy-Duty Cordura Dual Pistol Range Bag: PKR 9,500
    - Modular Tactical Plate Carrier Vest: PKR 14,500
    - MOLLE Tactical Shooter Belt System: PKR 5,200

    Policies:
    - Fast delivery across Pakistan via cash on delivery or bank transfer. WhatsApp: 03040124445
    """

    history = []
    convo = [
        "hello",
        "apke pass konse guns hain?",
        "iske ilawa",
        "assault rifles mil jaengay?",
        "kia rate hain inke?",
        "theek hai Canik METE SFx book kar dein",
    ]

    print("\n--- SIMULATING MULTI-TURN WHATSAPP CHAT ---")
    for msg in convo:
        await asyncio.sleep(2.0)
        print(f"\n[Customer]: {msg}")
        interaction = await agent.handle_customer_interaction(
            customer_message=msg,
            business_name="Haider Arms",
            industry="Tactical Gear & Firearms",
            catalog_context=haider_catalog,
            conversation_history=history,
        )
        reply = interaction["reply_text"]
        print(f"[Store Employee]: {reply}")
        history.append({"role": "customer", "text": msg})
        history.append({"role": "assistant", "text": reply})

    print("\n" + "=" * 70)
    print("CONVERSATION TEST FINISHED")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
