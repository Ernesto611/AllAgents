"""Ejecución segura de CLIs de IA (agy, codex, copilot).

- Sin shell: los argumentos van como lista, no hay inyección de comandos.
- Cada llamada corre en una carpeta temporal vacía (permisos 700) que se
  borra al terminar; es el único "espacio de trabajo" que ve el agente.
- Entorno mínimo (sin claves de API) y grupo de procesos propio para poder
  matar al agente y a todos sus hijos si se pasa del tiempo.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from ..security import child_env

# Los CLIs que reciben el prompt por argumento están limitados por el kernel
# (MAX_ARG_STRLEN = 128 KiB por argumento).
MAX_ARGV_PROMPT_BYTES = 120_000


class CliError(Exception):
    pass


@dataclass(frozen=True)
class CliResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


@asynccontextmanager
async def isolated_workspace() -> AsyncIterator[Path]:
    with tempfile.TemporaryDirectory(prefix="allagents-") as tmp:
        yield Path(tmp)


async def run_cli(argv: list[str], *, cwd: Path, timeout_s: int,
                  stdin_text: str | None = None) -> CliResult:
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=child_env(),
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError:
        raise CliError(f"no se encontró el ejecutable {argv[0]}") from None

    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin_text.encode() if stdin_text is not None else None),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        _kill_group(proc)
        await proc.wait()
        raise CliError(f"{Path(argv[0]).name} superó el tiempo máximo de {timeout_s}s") from None
    except asyncio.CancelledError:
        # Claude canceló la llamada: no dejar al agente corriendo en segundo plano.
        _kill_group(proc)
        raise

    return CliResult(
        returncode=proc.returncode or 0,
        stdout=out.decode("utf-8", errors="replace"),
        stderr=err.decode("utf-8", errors="replace"),
        duration_s=time.monotonic() - start,
    )


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def find_bin(configured: str, name: str, setting: str) -> str:
    """Ruta del CLI: la de ``setting`` si está definida; si no, se busca en el PATH."""
    if configured:
        path = Path(configured).expanduser()
        if not (path.is_file() and os.access(path, os.X_OK)):
            raise CliError(f"{setting}={configured} no es un ejecutable")
        return str(path)
    found = shutil.which(name, path=child_env()["PATH"])
    if not found:
        raise CliError(f"no se encontró '{name}' en el PATH (instálalo o define {setting})")
    return found
