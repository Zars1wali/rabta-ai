import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
import io


def _make_test_image(width=640, height=480, color=(128, 64, 32)):
    return Image.new("RGB", (width, height), color)


def _image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()




class TestEmbeddingService:
    @patch("app.services.embedding_service.genai")
    def test_embed_image_returns_vector(self, mock_genai):
        from app.services.embedding_service import EmbeddingService

        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        service = EmbeddingService()
        service.client = mock_client
        img = _make_test_image()
        img_bytes = _image_to_bytes(img)

        result = asyncio.run(service.embed_image(img_bytes))
        assert result is not None
        assert len(result) == 1536

    @patch("app.services.embedding_service.genai")
    def test_embed_text_returns_vector(self, mock_genai):
        from app.services.embedding_service import EmbeddingService

        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        service = EmbeddingService()
        service.client = mock_client
        result = asyncio.run(service.embed_text("Premium lawn suit"))
        assert result is not None
        assert len(result) == 1536


class TestConfidenceTiers:
    def test_confidence_tier_thresholds_ordered(self):
        from app.core.config import settings

        high = settings.VISUAL_MATCH_HIGH_THRESHOLD
        medium = settings.VISUAL_MATCH_MEDIUM_THRESHOLD
        low = settings.VISUAL_MATCH_LOW_THRESHOLD

        assert high > medium > low

        def get_tier(score):
            if score >= high:
                return "high"
            elif score >= medium:
                return "medium"
            elif score >= low:
                return "low"
            return "none"

        assert get_tier(0.9) == "high"
        assert get_tier(0.7) == "medium"
        assert get_tier(0.55) == "low"
        assert get_tier(0.3) == "none"
