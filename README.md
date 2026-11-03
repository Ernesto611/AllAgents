# AllAgents

Servidor **MCP local** que permite a Claude Code delegar subtareas a otras IAs
(tu Ollama local, Groq, Mistral, Cohere, Gemini, ChatGPT, OpenCode, DeepSeek…)
para **ahorrar tokens de Claude**. Claude ve cada IA como una herramienta
(`ask_ollama`, `ask_groq`, …) y recibe una **lista de prioridades**: primero lo
local e ilimitado, después lo gratuito y al final lo que tiene cuota escasa o se paga.

- **Se adapta a lo que tengas.** Detecta qué IAs hay en cada equipo y solo
  publica esas. Puedes añadir cualquier API compatible con OpenAI **sin escribir
  código**, solo con variables en `.env`.
- **Ahorra contexto de verdad.** Claude pasa *rutas* de archivos; el servidor los
  lee y los envía, así su contenido nunca entra en el contexto de Claude.
- **Sin puertos de red.** Solo funciona por stdio (Claude Code lo lanza como
  proceso hijo); nadie puede conectarse a él desde la red. Ver [SECURITY.md](SECURITY.md).
- **Protege los datos sensibles.** Las carpetas marcadas como solo-locales solo
  pueden enviarse a modelos locales; la nube las rechaza.

---

## Instalación (5 minutos)

**Requisitos:** Linux o macOS, Python 3.11+, [Claude Code](https://claude.com/claude-code),
y al menos una IA de la tabla de abajo.

```bash
git clone <url-del-repo> AllAgents && cd AllAgents
./scripts/setup.sh --register
```

`setup.sh` crea el entorno virtual con dependencias de versión fijada, crea tu
`.env` (permisos `600`), activa el hook de git que bloquea secretos y, con
`--register`, registra el servidor en Claude Code para todas tus carpetas.

Después:

1. Edita `.env` y rellena **solo** lo que tengas (cada variable está explicada).
   El archivo está oculto: en el explorador pulsa `Ctrl+H` para verlo.
2. Comprueba qué quedó disponible:
   ```bash
   .venv/bin/allagents check
   ```
3. Abre una sesión **nueva** de Claude Code: las herramientas `ask_*` aparecen solas.
4. **Recomendado:** haz que Claude delegue por iniciativa propia (siguiente sección).

---

## Que Claude delegue por iniciativa propia

El servidor ya envía a Claude la lista de prioridades y las reglas al empezar cada
sesión, sin que tengas que hacer nada. Pero si no se le recuerda, Claude tiende a
hacer el trabajo él mismo. Para que delegue de forma proactiva, pega este bloque en
`~/.claude/CLAUDE.md` (si no existe, créalo). Claude Code lo carga en todas tus
sesiones, en cualquier carpeta:

```markdown
## Delegación con AllAgents
Tienes el servidor MCP `allagents` (herramientas `ask_*`). Úsalo de forma proactiva para ahorrar tokens:
- Antes de hacer tú una tarea delegable (resumir archivos o logs, extraer datos, generar
  boilerplate, tests o docstrings, revisar código, segundas opiniones), delégala siguiendo
  la prioridad de sus instrucciones: primero `ask_ollama`.
- Pasa los archivos por ruta absoluta en `files`; no los leas tú antes.
- Datos sensibles (clientes, credenciales, layouts bancarios): solo `ask_ollama`.
- Revisa lo que devuelvan antes de aplicarlo y dime en una línea qué agente usaste.
- Si no ves las herramientas `ask_*`, avísame en lugar de seguir sin ellas.
```

Es corto a propósito: se carga en cada sesión. También puedes pedirlo en el momento:

- *"Resume este log con allagents: /home/…/app.log"*
- *"Pídele a Mistral que revise /home/…/procedimiento.sql"*
- *"Usa solo Ollama, son datos de clientes"*
- *"Antes de responder, pide una segunda opinión a Codex"*

---

## Agentes y prioridades

Orden por defecto. Claude usa el primero que sirva para la tarea y baja por la
lista solo cuando necesita más calidad, contexto o velocidad.

| # | Herramienta | IA | Nivel | Úsala para | Qué necesitas |
|---|---|---|---|---|---|
| 1 | `ask_ollama` | Modelos locales (qwen3-coder…) | **local · ilimitado** | Primera opción siempre; obligatoria con datos sensibles | [Ollama](https://ollama.com) corriendo |
| 2 | `ask_groq` | Qwen / GPT-OSS en LPU | gratis con límites | JSON, extracción de datos, scaffolding, baja latencia | `GROQ_API_KEY` |
| 3 | `ask_mistral` | Codestral | gratis con límites | Revisión de código, Python, T-SQL, Docker, C# | `MISTRAL_API_KEY` o `CODESTRAL_API_KEY` |
| 4 | `ask_cohere` | Command R | gratis con límites | Logs y documentos largos con citas (RAG) | `COHERE_API_KEY` |
| 5 | `ask_agy` | Google Gemini | suscripción con límites | Archivos gigantes, mucha documentación | CLI `agy` con sesión |
| 6 | `ask_opencode` | DeepSeek v4.1 Flash Free y otros | gratis (cupo muy bajo) | Código y razonamiento general | `OPENCODE_API_KEY` |
| 7 | `ask_codex` | ChatGPT | cuota escasa | Lógica difícil, revisión crítica | CLI `codex` con sesión |
| 8 | `ask_deepseek` | DeepSeek | pago por uso | Alternativa barata a ChatGPT | `DEEPSEEK_API_KEY` |
| 9 | `ask_copilot` | GitHub Copilot | suscripción | *Experimental, desactivado* | CLI `copilot` |

Además, `list_agents` muestra el estado de todos y por qué falta alguno.

La regla completa que recibe Claude (qué delegar, cómo, qué no mandar a la nube)
se genera según los agentes disponibles. Para verla:

```bash
.venv/bin/allagents check --instructions
```

Detalle de cada agente (conexión, costes, límites, modelos): [docs/agents.md](docs/agents.md).

---

## Adaptarlo a tus IAs

De menos a más trabajo:

1. **No hacer nada.** Lo que no esté instalado o no tenga clave no se publica.
2. **Desactivar uno** aunque esté configurado: `ALLAGENTS_DISABLE=codex,agy`
3. **Cambiar el orden**: `ALLAGENTS_PRIORITY=ollama,mistral,groq` (los que no
   pongas van detrás, en su orden por defecto).
4. **Añadir una IA compatible con OpenAI sin código** (OpenRouter, Together,
   xAI, LM Studio, vLLM…):
   ```bash
   ALLAGENTS_CUSTOM=openrouter
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   OPENROUTER_API_KEY=...
   OPENROUTER_MODEL=deepseek/deepseek-chat
   OPENROUTER_ROLE=acceso a muchos modelos con una sola clave
   OPENROUTER_DESCRIPTION=OpenRouter. Úsala para … NO la uses para …
   ```
   Crea la herramienta `ask_openrouter`. Para un servidor en tu máquina añade
   `<NOMBRE>_LOCAL=true` (solo se acepta con una URL `127.0.0.1`/`localhost`).
5. **Añadir una IA con API propia o un CLI**: crea un módulo en
   `src/allagents/agents/`, que se descubre solo. Guía: [docs/adding-an-agent.md](docs/adding-an-agent.md).

---

## Comandos

```bash
.venv/bin/allagents check                  # estado de cada agente y del .env
.venv/bin/allagents check --instructions   # … y la regla de prioridades que recibe Claude
.venv/bin/allagents models groq            # modelos disponibles de un agente
.venv/bin/python scripts/smoke_test.py     # prueba real por MCP de todos los agentes
.venv/bin/python scripts/smoke_test.py groq ollama   # … o solo algunos
.venv/bin/python scripts/smoke_test.py --security    # verificación de seguridad
```

`allagents serve` lo lanza Claude Code; no hace falta ejecutarlo a mano.
El registro de auditoría está en `logs/allagents.log`: solo metadatos (agente,
modelo, duración, tokens), nunca prompts, archivos ni respuestas.

---

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| No aparece ninguna herramienta `ask_*` en Claude | Abre una sesión nueva. Comprueba que está registrado: `claude mcp list` |
| Falta una herramienta concreta | `allagents check` dice por qué (clave, CLI, servicio caído…) |
| `.env ignorado: … permisos` | `chmod 600 .env` |
| `HTTP 429` / `Free usage limit reached` | Se agotó el cupo de ese proveedor; Claude pasará al siguiente |
| `model not found` / `model_not_found` | El proveedor retiró el modelo: `allagents models <agente>` y cambia `<AGENTE>_MODEL` |
| `fuera de ALLAGENTS_ALLOWED_DIRS` | Añade la carpeta de tu proyecto a `ALLAGENTS_ALLOWED_DIRS` |
| `ask_ollama` no aparece | Ollama no está corriendo en `OLLAMA_URL` (`ollama serve` o el servicio del sistema) |
| Tras añadir una clave no cambia nada | El servidor lee `.env` al arrancar: abre una sesión nueva de Claude Code |

---

## Estructura

```
AllAgents/
├── src/allagents/
│   ├── __main__.py        # CLI: serve | check | models
│   ├── server.py          # servidor MCP (solo stdio) + regla de prioridades para Claude
│   ├── config.py          # carga de .env con verificación de permisos
│   ├── security.py        # política de archivos, redacción de secretos, entorno de hijos, URLs
│   ├── files.py           # lectura de archivos y armado del prompt
│   ├── audit.py           # registro de auditoría (solo metadatos)
│   ├── clients/
│   │   ├── cli.py         # ejecución aislada de CLIs (carpeta temporal, sin shell, timeouts)
│   │   ├── http.py        # HTTP endurecido (TLS, sin redirecciones, sin proxies del entorno)
│   │   └── openai_compat.py  # Chat Completions (Groq, Mistral, OpenCode, DeepSeek, custom)
│   └── agents/            # un módulo por IA, descubiertos automáticamente
│       ├── base.py        # contrato de agente, niveles y flujo común
│       ├── custom.py      # agentes definidos solo en .env (ALLAGENTS_CUSTOM)
│       └── ollama.py groq.py mistral.py cohere.py agy.py opencode.py codex.py deepseek.py copilot.py
├── tests/                 # pytest: seguridad, configuración, prioridades, agentes custom
├── scripts/
│   ├── setup.sh           # instalación (+ --register)
│   ├── smoke_test.py      # prueba de punta a punta por MCP (+ --security)
│   └── git-hooks/pre-commit  # bloquea commits con secretos
├── docs/
│   ├── agents.md          # detalle de cada agente
│   └── adding-an-agent.md # cómo añadir una IA
├── SECURITY.md            # modelo de amenazas, medidas y cómo verificarlas
├── .env.example           # plantilla de configuración (sin secretos)
├── requirements.lock      # dependencias con versión exacta
└── pyproject.toml
```

## Desarrollo

```bash
.venv/bin/pip install pytest==9.2.0
.venv/bin/python -m pytest
```

Antes de cada commit, el hook `pre-commit` rechaza archivos de secretos y texto
con forma de clave. Es local: se activa al ejecutar `./scripts/setup.sh` en cada clon.
