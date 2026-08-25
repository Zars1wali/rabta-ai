import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.store_agent import WhatsAppStoreAgent

async def main():
    print("=" * 60)
    print("RABTA AI — Full WhatsApp Store & Catalog Manager Simulation")
    print("=" * 60)

    store = WhatsAppStoreAgent()
    business_name = "Gul Ahmed & Silk House"
    industry = "Pakistani Fabric & Fashion"
    
    catalog = """
    Store Products:
    1. Premium Embroidered Lawn 3-Piece: PKR 4,800 (Colors: Teal Blue, Rose Pink, Olive Green)
    2. Cotton Men's Kurta: PKR 2,400 (Sizes: S, M, L, XL)
    3. Pure Chiffon Dupatta: PKR 1,200 (Matches with all lawn suits)
    
    Store Policies:
    - Free shipping nationwide on orders above PKR 3,000.
    - Standard shipping: PKR 200 for orders under PKR 3,000.
    - Cash on Delivery (COD) available in all Pakistani cities.
    - 7-day hassle-free return and exchange guarantee.
    """

    simulated_customer_journey = [
        "Assalam o alaikum! Bhai aap k pas ladies lawn suits hain? Rates aur colors batayein.",
        "Mujhe 1 Teal Blue suit chahiye. Lahore k liye total bill kitna banay ga aur delivery charges?",
        "Main book karwana chahta hoon. Cash on delivery par bhej dein please. Mera naam Usman hai, House 14, Street 5, Gulberg 3 Lahore, phone 03001234567.",
    ]

    history = []

    for msg in simulated_customer_journey:
        print(f"\n[Customer]: {msg}")
        result = await store.handle_customer_interaction(
            customer_message=msg,
            business_name=business_name,
            industry=industry,
            catalog_context=catalog,
            conversation_history=history
        )
        safe_reply = result['reply_text'].encode('ascii', 'replace').decode('ascii')
        print(f"\n[AI WhatsApp Store Manager]:\n{safe_reply}")
        print(f"Order Intent Detected: {result['is_order_intent']}")
        print("-" * 60)
        
        # Track history
        history.append({"sender": "customer", "text": msg})
        history.append({"sender": "model", "text": result["reply_text"]})

if __name__ == "__main__":
    asyncio.run(main())
