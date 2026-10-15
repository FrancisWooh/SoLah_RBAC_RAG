#!/usr/bin/env python3
"""Quick test: can the Tencent CAM credentials call the Hunyuan embedding API?"""

import os
import sys

def main():
    secret_id = os.getenv("TENCENT_SECRET_ID", "")
    secret_key = os.getenv("TENCENT_SECRET_KEY", "")

    if not secret_id or not secret_key:
        print("FAIL: TENCENT_SECRET_ID or TENCENT_SECRET_KEY not set")
        sys.exit(1)

    print(f"SecretId: {secret_id[:6]}...")
    print(f"SecretKey: {secret_key[:4]}...")

    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "hunyuan.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client = hunyuan_client.HunyuanClient(cred, "ap-singapore", client_profile)

        req = models.GetEmbeddingRequest()
        req.Input = "test embedding"
        resp = client.GetEmbedding(req)

        vec = resp.Data[0].Embedding
        dim = len(vec)
        print(f"OK: Got embedding, dim={dim}")
        print(f"First 5 values: {vec[:5]}")
        print("CAM credentials work for Hunyuan embedding API")

    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
