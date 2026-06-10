"""
Protocol Runner — evaluates patient labs against YAML decision tables.
Rules live entirely in /protocols/*.yaml; no logic changes needed here
when protocols are updated.
"""

import yaml
from pathlib import Path

OPERATORS = {
    ">":          lambda a, b: a > b,
    "<":          lambda a, b: a < b,
    ">=":         lambda a, b: a >= b,
    "<=":         lambda a, b: a <= b,
    "==":         lambda a, b: a == b,
    "!=":         lambda a, b: a != b,
    "between":    lambda a, b: b[0] <= a <= b[1],
    "not_between":lambda a, b: not (b[0] <= a <= b[1]),
}

URGENCY_ORDER = {"urgent": 0, "soon": 1, "routine": 2, "monitor": 3}


def load_protocols(protocol_dir: str = "protocols") -> dict:
    protocols = {}
    for path in sorted(Path(protocol_dir).glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        protocols[data["protocol"]] = data
    return protocols


def _resolve(field: str, labs: dict, meds: dict):
    """Look up a field in labs first, then current_medications."""
    if field in labs:
        return labs[field]
    if field in meds:
        return meds[field]
    return None


def _eval_condition(cond: dict, labs: dict, meds: dict) -> bool:
    val = _resolve(cond["field"], labs, meds)
    if val is None:
        # Missing lab → condition fails; protocol YAML can mark required fields
        return False
    op = OPERATORS.get(cond["operator"])
    if op is None:
        raise ValueError(f"Unknown operator: {cond['operator']}")
    return op(val, cond["value"])


def _eval_rule(rule: dict, labs: dict, meds: dict) -> bool:
    conditions = rule.get("conditions", [])
    logic = rule.get("logic", "AND").upper()
    results = [_eval_condition(c, labs, meds) for c in conditions]
    if logic == "AND":
        return all(results)
    if logic == "OR":
        return any(results)
    raise ValueError(f"Unknown logic: {logic}")


def run_protocols(patient_data: dict, protocols: dict) -> list[dict]:
    """
    Returns a list of recommendations sorted by urgency (urgent first).
    Each recommendation includes rule metadata and proposed actions.
    """
    labs = patient_data.get("labs", {})
    meds = patient_data.get("current_medications", {})
    recs = []

    for protocol_name, protocol in protocols.items():
        for rule in protocol.get("rules", []):
            if not rule.get("enabled", True):
                continue
            if _eval_rule(rule, labs, meds):
                recs.append({
                    "rule_id":    rule["id"],
                    "protocol":   protocol_name,
                    "rule_name":  rule["name"],
                    "urgency":    rule.get("urgency", "routine"),
                    "actions":    rule.get("actions", []),
                    "rationale":  rule.get("rationale", ""),
                })

    recs.sort(key=lambda r: URGENCY_ORDER.get(r["urgency"], 99))
    return recs
