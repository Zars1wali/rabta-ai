import io
import logging
from typing import List, Optional
from google import genai
from google.genai import types
from PIL import Image
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Multimodal embedding generation using Gemini Embedding 2."""

    def __init__(self):
        self.model = settings.GEMINI_EMBEDDING_MODEL
        self.dimensions = settings.GEMINI_EMBEDDING_DIM
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            self.client = None
            logger.warning("[EmbeddingService] GEMINI_API_KEY not set.")

    def _prepare_image_bytes(self, image_bytes: bytes) -> bytes:
        """Normalize image to RGB JPEG for consistent embedding input."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            max_side = max(img.size)
            if max_side > 1024:
                ratio = 1024 / max_side
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        except Exception as e:
            logger.warning("[EmbeddingService] Image normalization failed, using raw bytes: %s", e)
            return image_bytes

    async def embed_image(self, image_bytes: bytes) -> Optional[List[float]]:
        """Generate embedding vector for a single image."""
        if not self.client:
            return None
        try:
            prepared = self._prepare_image_bytes(image_bytes)
            response = self.client.models.embed_content(
                model=self.model,
                contents=types.Part.from_bytes(data=prepared, mime_type="image/jpeg"),
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error("[EmbeddingService] Image embedding failed: %s", e, exc_info=True)
            return None

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text."""
        if not self.client:
            return None
        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error("[EmbeddingService] Text embedding failed: %s", e, exc_info=True)
            return None

    async def embed_images_batch(self, image_bytes_list: List[bytes]) -> List[Optional[List[float]]]:
        """Embed a batch of images. Returns list of vectors (None for failures)."""
        results = []
        for img_bytes in image_bytes_list:
            vec = await self.embed_image(img_bytes)
            results.append(vec)
        return results


embedding_service = EmbeddingService()
