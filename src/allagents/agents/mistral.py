"""Mistral AI (Codestral): modelo especializado en código.

Si hay CODESTRAL_API_KEY se usa el endpoint dedicado de Codestral; si no,
la API general de Mistral con MISTRAL_API_KEY.
"""

from __future__ import annotations

from ..clients import openai_compat
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_FREE, delegate

NAME = "mistral"
LOCAL = False
PRIORITY = 30
TIER = TIER_FREE
ROLE = "especialista en código: revisión, Python, T-SQL/SQL Server, Docker, C#"
MISTRAL_URL = "https://api.mistral.ai/v1"
CODESTRAL_URL = "https://codestral.mistral.ai/v1"


def _endpoint(settings: Settings) -> tuple[str, str]:
    if settings.get("CODESTRAL_API_KEY"):
        return CODESTRAL_URL, settings.get("CODESTRAL_API_KEY")
    return MISTRAL_URL, settings.get("MISTRAL_API_KEY")


def status(settings: Settings) -> str | None:
    return None if _endpoint(settings)[1] else "falta MISTRAL_API_KEY o CODESTRAL_API_KEY en .env"


async def models(settings: Settings) -> list[str]:
    url, key = _endpoint(settings)
    return await openai_compat.list_models(base_url=url, api_key=key)


def register(server, settings: Settings) -> None:
    default_model = settings.get("MISTRAL_MODEL", "codestral-latest")

    @server.tool(name="ask_mistral", annotations=CLOUD_TOOL)
    async def ask_mistral(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """Mistral AI, modelo Codestral. Especialidad: entrenamiento específico en más de
        80 lenguajes de programación.

        Úsala para:
        - Revisar código complejo.
        - Escribir scripts en Python.
        - Diseñar consultas, procedimientos almacenados y triggers para SQL Server (T-SQL).
        - Resolver problemas de microservicios en Docker y C#/.NET.

        NO la uses con datos sensibles (p. ej. filas reales de tablas de clientes): envía
        solo esquemas y código. Para datos reales, ask_ollama.

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            model: opcional; por defecto MISTRAL_MODEL (codestral-latest).
        """
        async def call(loaded):
            url, key = _endpoint(settings)
            return await openai_compat.chat(
                agent=NAME, base_url=url, api_key=key, model=model or default_model,
                prompt=build_prompt(prompt, loaded), timeout_s=settings.timeout_s,
                secrets=settings.secrets)

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
