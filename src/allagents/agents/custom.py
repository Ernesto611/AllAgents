"""Agentes compatibles con OpenAI definidos solo con variables de entorno.

Sirve para cualquier servicio con API ``/chat/completions`` (OpenRouter,
Together, xAI, un LM Studio o vLLM local…) sin escribir código. Ejemplo:

    ALLAGENTS_CUSTOM=lmstudio
    LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
    LMSTUDIO_MODEL=qwen2.5-7b-instruct
    LMSTUDIO_LOCAL=true
    LMSTUDIO_ROLE=modelo local de LM Studio, alternativa a Ollama
    LMSTUDIO_DESCRIPTION=Modelo local en LM Studio. Úsala para … NO la uses para …

Reglas de seguridad: un agente ``LOCAL=true`` solo se acepta si su URL es de
loopback (los datos de verdad no salen del equipo); uno en la nube exige
HTTPS y clave (``<NOMBRE>_API_KEY``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..clients import openai_compat
from ..config import Settings
from ..files import build_prompt
from ..security import SecurityError, require_https, require_loopback
from .base import CLOUD_TOOL, COMMON_ARGS_DOC, LOCAL_TOOL, TIER_LOCAL, delegate

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


@dataclass(frozen=True)
class CustomAgent:
    NAME: str
    LOCAL: bool
    PRIORITY: int
    TIER: str
    ROLE: str
    error: str | None = None

    @property
    def prefix(self) -> str:
        return self.NAME.upper()

    def _base_url(self, settings: Settings) -> str:
        url = settings.get(f"{self.prefix}_BASE_URL")
        return require_loopback(url) if self.LOCAL else require_https(url)

    def status(self, settings: Settings) -> str | None:
        if self.error:
            return self.error
        p = self.prefix
        if not settings.get(f"{p}_BASE_URL"):
            return f"falta {p}_BASE_URL en .env"
        try:
            self._base_url(settings)
        except SecurityError as exc:
            return str(exc)
        if not settings.get(f"{p}_MODEL"):
            return f"falta {p}_MODEL en .env"
        if not self.LOCAL and not settings.get(f"{p}_API_KEY"):
            return f"falta {p}_API_KEY en .env"
        return None

    async def models(self, settings: Settings) -> list[str]:
        return await openai_compat.list_models(base_url=self._base_url(settings),
                                               api_key=settings.get(f"{self.prefix}_API_KEY"))

    def register(self, server, settings: Settings) -> None:
        p, name, local = self.prefix, self.NAME, self.LOCAL
        default_model = settings.get(f"{p}_MODEL")
        where = "Los datos NO salen del equipo." if local else \
            "NO la uses con datos sensibles (salen del equipo): para eso, ask_ollama."
        description = (settings.get(f"{p}_DESCRIPTION", f"Agente personalizado '{name}'. {self.ROLE}")
                       + f"\n\n{where}\n" + COMMON_ARGS_DOC)

        async def ask(prompt: str, files: list[str] | None = None, model: str = "") -> str:
            async def call(loaded):
                return await openai_compat.chat(
                    agent=name, base_url=self._base_url(settings),
                    api_key=settings.get(f"{p}_API_KEY"), model=model or default_model,
                    prompt=build_prompt(prompt, loaded), timeout_s=settings.timeout_s,
                    secrets=settings.secrets)

            return await delegate(name, settings, local=local, files=files, call=call)

        server.tool(name=f"ask_{name}", description=description,
                    annotations=LOCAL_TOOL if local else CLOUD_TOOL)(ask)


def load(settings: Settings, *, reserved: set[str]) -> list[CustomAgent]:
    agents = []
    for name in settings.custom_agents:
        error = None
        if not _NAME_RE.match(name):
            error = f"nombre no válido en ALLAGENTS_CUSTOM: {name!r} (minúsculas, números y _)"
        elif name in reserved:
            error = f"'{name}' ya es un agente integrado; elige otro nombre"
        p = name.upper()
        local = settings.get_bool(f"{p}_LOCAL")
        agents.append(CustomAgent(
            NAME=name, LOCAL=local, error=error,
            PRIORITY=settings.get_int(f"{p}_PRIORITY", 15 if local else 65),
            TIER=TIER_LOCAL if local else settings.get(f"{p}_TIER", "personalizado"),
            ROLE=settings.get(f"{p}_ROLE", "agente personalizado"),
        ))
    return agents
