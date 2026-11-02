import asyncio

from allagents.agents import all_agents, ollama
from allagents.config import Settings
from allagents.server import agent_status, build_server

NO_CLIS = {"AGY_BIN": "/no/existe", "CODEX_BIN": "/no/existe", "COPILOT_BIN": "/no/existe"}


def _settings(tmp_path, **values) -> Settings:
    return Settings(values={**NO_CLIS, **values}, env_file=tmp_path / ".env")


def _agent(settings, name):
    return next(a for a in all_agents(settings) if a.NAME == name)


def test_cloud_custom_agent_is_published_with_its_description(tmp_path, monkeypatch):
    monkeypatch.setattr(ollama, "_reachable", lambda url: True)
    settings = _settings(tmp_path, ALLAGENTS_CUSTOM="openrouter",
                         OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
                         OPENROUTER_API_KEY="k", OPENROUTER_MODEL="m",
                         OPENROUTER_DESCRIPTION="Úsala para probar modelos.")
    tools = {t.name: t for t in asyncio.run(build_server(settings).list_tools())}
    assert "ask_openrouter" in tools
    assert "Úsala para probar modelos." in tools["ask_openrouter"].description
    assert "datos sensibles" in tools["ask_openrouter"].description
    assert set(tools["ask_openrouter"].input_schema["properties"]) == {"prompt", "files", "model"}


def test_cloud_custom_agent_requires_https_and_key(tmp_path):
    base = dict(ALLAGENTS_CUSTOM="x1", X1_MODEL="m")
    insecure = _settings(tmp_path, **base, X1_BASE_URL="http://api.example.com/v1", X1_API_KEY="k")
    assert "https" in agent_status(_agent(insecure, "x1"), insecure)
    no_key = _settings(tmp_path, **base, X1_BASE_URL="https://api.example.com/v1")
    assert "X1_API_KEY" in agent_status(_agent(no_key, "x1"), no_key)


def test_local_custom_agent_must_point_to_loopback(tmp_path):
    lan = _settings(tmp_path, ALLAGENTS_CUSTOM="lmstudio", LMSTUDIO_LOCAL="true",
                    LMSTUDIO_MODEL="m", LMSTUDIO_BASE_URL="http://192.168.1.20:1234/v1")
    assert "esta máquina" in agent_status(_agent(lan, "lmstudio"), lan)

    loopback = _settings(tmp_path, ALLAGENTS_CUSTOM="lmstudio", LMSTUDIO_LOCAL="true",
                         LMSTUDIO_MODEL="m", LMSTUDIO_BASE_URL="http://127.0.0.1:1234/v1")
    agent = _agent(loopback, "lmstudio")
    assert agent_status(agent, loopback) is None  # sin clave: es local
    assert agent.LOCAL and agent.PRIORITY < _agent(loopback, "groq").PRIORITY


def test_invalid_or_reserved_custom_names_are_reported(tmp_path):
    settings = _settings(tmp_path, ALLAGENTS_CUSTOM="groq,Mal-Nombre")
    custom = [a for a in all_agents(settings) if hasattr(a, "error") and a.error]
    reasons = {a.NAME: a.error for a in custom}
    assert "ya es un agente integrado" in reasons["groq"]
    assert "nombre no válido" in reasons["mal-nombre"]
