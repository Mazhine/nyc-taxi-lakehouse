"""Contract loading and validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_contract(path: str | Path) -> dict[str, Any]:
    """Load a YAML data contract file."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "required_columns" not in data:
        raise ValueError(f"Invalid contract file: {path}")
    return data


def required_column_names(contract: dict[str, Any]) -> list[str]:
    """Return required column names from a contract dict."""
    return [c["name"] for c in contract.get("required_columns", [])]


def missing_columns(contract: dict[str, Any], actual: list[str]) -> list[str]:
    """Return required columns absent from the actual schema."""
    actual_set = set(actual)
    return [c for c in required_column_names(contract) if c not in actual_set]
