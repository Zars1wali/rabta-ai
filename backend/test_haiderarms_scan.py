import asyncio
import httpx
import json

async def test_haider_arms():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        r = await client.post("/api/ingest/scan-footprint", json={
            "platform": "instagram",
            "url": "https://www.instagram.com/haiderarmsofficial",
            "industry_hint": "Licensed Firearms & Tactical Gear"
        })
        print("Status Code:", r.status_code)
        data = r.json()
        print("\nBrand Summary:", data.get("brand_summary"))
        print(f"\nExtracted {len(data.get('items', []))} items:")
        for idx, item in enumerate(data.get("items", []), 1):
            print(f"  {idx}. {item['name']} -- Category: {item['category']} (Price: PKR {item['price']})")
            print(f"     Image URL Preview: {item['image_url'][:65]}...")

if __name__ == "__main__":
    asyncio.run(test_haider_arms())
