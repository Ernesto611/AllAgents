"""Google Antigravity CLI (agy): Gemini con la suscripción del usuario.

Confinamiento verificado (2026-11-02, agy en modo print):
- Sin estos ajustes agy escribe archivos sin pedir permiso. Por eso cada
  llamada corre en una carpeta temporal vacía que se borra al terminar.
- ``allowNonWorkspaceAccess=false``: no puede leer nada fuera de esa carpeta.
- ``deny command(*) / mcp(*)``: sin terminal ni servidores MCP.
- ``--sandbox``: sandbox de terminal de agy como capa extra.
- El prompt va por stdin (stream-json), no por argumentos: no aparece en
  ``ps`` y no tiene el límite de 128 KiB de argv.
- Nunca se usan ``--dangerously-skip-permissions`` ni ``--remote-control``.
"""

from __future__ import annotations

import json

from ..clients.cli import find_bin, isolated_workspace, run_cli
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_SUBSCRIPTION, AgentError, AgentResult, delegate

NAME = "agy"
LOCAL = False
PRIORITY = 50
TIER = TIER_SUBSCRIPTION
ROLE = "contexto enorme: archivos/logs gigantes, mucha documentación, segundas opiniones"

CONFINEMENT = json.dumps({
    "allowNonWorkspaceAccess": False,
    "permissions": {"deny": ["command(*)", "mcp(*)"]},
})


def _bin(settings: Settings) -> str:
    return find_bin(settings.get("AGY_BIN"), "agy", "AGY_BIN")


def status(settings: Settings) -> str | None:
    try:
        _bin(settings)
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    return None


async def models(settings: Settings) -> list[str]:
    async with isolated_workspace() as ws:
        res = await run_cli([_bin(settings), "models"], cwd=ws, timeout_s=60)
    return [line.split("\t")[0] for line in res.stdout.splitlines() if "\t" in line]


def _parse(stdout: str) -> dict:
    """Devuelve el evento ``result`` de la salida stream-json de agy."""
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event") == "result":
            return event.get("result") or {}
    raise AgentError("agy no devolvió un resultado")


def register(server, settings: Settings) -> None:
    default_model = settings.get("AGY_MODEL", "gemini-3.8-flash-medium")

    @server.tool(name="ask_agy", annotations=CLOUD_TOOL)
    async def ask_agy(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """Google Gemini vía agy. Incluido en la suscripción del usuario.

        Especialidad: ventana de contexto muy grande (mucho mayor que Command R) y buen
        razonamiento general.

        Úsala para:
        - Archivos o logs gigantes que no caben en otros modelos (prefiérela a Cohere
          cuando el material supere ~400 KB de texto).
        - Leer mucha documentación de una vez y resumirla.
        - Segundas opiniones de diseño y preguntas generales.

        NO la uses con datos sensibles (salen a Google): para eso, ask_ollama.
        Corre aislada: no ve tus archivos ni tu terminal, solo `prompt` y `files`.

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            model: opcional. Por defecto gemini-3.8-flash-medium. Otros: gemini-3.8-flash-high
                (más razonamiento), gemini-3.8-flash-low (más rápido), gpt-oss-120b-medium.
        """
        use_model = model or default_model

        async def call(loaded):
            message = json.dumps({"event": "user",
                                  "message": {"content": build_prompt(prompt, loaded)}})
            async with isolated_workspace() as ws:
                res = await run_cli(
                    [_bin(settings), "--model", use_model,
                     "--input-format", "stream-json", "--output-format", "stream-json",
                     "--print-timeout", f"{settings.timeout_s}s",
                     "--sandbox", "--disable-slash-commands", "--settings", CONFINEMENT],
                    cwd=ws, timeout_s=settings.timeout_s + 15, stdin_text=message + "\n")
            result = _parse(res.stdout)
            if result.get("status") != "SUCCESS":
                raise AgentError(result.get("error") or res.stderr[-400:] or "agy falló")
            if not result.get("response", "").strip():
                # Pasa cuando intentó una herramienta bloqueada por el confinamiento.
                raise AgentError("agy no produjo respuesta. " + (res.stderr.strip()[-400:]
                                 or "Reformula el prompt para que no necesite herramientas."))
            usage = result.get("usage") or {}
            return AgentResult(agent=NAME, model=use_model, text=result.get("response", ""),
                               duration_s=res.duration_s,
                               input_tokens=usage.get("input_tokens"),
                               output_tokens=usage.get("output_tokens"))

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
