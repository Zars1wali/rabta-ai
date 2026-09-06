import asyncio
import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient, ASGITransport
from app.main import app

async def main():
    print("=" * 70)
    print("TESTING: Complete Business Onboarding, Inventory & AI Sales Workflow")
    print("=" * 70)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test onboarding page
        r_page = await client.get("/onboard")
        print(f"\n1. Onboarding UI Web Page: HTTP {r_page.status_code} ({len(r_page.text)} bytes)")
        assert r_page.status_code == 200

        # 2. Test Onboarding a real Pakistani Pilot Business
        pilot_phone = "+923185551234"
        owner_phone = "+923001112233"
        payload = {
            "business_name": "Khaadi Classic Pret Lahore",
            "business_phone": pilot_phone,
            "owner_whatsapp": owner_phone,
            "industry": "Pakistani Pret & Luxury Fabrics",
            "policies": "Free delivery across Pakistan on orders above PKR 3,000. Cash on delivery available.",
            "catalog": [
                {"name": "Luxury Silk Festive Kurti", "price": 5500, "category": "Pret", "details": "Hand-embroidered with mirror work, sizes S-XL"},
                {"name": "Embroidered 3-Piece Lawn Suit", "price": 6200, "category": "Unstitched", "details": "Printed chiffon dupatta and dyed trouser"},
                {"name": "Velvet Shawl Collection", "price": 8500, "category": "Winter", "details": "Heavy tilla work with zari lace border"}
            ]
        }

        r_onboard = await client.post("/api/business/onboard", json=payload)
        print(f"\n2. Business Onboarding API Result (HTTP {r_onboard.status_code}):")
        onboard_res = r_onboard.json()
        print(json.dumps(onboard_res, indent=2))
        assert r_onboard.status_code == 200
        assert onboard_res["status"] == "success"

        # 3. Test Business Listing
        r_list = await client.get("/api/business/list")
        print(f"\n3. Total Active Onboarded Businesses on Rabta AI:")
        list_res = r_list.json()
        print(f"Count: {list_res['total_businesses']}")
        for b in list_res["businesses"]:
            print(f" - {b['name']} ({b['business_phone']}) | Items: {b['total_items']}")

        # 4. Test Single Business Retrieval
        clean_phone = pilot_phone.replace("+", "")
        r_biz = await client.get(f"/api/business/{clean_phone}")
        print(f"\n4. Business Details for {clean_phone} (HTTP {r_biz.status_code}):")
        biz_data = r_biz.json()
        print(f" Name: {biz_data['name']}, Items in raw_catalog: {len(biz_data['raw_catalog'])}")
        assert len(biz_data["raw_catalog"]) == 3

        # 5. Test Customer AI Chat against the Newly Onboarded Inventory
        print("\n5. Customer Inquiry about Onboarded Product:")
        msg_payload = {
            "customer_phone": "923331234567",
            "business_phone": pilot_phone,
            "message": "Assalam o alaikum bhai, Luxury Silk Festive Kurti ki price aur details kya hain?",
            "platform": "whatsapp_test"
        }
        r_chat = await client.post("/api/gateway/process-message", json=msg_payload)
        chat_res = r_chat.json()
        print(f" Customer: '{msg_payload['message']}'")
        print(f" AI Reply:\n{chat_res.get('reply')}")
        print(f" Latency: {chat_res.get('latency_ms')} ms")
        assert chat_res["status"] == "success"

        # 6. Test Owner Slash Command: /status
        print("\n6. Owner /status Slash Command Test:")
        cmd_status = {
            "customer_phone": owner_phone,
            "business_phone": pilot_phone,
            "message": "/status",
            "platform": "whatsapp_test"
        }
        r_status = await client.post("/api/gateway/process-message", json=cmd_status)
        status_res = r_status.json()
        print(f" Owner sent: '/status'")
        print(f" Response status: {status_res.get('status')}")
        print(f" Response text:\n{status_res.get('reply')}")
        assert status_res["status"] == "owner_command"

        # 7. Test Owner Slash Command: /add
        print("\n7. Owner /add Quick Product Addition Test:")
        cmd_add = {
            "customer_phone": owner_phone,
            "business_phone": pilot_phone,
            "message": "/add Organza Wrap PKR 3200",
            "platform": "whatsapp_test"
        }
        r_add = await client.post("/api/gateway/process-message", json=cmd_add)
        add_res = r_add.json()
        print(f" Owner sent: '{cmd_add['message']}'")
        print(f" Response text:\n{add_res.get('reply')}")
        assert add_res["status"] == "owner_command"

        # 8. Verify Updated Inventory count
        r_biz_updated = await client.get(f"/api/business/{clean_phone}")
        updated_data = r_biz_updated.json()
        print(f"\n8. Updated items in catalog: {len(updated_data['raw_catalog'])}")
        assert len(updated_data["raw_catalog"]) == 4

        print("\n" + "=" * 70)
        print("ALL ONBOARDING & INVENTORY TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

