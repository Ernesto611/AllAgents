"""Punto de entrada: ``allagents [serve|check|models <agente>]``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from . import audit
from .agents import all_agents
from .config import load_settings
from .server import agent_status, build_instructions, build_server


def _serve() -> int:
    if sys.stdin.isatty():
        print("Este comando lo lanza Claude Code (MCP por stdio). Para probar la "
              "configuración usa: allagents check", file=sys.stderr)
        return 2
    settings = load_settings()
    audit.setup(settings.log_file)
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # sin una línea por petición
    # Único transporte permitido: stdio. No se abre ningún puerto de red.
    build_server(settings).run(transport="stdio")
    return 0


def _check() -> int:
    settings = load_settings()
    if not settings.env_file.exists():
        print(f"⚠️  No existe {settings.env_file} (cópialo de .env.example)")
    elif settings.env_error:
        print(f"❌ .env ignorado: {settings.env_error}")
    else:
        print(f"✅ .env cargado de {settings.env_file} (permisos seguros)")
    print("Carpetas permitidas para `files`:", ", ".join(map(str, settings.allowed_dirs)) or "ninguna")
    print("Carpetas solo-locales:", ", ".join(map(str, settings.local_only_dirs)) or "ninguna")
    print("\nAgentes en orden de prioridad:")
    agents = all_agents(settings)
    available = []
    for agent in agents:
        reason = agent_status(agent, settings)
        if reason is None:
            available.append(agent)
        mark = "✅" if reason is None else "❌"
        print(f"{mark} ask_{agent.NAME:<10} [{agent.TIER}] {reason or 'disponible'}")
    if "--instructions" in sys.argv:
        print("\nInstrucciones que recibe Claude:\n" + build_instructions(available))
    return 0


def _models(name: str) -> int:
    settings = load_settings()
    agents = all_agents(settings)
    agent = next((a for a in agents if a.NAME == name), None)
    if agent is None or not hasattr(agent, "models"):
        listable = ", ".join(a.NAME for a in agents if hasattr(a, "models"))
        print(f"Agente desconocido o sin listado de modelos. Opciones: {listable}", file=sys.stderr)
        return 2
    reason = agent_status(agent, settings)
    if reason:
        print(f"ask_{name} no disponible: {reason}", file=sys.stderr)
        return 1
    for model in asyncio.run(agent.models(settings)):
        print(model)
    return 0


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)  # todo lo que cree el servidor (logs, temporales) es privado
    parser = argparse.ArgumentParser(
        prog="allagents", description="Servidor MCP local para delegar tareas a otras IAs.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="inicia el servidor MCP por stdio (lo usa Claude Code)")
    check = sub.add_parser("check", help="muestra qué agentes están disponibles")
    check.add_argument("--instructions", action="store_true",
                       help="muestra también las instrucciones de prioridad que recibe Claude")
    models = sub.add_parser("models", help="lista los modelos de un agente")
    models.add_argument("agent")
    args = parser.parse_args(argv)

    if args.command == "check":
        return _check()
    if args.command == "models":
        return _models(args.agent)
    return _serve()


if __name__ == "__main__":
    sys.exit(main())
