"""
Unit tests for CrewAI integration: pending logic, run-exit flush, and gating.

Tests avoid requiring CrewAI at runtime by mocking crewai.hooks for import
and using fake context objects for hook/pending behavior.
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentdbg._integration_utils import _clear_test_run_lifecycle_registry
from agentdbg.integrations._error import MissingOptionalDependencyError


@pytest.fixture(autouse=True)
def clear_lifecycle_registry():
    """Clear run lifecycle callbacks so crewai's enter/exit don't persist across tests."""
    _clear_test_run_lifecycle_registry()
    yield
    _clear_test_run_lifecycle_registry()


def _make_fake_crewai_hooks_import_error():
    """Make 'from crewai.hooks import ...' raise ImportError so we test optional-deps message."""
    class HooksFake:
        def __getattr__(self, name):
            raise ImportError("No module named 'crewai.hooks'")

    crewai_fake = type(sys)("crewai")
    crewai_fake.hooks = HooksFake()
    return crewai_fake


def test_import_crewai_without_extra_raises_clear_error():
    """When crewai.hooks is not importable, importing the integration raises MissingOptionalDependencyError with pip hint."""
    to_restore_mods = []
    for mod in list(sys.modules.keys()):
        if mod == "agentdbg.integrations.crewai" or mod.startswith("agentdbg.integrations.crewai."):
            to_restore_mods.append((mod, sys.modules.pop(mod)))
    old_crewai = sys.modules.get("crewai")
    fake = _make_fake_crewai_hooks_import_error()
    try:
        sys.modules["crewai"] = fake
        with pytest.raises(MissingOptionalDependencyError) as exc_info:
            __import__("agentdbg.integrations.crewai")
        assert "agentdbg[crewai]" in str(exc_info.value)
    finally:
        if old_crewai is not None:
            sys.modules["crewai"] = old_crewai
        elif "crewai" in sys.modules and sys.modules["crewai"] is fake:
            del sys.modules["crewai"]
        for mod, val in to_restore_mods:
            sys.modules[mod] = val
        if "agentdbg.integrations.crewai" not in sys.modules:
            try:
                __import__("agentdbg.integrations.crewai")
            except MissingOptionalDependencyError:
                pass


@pytest.fixture
def crewai_module_with_mocked_hooks():
    """Load agentdbg.integrations.crewai with crewai.hooks mocked so no real CrewAI is required."""
    # Provide a minimal hooks module that has the four register functions (no-ops)
    hooks = MagicMock()
    with patch.dict("sys.modules", {"crewai": MagicMock(), "crewai.hooks": hooks}):
        # Force reimport so our patch is used
        for mod in list(sys.modules.keys()):
            if mod == "agentdbg.integrations.crewai":
                del sys.modules[mod]
                break
        try:
            import agentdbg.integrations.crewai as crewai_mod
            yield crewai_mod
        finally:
            pass


def test_hook_gating_no_run_no_op(crewai_module_with_mocked_hooks, temp_data_dir):
    """When no active AgentDbg run, before_llm returns None and does not record."""
    crewai = crewai_module_with_mocked_hooks
    with patch.object(crewai, "_get_active_run_id", return_value=None):
        ctx = SimpleNamespace(executor=SimpleNamespace(), iterations=0, messages=[], llm=None)
        result = crewai._before_llm_call(ctx)
    assert result is None
    assert not crewai._pending_llm


def test_pending_llm_before_after_duration(crewai_module_with_mocked_hooks, temp_data_dir):
    """Before adds pending entry; after pops, computes duration_ms, records with status=ok."""
    crewai = crewai_module_with_mocked_hooks
    run_id = "test-run-123"
    with patch.object(crewai, "_get_active_run_id", return_value=run_id):
        ctx_before = SimpleNamespace(
            executor=SimpleNamespace(),
            iterations=1,
            messages=[{"role": "user", "content": "hi"}],
            llm=SimpleNamespace(model_name="gpt-4"),
        )
        crewai._before_llm_call(ctx_before)
        assert run_id in crewai._pending_llm
        assert len(crewai._pending_llm[run_id]) == 1

        entry = next(iter(crewai._pending_llm[run_id].values()))
        assert entry["model"] == "gpt-4"
        assert entry["messages"] == [{"role": "user", "content": "hi"}]

        ctx_after = SimpleNamespace(
            executor=ctx_before.executor,
            iterations=1,
            response="Hello!",
        )
        with patch.object(crewai, "record_llm_call", MagicMock()) as record:
            crewai._after_llm_call(ctx_after)
            record.assert_called_once()
            call_kw = record.call_args.kwargs
            assert call_kw.get("status") == "ok"
            assert call_kw.get("response") == "Hello!"
            assert "crewai" in (call_kw.get("meta") or {})
    # Pending should be cleared for that call
    assert not crewai._pending_llm.get(run_id) or len(crewai._pending_llm[run_id]) == 0


def test_flush_pending_on_run_exit_emits_error_events(crewai_module_with_mocked_hooks, temp_data_dir):
    """On run exit, any pending LLM/tool entries get synthetic events with status=error and meta.crewai.completion=missing_after_hook."""
    crewai = crewai_module_with_mocked_hooks
    run_id = "flush-run"
    crewai._pending_llm[run_id] = {
        (0, 0, 0): {
            "start_ts": 0.0,
            "messages": [{"role": "user", "content": "x"}],
            "model": "gpt-4",
            "meta": {"framework": "crewai"},
        }
    }
    crewai._pending_tool[run_id] = {
        ("my_tool", 0): {
            "start_ts": 0.0,
            "tool_input": {"q": 1},
            "meta": {"framework": "crewai"},
        }
    }
    with patch.object(crewai, "record_llm_call", MagicMock()) as record_llm:
        with patch.object(crewai, "record_tool_call", MagicMock()) as record_tool:
            crewai._flush_pending_for_run(run_id, None, None, None)
    record_llm.assert_called_once()
    record_tool.assert_called_once()
    llm_kw = record_llm.call_args.kwargs
    tool_kw = record_tool.call_args.kwargs
    assert llm_kw.get("status") == "error"
    assert tool_kw.get("status") == "error"
    assert (llm_kw.get("meta") or {}).get("crewai", {}).get("completion") == "missing_after_hook"
    assert (tool_kw.get("meta") or {}).get("crewai", {}).get("completion") == "missing_after_hook"
    assert run_id not in crewai._pending_llm
    assert run_id not in crewai._pending_tool


def test_flush_pending_with_exception_attaches_error_payload(crewai_module_with_mocked_hooks, temp_data_dir):
    """When run exits with exception, flushed pending events get exception in error payload (error_type, message, stack)."""
    crewai = crewai_module_with_mocked_hooks
    run_id = "exc-run"
    crewai._pending_llm[run_id] = {
        (0, 0, 0): {
            "start_ts": 0.0,
            "messages": [],
            "model": "unknown",
            "meta": {},
        }
    }
    try:
        raise ValueError("run failed")
    except ValueError:
        import sys
        exc_type, exc_value, tb = sys.exc_info()
    with patch.object(crewai, "record_llm_call", MagicMock()) as record_llm:
        crewai._flush_pending_for_run(run_id, exc_type, exc_value, tb)
    record_llm.assert_called_once()
    call_kw = record_llm.call_args.kwargs
    assert call_kw.get("status") == "error"
    assert call_kw.get("error") is not None
    assert call_kw["error"].get("error_type") == "ValueError"
    assert "run failed" in str(call_kw["error"].get("message", ""))
    assert call_kw["error"].get("stack") is not None and "ValueError" in call_kw["error"]["stack"]
