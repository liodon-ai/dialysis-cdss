"""
Gold-standard validation: run each test patient through the protocol engine
and assert the fired rule IDs match expected_outputs.json exactly.

Usage:
    pytest tests/test_gold_standard.py -v
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend.protocol_runner import load_protocols, run_protocols

PATIENTS       = json.loads((ROOT / "test_cases" / "patients.json").read_text())
EXPECTED       = json.loads((ROOT / "test_cases" / "expected_outputs.json").read_text())
PROTOCOL_DIR   = str(ROOT / "protocols")


@pytest.fixture(scope="session")
def protocols():
    return load_protocols(PROTOCOL_DIR)


def _patient_payload(p: dict) -> dict:
    return {
        "patient_id":          p["patient_id"],
        "session_date":        p["session_date"],
        "labs":                p.get("labs", {}),
        "current_medications": p.get("current_medications", {}),
    }


@pytest.mark.parametrize("patient", PATIENTS, ids=[p["patient_id"] for p in PATIENTS])
def test_rule_ids_match_gold_standard(patient, protocols):
    pid = patient["patient_id"]
    if pid not in EXPECTED:
        pytest.skip(f"No gold-standard entry for {pid}")

    recs = run_protocols(_patient_payload(patient), protocols)
    fired_ids = sorted(r["rule_id"] for r in recs)
    expected_ids = sorted(EXPECTED[pid]["expected_rule_ids"])

    assert fired_ids == expected_ids, (
        f"\n{pid}: rule mismatch"
        f"\n  fired:    {fired_ids}"
        f"\n  expected: {expected_ids}"
        f"\n  notes:    {EXPECTED[pid].get('notes', '')}"
    )


@pytest.mark.parametrize("patient", PATIENTS, ids=[p["patient_id"] for p in PATIENTS])
def test_no_unexpected_urgent_flags(patient, protocols):
    """Urgent recommendations must always appear in the expected output."""
    pid = patient["patient_id"]
    if pid not in EXPECTED:
        pytest.skip(f"No gold-standard entry for {pid}")

    recs = run_protocols(_patient_payload(patient), protocols)
    urgent_fired    = sorted(r["rule_id"] for r in recs if r["urgency"] == "urgent")
    urgent_expected = sorted(
        rid for rid, urg in zip(
            EXPECTED[pid]["expected_rule_ids"],
            EXPECTED[pid]["expected_urgencies"]
        ) if urg == "urgent"
    )

    assert urgent_fired == urgent_expected, (
        f"\n{pid}: urgent flag mismatch"
        f"\n  fired:    {urgent_fired}"
        f"\n  expected: {urgent_expected}"
    )


def test_all_protocols_load():
    p = load_protocols(PROTOCOL_DIR)
    assert len(p) >= 3, "Expected at least 3 protocol files"
    for name, data in p.items():
        assert "rules" in data, f"Protocol {name} has no 'rules' key"
        for rule in data["rules"]:
            assert "id" in rule
            assert "conditions" in rule
            assert "actions" in rule
