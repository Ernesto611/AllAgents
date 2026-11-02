"""Groq: inferencia ultrarrápida en hardware LPU (API compatible con OpenAI)."""

from __future__ import annotations

from ..clients import openai_compat
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_FREE, delegate

NAME = "groq"
LOCAL = False
PRIORITY = 20
TIER = TIER_FREE
ROLE = "lo más rápido (<1 s): JSON, extracción de datos, scaffolding, baja latencia"
BASE_URL = "https://api.groq.com/openai/v1"


def status(settings: Settings) -> str | None:
    return None if settings.get("GROQ_API_KEY") else "falta GROQ_API_KEY en .env"


async def models(settings: Settings) -> list[str]:
    return await openai_compat.list_models(base_url=BASE_URL, api_key=settings.get("GROQ_API_KEY"))


def register(server, settings: Settings) -> None:
    default_model = settings.get("GROQ_MODEL", "qwen/qwen3.8-27b")

    @server.tool(name="ask_groq", annotations=CLOUD_TOOL)
    async def ask_groq(prompt: str, files: list[str] | None = None, json_mode: bool = False,
                       model: str = "") -> str:
        """Groq. Especialidad: velocidad de inferencia extrema mediante hardware LPU;
        responde en menos de un segundo.

        Úsala para:
        - Procesar y formatear JSON rápidamente (json_mode=True garantiza JSON válido;
          menciona "JSON" en el prompt).
        - Extraer datos estructurados de textos planos.
        - Generar andamiajes (scaffolding) de código repetitivo.
        - Cualquier tarea donde la latencia sea crítica.

        NO la uses con datos sensibles (salen a Groq) ni con archivos enormes: el plan
        gratuito limita los tokens por minuto. Para mucho texto, ask_agy o ask_cohere.

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            json_mode: True fuerza que la respuesta sea un objeto JSON válido.
            model: opcional. Por defecto qwen/qwen3.8-27b (el más rápido y el que menos
                tokens gasta). Para andamiaje o extracción más compleja:
                openai/gpt-oss-120b (razona antes de responder, ~1 s).
        """
        async def call(loaded):
            return await openai_compat.chat(
                agent=NAME, base_url=BASE_URL, api_key=settings.get("GROQ_API_KEY"),
                model=model or default_model, prompt=build_prompt(prompt, loaded),
                json_mode=json_mode, timeout_s=settings.timeout_s, secrets=settings.secrets)

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
