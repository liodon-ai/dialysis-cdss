"""
Protocol Runner — evaluates patient labs against YAML decision tables.
Rules live entirely in /protocols/*.yaml; no logic changes needed here
when protocols are updated.

Template syntax in action instructions:
  {field}          — resolves to the current value of a lab or med field
  {field + N}      — resolves to field value plus a numeric literal
  {field - N}
  {field * N}      — e.g. {epo_dose_units_per_week * 1.25} for a 25% increase
  {field / N}

If the field has no value (not prescribed / not drawn), the token is replaced
with "(not on file)".
"""

import re
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
    "is_null":    lambda a, b: a is None,   # b ignored; use value: null in YAML
    "is_not_null":lambda a, b: a is not None,
}

URGENCY_ORDER = {"urgent": 0, "soon": 1, "routine": 2, "monitor": 3}

_TEMPLATE_RE = re.compile(
    r"\{(\w+)"                          # field name
    r"(?:\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?))?"  # optional  op  number
    r"\}"
)


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


def _render(text: str, labs: dict, meds: dict) -> str:
    """Replace {field} / {field op N} tokens with real values."""
    def substitute(m: re.Match) -> str:
        field, op, rhs = m.group(1), m.group(2), m.group(3)
        val = _resolve(field, labs, meds)
        if val is None:
            return "(not on file)"
        if op and rhs:
            rhs_f = float(rhs)
            result = {"+": val + rhs_f, "-": val - rhs_f,
                      "*": val * rhs_f, "/": val / rhs_f}[op]
            # Show as int if the result is a whole number
            return str(int(result)) if result == int(result) else f"{result:.1f}"
        return str(int(val)) if isinstance(val, float) and val == int(val) else str(val)

    return _TEMPLATE_RE.sub(substitute, text)


def _eval_condition(cond: dict, labs: dict, meds: dict) -> bool:
    field    = cond["field"]
    operator = cond["operator"]
    value    = cond.get("value")

    # is_null / is_not_null don't need an actual value
    if operator in ("is_null", "is_not_null"):
        raw = _resolve(field, labs, meds)
        return OPERATORS[operator](raw, None)

    val = _resolve(field, labs, meds)
    if val is None:
        return False
    op = OPERATORS.get(operator)
    if op is None:
        raise ValueError(f"Unknown operator: {operator}")
    return op(val, value)


def _eval_rule(rule: dict, labs: dict, meds: dict) -> bool:
    conditions = rule.get("conditions", [])
    logic = rule.get("logic", "AND").upper()
    results = [_eval_condition(c, labs, meds) for c in conditions]
    if logic == "AND":
        return all(results)
    if logic == "OR":
        return any(results)
    raise ValueError(f"Unknown logic: {logic}")


def _render_actions(actions: list, labs: dict, meds: dict) -> list:
    rendered = []
    for action in actions:
        a = dict(action)
        if "instruction" in a:
            a["instruction"] = _render(a["instruction"], labs, meds)
        rendered.append(a)
    return rendered


def run_protocols(patient_data: dict, protocols: dict) -> list[dict]:
    """
    Returns a list of recommendations sorted by urgency (urgent first).
    Each recommendation includes rule metadata and rendered actions
    (with current doses substituted into instruction text).
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
                    "rule_id":   rule["id"],
                    "protocol":  protocol_name,
                    "rule_name": rule["name"],
                    "urgency":   rule.get("urgency", "routine"),
                    "actions":   _render_actions(rule.get("actions", []), labs, meds),
                    "rationale": _render(rule.get("rationale", ""), labs, meds),
                })

    recs.sort(key=lambda r: URGENCY_ORDER.get(r["urgency"], 99))
    return recs
