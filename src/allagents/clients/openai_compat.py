"""Chat Completions compatible con OpenAI (Groq, Mistral, DeepSeek, OpenCode Zen y
los agentes personalizados de ALLAGENTS_CUSTOM)."""

from __future__ import annotations

import time

from ..agents.base import AgentResult
from .http import HttpError, get_json, post_json


def _auth(api_key: str) -> dict[str, str]:
    # Los servidores locales (LM Studio, vLLM…) suelen no pedir clave.
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def chat(*, agent: str, base_url: str, api_key: str, model: str, prompt: str,
               timeout_s: int, secrets: tuple[str, ...], json_mode: bool = False,
               system: str | None = None) -> AgentResult:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    payload: dict = {"model": model, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    start = time.monotonic()
    data = await post_json(f"{base_url}/chat/completions", payload, headers=_auth(api_key),
                           timeout_s=timeout_s, secrets=secrets)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise HttpError("respuesta inesperada de la API (sin choices)") from None
    usage = data.get("usage") or {}
    return AgentResult(agent=agent, model=data.get("model", model), text=text,
                       duration_s=time.monotonic() - start,
                       input_tokens=usage.get("prompt_tokens"),
                       output_tokens=usage.get("completion_tokens"))


async def list_models(*, base_url: str, api_key: str, timeout_s: int = 30) -> list[str]:
    data = await get_json(f"{base_url}/models", headers=_auth(api_key), timeout_s=timeout_s,
                          secrets=(api_key,) if api_key else ())
    return sorted(m["id"] for m in data.get("data", []) if "id" in m)
