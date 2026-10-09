from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings


class InvalidTokenError(Exception):
    pass


def create_access_token(claims: dict, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload = {**claims, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
