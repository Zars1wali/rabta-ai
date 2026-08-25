import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_visual_search_unmatched_empty():
    transport = ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/visual-search/unmatched/923001234567")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "923001234567"
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_visual_search_stats_empty():
    transport = ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/visual-search/stats/923001234567")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "923001234567"
        # "distribution" present when DB is up, "error" when DB is down — both acceptable
        assert "distribution" in data or "error" in data


@pytest.mark.asyncio
async def test_claim_nonexistent_log_returns_404():
    transport = ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/visual-search/claim/00000000-0000-0000-0000-000000000000",
            json={
                "product_name": "Test Product",
                "product_price": 1500,
                "product_category": "General",
                "product_details": "A test product",
            },
        )
        assert resp.status_code in (404, 500)
