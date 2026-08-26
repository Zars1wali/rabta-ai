import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from PIL import Image, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-load YOLO model to avoid import at module level
_yolo_model = None


def _get_yolo():
    """Lazy-load YOLOv8-nano. Downloads weights on first call."""
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            _yolo_model = YOLO("yolov8n.pt")
            logger.info("[Preprocessor] YOLOv8-nano loaded successfully.")
        except Exception as e:
            logger.error("[Preprocessor] Failed to load YOLOv8-nano: %s", e)
    return _yolo_model


# COCO classes that typically represent products (retail-relevant)
PRODUCT_CLASSES = {
    "bottle", "cup", "bowl", "banana", "apple", "orange", "cake",
    "chair", "couch", "bed", "dining table", "toilet",
    "tv", "laptop", "mouse", "keyboard", "cell phone", "remote",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove",
    "wine glass", "fork", "knife", "spoon",
    "refrigerator", "microwave", "oven", "toaster", "sink",
    "potted plant", "backpack", "umbrella",
}

# Classes to explicitly skip (people, animals, vehicles)
SKIP_CLASSES = {"person", "cat", "dog", "horse", "sheep", "cow",
                "elephant", "bear", "zebra", "giraffe",
                "car", "truck", "bus", "motorcycle", "bicycle",
                "airplane", "train", "boat"}


@dataclass
class DetectedRegion:
    """A detected product region in an image."""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    class_name: str
    confidence: float
    area_ratio: float  # fraction of total image area


@dataclass
class PreprocessingResult:
    """Output of the image preprocessing pipeline."""
    original_image: bytes
    cropped_image: bytes
    regions: List[DetectedRegion] = field(default_factory=list)
    is_multi_product: bool = False
    crop_method: str = "none"  # "yolo", "heuristic", "none"


def _compute_blur_score(img: Image.Image) -> float:
    """Compute blur metric using Laplacian variance. Lower = blurrier."""
    gray = img.convert("L")
    laplacian = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
        scale=1, offset=0,
    ))
    arr = np.array(laplacian, dtype=np.float64)
    return float(arr.var())


def _detect_regions_yolo(image_bytes: bytes) -> List[DetectedRegion]:
    """Run YOLOv8-nano object detection and return product regions."""
    model = _get_yolo()
    if model is None:
        return []

    try:
        results = model.predict(
            source=io.BytesIO(image_bytes),
            verbose=False,
            conf=0.25,
            imgsz=640,
        )
    except Exception as e:
        logger.warning("[Preprocessor] YOLO predict failed: %s", e)
        return []

    if not results or len(results) == 0:
        return []

    result = results[0]
    img = Image.open(io.BytesIO(image_bytes))
    total_area = img.width * img.height
    regions = []

    for box in result.boxes:
        cls_id = int(box.cls[0])
        class_name = result.names.get(cls_id, "")
        conf = float(box.conf[0])

        if class_name in SKIP_CLASSES:
            continue

        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        area = (x2 - x1) * (y2 - y1)
        area_ratio = area / total_area if total_area > 0 else 0

        if area_ratio < 0.03:
            continue

        regions.append(DetectedRegion(
            bbox=(x1, y1, x2, y2),
            class_name=class_name,
            confidence=conf,
            area_ratio=area_ratio,
        ))

    regions.sort(key=lambda r: r.area_ratio, reverse=True)
    return regions


def _crop_region(img: Image.Image, bbox: Tuple[int, int, int, int], padding: float = 0.10) -> Image.Image:
    """Crop to a bounding box with padding."""
    x1, y1, x2, y2 = bbox
    w, h = img.size
    pad_w = int((x2 - x1) * padding)
    pad_h = int((y2 - y1) * padding)
    cx1 = max(0, x1 - pad_w)
    cy1 = max(0, y1 - pad_h)
    cx2 = min(w, x2 + pad_w)
    cy2 = min(h, y2 + pad_h)
    return img.crop((cx1, cy1, cx2, cy2))


def _heuristic_crop(img: Image.Image) -> Image.Image:
    """Fallback: crop top/bottom 15% to remove UI chrome (status bars, nav)."""
    w, h = img.size
    top = int(h * 0.15)
    bottom = int(h * 0.85)
    return img.crop((0, top, w, bottom))


def preprocess_image(image_bytes: bytes) -> PreprocessingResult:
    """
    Main preprocessing pipeline.
    Returns original + cropped image bytes, detected regions, and metadata.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
    except Exception as e:
        logger.error("[Preprocessor] Cannot open image: %s", e)
        return PreprocessingResult(
            original_image=image_bytes,
            cropped_image=image_bytes,
            crop_method="none",
        )

    max_side = max(img.size)
    if max_side > 1024:
        ratio = 1024 / max_side
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    buf_orig = io.BytesIO()
    img.save(buf_orig, format="JPEG", quality=90)
    original_bytes = buf_orig.getvalue()

    regions = _detect_regions_yolo(original_bytes)

    if len(regions) >= 3:
        significant = [r for r in regions if r.area_ratio >= 0.08]
        if len(significant) >= 3:
            logger.info("[Preprocessor] Multi-product detected: %d regions", len(significant))
            return PreprocessingResult(
                original_image=original_bytes,
                cropped_image=original_bytes,
                regions=regions,
                is_multi_product=True,
                crop_method="yolo",
            )

    if regions:
        best = regions[0]
        cropped = _crop_region(img, best.bbox)
        buf_crop = io.BytesIO()
        cropped.save(buf_crop, format="JPEG", quality=90)
        logger.info("[Preprocessor] YOLO crop: class=%s conf=%.2f area=%.1f%%",
                     best.class_name, best.confidence, best.area_ratio * 100)
        return PreprocessingResult(
            original_image=original_bytes,
            cropped_image=buf_crop.getvalue(),
            regions=regions,
            crop_method="yolo",
        )

    cropped = _heuristic_crop(img)
    buf_crop = io.BytesIO()
    cropped.save(buf_crop, format="JPEG", quality=90)
    logger.info("[Preprocessor] Heuristic crop (no YOLO detections)")
    return PreprocessingResult(
        original_image=original_bytes,
        cropped_image=buf_crop.getvalue(),
        crop_method="heuristic",
    )


def extract_individual_products(image_bytes: bytes, regions: List[DetectedRegion]) -> List[bytes]:
    """For multi-product images, extract each detected region as a separate image."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")

    crops = []
    for region in regions:
        if region.area_ratio < 0.05:
            continue
        cropped = _crop_region(img, region.bbox, padding=0.15)
        buf = io.BytesIO()
        cropped.save(buf, format="JPEG", quality=90)
        crops.append(buf.getvalue())
    return crops
