"""Cliente HTTP endurecido para las APIs de los agentes.

- TLS verificado siempre; sin seguir redirecciones (la clave no viaja a otro host).
- ``trust_env=False``: ignora proxies de variables de entorno y ``~/.netrc``.
- Los errores se devuelven sin la clave y recortados.
"""

from __future__ import annotations

from typing import Any

import httpx2

from ..security import redact


class HttpError(Exception):
    pass


def _client(timeout_s: int) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(timeout=timeout_s, verify=True, follow_redirects=False,
                              trust_env=False)


def _check(response: httpx2.Response, secrets: tuple[str, ...]) -> Any:
    if response.status_code >= 400:
        body = redact(response.text[:600], secrets)
        raise HttpError(f"HTTP {response.status_code}: {body}")
    try:
        return response.json()
    except ValueError:
        raise HttpError("la respuesta no es JSON válido") from None


async def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str],
                    timeout_s: int, secrets: tuple[str, ...] = ()) -> Any:
    try:
        async with _client(timeout_s) as client:
            return _check(await client.post(url, json=payload, headers=headers), secrets)
    except httpx2.TimeoutException:
        raise HttpError(f"tiempo agotado tras {timeout_s}s") from None
    except httpx2.HTTPError as exc:
        raise HttpError(redact(f"{type(exc).__name__}: {exc}", secrets)) from None


async def get_json(url: str, *, headers: dict[str, str], timeout_s: int,
                   secrets: tuple[str, ...] = ()) -> Any:
    try:
        async with _client(timeout_s) as client:
            return _check(await client.get(url, headers=headers), secrets)
    except httpx2.TimeoutException:
        raise HttpError(f"tiempo agotado tras {timeout_s}s") from None
    except httpx2.HTTPError as exc:
        raise HttpError(redact(f"{type(exc).__name__}: {exc}", secrets)) from None
