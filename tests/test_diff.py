"""Tests for agentdbg.diff: structural run comparison."""

import pytest

from agentdbg.baseline import create_baseline
from agentdbg.config import load_config
from agentdbg.diff import compute_diff, format_diff_text
from agentdbg.events import EventType, new_event
from agentdbg.storage import append_event, create_run, finalize_run


def _make_run(config, *, name="test_run", events=None, status="ok"):
    """Helper: create a run, append events, finalize, return run_id."""
    run = create_run(name, config)
    run_id = run["run_id"]
    counts = {"llm_calls": 0, "tool_calls": 0, "errors": 0, "loop_warnings": 0}
    for ev_type, ev_name, payload in events or []:
        ev = new_event(ev_type, run_id, ev_name, payload)
        append_event(run_id, ev, config)
        if ev_type == EventType.TOOL_CALL:
            counts["tool_calls"] += 1
        elif ev_type == EventType.LLM_CALL:
            counts["llm_calls"] += 1
        elif ev_type == EventType.ERROR:
            counts["errors"] += 1
        elif ev_type == EventType.LOOP_WARNING:
            counts["loop_warnings"] += 1
    finalize_run(run_id, status, counts, config)
    return run_id


# ---------------------------------------------------------------------------
# Tool diff
# ---------------------------------------------------------------------------


def test_diff_detects_added_tools(temp_data_dir):
    config = load_config()
    events_a = [
        (EventType.TOOL_CALL, "search", {}),
        (EventType.TOOL_CALL, "parse", {}),
        (EventType.TOOL_CALL, "salesforce", {}),
    ]
    events_b = [(EventType.TOOL_CALL, "search", {})]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert "parse" in d.new_tools
    assert "salesforce" in d.new_tools
    assert d.removed_tools == []


def test_diff_detects_removed_tools(temp_data_dir):
    config = load_config()
    events_a = [(EventType.TOOL_CALL, "search", {})]
    events_b = [
        (EventType.TOOL_CALL, "search", {}),
        (EventType.TOOL_CALL, "parse", {}),
    ]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert "parse" in d.removed_tools
    assert d.new_tools == []


# ---------------------------------------------------------------------------
# Event count diff
# ---------------------------------------------------------------------------


def test_diff_detects_changed_event_counts(temp_data_dir):
    config = load_config()
    events_a = [
        (EventType.TOOL_CALL, "t", {}),
        (EventType.TOOL_CALL, "t", {}),
        (EventType.LLM_CALL, "gpt-4", {}),
    ]
    events_b = [(EventType.TOOL_CALL, "t", {})]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert d.event_count_diff["TOOL_CALL"] == (2, 1)
    assert d.event_count_diff["LLM_CALL"] == (1, 0)


# ---------------------------------------------------------------------------
# Summary diff
# ---------------------------------------------------------------------------


def test_diff_detects_summary_changes(temp_data_dir):
    config = load_config()
    events_a = [(EventType.TOOL_CALL, "t", {}) for _ in range(5)]
    events_b = [(EventType.TOOL_CALL, "t", {})]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert "tool_calls" in d.summary_diff
    assert d.summary_diff["tool_calls"] == (5, 1)


# ---------------------------------------------------------------------------
# Identical runs
# ---------------------------------------------------------------------------


def test_diff_identical_runs_no_changes(temp_data_dir):
    config = load_config()
    events = [(EventType.TOOL_CALL, "search", {})]
    rid_a = _make_run(config, events=events, name="run_a")
    rid_b = _make_run(config, events=events, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert d.new_tools == []
    assert d.removed_tools == []
    assert d.model_changes == {"added": [], "removed": []}
    for et, (ca, cb) in d.event_count_diff.items():
        assert ca == cb


# ---------------------------------------------------------------------------
# Diff against baseline dict
# ---------------------------------------------------------------------------


def test_diff_against_baseline(temp_data_dir):
    config = load_config()
    bl_events = [(EventType.TOOL_CALL, "search", {})]
    bl_rid = _make_run(config, events=bl_events, name="baseline")
    bl = create_baseline(bl_rid, config)

    run_events = [
        (EventType.TOOL_CALL, "search", {}),
        (EventType.TOOL_CALL, "new_api", {}),
    ]
    run_id = _make_run(config, events=run_events, name="current")

    d = compute_diff(run_id, baseline=bl, config=config)
    assert "new_api" in d.new_tools
    assert d.run_b_id == bl_rid


# ---------------------------------------------------------------------------
# Model changes
# ---------------------------------------------------------------------------


def test_diff_model_changes(temp_data_dir):
    config = load_config()
    events_a = [(EventType.LLM_CALL, "gpt-4", {})]
    events_b = [(EventType.LLM_CALL, "gpt-3.5-turbo", {})]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    assert "gpt-4" in d.model_changes["added"]
    assert "gpt-3.5-turbo" in d.model_changes["removed"]


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def test_format_diff_text_output(temp_data_dir):
    config = load_config()
    events_a = [(EventType.TOOL_CALL, "search", {})]
    events_b = [(EventType.TOOL_CALL, "parse", {})]
    rid_a = _make_run(config, events=events_a, name="run_a")
    rid_b = _make_run(config, events=events_b, name="run_b")

    d = compute_diff(rid_a, run_b_id=rid_b, config=config)
    text = format_diff_text(d)
    assert "Run comparison:" in text
    assert rid_a[:8] in text


# ---------------------------------------------------------------------------
# Error: neither run_b nor baseline
# ---------------------------------------------------------------------------


def test_compute_diff_raises_without_target(temp_data_dir):
    config = load_config()
    rid = _make_run(config, events=[])
    with pytest.raises(ValueError, match="Either run_b_id or baseline"):
        compute_diff(rid, config=config)
