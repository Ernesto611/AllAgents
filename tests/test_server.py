import asyncio

import pytest

from allagents.agents import all_agents, ollama
from allagents.config import Settings
from allagents.server import build_instructions, build_server

# Valores que dejan fuera a los CLIs de la máquina donde corren los tests.
NO_CLIS = {"AGY_BIN": "/no/existe", "CODEX_BIN": "/no/existe", "COPILOT_BIN": "/no/existe"}


@pytest.fixture(autouse=True)
def ollama_up(monkeypatch):
    """Por defecto Ollama "responde"; los tests que lo necesiten lo apagan."""
    monkeypatch.setattr(ollama, "_reachable", lambda url: True)


def _settings(tmp_path, **values) -> Settings:
    return Settings(values={**NO_CLIS, **values}, env_file=tmp_path / ".env")


def _tool_names(settings: Settings) -> set[str]:
    server = build_server(settings)
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_only_available_agents_are_published(tmp_path):
    assert _tool_names(_settings(tmp_path)) == {"list_agents", "ask_ollama"}


def test_agents_with_keys_are_published(tmp_path):
    settings = _settings(tmp_path, GROQ_API_KEY="k1", COHERE_API_KEY="k2",
                         CODESTRAL_API_KEY="k3", OPENCODE_API_KEY="k4")
    assert {"ask_groq", "ask_cohere", "ask_mistral", "ask_opencode"} <= _tool_names(settings)


def test_disabled_agents_are_not_published(tmp_path):
    settings = _settings(tmp_path, ALLAGENTS_DISABLE="ollama,copilot")
    assert _tool_names(settings) == {"list_agents"}


def test_ollama_not_published_when_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(ollama, "_reachable", lambda url: False)
    assert "ask_ollama" not in _tool_names(_settings(tmp_path))


def test_ollama_rejects_non_loopback_url(tmp_path):
    settings = _settings(tmp_path, OLLAMA_URL="http://192.168.1.50:11434")
    assert "ask_ollama" not in _tool_names(settings)


def test_default_priority_puts_local_first_and_scarce_last(tmp_path):
    names = [a.NAME for a in all_agents(_settings(tmp_path))]
    assert names[0] == "ollama"
    assert names.index("groq") < names.index("agy") < names.index("codex") < names.index("deepseek")


def test_priority_can_be_overridden(tmp_path):
    names = [a.NAME for a in all_agents(_settings(tmp_path, ALLAGENTS_PRIORITY="codex,groq"))]
    assert names[:3] == ["codex", "groq", "ollama"]


def test_instructions_list_only_available_agents_in_order(tmp_path):
    settings = _settings(tmp_path, GROQ_API_KEY="k1")
    agents = [a for a in all_agents(settings) if a.status(settings) is None
              and a.NAME not in settings.disabled_agents]
    text = build_instructions(agents)
    assert "1. ask_ollama [local · ilimitado]" in text
    assert "2. ask_groq" in text
    assert "ask_cohere" not in text
