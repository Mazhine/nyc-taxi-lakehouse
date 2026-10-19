"""Contract tests: schema presence, no silent acceptance of drift.

These tests guard the *contract itself* and the helper that compares it to an
actual schema. They need no Spark and run everywhere (CI, local Windows).
"""

from pathlib import Path

import yaml

from src.ingestion import load_contract, missing_columns

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "yellow_trips.v1.yaml"


def test_contract_loads_and_has_required_columns():
    """The shipped contract must parse and declare the expected structure."""
    contract = load_contract(CONTRACT)
    assert contract["contract"] == "yellow_trips"
    assert len(contract["required_columns"]) >= 10
    assert "rules" in contract and len(contract["rules"]) >= 3


def test_missing_column_detected():
    """A source schema lacking required columns must be reported (file-level quarantine)."""
    contract = load_contract(CONTRACT)
    actual = ["VendorID", "trip_distance"]  # deliberately incomplete
    missing = missing_columns(contract, actual)
    assert "tpep_pickup_datetime" in missing
    assert "total_amount" in missing


def test_extra_columns_allowed_but_required_must_hold():
    """Extra columns are tolerated; required ones must exist and rejections carry a reason."""
    contract = load_contract(CONTRACT)
    assert contract.get("allowed_extra_columns") is True
    assert contract.get("forbidden_missing_columns") is True
    raw = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert raw["quarantine"]["reason_field"] == "_quarantine_reason"
