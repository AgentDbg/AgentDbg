# Integrations

## Philosophy

AgentDbg is **framework-agnostic** at the core. The SDK is a thin layer: you call `@trace` and `record_llm_call` / `record_tool_call` / `record_state` from any Python code. No required dependency on LangChain, OpenAI Agents SDK, or others.

**Adapters** are thin translation layers: they hook into a framework's callbacks and emit AgentDbg events. They do not lock you into that framework for the rest of your app.

---

## Available

### LangChain / LangGraph callback handler

**Status: available.** An optional callback handler lives at `agentdbg.integrations.langchain`. It records LLM calls and tool calls to the active AgentDbg run automatically.

**Requirements:** `langchain-core` must be installed. Install the optional dependency group:

```bash
pip install -e ".[langchain]"
```

If `langchain-core` is not installed, importing the integration raises a clear `ImportError` with install instructions. The integration is optional; the core package does not depend on it.

**Usage:**

```python
from agentdbg import trace
from agentdbg.integrations import AgentDbgLangChainCallbackHandler

@trace
def run_agent():
    handler = AgentDbgLangChainCallbackHandler()
    config = {"callbacks": [handler]}

    # Use config with any LangChain chain, LLM, or tool:
    result = my_chain.invoke(input_data, config=config)
    return result
```

The handler captures:

- **LLM calls** (`on_llm_start` / `on_chat_model_start` -> `on_llm_end`): records model name, prompt, response, and token usage via `record_llm_call`.
- **Tool calls** (`on_tool_start` -> `on_tool_end` / `on_tool_error`): records tool name, args, result, and error status via `record_tool_call`.

See `examples/langchain/minimal.py` for a runnable example:

```bash
uv run --extra langchain python examples/langchain/minimal.py
agentdbg view
```

**Guardrails (e.g. `stop_on_loop`) with LangChain / LangGraph:**
All guardrails work with the callback handler. When a guardrail fires, the handler raises `_AgentDbgAbortSignal` (a `BaseException`) which bypasses both LangChain's callback error handling and LangGraph's graph executor — stopping the run immediately and preventing further token-wasting LLM calls. See [Guardrails](guardrails.md) for details. To reuse a handler across runs, call `handler.reset()` between runs.

**Notes:**

- The handler requires an active AgentDbg run - wrap your entrypoint with `@trace` or set `AGENTDBG_IMPLICIT_RUN=1`.
- Tool errors are recorded as `TOOL_CALL` events with `status="error"` and include the error message.
- LLM errors are recorded as `LLM_CALL` events with `status="error"` (not as separate `ERROR` events).

---

### OpenAI Agents SDK tracing adapter

**Status: available.** An optional adapter lives at `agentdbg.integrations.openai_agents`. Importing it registers an OpenAI Agents tracing processor that forwards SDK generation, function, and handoff spans into the active AgentDbg run.

**Requirements:** `openai-agents` must be installed. Install the optional OpenAI dependency group (the `openai` group contains `openai-agents`):

```bash
pip install -e ".[openai]"
```

If `openai-agents` is not installed, importing the integration raises a clear `ImportError` with install instructions. The integration is optional; the core package does not depend on it.

**Usage:**

```python
from agentdbg import trace
from agentdbg.integrations import openai_agents  # registers hooks


@trace
def run_agent():
    # ... OpenAI Agents SDK code ...
    pass
```

The adapter captures:

- **LLM calls** (`GenerationSpanData`): records model, prompt, response, and usage via `record_llm_call`.
- **Tool calls** (`FunctionSpanData`): records tool name, args, result, and error status via `record_tool_call`.
- **Handoffs** (`HandoffSpanData`): records a `TOOL_CALL` named `handoff`, with framework-specific details stored in `meta`.

See `examples/openai_agents/minimal.py` for a runnable fake-data example:

```bash
uv run --extra openai python examples/openai_agents/minimal.py
agentdbg view
```

**Guardrails with OpenAI Agents SDK:**
All guardrails work with the tracing processor. When a guardrail fires, the processor raises `_AgentDbgAbortSignal` (a `BaseException`) which bypasses the SDK's `except Exception` error handling — stopping the run immediately:

```python
from agentdbg import trace, AgentDbgLoopAbort

@trace(stop_on_loop=True)
def run_agent():
    result = Runner.run_sync(agent, input)
    return result
```

As a defensive fallback, the exception is also stored on `PROCESSOR.abort_exception` with a `PROCESSOR.raise_if_aborted()` convenience method.

**Notes:**

- The adapter records events only while an explicit AgentDbg run is active; wrap your entrypoint with `@trace` or `traced_run(...)`.
- Framework-specific span details stay in `meta.openai_agents.*`, not the event payload.
- The example uses low-level SDK tracing spans with deterministic fake data, so it needs no API key and makes no model calls.

---

### CrewAI execution-hook adapter

**Status: available.** An optional adapter lives at `agentdbg.integrations.crewai`. Importing it registers CrewAI execution hooks that automatically record LLM and tool calls into the active AgentDbg run.

**Requirements:** `crewai[tools]` must be installed. Install the optional dependency group:

```bash
pip install -e ".[crewai]"
```

If `crewai` is not installed, importing the integration raises a clear `ImportError` with install instructions.

**Usage:**

```python
import agentdbg
from agentdbg.integrations import crewai as adbg_crewai  # registers hooks

@agentdbg.trace
def run_crew():
    # ... your CrewAI crew.kickoff() or flow.kickoff() ...
    pass
```

The adapter captures:

- **LLM calls** (`before_llm_call` / `after_llm_call`): records model, prompt messages, and response via `record_llm_call`.
- **Tool calls** (`before_tool_call` / `after_tool_call`): records tool name, args, result, and timing via `record_tool_call`.

Framework-specific context (agent role, task description, executor ID) is stored in `meta.crewai.*`.

**Notes:**

- The adapter requires an active AgentDbg run — wrap your entrypoint with `@trace` or `traced_run(...)`.
- Hook ordering caveat: if another before-hook returns `False` and blocks execution, that specific call may not be captured.
- No runnable example script yet — see the [Known issues in CHANGELOG](../CHANGELOG.md) for status.

---

## Planned

Planned framework adapters (not yet implemented):

1. **Agno** - optional adapter for Agno-based agents.
2. Others as needed (e.g. AutoGen, custom loops).

For guidance on adding new integrations (optional deps, mapping callbacks to `record_*`, tests), see [CONTRIBUTING.md](../CONTRIBUTING.md#adding-integrations--adapters) in the repo root.
