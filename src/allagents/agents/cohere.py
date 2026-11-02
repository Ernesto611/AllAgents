"""Cohere (Command R): contexto grande y RAG con citas.

Los ``files`` no se pegan en el prompt: se envían como documentos separados
de la API de Cohere, y la respuesta indica qué documento respalda cada parte.
"""

from __future__ import annotations

import time

from ..clients.http import HttpError, get_json, post_json
from ..config import Settings
from .base import CLOUD_TOOL, TIER_FREE, AgentResult, delegate

NAME = "cohere"
LOCAL = False
PRIORITY = 40
TIER = TIER_FREE
ROLE = "documentos largos con citas (RAG): logs extensos, configuraciones enormes, varios docs"
BASE_URL = "https://api.cohere.com"


def status(settings: Settings) -> str | None:
    return None if settings.get("COHERE_API_KEY") else "falta COHERE_API_KEY en .env"


def _headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.get('COHERE_API_KEY')}"}


async def models(settings: Settings) -> list[str]:
    data = await get_json(f"{BASE_URL}/v1/models?endpoint=chat", headers=_headers(settings),
                          timeout_s=30, secrets=settings.secrets)
    return sorted(m["name"] for m in data.get("models", []) if "name" in m)


def _citations(message: dict) -> str:
    sources: dict[str, set[str]] = {}
    for citation in message.get("citations") or []:
        for source in citation.get("sources") or []:
            doc_id = source.get("id") or (source.get("document") or {}).get("id", "?")
            sources.setdefault(doc_id, set()).add(citation.get("text", "").strip()[:80])
    if not sources:
        return ""
    lines = [f"- {doc}: {len(snippets)} fragmento(s) citado(s)" for doc, snippets in sources.items()]
    return "Fuentes citadas:\n" + "\n".join(lines)


def register(server, settings: Settings) -> None:
    default_model = settings.get("COHERE_MODEL", "command-r-08-2024")

    @server.tool(name="ask_cohere", annotations=CLOUD_TOOL)
    async def ask_cohere(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """Cohere, modelo Command R. Especialidad: ventana de contexto grande (hasta 128k
        tokens) y RAG: responde citando qué documento respalda cada afirmación.

        Úsala para:
        - Enviarle logs de errores muy largos.
        - Analizar archivos de configuración gigantes (como layouts bancarios SIN datos
          reales de clientes).
        - Leer múltiples documentos de documentación técnica de una sola vez y obtener
          respuestas con citas. Cada archivo de `files` se envía como documento aparte.

        Si el material supera ~128k tokens (~400 KB de texto), usa ask_agy.
        NO la uses con datos sensibles: layouts o logs con datos reales → ask_ollama.

        Args:
            prompt: la pregunta o tarea sobre los documentos.
            files: rutas ABSOLUTAS de los documentos (el servidor los lee).
            model: opcional; por defecto COHERE_MODEL.
        """
        use_model = model or default_model

        async def call(loaded):
            payload: dict = {"model": use_model,
                             "messages": [{"role": "user", "content": prompt}]}
            if loaded:
                payload["documents"] = [{"id": f.path, "data": {"title": f.path, "text": f.text}}
                                        for f in loaded]
            start = time.monotonic()
            data = await post_json(f"{BASE_URL}/v2/chat", payload, headers=_headers(settings),
                                   timeout_s=settings.timeout_s, secrets=settings.secrets)
            message = data.get("message") or {}
            parts = [c.get("text", "") for c in message.get("content") or [] if c.get("type") == "text"]
            if not parts:
                raise HttpError("respuesta inesperada de Cohere (sin texto)")
            tokens = (data.get("usage") or {}).get("tokens") or {}
            return AgentResult(agent=NAME, model=use_model, text="".join(parts),
                               duration_s=time.monotonic() - start,
                               input_tokens=tokens.get("input_tokens"),
                               output_tokens=tokens.get("output_tokens"),
                               footer=_citations(message))

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
