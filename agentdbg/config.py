"""Configuration for AgentDbg: redaction, loop detection, and data directory."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Defaults (mirror env defaults)
_DEFAULT_REDACT = True
_DEFAULT_REDACT_KEYS = [
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
]
_DEFAULT_MAX_FIELD_BYTES = 20000
_DEFAULT_LOOP_WINDOW = 12
_DEFAULT_LOOP_REPETITIONS = 3

_MIN_MAX_FIELD_BYTES = 100
_MIN_LOOP_WINDOW = 4
_MIN_LOOP_REPETITIONS = 2


@dataclass
class AgentDbgConfig:
    """Runtime configuration for tracing, redaction, and loop detection."""

    redact: bool
    redact_keys: list[str]
    max_field_bytes: int
    loop_window: int
    loop_repetitions: int
    data_dir: Path


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML from path. Return {} if file missing, invalid, or yaml unavailable."""
    if yaml is None:
        return {}
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _apply_yaml(config: dict[str, Any], key: str, default: Any) -> Any:
    """Get value from config dict if present and valid; else return default."""
    if key not in config:
        return default
    val = config[key]
    if key == "redact":
        return bool(val) if val is not None else default
    if key == "redact_keys":
        if isinstance(val, list) and all(isinstance(x, str) for x in val):
            return list(val)
        return default
    if key == "max_field_bytes":
        try:
            return max(_MIN_MAX_FIELD_BYTES, int(val))
        except (TypeError, ValueError):
            return default
    if key == "loop_window":
        try:
            return max(_MIN_LOOP_WINDOW, int(val))
        except (TypeError, ValueError):
            return default
    if key == "loop_repetitions":
        try:
            return max(_MIN_LOOP_REPETITIONS, int(val))
        except (TypeError, ValueError):
            return default
    if key == "data_dir":
        if val is None:
            return default
        return Path(val) if isinstance(val, (str, Path)) else default
    return default


def load_config(project_root: Path | None = None) -> AgentDbgConfig:
    """
    Load AgentDbgConfig with precedence (highest first):
    1. Environment variables
    2. .agentdbg/config.yaml in project root (if present)
    3. ~/.agentdbg/config.yaml
    """
    base = Path.home() / ".agentdbg"
    redact = _DEFAULT_REDACT
    redact_keys = _DEFAULT_REDACT_KEYS.copy()
    max_field_bytes = _DEFAULT_MAX_FIELD_BYTES
    loop_window = _DEFAULT_LOOP_WINDOW
    loop_repetitions = _DEFAULT_LOOP_REPETITIONS
    data_dir = base

    # 3. User config
    user_config_path = base / "config.yaml"
    user_cfg = _load_yaml(user_config_path)
    if user_cfg:
        redact = _apply_yaml(user_cfg, "redact", redact)
        redact_keys = _apply_yaml(user_cfg, "redact_keys", redact_keys)
        max_field_bytes = _apply_yaml(user_cfg, "max_field_bytes", max_field_bytes)
        loop_window = _apply_yaml(user_cfg, "loop_window", loop_window)
        loop_repetitions = _apply_yaml(user_cfg, "loop_repetitions", loop_repetitions)
        data_dir = _apply_yaml(user_cfg, "data_dir", data_dir)

    # 2. Project config (overrides user)
    # TODO: `cwd()` might not be the best default for CLI root:
    #       If the tool is called from another location, CWD
    #       will not set the root to the project, but the place
    #       where CLI was called from.
    root = project_root if project_root is not None else Path.cwd()
    project_config_path = root / ".agentdbg" / "config.yaml"
    proj_cfg = _load_yaml(project_config_path)
    if proj_cfg:
        redact = _apply_yaml(proj_cfg, "redact", redact)
        redact_keys = _apply_yaml(proj_cfg, "redact_keys", redact_keys)
        max_field_bytes = _apply_yaml(proj_cfg, "max_field_bytes", max_field_bytes)
        loop_window = _apply_yaml(proj_cfg, "loop_window", loop_window)
        loop_repetitions = _apply_yaml(proj_cfg, "loop_repetitions", loop_repetitions)
        data_dir = _apply_yaml(proj_cfg, "data_dir", data_dir)

    # 1. Env overrides (only when the key is explicitly set in the environment)
    if "AGENTDBG_REDACT" in os.environ:
        redact = os.environ["AGENTDBG_REDACT"].strip().lower() in ("1", "true", "yes")

    if "AGENTDBG_REDACT_KEYS" in os.environ:
        env_keys = os.environ["AGENTDBG_REDACT_KEYS"]
        redact_keys = [k.strip() for k in env_keys.split(",") if k.strip()]

    if "AGENTDBG_MAX_FIELD_BYTES" in os.environ:
        try:
            max_field_bytes = max(_MIN_MAX_FIELD_BYTES, int(os.environ["AGENTDBG_MAX_FIELD_BYTES"]))
        except ValueError:
            pass

    if "AGENTDBG_LOOP_WINDOW" in os.environ:
        try:
            loop_window = max(_MIN_LOOP_WINDOW, int(os.environ["AGENTDBG_LOOP_WINDOW"]))
        except ValueError:
            pass

    if "AGENTDBG_LOOP_REPETITIONS" in os.environ:
        try:
            loop_repetitions = max(_MIN_LOOP_REPETITIONS, int(os.environ["AGENTDBG_LOOP_REPETITIONS"]))
        except ValueError:
            pass

    if "AGENTDBG_DATA_DIR" in os.environ:
        env_data = os.environ["AGENTDBG_DATA_DIR"].strip()
        if env_data:
            data_dir = Path(env_data).expanduser()

    return AgentDbgConfig(
        redact=redact,
        redact_keys=redact_keys,
        max_field_bytes=max_field_bytes,
        loop_window=loop_window,
        loop_repetitions=loop_repetitions,
        data_dir=data_dir,
    )
