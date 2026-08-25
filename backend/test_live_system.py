import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)

async def run_live_test():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        # 1. Onboard a luxury boutique with single WhatsApp, social media footprint, and products with images
        onboard_payload = {
            "business_name": "Sapphire Couture Lahore",
            "owner_whatsapp": "+923169827188",
            "industry": "Pakistani Fabric & Fashion",
            "social_links": {
                "instagram": "https://instagram.com/sapphirepakistan",
                "facebook": "https://facebook.com/sapphirecouture",
                "tiktok": "https://tiktok.com/@sapphireofficial"
            },
            "inventory_context": "Famous for festive jacquard luxury pret, silk dupattas, and Eid unstitched 3-piece collections with hand zardozi work.",
            "policies": "Free delivery across Pakistan on orders above PKR 3,500. Same day dispatch for Lahore.",
            "catalog": [
                {
                    "name": "Luxury Silk Jacquard 3-Piece",
                    "price": 6800,
                    "category": "Festive Wear",
                    "details": "Raw silk embroidered shirt with organza dupatta and dyed silk trouser"
                },
                {
                    "name": "Daily Pret Lawn Kurti",
                    "price": 2450,
                    "category": "Casual Pret",
                    "details": "Digitally printed lawn kurti with pearl neck detailing"
                }
            ]
        }

        print("\n--- [1] Testing Luxury Self-Onboarding API ---")
        onboard_res = await client.post("/api/business/onboard", json=onboard_payload)
        print("Status:", onboard_res.status_code)
        print("Response:", onboard_res.json())

        # 2. Simulate a customer asking on WhatsApp about products, prices, and past collections
        print("\n--- [2] Simulating Customer Message over WhatsApp Gateway Bridge ---")
        chat_payload = {
            "customer_phone": "923007654321",
            "business_phone": "923169827188",
            "message": "Assalam o alaikum! Sapphire Couture se baat ho rahi hai? Mujhe Eid k liye silk jacquard suit aur ek kurti leni hai, total bill kitna hoga aur delivery kab tak milegi?",
            "platform": "baileys_qr"
        }

        msg_res = await client.post("/api/gateway/process-message", json=chat_payload)
        print("Status:", msg_res.status_code)
        resp_data = msg_res.json()
        print("\nAI Sales Brain Reply:")
        print("="*60)
        try:
            print(resp_data.get("reply", ""))
        except UnicodeEncodeError:
            print(resp_data.get("reply", "").encode("ascii", "replace").decode())
        print("="*60)

if __name__ == "__main__":
    asyncio.run(run_live_test())
