"""OpenCode Zen: modelos gratuitos (DeepSeek v4.1 Flash Free, GLM, MiMo…) por API.

Se usa la API HTTP compatible con OpenAI y NO el CLI ``opencode``: en las
pruebas (2026-11-02) el CLI leía archivos, ejecutaba comandos y escribía sin
pedir permiso, y con ``"permission": {"*": "deny"}`` su herramienta
``execute`` seguía corriendo. Por API el modelo solo devuelve texto.

El cupo gratuito es muy bajo y compartido por todos los modelos gratuitos de
la cuenta (se agotó con ~10 llamadas): por eso tiene prioridad baja.
"""

from __future__ import annotations

from ..clients import openai_compat
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_FREE, delegate

NAME = "opencode"
LOCAL = False
PRIORITY = 60
TIER = f"{TIER_FREE} (cupo muy bajo)"
ROLE = "DeepSeek v4.1 Flash y otros modelos gratuitos; código y razonamiento general"
BASE_URL = "https://opencode.ai/zen/v1"


def status(settings: Settings) -> str | None:
    return None if settings.get("OPENCODE_API_KEY") else "falta OPENCODE_API_KEY en .env"


async def models(settings: Settings) -> list[str]:
    return await openai_compat.list_models(base_url=BASE_URL,
                                           api_key=settings.get("OPENCODE_API_KEY"))


def register(server, settings: Settings) -> None:
    default_model = settings.get("OPENCODE_MODEL", "deepseek-v4.1-flash-free")

    @server.tool(name="ask_opencode", annotations=CLOUD_TOOL)
    async def ask_opencode(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """OpenCode Zen, modelos gratuitos. Por defecto DeepSeek v4.1 Flash Free.

        Especialidad: código y razonamiento general sin coste.

        Úsala para: tareas de código o análisis cuando Ollama no da la calidad y no
        conviene gastar la cuota de ChatGPT (ask_codex).

        Límite: el cupo gratuito es MUY bajo y compartido entre todos los modelos
        gratuitos. Si responde "Free usage limit reached" (HTTP 429), no reintentes:
        usa otra herramienta.
        NO la uses con datos sensibles (salen del equipo): para eso, ask_ollama.

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            model: opcional. Otros gratuitos: glm-5.3-flash-free, mimo-v2.6-flash-free,
                nemotron-3.5-lightning-free.
        """
        async def call(loaded):
            return await openai_compat.chat(
                agent=NAME, base_url=BASE_URL, api_key=settings.get("OPENCODE_API_KEY"),
                model=model or default_model, prompt=build_prompt(prompt, loaded),
                timeout_s=settings.timeout_s, secrets=settings.secrets)

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
