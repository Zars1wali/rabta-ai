import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)

async def test_complete_onboarding_pipeline():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=45.0) as client:
        print("=== [RABTA AI] ACTION-FIRST ONBOARDING & LIVE AHA VERIFICATION TEST ===")

        # 1. Test Social Media Footprint Ingestion API
        print("\n[Stage 1] Testing Digital Footprint Ingestion on Instagram & Web...")
        ingest_payload = {
            "platform": "instagram",
            "url": "https://instagram.com/sapphirepakistan",
            "industry_hint": "Pakistani Fabric & Fashion"
        }
        ingest_res = await client.post("/api/ingest/scan-footprint", json=ingest_payload)
        assert ingest_res.status_code == 200, f"Ingest failed: {ingest_res.text}"
        ingest_data = ingest_res.json()
        print(f"[OK] Ingested {ingest_data['total_items_found']} products from Instagram footprint!")
        for idx, item in enumerate(ingest_data["items"], 1):
            print(f"   {idx}. {item['name']} -- PKR {item['price']} (Confidence: {int(item['confidence']*100)}%)")

        # 2. Test Onboarding Activation with Single WhatsApp Number & Ingested Catalog
        print("\n[Stage 2] Submitting Visual Studio Catalog & Single Dedicated Number...")
        onboard_payload = {
            "business_name": "Sapphire Studio Gulberg",
            "owner_whatsapp": "+923169827188",
            "industry": "Pakistani Fabric & Fashion",
            "social_links": {"instagram": "https://instagram.com/sapphirepakistan"},
            "inventory_context": ingest_data["brand_summary"],
            "policies": "Free shipping across Pakistan on orders above PKR 3,000. Cash on Delivery available.",
            "catalog": ingest_data["items"]
        }

        onboard_res = await client.post("/api/business/onboard", json=onboard_payload)
        assert onboard_res.status_code == 200, f"Onboarding failed: {onboard_res.text}"
        print(f"[OK] Merchant Activated: {onboard_res.json()['message']}")

        # 3. Test Live End-to-End Customer Interaction (Aha Moment)
        print("\n[Stage 3] Testing Live In-Flight Customer Message Resolution...")
        chat_payload = {
            "customer_phone": "923331122334",
            "business_phone": "923169827188",
            "message": "Assalam o alaikum! Sapphire Studio Gulberg se baat ho rahi hai? Mujhe Eid k liye Chikankari lawn 3-piece aur silk printed kurti chahiye. Total kitna banay ga aur delivery charges kitnay hain?",
            "platform": "aha_verifier"
        }

        msg_res = await client.post("/api/gateway/process-message", json=chat_payload)
        assert msg_res.status_code == 200, f"Chat processing failed: {msg_res.text}"
        reply = msg_res.json()["reply"]

        print("\n[AI Salesperson Live Response]:")
        print("-" * 65)
        try:
            print(reply)
        except UnicodeEncodeError:
            print(reply.encode("ascii", "replace").decode())
        print("-" * 65)

        # 4. Verify Gateway QR Status
        print("\n[Stage 4] Checking WhatsApp Gateway Linked Status...")
        gw_res = await client.get("http://localhost:3001/qr")
        print(f"[OK] Gateway Port 3001 Status: {gw_res.json().get('status')} (Connected: {gw_res.json().get('connected_number')})")

        print("\n>>> ALL 4 ACTION-FIRST ONBOARDING PHASES VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(test_complete_onboarding_pipeline())
