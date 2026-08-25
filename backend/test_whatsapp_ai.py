import asyncio
import httpx
import json

async def test_whatsapp_ai():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        payload = {
            "customer_phone": "923001122334",
            "business_phone": "923040124445",
            "message": "Assalam o alaikum, aap ke paas kaunse pistols available hain?",
            "platform": "baileys_qr"
        }
        print("Sending test message to AI gateway...")
        r = await client.post("/api/gateway/process-message", json=payload)
        print("Status:", r.status_code)
        data = r.json()
        print("\nAI Reply:\n", data.get("reply", "NO REPLY"))
        print("Order Intent:", data.get("is_order_intent"))

if __name__ == "__main__":
    asyncio.run(test_whatsapp_ai())
