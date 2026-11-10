"""Clave de API para /v2 (D15: túnel WireGuard + clave de API).

Cabecera `Authorization: Bearer <clave>` o `X-API-Key: <clave>`. Si
LLM_API_KEYS está vacía no se exige clave (solo para desarrollo; el
arranque lo avisa en el log).
"""

import hmac

from fastapi import HTTPException, Request, status

from app.config import settings


def _presented(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


async def require_api_key(request: Request) -> None:
    keys = settings.api_key_set
    if not keys:
        return
    given = _presented(request)
    if not given or not any(hmac.compare_digest(given, k) for k in keys):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="clave de API no válida",
                            headers={"WWW-Authenticate": "Bearer"})
