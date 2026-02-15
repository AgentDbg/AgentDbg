"""
Tests for tracing: @trace decorator, RUN_START/RUN_END, ERROR path, run.json status.
Uses a temp dir via AGENTDBG_DATA_DIR so runs are isolated from user data.
"""
import pytest

from agentdbg.config import load_config
from agentdbg.events import EventType
from agentdbg.storage import load_events, load_run_meta
from agentdbg.tracing import trace

from conftest import get_latest_run_id


def test_trace_success_run_start_run_end_and_run_json_ok(temp_data_dir):
    """Success path: RUN_START + RUN_END written, run.json status ok, counts correct."""
    @trace
    def ok_run():
        return 42

    result = ok_run()
    assert result == 42

    config = load_config()
    run_id = get_latest_run_id(config)
    events = load_events(run_id, config)
    run_meta = load_run_meta(run_id, config)

    run_start = [e for e in events if e.get("event_type") == EventType.RUN_START.value]
    run_end = [e for e in events if e.get("event_type") == EventType.RUN_END.value]
    assert len(run_start) == 1, "expected exactly one RUN_START"
    assert len(run_end) == 1, "expected exactly one RUN_END"

    assert run_meta["status"] == "ok"
    counts = run_meta["counts"]
    assert counts["llm_calls"] == 0
    assert counts["tool_calls"] == 0
    assert counts["errors"] == 0


def test_trace_error_emits_error_and_run_json_status_error(temp_data_dir):
    """Error path: ERROR event exists, run.json status error."""
    @trace
    def failing_run():
        raise ValueError("expected test failure")

    with pytest.raises(ValueError, match="expected test failure"):
        failing_run()

    config = load_config()
    run_id = get_latest_run_id(config)
    events = load_events(run_id, config)
    run_meta = load_run_meta(run_id, config)

    errors = [e for e in events if e.get("event_type") == EventType.ERROR.value]
    assert len(errors) == 1, "expected exactly one ERROR event"
    assert errors[0]["payload"].get("message") == "expected test failure"

    assert run_meta["status"] == "error"
    assert run_meta["counts"]["errors"] == 1
