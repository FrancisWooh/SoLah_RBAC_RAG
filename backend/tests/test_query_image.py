"""Scenario 4: image upload -> real Tesseract OCR -> same RBAC-filtered
query pipeline as /text. Test images are rendered with Pillow (no real
scanned photo available), using the CJK font installed in the backend image
(see Dockerfile) — this is genuine OCR, not a mocked/stubbed result.
"""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.db import get_db
from app.main import app

FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def _render_text_image(text: str) -> bytes:
    font = ImageFont.truetype(FONT_PATH, 40)
    img = Image.new("RGB", (700, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session
    yield test_client
    app.dependency_overrides.clear()


def _login(client, username: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_scenario_four_image_query_is_allowed_for_authorized_role(client):
    token = _login(client, "alice")
    image_bytes = _render_text_image("CASA账户的KYC要求")

    resp = client.post(
        "/api/query/image",
        headers=_auth(token),
        files={"file": ("note.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "CASA" in body["recognized_text"]
    assert body["decision"] == "allow"
    assert "doc_casa_kyc_requirements" in {c["doc_id"] for c in body["citations"]}


def test_image_query_is_denied_outside_requester_domain(client):
    token = _login(client, "alice")
    image_bytes = _render_text_image("客户投诉处理SOP")

    resp = client.post(
        "/api/query/image",
        headers=_auth(token),
        files={"file": ("note.png", image_bytes, "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "deny"
    assert body["citations"] == []


def test_blank_image_is_handled_without_hitting_rbac_pipeline(client):
    token = _login(client, "alice")
    blank = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    blank.save(buf, format="PNG")

    resp = client.post(
        "/api/query/image",
        headers=_auth(token),
        files={"file": ("blank.png", buf.getvalue(), "image/png")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["recognized_text"] == ""
    assert body["citations"] == []


def test_image_query_requires_auth(client):
    image_bytes = _render_text_image("test")
    resp = client.post(
        "/api/query/image", files={"file": ("note.png", image_bytes, "image/png")}
    )
    assert resp.status_code in (401, 403)


def test_oversized_image_is_rejected(client, monkeypatch):
    import app.api.query as query_module

    monkeypatch.setattr(query_module, "MAX_IMAGE_BYTES", 10)
    token = _login(client, "alice")
    image_bytes = _render_text_image("test")

    resp = client.post(
        "/api/query/image",
        headers=_auth(token),
        files={"file": ("note.png", image_bytes, "image/png")},
    )
    assert resp.status_code == 413
