"""Piezas comunes a todos los agentes.

Contrato de un agente (módulo en este paquete u objeto de custom.py):
  NAME        nombre corto: herramienta ``ask_<NAME>``, ALLAGENTS_DISABLE, CLI.
  LOCAL       True solo si los datos no salen del equipo.
  PRIORITY    orden por defecto (menor = se prefiere antes). ALLAGENTS_PRIORITY lo cambia.
  TIER        etiqueta de coste/límites que Claude ve en la lista de prioridades.
  ROLE        una línea: para qué usarlo. Va en las instrucciones del servidor.
  status()    None si está listo, o el motivo por el que no está disponible.
  register()  publica su herramienta en el servidor MCP.
  models()    (opcional) lista los modelos disponibles.

``delegate`` concentra lo que toda herramienta debe hacer igual: leer y
validar archivos, medir, auditar, redactar secretos y recortar la salida.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .. import audit
from ..config import Settings
from ..files import LoadedFile, load_files
from ..security import redact, truncate

# Todas las herramientas solo consultan: no modifican nada en el equipo.
CLOUD_TOOL = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                             idempotent_hint=False, open_world_hint=True)
LOCAL_TOOL = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                             idempotent_hint=False, open_world_hint=False)

# Niveles de coste. Guían a Claude: primero lo ilimitado, al final lo que cuesta.
TIER_LOCAL = "local · ilimitado"
TIER_FREE = "gratis con límites"
TIER_SUBSCRIPTION = "suscripción con límites"
TIER_SCARCE = "cuota escasa: resérvala"
TIER_PAID = "pago por uso"

# Documentación de los argumentos comunes, para herramientas sin docstring propio.
COMMON_ARGS_DOC = """
Args:
    prompt: la tarea, completa y autocontenida (el modelo no ve tu conversación).
    files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
    model: opcional; por defecto el configurado en .env."""


class AgentError(Exception):
    """Error esperado de un agente; su mensaje se muestra a Claude (redactado)."""


@dataclass
class AgentResult:
    agent: str
    model: str
    text: str
    duration_s: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    footer: str = ""

    def render(self, max_chars: int) -> str:
        meta = [self.agent, self.model or "?", f"{self.duration_s:.1f}s"]
        if self.input_tokens is not None or self.output_tokens is not None:
            meta.append(f"tokens in {self.input_tokens or 0}/out {self.output_tokens or 0}")
        body = truncate(self.text.strip(), max_chars)
        return f"[{' · '.join(meta)}]\n{body}" + (f"\n\n{self.footer}" if self.footer else "")


Call = Callable[[list[LoadedFile]], Awaitable[AgentResult]]


async def delegate(agent: str, settings: Settings, *, local: bool, files: list[str] | None,
                   call: Call) -> str:
    start = time.monotonic()
    loaded: list[LoadedFile] = []
    try:
        loaded = load_files(files, settings, local_agent=local)
        result = await call(loaded)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo se reporta redactado
        message = redact(str(exc) or type(exc).__name__, settings.secrets)
        audit.record(agent, ok=False, duration_s=time.monotonic() - start, files=len(loaded),
                     error=f"{type(exc).__name__}: {message}")
        raise ToolError(f"{agent}: {message}") from None

    audit.record(agent, ok=True, duration_s=result.duration_s, model=result.model,
                 files=len(loaded), input_chars=sum(len(f.text) for f in loaded),
                 input_tokens=result.input_tokens, output_tokens=result.output_tokens)
    return redact(result.render(settings.max_output_chars), settings.secrets)
