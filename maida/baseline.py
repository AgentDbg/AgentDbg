"""Baseline snapshot creation, persistence, and shared metric extraction.

A baseline captures the structural behavior of a completed run (tool path,
event sequence, token usage, etc.) for later comparison by ``assertions.py``.
"""

import json
from collections import Counter
from pathlib import Path

from agentdbg.config import AgentDbgConfig
from agentdbg.events import EventType, utc_now_iso_ms_z
from agentdbg.storage import load_events, load_run_meta

_BASELINE_SCHEMA_VERSION = "0.1"


def extract_run_metrics(meta: dict, events: list[dict]) -> dict:
    """Extract structural metrics from run metadata and events.

    Shared by ``create_baseline`` and ``run_assertions`` so both operate on
    identical metric derivation logic.
    """
    counts = meta.get("counts") or {}
    tool_names_ordered: set[str] = []
    tool_counter: Counter[str] = Counter()
    llm_models: set[str] = set()
    event_type_seq: list[str] = []
    total_tokens = 0
    guardrail_events: list[dict] = []

    for ev in events:
        et = ev.get("event_type", "")
        event_type_seq.append(et)

        if et == EventType.TOOL_CALL.value:
            name = ev.get("name", "")
            tool_counter[name] += 1
            if name not in tool_names_ordered:
                tool_names_ordered.append(name)

        elif et == EventType.LLM_CALL.value:
            model = ev.get("name", "")
            if model:
                llm_models.add(model)
            payload = ev.get("payload") or {}
            usage = payload.get("usage") or {}
            tok = usage.get("total_tokens")
            if isinstance(tok, (int, float)):
                total_tokens += int(tok)

        elif et == EventType.ERROR.value:
            payload = ev.get("payload") or {}
            if "guardrail" in payload:
                guardrail_events.append(ev)

    return {
        "summary": {
            "status": meta.get("status", ""),
            "total_events": len(events),
            "llm_calls": counts.get("llm_calls", 0),
            "tool_calls": counts.get("tool_calls", 0),
            "errors": counts.get("errors", 0),
            "loop_warnings": counts.get("loop_warnings", 0),
            "duration_ms": meta.get("duration_ms", 0),
            "total_tokens": total_tokens,
        },
        "tool_path": sorted(tool_names_ordered),
        "tool_call_counts": dict(tool_counter),
        "llm_models_used": sorted(llm_models),
        "event_type_sequence": event_type_seq,
        "guardrail_events": guardrail_events,
        "final_status": meta.get("status", ""),
    }


def create_baseline(run_id: str, config: AgentDbgConfig) -> dict:
    """Load a completed run and return a baseline snapshot dict."""
    meta = load_run_meta(run_id, config)
    events = load_events(run_id, config)
    metrics = extract_run_metrics(meta, events)
    return {
        "schema_version": _BASELINE_SCHEMA_VERSION,
        "created_at": utc_now_iso_ms_z(),
        "source_run_id": run_id,
        "source_run_name": meta.get("run_name"),
        **metrics,
    }


def save_baseline(baseline: dict, path: Path, force: bool = True) -> None:
    """Write a baseline dict to *path* as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(
            f"Baseline file already exists: {path}. "
            "Cowardly refusing to overwrite without --force."
        )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)


def load_baseline(path: Path) -> dict:
    """Read a baseline JSON file and return its contents.

    Raises ``FileNotFoundError`` if *path* does not exist or
    ``json.JSONDecodeError`` if the file is malformed.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
