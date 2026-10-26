"""SQLite case memory and audit log."""

import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("ADVISORY_DB", Path(__file__).resolve().parent.parent / "data" / "advisory.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id    TEXT PRIMARY KEY,
    client     TEXT,
    status     TEXT,
    stage      TEXT,
    updated_at TEXT,
    data       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    case_id   TEXT,
    stage     TEXT,
    agent     TEXT,
    action    TEXT,
    result    TEXT,
    details   TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
"""


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as conn:
        conn.executescript(SCHEMA)


def save_case(case):
    """Persist the case and flush its queued audit events. Returns the saved case."""
    events = case.get("_events", [])
    stored = {k: v for k, v in case.items() if k != "_events"}
    with _conn() as conn:
        conn.executemany(
            "INSERT INTO audit_log (timestamp, case_id, stage, agent, action, result, details) "
            "VALUES (:timestamp, :case_id, :stage, :agent, :action, :result, :details)",
            events,
        )
        conn.execute(
            "INSERT OR REPLACE INTO cases (case_id, client, status, stage, updated_at, data) VALUES (?,?,?,?,?,?)",
            (case["case_id"], case["client"].get("name") or "", case["status"], case["current_stage"],
             case["updated_at"], json.dumps(stored)),
        )
    case["_events"] = []
    return case


def get_case(case_id):
    with _conn() as conn:
        row = conn.execute("SELECT data FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        return None
    case = json.loads(row["data"])
    case["_events"] = []
    return case


def list_cases():
    with _conn() as conn:
        rows = conn.execute("SELECT data FROM cases ORDER BY case_id").fetchall()
    cases = [json.loads(r["data"]) for r in rows]
    for c in cases:
        c["_events"] = []
    return cases


def next_case_id():
    with _conn() as conn:
        row = conn.execute("SELECT case_id FROM cases ORDER BY case_id DESC LIMIT 1").fetchone()
    n = int(row["case_id"].split("-")[-1]) + 1 if row else 1001
    return f"ADV-{n}"


def audit(case_id=None):
    sql = "SELECT timestamp, case_id, stage, agent, action, result, details FROM audit_log"
    params = ()
    if case_id:
        sql += " WHERE case_id = ?"
        params = (case_id,)
    with _conn() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY id", params).fetchall()]


def count_cases():
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]


def reset():
    with _conn() as conn:
        conn.executescript("DROP TABLE IF EXISTS cases; DROP TABLE IF EXISTS audit_log;")
    init()
