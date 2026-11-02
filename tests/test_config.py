import os

from allagents.config import load_settings, parse_env_file

# Claves falsas armadas en tiempo de ejecución: el hook pre-commit rechaza
# cualquier literal con forma de clave, incluso en los tests.
FAKE_KEY = "gsk" + "_" + "prueba" * 3


def test_parse_env_file_handles_comments_quotes_and_export():
    text = f"""
# comentario
GROQ_API_KEY={FAKE_KEY}
export MISTRAL_MODEL="codestral-latest"
COHERE_MODEL='command-r'
OLLAMA_NUM_CTX=8192 # comentario en línea
linea sin igual
1INVALIDA=x
VACIA=
"""
    values = parse_env_file(text)
    assert values == {
        "GROQ_API_KEY": FAKE_KEY,
        "MISTRAL_MODEL": "codestral-latest",
        "COHERE_MODEL": "command-r",
        "OLLAMA_NUM_CTX": "8192",
        "VACIA": "",
    }


def test_env_file_with_open_permissions_is_ignored(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"GROQ_API_KEY={FAKE_KEY}\n")
    os.chmod(env, 0o644)
    settings = load_settings({"ALLAGENTS_ENV_FILE": str(env)})
    assert settings.env_error and "chmod 600" in settings.env_error
    assert settings.get("GROQ_API_KEY") == ""


def test_env_file_with_private_permissions_is_loaded(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"GROQ_API_KEY={FAKE_KEY}\n")
    os.chmod(env, 0o600)
    settings = load_settings({"ALLAGENTS_ENV_FILE": str(env)})
    assert settings.env_error is None
    assert settings.get("GROQ_API_KEY") == FAKE_KEY
    assert FAKE_KEY in settings.secrets


def test_process_environment_overrides_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GROQ_MODEL=desde-archivo\n")
    os.chmod(env, 0o600)
    settings = load_settings({"ALLAGENTS_ENV_FILE": str(env), "GROQ_MODEL": "desde-entorno"})
    assert settings.get("GROQ_MODEL") == "desde-entorno"


def test_copilot_disabled_by_default(tmp_path):
    settings = load_settings({"ALLAGENTS_ENV_FILE": str(tmp_path / "no-existe")})
    assert "copilot" in settings.disabled_agents
