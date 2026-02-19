# Configuration reference

AgentDbg is configured via **environment variables** and **YAML config files**. All settings are optional; defaults are tuned for safe, local-only tracing.

---

## Precedence

Configuration is merged in this order (highest wins):

1. **Environment variables**
2. **Project config:** `.agentdbg/config.yaml` in project root (current working directory when config is loaded)
3. **User config:** `~/.agentdbg/config.yaml`
4. **Defaults** (see below)

---

## Settings

### Data directory

| Env | YAML key | Default | Description |
|-----|----------|---------|-------------|
| `AGENTDBG_DATA_DIR` | `data_dir` | `~/.agentdbg` | Base directory for runs. Runs are stored under `<data_dir>/runs/<run_id>/`. |

**Example (env):**

```bash
export AGENTDBG_DATA_DIR=/path/to/my/agentdbg/data
```

**Example (YAML):**

```yaml
# ~/.agentdbg/config.yaml or .agentdbg/config.yaml
data_dir: /path/to/my/agentdbg/data
```

---

### Redaction

| Env | YAML key | Default | Description |
|-----|----------|---------|-------------|
| `AGENTDBG_REDACT` | `redact` | `1` (on) | Enable redaction. Use `1`, `true`, or `yes` to enable; any other value disables. |
| `AGENTDBG_REDACT_KEYS` | `redact_keys` | `api_key,token,authorization,cookie,secret,password` | Comma-separated list of key patterns (case-insensitive substring match). |
| `AGENTDBG_MAX_FIELD_BYTES` | `max_field_bytes` | `20000` | Maximum size in bytes for a string/field before truncation. Minimum enforced: 100. |

**Redaction behavior:**

- Applied **recursively** to nested dicts and lists (e.g. payloads and meta).
- **Key match:** If a dict key contains any of the redact keys as a **case-insensitive substring**, the value is replaced with `__REDACTED__` (the key is not redacted; the value is). Example: `auth_token` matches `token`; `API_KEY` matches `api_key`.
- **Recursion depth:** Traversal is limited to depth 10 to avoid pathological structures; deeper values are replaced with the truncation marker.

**Truncation behavior:**

- Strings (and other values serialized to strings) longer than `AGENTDBG_MAX_FIELD_BYTES` bytes (UTF-8) are truncated and suffixed with `__TRUNCATED__`.
- At the recursion depth limit (10), the value is replaced with `__TRUNCATED__`.

**Example (env):**

```bash
export AGENTDBG_REDACT=1
export AGENTDBG_REDACT_KEYS="api_key,token,password,secret"
export AGENTDBG_MAX_FIELD_BYTES=10000
```

**Example (YAML):**

```yaml
redact: true
redact_keys:
  - api_key
  - token
  - authorization
  - password
max_field_bytes: 10000
```

---

### Loop detection

| Env | YAML key | Default | Description |
|-----|----------|---------|-------------|
| `AGENTDBG_LOOP_WINDOW` | `loop_window` | `12` | Number of recent events to consider for pattern detection. Minimum: 4. |
| `AGENTDBG_LOOP_REPETITIONS` | `loop_repetitions` | `3` | Consecutive repetitions of a pattern required to emit `LOOP_WARNING`. Minimum: 2. |

**Example (env):**

```bash
export AGENTDBG_LOOP_WINDOW=20
export AGENTDBG_LOOP_REPETITIONS=4
```

**Example (YAML):**

```yaml
loop_window: 20
loop_repetitions: 4
```

---

### Run name (env only)

| Env | YAML | Default | Description |
|-----|------|---------|-------------|
| `AGENTDBG_RUN_NAME` | *(not in YAML)* | *(derived)* | Override the run name for the current process. Used when starting a run via `@trace`, `traced_run()`, or implicit run. If unset, run name is the explicit name argument, or a default like `path/to/script.py:main - 2026-02-18 14:12`. |

**Example:**

```bash
export AGENTDBG_RUN_NAME="my-experiment-v1"
```

---

### Implicit run (env only)

| Env | YAML | Default | Description |
|-----|------|---------|-------------|
| `AGENTDBG_IMPLICIT_RUN` | *(not in YAML)* | unset (off) | If set to `1`, the first `record_*` call with no active run creates an implicit run; all subsequent recorder calls attach to it until process exit. |

This is useful for scripts without a single `@trace` entrypoint. Only read from the environment; not configurable via YAML.

**Example:**

```bash
export AGENTDBG_IMPLICIT_RUN=1
```

---

## Full YAML example

```yaml
# ~/.agentdbg/config.yaml or .agentdbg/config.yaml
data_dir: ~/.agentdbg
redact: true
redact_keys:
  - api_key
  - token
  - authorization
  - cookie
  - secret
  - password
max_field_bytes: 20000
loop_window: 12
loop_repetitions: 3
```

---

## Safe-by-default local traces

- **Redaction is on by default** so that common secret keys are not written to disk.
- **Data directory** defaults to `~/.agentdbg` so traces stay on the machine.
- No cloud or network is used for trace storage. Override only what you need (e.g. `AGENTDBG_DATA_DIR` for project-local storage, or `AGENTDBG_REDACT=0` for local debugging with full payloads).
