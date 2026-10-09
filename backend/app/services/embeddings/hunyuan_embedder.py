"""Tencent Hunyuan embedding backend (the primary path per readme.txt /
feedback.txt). NOT exercised against a real Tencent Cloud account here — no
TENCENT_SECRET_ID/KEY were available. Smoke-test before relying on it.
"""

from app.core.config import settings


class HunyuanEmbedder:
    def __init__(self, dim: int | None = None):
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.hunyuan.v20230901 import hunyuan_client

        self.dim = dim or settings.embedding_dim

        cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "hunyuan.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = hunyuan_client.HunyuanClient(cred, "ap-singapore", client_profile)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from tencentcloud.hunyuan.v20230901 import models

        vectors = []
        for text in texts:
            req = models.GetEmbeddingRequest()
            req.Input = text
            resp = self._client.GetEmbedding(req)
            vectors.append(resp.Data[0].Embedding)
        return vectors
