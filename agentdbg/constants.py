"""Shared constants: spec version, count schema, and redaction/truncation markers."""

REDACTED_MARKER = "__REDACTED__"
TRUNCATED_MARKER = "__TRUNCATED__"

# SPEC version for run.json and event payloads (single source of truth).
SPEC_VERSION = "0.1"


def default_counts() -> dict[str, int]:
    """Default counts per SPEC run.json schema. Keys: llm_calls, tool_calls, errors, loop_warnings."""
    return {
        "llm_calls": 0,
        "tool_calls": 0,
        "errors": 0,
        "loop_warnings": 0,
    }
