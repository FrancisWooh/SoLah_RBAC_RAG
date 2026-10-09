"""Local/offline OCR backend — real, working, verified in this environment
(see task.txt M9 notes: rendered a Chinese test image with Pillow, OCR'd it,
got an exact match back). Substituted for readme.txt's original
"PaddleOCR（本地）" suggestion: PaddleOCR pulls in the full PaddlePaddle
framework plus model downloads, which is heavy for this sandbox and risky to
get reliably working; Tesseract + chi_sim is far lighter, still a genuine
local OCR engine (not a stub), and installs cleanly via apt (see Dockerfile).
Chinese handwriting recognition quality is mediocre compared to a real
handwriting-tuned model like PaddleOCR — fine for the demo's printed-style
note, not a production-grade substitute.
"""

import io

import pytesseract
from PIL import Image


class TesseractOCR:
    def __init__(self, lang: str = "chi_sim+eng"):
        self.lang = lang

    def extract_text(self, image_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image, lang=self.lang).strip()
