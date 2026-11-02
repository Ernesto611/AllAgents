# Cómo añadir una IA

Hay dos caminos. Usa el primero siempre que puedas.

## Opción A — Sin código (API compatible con OpenAI)

Si el servicio ofrece un endpoint `/chat/completions` al estilo OpenAI
(OpenRouter, Together, Fireworks, xAI, Azure OpenAI, LM Studio, vLLM,
llama.cpp server…), basta con `.env`:

```bash
ALLAGENTS_CUSTOM=together            # varios: together,lmstudio
TOGETHER_BASE_URL=https://api.together.xyz/v1
TOGETHER_API_KEY=...
TOGETHER_MODEL=meta-llama/Llama-4-Scout-17B-16E-Instruct
TOGETHER_ROLE=modelos abiertos baratos; alternativa a Groq
TOGETHER_DESCRIPTION=Together AI. Úsala para … NO la uses para …
TOGETHER_PRIORITY=45                 # opcional: menor = antes
TOGETHER_TIER=pago por uso           # opcional: etiqueta que ve Claude
```

Esto publica `ask_together`. Reglas que aplica el servidor:

- En la nube: la URL debe ser `https://` y hace falta `<NOMBRE>_API_KEY`.
- Local: `<NOMBRE>_LOCAL=true` **solo** se acepta si la URL apunta a esta
  máquina (`127.0.0.1`, `::1` o `localhost`). Así "local" significa de verdad
  que los datos no salen. Los agentes locales pueden leer archivos de
  `ALLAGENTS_LOCAL_ONLY_DIRS`.
- El nombre: minúsculas, números y `_`, y que no coincida con un agente integrado.

Comprueba con `allagents check` y `allagents models <nombre>`.

## Opción B — Módulo propio (API distinta o CLI)

Crea `src/allagents/agents/<nombre>.py`. Se descubre automáticamente: no hay
que registrarlo en ningún sitio. Contrato mínimo (ejemplo con una API propia;
mira `cohere.py` como referencia de API no compatible con OpenAI y `agy.py`
para un CLI):

```python
"""<Proveedor>: una línea sobre qué es."""

from __future__ import annotations

import time

from ..clients.http import post_json
from ..config import Settings
from ..files import build_prompt
from .base import CLOUD_TOOL, TIER_FREE, AgentResult, delegate

NAME = "nuevo"            # herramienta ask_nuevo
LOCAL = False             # True solo si los datos no salen del equipo
PRIORITY = 45             # menor = Claude lo prefiere antes
TIER = TIER_FREE          # nivel de coste (ver base.py)
ROLE = "una línea: para qué sirve"   # aparece en la lista de prioridades
BASE_URL = "https://api.proveedor.com"   # siempre https


def status(settings: Settings) -> str | None:
    """None si está listo; si no, el motivo (se muestra en `allagents check`)."""
    return None if settings.get("NUEVO_API_KEY") else "falta NUEVO_API_KEY en .env"


def register(server, settings: Settings) -> None:
    @server.tool(name="ask_nuevo", annotations=CLOUD_TOOL)
    async def ask_nuevo(prompt: str, files: list[str] | None = None, model: str = "") -> str:
        """<Proveedor>. Especialidad: …

        Úsala para:
        - …

        NO la uses con datos sensibles (salen a <proveedor>): para eso, ask_ollama.

        Args:
            prompt: la tarea, completa y autocontenida.
            files: rutas ABSOLUTAS de archivos de texto a incluir (el servidor los lee).
            model: opcional; por defecto NUEVO_MODEL.
        """
        async def call(loaded):
            start = time.monotonic()
            data = await post_json(
                f"{BASE_URL}/v1/generate",
                {"model": model or settings.get("NUEVO_MODEL", "por-defecto"),
                 "input": build_prompt(prompt, loaded)},
                headers={"Authorization": f"Bearer {settings.get('NUEVO_API_KEY')}"},
                timeout_s=settings.timeout_s, secrets=settings.secrets)
            return AgentResult(agent=NAME, model=data["model"], text=data["output"],
                               duration_s=time.monotonic() - start)

        return await delegate(NAME, settings, local=LOCAL, files=files, call=call)
```

`delegate()` hace por ti lo común: valida y lee `files` con la política de
seguridad, mide el tiempo, registra la auditoría, redacta secretos de
cualquier error y recorta la respuesta.

Después:

1. Añade sus variables a `.env.example`. Las claves deben acabar en `_API_KEY`,
   `_TOKEN` o `_SECRET`: así se redactan solas de errores y logs.
2. Documenta el agente en `docs/agents.md` y en la tabla del README.
3. Si es un **CLI con herramientas** (puede leer, escribir o ejecutar):
   confínalo como `agy.py` o `codex.py` y comprueba que responde BLOQUEADO a las
   pruebas de SECURITY.md §4. Si no puedes confinarlo, usa su API HTTP (como
   `opencode.py`) o no lo integres.
4. Ejecuta `python -m pytest` y `scripts/smoke_test.py <nombre>`.

## Sobre el docstring

Es lo que Claude lee para decidir y se carga en cada sesión, así que debe ser
**corto y concreto**: especialidad, cuándo usarla, cuándo NO (datos
sensibles) y los argumentos. El `ROLE` es aún más corto: una línea para la
lista de prioridades.
