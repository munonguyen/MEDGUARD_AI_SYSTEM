class OcrPipelineError(RuntimeError):
    """Stable, non-sensitive failure returned by the OCR orchestration layer."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def ocr_error_code(exc: Exception) -> str:
    if isinstance(exc, OcrPipelineError):
        return exc.code
    return "ocr_processing_failed"
