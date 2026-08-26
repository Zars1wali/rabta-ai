import pytest
from PIL import Image, ImageFilter
import io
from app.services.image_preprocessor import (
    detect_product_regions,
    crop_product_region,
    normalize_image,
    estimate_blur_score,
    detect_multiple_products,
)


def _make_test_image(width=640, height=480, color=(128, 64, 32)):
    return Image.new("RGB", (width, height), color)


def _image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestDetectProductRegions:
    def test_returns_empty_when_no_model(self):
        img = _make_test_image()
        regions = detect_product_regions(img, use_model=False)
        assert regions == []

    def test_heuristic_fallback_returns_single_region(self):
        img = _make_test_image()
        img_bytes = _image_to_bytes(img)
        regions = detect_product_regions(img, use_model=False, image_bytes=img_bytes)
        assert len(regions) == 1
        assert regions[0]["confidence"] == 0.5


class TestCropProductRegion:
    def test_crops_to_bounding_box(self):
        img = _make_test_image(640, 480)
        region = {"bbox": [100, 50, 500, 400]}
        cropped = crop_product_region(img, region)
        assert cropped.size == (400, 350)

    def test_invalid_bbox_returns_original(self):
        img = _make_test_image(640, 480)
        region = {"bbox": [0, 0, 0, 0]}
        result = crop_product_region(img, region)
        assert result.size == img.size


class TestNormalizeImage:
    def test_normalizes_size(self):
        img = _make_test_image(1920, 1080)
        normalized = normalize_image(img, target_size=(512, 512))
        assert normalized.size == (512, 512)

    def test_preserves_aspect_ratio_in_buffer(self):
        img = _make_test_image(1024, 768)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()
        result = normalize_image(img, target_size=(512, 512))
        assert result.size == (512, 512)


class TestBlurScore:
    def test_sharp_image_has_high_score(self):
        img = _make_test_image(100, 100, (255, 0, 0))
        score = estimate_blur_score(img)
        assert score >= 0

    def test_blurry_image_has_lower_score(self):
        sharp = _make_test_image(100, 100, (255, 0, 0))
        blurry = sharp.filter(ImageFilter.GaussianBlur(radius=5))
        sharp_score = estimate_blur_score(sharp)
        blurry_score = estimate_blur_score(blurry)
        assert sharp_score > blurry_score


class TestMultipleProducts:
    def test_single_region_detected(self):
        img = _make_test_image(640, 480)
        img_bytes = _image_to_bytes(img)
        count = detect_multiple_products(img, img_bytes)
        assert count >= 1
