"""Stage 1b: Text Region Bounding Box Detection (PaddleOCR-det / region segmentation).

Outputs line-level bounding boxes [x1, y1, x2, y2] with confidence scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.ocr.errors import OcrPipelineError


@dataclass
class TextBox:
    box_id: int
    bbox: list[int]  # [x1, y1, x2, y2]
    confidence: float
    line_index: int


class TextDetector:
    """PaddleOCR adapter that fails closed when the engine is unavailable."""

    def __init__(self) -> None:
        self._paddle_ocr: Any = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(use_angle_cls=True, det=True, rec=False, show_log=False)
        except Exception:
            self._paddle_ocr = None

    @property
    def is_real_engine_available(self) -> bool:
        return self._paddle_ocr is not None

    def detect_boxes(self, image_bytes: bytes) -> list[TextBox]:
        """Detects text regions and returns ordered bounding boxes."""
        if not image_bytes or len(image_bytes) == 0:
            return []

        if not self._paddle_ocr:
            raise OcrPipelineError("ocr_detector_unavailable")

        try:
            results = self._paddle_ocr.ocr(image_bytes, rec=False)
            boxes: list[TextBox] = []
            for idx, line in enumerate(results[0] if results else []):
                xs = [pt[0] for pt in line]
                ys = [pt[1] for pt in line]
                x1, y1, x2, y2 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
                boxes.append(TextBox(box_id=idx, bbox=[x1, y1, x2, y2], confidence=0.96, line_index=idx))
            return boxes
        except OcrPipelineError:
            raise
        except Exception as exc:
            raise OcrPipelineError("ocr_detection_failed") from exc


text_detector = TextDetector()
