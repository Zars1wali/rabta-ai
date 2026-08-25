import logging
from typing import Optional
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """Extract visible text from customer images using Gemini Vision."""

    def __init__(self):
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            self.client = None

    async def extract_text(self, image_bytes: bytes) -> Optional[str]:
        """
        Send image to Gemini and extract any visible text —
        hashtags, captions, brand names, prices, product labels.
        Returns extracted text or None if nothing found / on error.
        """
        if not self.client:
            return None

        try:
            response = await genai.aio.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    "Extract ONLY the visible text from this image. Include hashtags, "
                    "brand names, prices, product labels, captions, and any other readable text. "
                    "Return just the extracted text, separated by newlines. "
                    "If there is no readable text, return exactly: NONE",
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=200,
                ),
            )
            text = response.text.strip() if response.text else ""
            if text.upper() == "NONE" or not text:
                return None
            return text

        except Exception as e:
            logger.warning("[OCR] Extraction failed: %s", e)
            return None


ocr_service = OCRService()
