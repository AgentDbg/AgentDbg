# SDK

The AgentDbg Python SDK exposes a decorator, a context manager, and three recording functions. All recording attaches to the current active run (via contextvars). If there is no active run, recorders no-op unless implicit runs are enabled.

For the exact shape of stored events and run metadata, see the [Trace format](reference/trace-format.md) reference.

---

## `@trace`

Decorator that turns a function into a traced run.

```python
from agentdbg import trace

@trace
def run_agent():
    ...
```

**Behavior:**

- When the function is called **and no run is active:** creates a new run, emits `RUN_START`, runs the function, then emits `RUN_END`. On exception, emits `ERROR` then `RUN_END` with status `error` and re-raises.
- When called **inside an already active run:** runs the function without creating a new run or extra run events. All `record_*` calls inside still attach to the outer run.

---

## `traced_run`

Context manager that starts a traced run. Useful when a decorator doesn't fit - for example, in scripts, notebooks, or dynamic workflows.

```python
from agentdbg import traced_run, record_tool_call, record_llm_call

with traced_run(name="my_pipeline"):
    record_tool_call(name="fetch", args={"url": "..."}, result="...")
    record_llm_call(model="gpt-4", prompt="...", response="...")
```

**Behavior** is identical to `@trace`: creates a run if none is active, otherwise attaches to the existing one.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str \| None` | `None` | Run name (shown in `agentdbg list` and the timeline) |

---

## `record_llm_call`

Record an LLM call event.

```python
from agentdbg import record_llm_call

record_llm_call(
    model="gpt-4",
    prompt="Summarize the search results.",
    response="Found 2 users.",
    usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    meta={"step": "summarize"},
    provider="openai",
    temperature=0.7,
    stop_reason="stop",
    status="ok",
    error=None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | *(required)* | Model name (e.g. `"gpt-4"`, `"claude-3-opus"`) |
| `prompt` | `Any` | `None` | Prompt sent to the model (string, dict, or list) |
| `response` | `Any` | `None` | Model response |
| `usage` | `dict \| None` | `None` | Token usage: `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `meta` | `dict \| None` | `None` | Freeform metadata (labels, tags, etc.) |
| `provider` | `str` | `"unknown"` | Provider name (`"openai"`, `"anthropic"`, `"local"`, etc.) |
| `temperature` | `float \| None` | `None` | Sampling temperature |
| `stop_reason` | `str \| None` | `None` | Why the model stopped (`"stop"`, `"length"`, etc.) |
| `status` | `str` | `"ok"` | `"ok"` or `"error"` |
| `error` | `str \| Exception \| dict \| None` | `None` | Error details when `status="error"` |

Payload and meta are redacted and truncated according to config before storage.

---

## `record_tool_call`

Record a tool call event.

```python
from agentdbg import record_tool_call

record_tool_call(
    name="search_db",
    args={"query": "active users"},
    result={"count": 42},
    meta=None,
    status="ok",
    error=None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | Tool name |
| `args` | `Any` | `None` | Arguments passed to the tool |
| `result` | `Any` | `None` | Tool return value |
| `meta` | `dict \| None` | `None` | Freeform metadata |
| `status` | `str` | `"ok"` | `"ok"` or `"error"` |
| `error` | `str \| Exception \| dict \| None` | `None` | Error details when `status="error"` |

**Recording a failed tool call:**

```python
try:
    result = my_tool(args)
    record_tool_call(name="my_tool", args=args, result=result)
except Exception as e:
    record_tool_call(name="my_tool", args=args, status="error", error=e)
    raise
```

Payload and meta are redacted and truncated.

---

## `record_state`

Record a state-update event (e.g. agent state snapshot between steps).

```python
from agentdbg import record_state

record_state(
    state={"step": 3, "messages": ["..."]},
    meta={"label": "after_search"},
    diff=None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `state` | `Any` | `None` | State snapshot (object or string) |
| `meta` | `dict \| None` | `None` | Freeform metadata |
| `diff` | `Any` | `None` | Optional diff from previous state |

Redaction and truncation apply. Does not increment LLM/tool counts; useful for timeline context.

---

## Example: tracing a ReAct-style agent loop

A typical pattern - instrument a loop that alternates between LLM reasoning and tool execution:

```python
from agentdbg import trace, record_llm_call, record_tool_call, record_state

TOOLS = {"search": search_fn, "calculator": calc_fn}

@trace
def react_agent(question: str):
    messages = [{"role": "user", "content": question}]

    for step in range(10):
        response = llm_chat(messages)
        record_llm_call(
            model="gpt-4",
            prompt=messages,
            response=response,
            usage=response.get("usage"),
        )

        action = parse_action(response)
        if action is None:
            return response["content"]

        tool_fn = TOOLS[action["tool"]]
        result = tool_fn(**action["args"])
        record_tool_call(
            name=action["tool"],
            args=action["args"],
            result=result,
        )

        messages.append({"role": "assistant", "content": response["content"]})
        messages.append({"role": "tool", "content": str(result)})
        record_state(state={"step": step, "messages_count": len(messages)})

    return "Max steps reached"
```

After running, `agentdbg view` shows every LLM call, tool call, and state update in order - making it easy to see where the agent went wrong or got stuck in a loop.

---

## Implicit runs (`AGENTDBG_IMPLICIT_RUN=1`)

By default, calling `record_llm_call` / `record_tool_call` / `record_state` **outside** a `@trace`-decorated function or `traced_run` block does nothing.

If you set:

```bash
export AGENTDBG_IMPLICIT_RUN=1
```

then the first recorder call with no active run creates a single **implicit run**. All subsequent recorder calls attach to it until process exit, when the run is automatically finalized. Use this for scripts that don't have a single top-level entrypoint.

---

## Redaction and truncation

- **Redaction:** Dict keys matching configured patterns (e.g. `api_key`, `token`, `password`) have their values replaced with `__REDACTED__`. Applied recursively (depth limit: 10).
- **Truncation:** Strings exceeding `AGENTDBG_MAX_FIELD_BYTES` (default 20000) are truncated and suffixed with `__TRUNCATED__`.

**Config precedence (highest first):**

1. Environment variables (`AGENTDBG_REDACT`, `AGENTDBG_REDACT_KEYS`, `AGENTDBG_MAX_FIELD_BYTES`)
2. `.agentdbg/config.yaml` in project root
3. `~/.agentdbg/config.yaml`

See the [configuration reference](reference/config.md) for the full list of env vars, YAML keys, and defaults.
