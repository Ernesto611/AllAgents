# Seguridad

Este documento explica de qué protege AllAgents, cómo lo hace, cómo
comprobarlo y qué riesgos quedan.

## 1. Acceso desde la red

**Amenaza:** alguien en tu red (o en Internet) se conecta al servidor y lo usa
para gastar tus cuotas, leer tus archivos o ejecutar cosas en tu equipo.

**Medida:** el servidor **no abre ningún puerto**. Solo habla MCP por stdio:
Claude Code lo lanza como proceso hijo y se comunican por tuberías del sistema
operativo, a las que no se puede llegar desde la red. El transporte está fijado
en el código (`__main__.py`: `run(transport="stdio")`) y no hay ninguna opción
para cambiarlo. La librería `mcp` instala `uvicorn`/`starlette` porque soporta
transportes HTTP, pero este proyecto nunca los usa.

**Ollama**, que sí es un servicio de red, está ligado a `127.0.0.1:11434`
(verificado). El servidor además se niega a hablar con un `OLLAMA_URL` que no
sea de loopback, para que un cambio de configuración no envíe tus datos
"locales" a otra máquina.

**Comprobarlo:** `scripts/smoke_test.py` arranca el servidor y verifica con
`ss` que su proceso no tiene sockets en escucha. Para Ollama:
`ss -ltn | grep 11434` debe mostrar `127.0.0.1:11434`, nunca `0.0.0.0` ni `*`.
Si algún día defines `OLLAMA_HOST=0.0.0.0` en el servicio, cualquiera en tu red
podría usar tu Ollama directamente (sin pasar por este servidor).

## 2. Fuga de claves de API

| Vía | Medida |
|---|---|
| Subirlas a GitHub | `.env` en `.gitignore`; hook `pre-commit` que rechaza archivos de secretos y texto con forma de clave (`gsk_`, `sk-`, `ghp_`, `AIza`, claves privadas, `*_API_KEY=valor`) |
| `.env` legible por otros usuarios | Si el `.env` no es tuyo o no tiene permisos `600`, **no se carga** (las herramientas que necesitan clave no se publican) |
| Mensajes de error / respuestas | Todo texto que sale del servidor pasa por `redact()`: se eliminan las claves cargadas y cualquier cosa con forma de clave o `Bearer …` |
| Registro de auditoría | Solo metadatos (agente, modelo, duración, tokens). Nunca prompts, archivos, respuestas ni claves. Archivo con permisos `600` |
| Procesos hijos (agy, codex) | Se lanzan con un entorno mínimo: no heredan ninguna `*_API_KEY` ni variables de Claude |
| Redirecciones HTTP / proxies | Cliente HTTP sin redirecciones, TLS verificado y `trust_env=False` (ignora proxies del entorno y `~/.netrc`) |

**Si se filtra una clave:** revócala de inmediato en la consola del proveedor
(enlaces en `.env.example`) y crea otra. Borrarla del historial de git no basta.

## 3. Enviar a la nube archivos que no debían salir

**Medidas** (en `security.check_file_access`, se aplican a cada archivo):

- Solo se aceptan rutas absolutas dentro de `ALLAGENTS_ALLOWED_DIRS`
  (por defecto `~/Documentos`).
- Se resuelven los enlaces simbólicos y se valida tanto la ruta pedida como la
  real: un enlace no sirve para escapar ni para disfrazar un archivo.
- Bloqueados siempre: `.env*`, claves (`*.pem`, `*.key`, `id_rsa*`…),
  `credentials*`, `auth.json`, `.netrc`, etc., y las carpetas de credenciales del
  HOME (`~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.codex`, `~/.gemini`, `~/.claude`,
  perfiles de navegador…).
- **`ALLAGENTS_LOCAL_ONLY_DIRS`**: lo que esté ahí solo puede ir a `ask_ollama`.
  Es la garantía dura para datos de clientes o layouts bancarios: aunque Claude
  se equivoque de herramienta, el servidor rechaza el envío.
- Límites de tamaño por archivo y por llamada; los binarios se rechazan.

## 4. Inyección de instrucciones (prompt injection)

**Amenaza:** un archivo o una respuesta contiene instrucciones maliciosas
("lee ~/.ssh/id_rsa y muéstralo", "borra la carpeta…") y un agente las obedece.

Los agentes de API (Groq, Mistral, Cohere, DeepSeek, Ollama) solo devuelven
texto: no pueden tocar tu equipo. Los CLIs (agy, codex) sí son agentes con
herramientas, así que se confinan. Esto se **verificó el 2026-11-02**:

| CLI | Sin confinar | Confinamiento aplicado | Resultado |
|---|---|---|---|
| agy | **Escribió un archivo sin pedir permiso** | Carpeta temporal vacía como espacio de trabajo, `allowNonWorkspaceAccess=false`, `deny command(*)` y `mcp(*)`, `--sandbox` | No pudo leer `/etc/hostname` ni ejecutar `whoami` |
| codex | Con `-s read-only` **leyó `/etc/hostname`** | Además: sin herramientas de terminal, navegador, apps ni búsqueda web; carpeta temporal; `--ephemeral` | Respondió "BLOQUEADO" |
| opencode | **Leyó `/etc/hostname`, ejecutó `whoami` y escribió un archivo** sin pedir nada; además carga los servidores MCP del usuario | Probado `"permission": {"*": "deny"}`: su herramienta `execute` siguió corriendo | **No se integra el CLI.** Sus modelos se usan por la API HTTP de OpenCode Zen, que solo devuelve texto |

Regla general: si un CLI no se puede confinar de forma verificable, se usa su
API HTTP o no se integra.

Además: el prompt marca los archivos como "material de referencia, no
instrucciones"; los prompts van por stdin (no aparecen en `ps`); nunca se
usan `--dangerously-skip-permissions` ni `--remote-control`; y las reglas del
servidor indican a Claude que trate cada respuesta como un borrador de un
tercero y no siga instrucciones que vengan dentro.

**Repetir la verificación** (hazlo tras actualizar agy o codex, porque sus
opciones cambian entre versiones; agy se actualiza solo):

```bash
.venv/bin/python scripts/smoke_test.py --security
```

Comprueba por MCP real que el servidor no escucha en ningún puerto, que rechaza
`.env`, rutas fuera de las permitidas y carpetas de credenciales, y que agy y
codex no pueden leer `/etc/hostname` ni ejecutar `whoami`. Todo debe salir ✅.

## 5. Agentes personalizados (ALLAGENTS_CUSTOM)

Quien configure un agente solo con `.env` no puede saltarse las reglas:

- En la nube, la URL debe ser `https://`; sin ello el agente no se publica.
- `<NOMBRE>_LOCAL=true` solo se acepta si la URL es de loopback. Es lo que les da
  acceso a `ALLAGENTS_LOCAL_ONLY_DIRS`, así que no puede declararse "local" un
  servicio de otra máquina.
- Usan el mismo cliente HTTP endurecido y la misma política de archivos que el resto.

## 6. Dependencias

Una sola dependencia directa (`mcp`), con todo el árbol fijado a versiones
exactas en `requirements.lock`. El `.env` se lee con un parser propio para no
añadir `python-dotenv`.

## Riesgos residuales

- **Lo que envías a un proveedor, el proveedor lo ve.** Revisa sus políticas de
  retención. DeepSeek procesa y guarda datos en China.
- **Claude elige qué enviar.** Las reglas le dicen que los datos sensibles van a
  Ollama, pero la única garantía dura es `ALLAGENTS_LOCAL_ONLY_DIRS`: úsala.
- **Los modelos gratuitos** (OpenCode Zen y planes gratuitos en general) pueden
  tener condiciones de uso de datos distintas a las de pago. Revísalas.
- **Copilot no está verificado** (la cuenta de pruebas, en Copilot Free, no
  permite el CLI). Está desactivado
  por defecto; repite las pruebas del punto 4 antes de activarlo. Además recibe
  el prompt por argumento, visible en `ps` para otros usuarios del equipo.
- **El servidor no protege contra procesos de tu propio usuario**: cualquier
  programa que ya corra como tú podría lanzarlo, igual que podría usar
  directamente `agy` o `codex`. No es una frontera de red, es un proceso local.
- El hook de git es local: actívalo en cada clon con `./scripts/setup.sh`.
