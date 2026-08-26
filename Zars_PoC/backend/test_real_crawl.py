import asyncio
import httpx
import json

async def test_live_crawl():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        # Test 1: Gul Ahmed Fashion Instagram
        r = await client.post("/api/ingest/scan-footprint", json={
            "platform": "instagram",
            "url": "https://instagram.com/gulahmedfashion",
            "industry_hint": "Pakistani Lawn & Unstitched"
        })
        print("Gul Ahmed Scan Status:", r.status_code)
        data = r.json()
        print("Summary:", data.get("brand_summary"))
        print(f"Extracted {len(data.get('items', []))} products dynamically with Gemini:")
        for idx, item in enumerate(data.get("items", []), 1):
            print(f"  {idx}. {item['name']} -- PKR {item['price']} (Confidence: {int(item['confidence']*100)}%)")

if __name__ == "__main__":
    asyncio.run(test_live_crawl())
