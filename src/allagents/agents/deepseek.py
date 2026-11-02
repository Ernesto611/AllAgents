"""DeepSeek: API de pago muy barata, compatible con OpenAI."""

from __future__ import annotations

from ..clients import openai_compat
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_PAID, delegate

NAME = "deepseek"
LOCAL = False
PRIORITY = 80
TIER = TIER_PAID
ROLE = "alternativa barata a ChatGPT para código y razonamiento; datos en China"
BASE_URL = "https://api.deepseek.com"


def status(settings: Settings) -> str | None:
    return None if settings.get("DEEPSEEK_API_KEY") else "falta DEEPSEEK_API_KEY en .env"


async def models(settings: Settings) -> list[str]:
    return await openai_compat.list_models(base_url=BASE_URL, api_key=settings.get("DEEPSEEK_API_KEY"))


def register(server, settings: Settings) -> None:
    default_model = settings.get("DEEPSEEK_MODEL", "deepseek-chat")

    @server.tool(name="ask_deepseek", annotations=CLOUD_TOOL)
    async def ask_deepseek(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """DeepSeek. Especialidad: buena calidad en código y razonamiento a muy bajo costo.

        Úsala como alternativa económica a ask_codex para código y razonamiento cuando
        convenga no gastar la cuota de ChatGPT.

        NO la uses nunca con datos sensibles: los datos se procesan y guardan en
        servidores de DeepSeek en China. Para eso, ask_ollama (que además tiene
        deepseek-coder-v2 en local).

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            model: opcional; deepseek-chat (por defecto) o deepseek-reasoner.
        """
        async def call(loaded):
            return await openai_compat.chat(
                agent=NAME, base_url=BASE_URL, api_key=settings.get("DEEPSEEK_API_KEY"),
                model=model or default_model, prompt=build_prompt(prompt, loaded),
                timeout_s=settings.timeout_s, secrets=settings.secrets)

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
