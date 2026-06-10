"""
SQLite-backed deviation log and patient session store.
Tables are created on first run — no migration tooling needed for the prototype.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / "data" / "cdss.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS deviation_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      TEXT NOT NULL,
            patient_id      TEXT NOT NULL,
            session_date    TEXT NOT NULL,
            rule_id         TEXT NOT NULL,
            protocol        TEXT NOT NULL,
            rule_name       TEXT NOT NULL,
            recommended     TEXT NOT NULL,   -- JSON list of action dicts
            ordered         TEXT NOT NULL,   -- free-text of what was actually ordered
            override_reason TEXT NOT NULL,   -- reason code from dropdown
            clinician_note  TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS patient_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      TEXT NOT NULL,
            patient_id      TEXT NOT NULL,
            session_date    TEXT NOT NULL,
            lab_snapshot    TEXT NOT NULL,   -- full input JSON
            recommendations TEXT NOT NULL    -- JSON list of recs
        );
        """)


def log_deviation(
    patient_id: str,
    session_date: str,
    rule_id: str,
    protocol: str,
    rule_name: str,
    recommended: list,
    ordered: str,
    override_reason: str,
    clinician_note: str = "",
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO deviation_log
               (created_at, patient_id, session_date, rule_id, protocol,
                rule_name, recommended, ordered, override_reason, clinician_note)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (now, patient_id, session_date, rule_id, protocol, rule_name,
             json.dumps(recommended), ordered, override_reason, clinician_note),
        )
        return cur.lastrowid


def save_session(patient_id: str, session_date: str, lab_snapshot: dict, recommendations: list) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO patient_sessions
               (created_at, patient_id, session_date, lab_snapshot, recommendations)
               VALUES (?,?,?,?,?)""",
            (now, patient_id, session_date,
             json.dumps(lab_snapshot), json.dumps(recommendations)),
        )
        return cur.lastrowid


def get_deviations(patient_id: str | None = None, limit: int = 500) -> list[dict]:
    with _conn() as conn:
        if patient_id:
            rows = conn.execute(
                "SELECT * FROM deviation_log WHERE patient_id=? ORDER BY created_at DESC LIMIT ?",
                (patient_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM deviation_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["recommended"] = json.loads(d["recommended"])
        result.append(d)
    return result


def get_sessions(patient_id: str, limit: int = 12) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM patient_sessions
               WHERE patient_id=? ORDER BY session_date DESC LIMIT ?""",
            (patient_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["lab_snapshot"]    = json.loads(d["lab_snapshot"])
        d["recommendations"] = json.loads(d["recommendations"])
        result.append(d)
    return result
