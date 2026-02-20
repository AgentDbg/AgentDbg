"""Tests for event helpers: JSON-safety and depth limit (consistent with redaction)."""
import pytest

from agentdbg.constants import DEPTH_LIMIT, TRUNCATED_MARKER
from agentdbg.events import _ensure_json_safe, _json_safe_value


def test_json_safe_value_depth_exceeded_returns_truncated_marker():
    """When depth is exceeded, _json_safe_value returns TRUNCATED_MARKER (consistent with _redact_and_truncate)."""
    # Nest deeper than DEPTH_LIMIT so the inner value is at depth > DEPTH_LIMIT
    deep = "leaf"
    for _ in range(DEPTH_LIMIT + 1):
        deep = [deep]
    result = _ensure_json_safe(deep)
    # Navigate to the innermost element
    inner = result
    for _ in range(DEPTH_LIMIT + 1):
        assert isinstance(inner, list)
        assert len(inner) == 1
        inner = inner[0]
    assert inner == TRUNCATED_MARKER


def test_json_safe_value_at_limit_preserves_value():
    """At exactly DEPTH_LIMIT depth we still recurse; only beyond it we substitute TRUNCATED_MARKER."""
    # Nest exactly DEPTH_LIMIT levels of lists, with a string at the bottom
    inner = "ok"
    for _ in range(DEPTH_LIMIT):
        inner = [inner]
    result = _ensure_json_safe(inner)
    current = result
    for _ in range(DEPTH_LIMIT):
        assert isinstance(current, list)
        assert len(current) == 1
        current = current[0]
    assert current == "ok"
