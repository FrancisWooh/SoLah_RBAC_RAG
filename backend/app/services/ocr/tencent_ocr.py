"""Tencent Cloud OCR (GeneralBasicOCR) — the primary backend per readme.txt.
NOT exercised against a real Tencent Cloud account here — no
TENCENT_SECRET_ID/KEY were available. Request/response field names
(ImageBase64, TextDetections[].DetectedText) are confirmed against the
installed tencentcloud-sdk-python-ocr package's own docstrings, same as the
other Tencent adapters, but the live call itself is untested.
"""

import base64

from app.core.config import settings


class TencentOCR:
    def __init__(self):
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.ocr.v20181119 import ocr_client

        cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = ocr_client.OcrClient(cred, "ap-singapore", client_profile)

    def extract_text(self, image_bytes: bytes) -> str:
        from tencentcloud.ocr.v20181119 import models

        req = models.GeneralBasicOCRRequest()
        req.ImageBase64 = base64.b64encode(image_bytes).decode("ascii")
        req.LanguageType = "zh"

        resp = self._client.GeneralBasicOCR(req)
        return "\n".join(d.DetectedText for d in resp.TextDetections)
