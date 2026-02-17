# AgentDbg - local-first debugger for AI agents

AgentDbg is a **local-only** developer tool that captures structured traces of agent runs (LLM calls, tool calls, state updates, errors) and provides a **minimal timeline UI** to inspect what happened.

**Positioning:** *Debugger for AI agents* (not "observability").
**Scope:** Python SDK + local viewer. No cloud, no accounts.


## Why AgentDbg

When agents misbehave, logs aren't enough. AgentDbg gives you a timeline with:
- LLM prompts/responses (redacted by default)
- tool calls + results
- errors + stack traces
- loop warnings (you may see `LOOP_WARNING` events when repetition is detected)

**Goal:** instrument an agent in <10 minutes and immediately see a full run timeline.


## Install (local dev)

This repo is `uv`-managed.

```bash
uv venv
uv sync
uv pip install -e .
```

(If you don't use `uv`, a standard editable install works too.)


## Quickstart

Get a full run timeline in a few minutes: instrument one function, run it, then open the viewer.

### 1. Instrument your agent

Wrap your agent entrypoint with `@trace` and record LLM and tool activity:

```python
from agentdbg import trace, record_tool_call, record_llm_call

@trace
def run_agent():
    record_tool_call(
        name="search_db",
        args={"query": "find users"},
        result={"count": 2},
    )
    record_llm_call(
        model="gpt-4",
        prompt="Summarize the results.",
        response="Found 2 users.",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )

run_agent()
```

Traces are written under `~/.agentdbg/runs/<run_id>/` (or `AGENTDBG_DATA_DIR`).

### 2. View the timeline

```bash
agentdbg view
```

Starts a local server (default `127.0.0.1:8712`) and opens the UI. Use **List runs** and **View a specific run** below to pick a run.

### Try the example

From the repo root (after `uv sync` and `uv pip install -e .`):

```bash
python examples/minimal_agent/main.py
agentdbg view
```


## CLI

### List runs

```bash
agentdbg list
agentdbg list --limit 50
agentdbg list --json
```

### View a specific run

```bash
agentdbg view <RUN_ID>
agentdbg view --host 127.0.0.1 --port 8712
agentdbg view --no-browser
agentdbg view --json
```

### Export a run

```bash
agentdbg export <RUN_ID> --out run.json
```


## Storage layout

AgentDbg writes traces locally:

* Default data dir: `~/.agentdbg/`
* Runs live under: `~/.agentdbg/runs/<run_id>/`

  * `run.json` (metadata)
  * `events.jsonl` (append-only events)

Override the location:

```bash
export AGENTDBG_DATA_DIR=/path/to/agentdbg-data
```


## Redaction & privacy

Redaction is **ON by default** (`AGENTDBG_REDACT=1`).

AgentDbg redacts values for payload keys that match configured substrings (case-insensitive) and truncates very large fields.

Key env vars:

```bash
export AGENTDBG_REDACT=1
export AGENTDBG_REDACT_KEYS="api_key,token,authorization,cookie,secret,password"
export AGENTDBG_MAX_FIELD_BYTES=20000
```


## Development

Run tests:

```bash
uv run pytest
```

Run the example:

```bash
python examples/minimal_agent/main.py
agentdbg view
```


## Status

**Works today (v0.1):**

- `@trace` decorator + `record_llm_call` / `record_tool_call` / `record_state`
- Local JSONL storage under `~/.agentdbg/` with automatic redaction
- `agentdbg list`, `agentdbg view` (timeline UI), `agentdbg export`
- Loop detection (`LOOP_WARNING` events when repetitive patterns detected)
- LangChain/LangGraph callback handler (optional; requires `langchain-core`)

**Planned (v0.2+):**

- Deterministic replay / tool mocking
- OpenAI Agents SDK adapter
- Eval + regression CI support
- Optional hosted trace store


## Integrations

AgentDbg is **framework-agnostic** at its core. The SDK works with any Python code.

### Available in v0.1

**LangChain / LangGraph** - optional callback handler that records LLM and tool events automatically. Requires `langchain-core` (install with `pip install agentdbg[langchain]`).

```python
from agentdbg import trace
from agentdbg.integrations import AgentDbgLangChainCallbackHandler

@trace
def run_agent():
    handler = AgentDbgLangChainCallbackHandler()
    # pass handler to your chain/agent via config={"callbacks": [handler]}
    ...
```

See `examples/langchain_minimal/` for a runnable example.

### Planned

- **OpenAI Agents SDK** adapter
- **Agno** adapter
- Others as needed (AutoGen, CrewAI, custom loops)

These are not implemented yet. Until then, use the core SDK: wrap your entrypoint with `@trace` and call `record_llm_call` / `record_tool_call` from your own callbacks.


## License

TBD
