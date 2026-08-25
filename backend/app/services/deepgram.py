import logging
import httpx
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepgramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.api_url = "https://api.deepgram.com/v1/listen"

    async def transcribe_audio_url(self, audio_url: str, mime_type: str = "audio/ogg") -> Optional[str]:
        """Transcribes WhatsApp voice notes (Urdu / English) using Deepgram's multi-lingual speech model."""
        if not self.api_key:
            logger.warning("[Deepgram] No API key provided. Skipping transcription.")
            return None

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

        # Query params: detect Urdu and English code-switching
        params = {
            "model": "nova-2",
            "language": "ur",  # Urdu with English loan words
            "smart_format": "true",
            "punctuate": "true",
        }

        payload = {"url": audio_url}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.api_url, json=payload, headers=headers, params=params)
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
