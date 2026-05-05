# Writing AgentDbg Integration Adapters

This guide captures the patterns and pitfalls discovered while building the LangChain, OpenAI Agents SDK, and CrewAI integrations. Follow these guidelines to avoid repeating the same issues.

---

## The core problem

Every agent framework has its own error handling around callbacks/hooks/processors. When agentdbg detects a loop or a guardrail violation, it raises an exception. The framework almost always catches it:

| Framework | Hook mechanism | Error handling |
|---|---|---|
| LangChain / LangGraph | `BaseCallbackHandler` methods | `except Exception` in callback manager; graph executor also catches `Exception` from nodes |
| OpenAI Agents SDK | `TracingProcessor.on_span_end` | `except Exception` in `SynchronousMultiTracingProcessor` |
| CrewAI | Execution hooks | `except Exception` in hook runner |

Because `AgentDbgGuardrailExceeded` inherits from `Exception`, it gets caught and swallowed at **two levels**: once by the callback dispatcher and once by the framework's execution loop.

---

## The `_AgentDbgAbortSignal` pattern

The solution is `_AgentDbgAbortSignal`, an internal `BaseException` subclass defined in `agentdbg.exceptions`. `BaseException` subclasses bypass `except Exception` blocks — the same mechanism Python uses for `KeyboardInterrupt`, `SystemExit`, and `asyncio.CancelledError`.

### How it works

```
Framework calls adapter hook
  → adapter calls record_llm_call / record_tool_call
    → guardrail fires → raises AgentDbgGuardrailExceeded (Exception)
  → adapter catches it, stores on _abort_exception
  → adapter raises _AgentDbgAbortSignal(cause) (BaseException)
→ framework's `except Exception` does NOT catch it
→ signal propagates through the framework's execution loop
→ signal reaches traced_run / @trace context manager
→ _run_context catches _AgentDbgAbortSignal
→ records ERROR + RUN_END
→ re-raises the wrapped AgentDbgGuardrailExceeded (the public exception type)
→ user sees AgentDbgLoopAbort or AgentDbgGuardrailExceeded
```

### Rules for using `_AgentDbgAbortSignal`

1. **Always wrap the original exception.** `_AgentDbgAbortSignal(cause)` stores the original `AgentDbgGuardrailExceeded` on `.cause`. The lifecycle layer unwraps it so the user sees the public exception type.

2. **Always store the original on `_abort_exception` before raising the signal.** This is a defensive fallback — if the signal is caught by the framework despite being a `BaseException`, the user can still call `raise_if_aborted()`.

3. **Use `raise _AgentDbgAbortSignal(e) from e`** to preserve the exception chain.

4. **Never raise `_AgentDbgAbortSignal` from the core SDK** (`record_llm_call`, `record_tool_call`, etc.). The core raises `AgentDbgGuardrailExceeded` (an `Exception`). Only integration adapters escalate to `_AgentDbgAbortSignal` because they know the framework will catch `Exception`.

---

## Guard subsequent callbacks after an abort

Once a guardrail fires, the framework may continue calling your adapter for subsequent operations. You must block these immediately:

```python
def _check_aborted(self) -> None:
    if self._abort_exception is not None:
        raise _AgentDbgAbortSignal(self._abort_exception)
```

Call `_check_aborted()` at the **start** of every hook method that initiates a new operation (`on_llm_start`, `on_tool_start`, `on_chat_model_start`, `on_span_start`, etc.). This prevents:
- New LLM API calls from being made (wasting tokens)
- New tool invocations from running
- Misleading events from being recorded after the abort

---

## Do not auto-reset abort state

A common mistake: resetting `_abort_exception = None` at the start of each top-level callback. This defeats the abort guard because the framework keeps calling hooks.

**Wrong:**
```python
def on_llm_start(self, ...):
    if parent_run_id is None:
        self._abort_exception = None  # BAD: clears the abort
        self.raise_error = False
```

**Right:** Provide an explicit `reset()` method for handler reuse across separate runs:
```python
def reset(self) -> None:
    self._abort_exception = None
```

The user calls `reset()` or creates a new handler instance between runs.

---

## Handle errors in error callbacks

Frameworks call error hooks (`on_llm_error`, `on_tool_error`) when operations fail. If you call `record_llm_call(status="error")` inside these, loop detection may fire. You must catch `AgentDbgGuardrailExceeded` in error hooks too:

```python
def on_llm_error(self, error, **kwargs):
    try:
        record_llm_call(model=model, status="error", error=error, ...)
    except AgentDbgGuardrailExceeded as e:
        self._abort_exception = e
        raise _AgentDbgAbortSignal(e) from e
```

---

## Loop detection deduplication

The core loop detector emits one `LOOP_WARNING` per distinct pattern and deduplicates subsequent detections. When `stop_on_loop=True`, the core re-raises `AgentDbgLoopAbort` on every detection opportunity (even for already-emitted patterns) so that frameworks that swallow the first exception still get interrupted.

Your adapter does not need to handle dedup — the core handles it in `_maybe_emit_loop_warning`. Your adapter only needs to:
1. Catch `AgentDbgGuardrailExceeded` from `record_*` calls
2. Escalate to `_AgentDbgAbortSignal`
3. Guard subsequent hooks with `_check_aborted()`

---

## Async support

The `@trace` decorator detects async functions via `asyncio.iscoroutinefunction()` and uses an `async def` wrapper that `await`s inside the `_run_context`. Without this, the context manager tears down before the coroutine body executes, and no events are recorded.

If your integration involves async callbacks, ensure the adapter works in both sync and async contexts. The `_AgentDbgAbortSignal` pattern works identically in both — `BaseException` subclasses propagate through `await` chains.

---

## Nested `traced_run` inside `@trace`

When `traced_run(stop_on_loop=True)` is used inside an existing `@trace` run, the `_run_context` applies the inner guardrail params for the duration of the block. This is handled by the lifecycle layer — your adapter does not need to worry about it.

However, be aware that for sync code, the inner `traced_run` reuses the outer run (no new `run_id`). For async code where `@trace` wraps an async function, the outer context is properly maintained.

---

## Testing checklist

Every integration should have tests for:

1. **Normal event recording** — LLM calls and tool calls are recorded with correct payloads
2. **Error status recording** — failed operations record `status="error"` with error details
3. **Guardrail propagation** — when `stop_on_loop=True` fires, the abort signal propagates through the simulated framework and the run ends with `status="error"`
4. **Abort guard blocks subsequent operations** — after an abort, `on_*_start` methods raise immediately
5. **Handler reset** — `reset()` clears abort state for reuse
6. **Dedup** — only one `LOOP_WARNING` per distinct pattern, even when the abort is caught

Use `_simulate_framework_handle_event` helpers that mimic the framework's error handling:

```python
def _simulate_handle_event(handler, method_name, *args, **kwargs):
    """Simulate framework error handling: except Exception swallows errors."""
    try:
        getattr(handler, method_name)(*args, **kwargs)
    except Exception:
        # Framework swallows Exception but not BaseException
        pass
```

This ensures your tests verify that `_AgentDbgAbortSignal` (BaseException) propagates while `AgentDbgGuardrailExceeded` (Exception) would be swallowed.

---

## Quick reference

| Concern | Pattern |
|---|---|
| Guardrail exception from core | `AgentDbgGuardrailExceeded(Exception)` — caught by frameworks |
| Abort signal from adapter | `_AgentDbgAbortSignal(BaseException)` — bypasses frameworks |
| Store abort for fallback | `self._abort_exception = e` before raising signal |
| Guard subsequent hooks | `_check_aborted()` at start of every `on_*_start` / `on_span_start` |
| Reset for reuse | Explicit `reset()` method, never auto-reset in hooks |
| Error callbacks | Catch `AgentDbgGuardrailExceeded` in `on_*_error` too |
| Lifecycle handling | `_run_context` catches `_AgentDbgAbortSignal`, records ERROR + RUN_END, unwraps to public exception |
