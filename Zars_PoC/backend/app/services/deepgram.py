import logging
import httpx
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepgramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.api_url = "https://api.deepgram.com/v1/listen"

    def _headers(self) -> dict:
        return {"Authorization": f"Token {self.api_key}"}

    def _params(self) -> dict:
        return {
            "model": "nova-3",
            "language": "ur",       # Urdu primary — Deepgram handles code-switching with English
            "smart_format": "true",
            "punctuate": "true",
        }

    async def transcribe_audio_bytes(self, audio_bytes: bytes, mime_type: str = "audio/ogg; codecs=opus") -> Optional[str]:
        """Transcribes raw audio bytes (WhatsApp voice notes) using Deepgram nova-2.
        
        Baileys downloads audio as raw bytes (OGG Opus). We POST them directly
        to Deepgram's streaming endpoint with the correct Content-Type header.
        """
        if not self.api_key:
            logger.warning("[Deepgram] No API key configured. Skipping voice transcription.")
            return None

        # Normalize mime — WhatsApp uses 'audio/ogg; codecs=opus' but Deepgram prefers 'audio/ogg'
        clean_mime = mime_type.split(";")[0].strip() if mime_type else "audio/ogg"

        headers = {**self._headers(), "Content-Type": clean_mime}
        params = self._params()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.api_url, content=audio_bytes, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    transcript = (
                        data.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    logger.info("[Deepgram] Transcription success: '%s'", transcript[:100])
                    return transcript
                else:
                    logger.error("[Deepgram] HTTP %s: %s", res.status_code, res.text[:200])
            except Exception as e:
                logger.error("[Deepgram] Request exception: %s", e)
        return None

    async def transcribe_audio_url(self, audio_url: str, mime_type: str = "audio/ogg") -> Optional[str]:
        """Transcribes WhatsApp voice notes from a public URL (legacy webhook path)."""
        if not self.api_key:
            logger.warning("[Deepgram] No API key provided. Skipping transcription.")
            return None

        headers = {**self._headers(), "Content-Type": "application/json"}
        payload = {"url": audio_url}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.api_url, json=payload, headers=headers, params=self._params())
                if res.status_code == 200:
                    data = res.json()
                    transcript = (
                        data.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    return transcript
                else:
                    logger.error("Deepgram transcription failed: %s - %s", res.status_code, res.text)
            except Exception as e:
                logger.error("Deepgram request exception: %s", e)
        return None
