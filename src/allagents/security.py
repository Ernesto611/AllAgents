"""Controles de seguridad compartidos.

- Qué archivos se pueden enviar a un agente (carpetas permitidas, archivos
  sensibles bloqueados, carpetas solo-locales, enlaces simbólicos resueltos).
- Redacción de secretos en cualquier texto que salga del servidor.
- Entorno mínimo para los procesos hijos (los CLIs no heredan claves).
- Validación de URLs: HTTPS para la nube, solo loopback para Ollama.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from .config import Settings


class SecurityError(Exception):
    """Una petición viola la política de seguridad; el mensaje explica por qué."""


# Nombres de archivo que nunca se envían, estén donde estén.
SENSITIVE_NAME_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.kdbx",
    "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", "*.ppk",
    ".netrc", "_netrc", ".pgpass", ".git-credentials", ".npmrc", ".pypirc",
    "credentials", "credentials.*", "secrets.*", "*.keystore",
    "auth.json", "token.json", "known_hosts", "authorized_keys",
)
# Excepciones explícitas a los patrones anteriores.
SENSITIVE_NAME_EXCEPTIONS = (".env.example", ".env.sample", ".env.template")

# Carpetas (relativas al HOME) con credenciales de herramientas.
SENSITIVE_HOME_DIRS = (
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store",
    ".codex", ".copilot", ".gemini", ".claude", ".config/gh", ".config/gcloud",
    ".local/share/keyrings", ".mozilla", ".config/google-chrome",
    ".config/BraveSoftware", ".zen",
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-~+/]{12,}=*"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),            # OpenAI / DeepSeek
    re.compile(r"\bgsk_[A-Za-z0-9]{16,}"),              # Groq
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),        # GitHub
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),           # Google
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)

REDACTED = "[REDACTADO]"


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Quita de ``text`` los secretos conocidos y los que tienen forma de clave."""
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + REDACTED, text)
    return text


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[… respuesta recortada: {len(text) - limit} caracteres omitidos]"


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _is_sensitive_name(name: str) -> bool:
    if name in SENSITIVE_NAME_EXCEPTIONS:
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in SENSITIVE_NAME_PATTERNS)


def _reject_if_sensitive(path: Path, raw_path: str) -> None:
    if any(_is_sensitive_name(part) for part in path.parts):
        raise SecurityError(f"archivo sensible bloqueado: {raw_path}")
    home = Path.home().resolve()
    for sensitive in SENSITIVE_HOME_DIRS:
        if _is_within(path, home / sensitive):
            raise SecurityError(f"carpeta de credenciales bloqueada: {raw_path}")


def check_file_access(raw_path: str, settings: Settings, *, local_agent: bool) -> Path:
    """Valida que ``raw_path`` se pueda enviar al agente; devuelve la ruta real.

    La ruta pedida se revisa antes de tocar el disco (así un rechazo no revela
    si el archivo existe) y la real, tras resolver enlaces simbólicos, otra vez:
    un enlace no sirve para escapar de las carpetas permitidas ni para disfrazar
    un archivo sensible.
    """
    requested = Path(raw_path).expanduser()
    if not requested.is_absolute():
        raise SecurityError(f"usa rutas absolutas: {raw_path!r}")
    _reject_if_sensitive(Path(os.path.normpath(requested)), raw_path)
    try:
        real = requested.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise SecurityError(f"no existe: {raw_path}") from None
    _reject_if_sensitive(real, raw_path)
    if not real.is_file():
        raise SecurityError(f"no es un archivo: {raw_path}")

    if settings.env_file.exists() and real == settings.env_file.resolve():
        raise SecurityError("el .env del servidor nunca se envía")

    if not any(_is_within(real, allowed) for allowed in settings.allowed_dirs):
        allowed = ", ".join(str(p) for p in settings.allowed_dirs) or "(ninguna)"
        raise SecurityError(f"fuera de ALLAGENTS_ALLOWED_DIRS ({allowed}): {raw_path}")
    if not local_agent and any(_is_within(real, d) for d in settings.local_only_dirs):
        raise SecurityError(
            f"{raw_path} está en ALLAGENTS_LOCAL_ONLY_DIRS: solo puede enviarse a ask_ollama")
    return real


# Variables que los CLIs necesitan para funcionar y encontrar su sesión.
_CHILD_ENV_KEYS = (
    "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TZ",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
)


def child_env(extra_path: tuple[str, ...] = ()) -> dict[str, str]:
    """Entorno mínimo para procesos hijos: sin claves de API ni tokens."""
    env = {k: os.environ[k] for k in _CHILD_ENV_KEYS if k in os.environ}
    env.update({k: v for k, v in os.environ.items() if k.startswith("LC_")})
    home = Path.home()
    path = [*extra_path, str(home / ".local/bin"), str(home / ".npm-global/bin"),
            "/usr/local/bin", "/usr/bin", "/bin"]
    env["PATH"] = ":".join(dict.fromkeys(path))
    env["NO_COLOR"] = "1"
    return env


def require_https(url: str) -> str:
    if urlsplit(url).scheme != "https":
        raise SecurityError(f"solo se permiten URLs https para servicios en la nube: {url}")
    return url.rstrip("/")


def require_loopback(url: str) -> str:
    """Acepta solo URLs a la propia máquina (Ollama no debe salir a la red)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https"):
        raise SecurityError(f"URL no válida: {url}")
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise SecurityError(
                f"OLLAMA_URL debe apuntar a esta máquina (127.0.0.1, ::1 o localhost): {url}"
            ) from None
    return url.rstrip("/")
