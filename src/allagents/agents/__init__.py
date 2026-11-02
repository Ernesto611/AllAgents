"""Descubrimiento de agentes.

Cada módulo de este paquete (salvo ``base`` y ``custom``) es un agente: para
añadir uno basta con crear su archivo (ver docs/adding-an-agent.md). Los
agentes compatibles con OpenAI pueden definirse además solo con variables de
entorno (ALLAGENTS_CUSTOM), sin escribir código: ver ``custom.py``.
"""

from __future__ import annotations

import importlib
import pkgutil

from ..config import Settings
from . import custom

_INTERNAL = {"base", "custom"}


def builtin_agents() -> list:
    modules = []
    for info in pkgutil.iter_modules(__path__):
        if info.name in _INTERNAL or info.name.startswith("_"):
            continue
        modules.append(importlib.import_module(f"{__name__}.{info.name}"))
    return modules


def all_agents(settings: Settings) -> list:
    """Todos los agentes (integrados y personalizados), en orden de prioridad."""
    builtins = builtin_agents()
    agents = builtins + custom.load(settings, reserved={a.NAME for a in builtins})
    order = settings.priority

    def key(agent):
        explicit = order.index(agent.NAME) if agent.NAME in order else len(order)
        return (explicit, agent.PRIORITY, agent.NAME)

    return sorted(agents, key=key)
