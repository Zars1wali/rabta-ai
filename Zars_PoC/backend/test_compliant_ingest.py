import asyncio
import httpx
import json

async def test_compliant_ingestion_engine():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=45.0) as client:
        print("=== [RABTA AI] TESTING COMPLIANT INGESTION PIPELINE v2 ===")

        # 1. Test Instagram Graph API Connector
        print("\n[Step 1] Executing Instagram Graph API Ingestion for @sapphirepakistan...")
        resp = await client.post("/api/ingest/v2/connect-instagram", params={"account_handle_or_auth_code": "sapphirepakistan"})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()

        print(f"[OK] Extracted {data['total_draft_products']} Draft Products.")
        print(f"     Brand Persona: {data['brand_persona_summary']}")
        print(f"     Tone Recommendation: {data['brand_tone_recommendation']}")

        for idx, item in enumerate(data["draft_catalog"], 1):
            print(f"     {idx}. {item['suggested_name']} -- PKR {item['suggested_price']} [STATUS: {item['status']}] (Images: {len(item['media_assets'])})")

        # 2. Test Merchant Review & Confirmation Contract
        print("\n[Step 2] Testing Merchant Review Layer (Promoting Draft -> Confirmed)...")
        confirm_payload = {
            "business_phone": "923169827188",
            "confirmed_products": [
                {
                    "name": data["draft_catalog"][0]["suggested_name"],
                    "price": data["draft_catalog"][0]["suggested_price"],
                    "category": data["draft_catalog"][0]["category"],
                    "details": data["draft_catalog"][0]["details"],
                    "image_url": data["draft_catalog"][0]["media_assets"][0]["url"]
                }
            ],
            "confirmed_policies": "Free shipping across Pakistan on orders above PKR 3,000. Cash on Delivery available."
        }

        conf_resp = await client.post("/api/ingest/v2/confirm-draft-catalog", json=confirm_payload)
        assert conf_resp.status_code == 200, f"Confirmation failed: {conf_resp.text}"
        print(f"[OK] {conf_resp.json()['message']}")

        print("\n>>> ALL COMPLIANT INGESTION & DATA CONTRACT TESTS PASSED! <<<")

if __name__ == "__main__":
    asyncio.run(test_compliant_ingestion_engine())
