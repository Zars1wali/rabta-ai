import pytest
from PIL import Image, ImageFilter
import io
from unittest.mock import patch
from app.services.image_preprocessor import (
    preprocess_image,
    extract_individual_products,
    _crop_region,
    _compute_blur_score,
    DetectedRegion,
)


def _make_test_image(width=640, height=480, color=(128, 64, 32)):
    return Image.new("RGB", (width, height), color)


def _image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPreprocess:
    def test_invalid_bytes_never_crashes(self):
        res = preprocess_image(b"not an image at all")
        assert res.crop_method == "none"
        assert res.original_image == b"not an image at all"

    def test_heuristic_crop_when_no_detections(self):
        img = _make_test_image(640, 480)
        with patch("app.services.image_preprocessor._detect_regions_yolo", return_value=[]):
            res = preprocess_image(_image_to_bytes(img))
        assert res.crop_method == "heuristic"
        assert len(res.regions) == 0
        assert res.original_image != res.cropped_image

    def test_large_image_downscaled_to_max_1024(self):
        with patch("app.services.image_preprocessor._detect_regions_yolo", return_value=[]):
            res = preprocess_image(_image_to_bytes(_make_test_image(2000, 1500)))
        w = Image.open(io.BytesIO(res.original_image)).width
        assert w <= 1024

    def test_single_region_uses_yolo_crop(self):
        regions = [DetectedRegion(bbox=(10, 10, 300, 300), class_name="gun", confidence=0.9, area_ratio=0.28)]
        img = _make_test_image()
        with patch("app.services.image_preprocessor._detect_regions_yolo", return_value=regions):
            res = preprocess_image(_image_to_bytes(img))
        assert res.crop_method == "yolo"
        assert res.regions[0].confidence == 0.9

    def test_three_significant_regions_flagged_multi_product(self):
        regions = [
            DetectedRegion(bbox=(10, 10, 200, 150), class_name="gun", confidence=0.9, area_ratio=0.2),
            DetectedRegion(bbox=(210, 10, 400, 150), class_name="rifle", confidence=0.8, area_ratio=0.2),
            DetectedRegion(bbox=(410, 10, 600, 150), class_name="pistol", confidence=0.7, area_ratio=0.2),
        ]
        img = _make_test_image()
        with patch("app.services.image_preprocessor._detect_regions_yolo", return_value=regions):
            res = preprocess_image(_image_to_bytes(img))
        assert res.is_multi_product is True
        assert res.crop_method == "yolo"


class TestExtractIndividualProducts:
    def test_empty_regions(self):
        assert extract_individual_products(_image_to_bytes(_make_test_image()), []) == []

    def test_extracts_all_regions(self):
        regions = [
            DetectedRegion(bbox=(10, 10, 200, 150), class_name="gun", confidence=0.9, area_ratio=0.1),
            DetectedRegion(bbox=(210, 10, 400, 150), class_name="rifle", confidence=0.8, area_ratio=0.1),
        ]
        crops = extract_individual_products(_image_to_bytes(_make_test_image(640, 480)), regions)
        assert len(crops) == 2


class TestBlurScore:
    def test_sharp_scored_higher_than_blurred(self):
        import numpy as np
        rng = np.random.default_rng(42)
        arr = rng.integers(0, 255, (120, 120, 3), dtype=np.uint8)
        sharp = Image.fromarray(arr, "RGB")
        blurry = sharp.filter(ImageFilter.GaussianBlur(radius=5))
        assert _compute_blur_score(sharp) > _compute_blur_score(blurry)


class TestCropRegion:
    def test_crops_with_padding_within_bounds(self):
        img = _make_test_image(640, 480)
        cropped = _crop_region(img, (10, 10, 300, 300))
        assert cropped.size[0] <= 640
        assert cropped.size[1] <= 480

    def test_bbox_beyond_image_clamped(self):
        img = _make_test_image(640, 480)
        cropped = _crop_region(img, (200, 200, 10000, 10000))
        assert cropped.size == img.size or (cropped.size[0] <= 640 and cropped.size[1] <= 480)