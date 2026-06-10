# Dialysis CDSS — Phase 1 Prototype

A lightweight clinical decision support system for monthly dialysis patient rounding.

## What it does

1. **Protocol Runner** — takes a patient's monthly labs (JSON or web form), evaluates them against configurable decision tables, returns recommendations with urgency flags.
2. **Deviation Logger** — when you override a recommendation, captures what was recommended, what you ordered, and your reason. Stored as structured data for future ML training.
3. **Rounding Summary** — single-page web view with current/prior lab trends, recommendations, and approve/override toggles.

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server (from the repo root)
uvicorn backend.main:app --reload --port 8000

# 3. Open browser
open http://localhost:8000
```

## Running the gold-standard tests

```bash
pytest tests/test_gold_standard.py -v
```

The tests verify that the protocol engine fires exactly the expected rule IDs for each of the 5 test cases in `test_cases/`.

> **Before you run them**: update `test_cases/expected_outputs.json` with your manually prepared gold-standard outputs. The current expected outputs are placeholders based on the example protocols.

## Updating protocols

All clinical rules live in `protocols/*.yaml`. No code changes needed.

```
protocols/
  bone_mineral_metabolism.yaml   # PTH, calcium, vitamin D
  anemia.yaml                    # hemoglobin, ESA, iron
  phosphorus.yaml                # phosphate binders
```

### Adding a rule

```yaml
- id: BMM-009
  name: "My new rule"
  enabled: true
  urgency: routine            # urgent | soon | routine | monitor
  logic: AND                  # AND | OR
  conditions:
    - field: pth
      operator: ">"           # > < >= <= == != between not_between
      value: 600
    - field: calcium
      operator: between
      value: [8.4, 10.2]      # list of [low, high] for between/not_between
  actions:
    - type: increase_dose
      medication: paricalcitol
      instruction: "Increase paricalcitol by 2 mcg."
  rationale: "Why this rule fires."
```

### Disabling a rule without deleting it

```yaml
- id: BMM-002
  enabled: false
  ...
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/evaluate` | Run protocols, returns recommendations |
| POST | `/api/deviations` | Log an override decision |
| GET  | `/api/deviations` | List logged deviations (optional `?patient_id=X`) |
| GET  | `/api/sessions/{patient_id}` | Prior sessions for a patient |
| GET  | `/api/override-reasons` | Allowed override reason strings |
| GET  | `/api/protocols` | List loaded protocols and rule counts |

### Example `POST /api/evaluate` payload

```json
{
  "patient_id": "MRN-12345",
  "patient_name": "Jane Smith",
  "session_date": "2026-06-01",
  "labs": {
    "hemoglobin": 9.2,
    "ferritin": 180,
    "tsat": 18,
    "pth": 680,
    "calcium": 9.5,
    "phosphorus": 5.9
  },
  "current_medications": {
    "epo_dose_units_per_week": 6000,
    "paricalcitol_mcg": 2,
    "sevelamer_mg_tid": 800
  }
}
```

## Data

Deviation logs and sessions are stored in `data/cdss.db` (SQLite). This file is gitignored — back it up separately.

## Project layout

```
dialysis-cdss/
├── backend/
│   ├── main.py              # FastAPI app + routes
│   ├── protocol_runner.py   # Rule engine (reads protocols/*.yaml)
│   ├── database.py          # SQLite: deviation log + session store
│   └── models.py            # Pydantic schemas + override reasons
├── protocols/               # ← Edit these to change clinical rules
│   ├── bone_mineral_metabolism.yaml
│   ├── anemia.yaml
│   └── phosphorus.yaml
├── frontend/
│   └── index.html           # Single-page rounding summary
├── test_cases/
│   ├── patients.json         # 5 test patients
│   └── expected_outputs.json # Gold-standard rule IDs — update these
├── tests/
│   └── test_gold_standard.py
└── requirements.txt
```
