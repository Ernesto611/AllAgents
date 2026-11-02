"""Registro de auditoría: qué se delegó, a quién, cuánto tardó y si falló.

Solo metadatos. Nunca se registran prompts, contenido de archivos,
respuestas ni claves. El archivo se crea con permisos 600.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger = logging.getLogger("allagents.audit")


def setup(log_file: Path) -> None:
    if _logger.handlers:
        return
    log_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_file.touch(mode=0o600, exist_ok=True)
    os.chmod(log_file, 0o600)
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def record(agent: str, *, ok: bool, duration_s: float, model: str = "", files: int = 0,
           input_chars: int = 0, input_tokens: int | None = None,
           output_tokens: int | None = None, error: str = "") -> None:
    fields = [f"agent={agent}", f"ok={ok}", f"dur={duration_s:.1f}s", f"model={model or '-'}",
              f"files={files}", f"in_chars={input_chars}"]
    if input_tokens is not None:
        fields.append(f"in_tok={input_tokens}")
    if output_tokens is not None:
        fields.append(f"out_tok={output_tokens}")
    if error:
        fields.append(f"error={error[:200]!r}")
    _logger.info(" ".join(fields))
