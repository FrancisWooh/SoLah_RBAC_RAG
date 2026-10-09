from functools import lru_cache

from app.core.config import settings
from app.services.ocr.base import OCREngine


@lru_cache
def get_ocr_engine() -> OCREngine:
    if settings.ocr_backend == "tencent":
        from app.services.ocr.tencent_ocr import TencentOCR

        return TencentOCR()

    from app.services.ocr.tesseract_ocr import TesseractOCR

    return TesseractOCR()
