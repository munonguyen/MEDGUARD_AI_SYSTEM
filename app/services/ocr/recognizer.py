"""Stage 2: Vietnamese Line Recognition (VietOCR).

Takes cropped text region bounding boxes and produces Unicode Vietnamese text
along with line-level recognition confidence scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.ocr.detector import TextBox
from app.services.ocr.errors import OcrPipelineError


@dataclass
class RecognizedLine:
    line_index: int
    text: str
    confidence: float
    bbox: list[int]


class VietnameseLineRecognizer:
    """VietOCR adapter that fails closed when the engine is unavailable."""

    def __init__(self) -> None:
        self._predictor: Any = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            from vietocr.tool.config import Cfg
            from vietocr.tool.predictor import Predictor
            config = Cfg.load_config_from_name("vgg_transformer")
            config["device"] = "cpu"
            self._predictor = Predictor(config)
        except Exception:
            self._predictor = None

    @property
    def is_real_engine_available(self) -> bool:
        return self._predictor is not None

    def recognize_lines(self, image_bytes: bytes, boxes: list[TextBox]) -> list[RecognizedLine]:
        """Recognizes text lines corresponding to detected bounding boxes."""
        if not boxes:
            return []

        if not self._predictor:
            raise OcrPipelineError("ocr_recognizer_unavailable")

        try:
            import io
            from PIL import Image
            full_img = Image.open(io.BytesIO(image_bytes))
            lines: list[RecognizedLine] = []
            for box in boxes:
                x1, y1, x2, y2 = box.bbox
                cropped = full_img.crop((x1, y1, x2, y2))
                text, prob = self._predictor.predict(cropped, return_prob=True)
                lines.append(
                    RecognizedLine(
                        line_index=box.line_index,
                        text=text.strip(),
                        confidence=float(prob),
                        bbox=box.bbox,
                    )
                )
            return lines
        except OcrPipelineError:
            raise
        except Exception as exc:
            raise OcrPipelineError("ocr_recognition_failed") from exc


line_recognizer = VietnameseLineRecognizer()
