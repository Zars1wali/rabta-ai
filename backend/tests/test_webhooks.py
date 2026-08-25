import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_whatsapp_webhook_verification():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "challenge_code_12345",
        }
        response = await client.get("/webhooks/whatsapp", params=params)
        assert response.status_code == 200
        assert response.text == "challenge_code_12345"
