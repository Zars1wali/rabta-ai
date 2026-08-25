import logging
import httpx
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Meta error code reference (subset relevant to message sending)
_META_ERROR_CODES = {
    100: "Invalid parameter / token issue",
    130429: "Rate limit exceeded (API-level throttling)",
    131026: "Message undeliverable — user may have blocked or 24h window expired",
    131047: "Re-engagement message — 24h customer window expired, template required",
    132000: "Template param count mismatch",
    132001: "Template does not exist / not approved",
    133004: "Server busy — try again later",
    135000: "Generic send failure",
    368: "Rate limit / temporary ban on the WhatsApp account",
}


class WhatsAppService:
    def __init__(self):
        self.api_url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    async def send_text_message(self, to_phone: str, message: str) -> bool:
        """Sends a text message to a WhatsApp user using Meta Cloud API."""
        if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            logger.warning("[WhatsApp] Missing API keys. Simulating message output:\nTo: %s\nText: %s", to_phone, message)
            return True

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(self.api_url, json=payload, headers=self.headers)

                if response.status_code == 200:
                    logger.info("Message sent OK to %s (len=%d)", to_phone, len(message))
                    return True

                # Parse Meta error response for structured logging
                status = response.status_code
                try:
                    err_body = response.json()
                    err_code = err_body.get("error", {}).get("code", 0)
                    err_msg = err_body.get("error", {}).get("message", response.text[:200])
                    err_type = err_body.get("error", {}).get("type", "")
                    err_sub = err_body.get("error", {}).get("error_subcode", "")
                    human_desc = _META_ERROR_CODES.get(err_code, "Unknown error")
                except Exception:
                    err_code = 0
                    err_msg = response.text[:200]
                    err_type = ""
                    err_sub = ""
                    human_desc = ""

                logger.error(
                    "[WhatsApp] Send FAILED → to=%s status=%d meta_code=%d subcode=%s type=%s desc=%s msg=%s",
                    to_phone, status, err_code, err_sub, err_type, human_desc, err_msg,
                )

                # Rate limiting / banned — flag clearly so operators see it
                if err_code in (130429, 368):
                    logger.critical(
                        "[WhatsApp] RATE LIMIT / BAN detected (code=%d) for business number. "
                        "Check WhatsApp Manager quality rating immediately.", err_code
                    )

                # 24-hour window expired — free-form reply blocked
                if err_code in (131047, 131026):
                    logger.warning(
                        "[WhatsApp] 24-hour customer service window may have expired for %s. "
                        "Template message fallback needed.", to_phone
                    )

                return False

            except httpx.TimeoutException:
                logger.error("[WhatsApp] TIMEOUT sending to %s (10s exceeded)", to_phone)
                return False
            except httpx.ConnectError as e:
                logger.error("[WhatsApp] CONNECTION ERROR sending to %s: %s", to_phone, e)
                return False
            except Exception as e:
                logger.error("[WhatsApp] UNEXPECTED error sending to %s: %s", to_phone, e, exc_info=True)
                return False

    async def get_media_url(self, media_id: str) -> Optional[str]:
        """Fetches the download URL for audio/voice note or image media."""
        if not settings.WHATSAPP_ACCESS_TOKEN:
            return None

        url = f"https://graph.facebook.com/v21.0/{media_id}"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.json().get("url")
                logger.warning("[WhatsApp] Media URL fetch failed: %d %s", res.status_code, res.text[:100])
            except Exception as e:
                logger.error("[WhatsApp] Error retrieving media URL: %s", e)
        return None

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media bytes from WhatsApp Cloud API by media ID."""
        media_url = await self.get_media_url(media_id)
        if not media_url:
            return None

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.get(media_url, headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"})
                if res.status_code == 200:
                    logger.info("[WhatsApp] Downloaded media %s (%d bytes)", media_id, len(res.content))
                    return res.content
                logger.warning("[WhatsApp] Media download failed: %d", res.status_code)
            except Exception as e:
                logger.error("[WhatsApp] Error downloading media %s: %s", media_id, e)
        return None
