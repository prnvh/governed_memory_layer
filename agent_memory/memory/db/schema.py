"""
Table definitions and database initialization for the governed memory layer.
All canonical view tables and the append-only event ledger are defined here.
"""

import sqlite3


CREATE_MEMORY_EVENTS = """
CREATE TABLE IF NOT EXISTS memory_events (
    event_id                TEXT PRIMARY KEY,
    timestamp               TEXT NOT NULL,
    source_agent            TEXT NOT NULL,
    bucket                  TEXT NOT NULL,
    target_id               TEXT NOT NULL,
    operation               TEXT NOT NULL,
    payload_json            TEXT NOT NULL,
    raw_input               TEXT,
    source_ref              TEXT,
    applied_successfully    INTEGER NOT NULL DEFAULT 1
)
"""

CREATE_PLAN_VIEW = """
CREATE TABLE IF NOT EXISTS plan_view (
    target_id               TEXT PRIMARY KEY,
    version                 INTEGER NOT NULL DEFAULT 1,
    plan_json               TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_CONSTRAINTS_VIEW = """
CREATE TABLE IF NOT EXISTS constraints_view (
    constraint_id           TEXT PRIMARY KEY,
    text                    TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active',
    scope                   TEXT,
    source_event_id         TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_ISSUES_VIEW = """
CREATE TABLE IF NOT EXISTS issues_view (
    issue_id                TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    description             TEXT,
    status                  TEXT NOT NULL DEFAULT 'open',
    severity                TEXT,
    entity_type             TEXT,
    entity_id               TEXT,
    first_seen_event_id     TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_DECISIONS_VIEW = """
CREATE TABLE IF NOT EXISTS decisions_view (
    decision_id             TEXT PRIMARY KEY,
    statement               TEXT NOT NULL,
    rationale               TEXT,
    scope                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'active',
    source_event_id         TEXT NOT NULL
)
"""

CREATE_RESULTS_VIEW = """
CREATE TABLE IF NOT EXISTS results_view (
    result_id               TEXT PRIMARY KEY,
    experiment_id           TEXT,
    metric_name             TEXT NOT NULL,
    metric_value            TEXT NOT NULL,
    baseline_value          TEXT,
    notes                   TEXT,
    source_event_id         TEXT NOT NULL
)
"""

CREATE_TASK_STATE_VIEW = """
CREATE TABLE IF NOT EXISTS task_state_view (
    task_id                 TEXT PRIMARY KEY,
    status                  TEXT NOT NULL,
    phase                   TEXT,
    owner_agent             TEXT,
    blockers_json           TEXT,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_LEARNINGS_VIEW = """
CREATE TABLE IF NOT EXISTS learnings_view (
    learning_id             TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    statement               TEXT NOT NULL,
    category                TEXT,
    scope                   TEXT,
    confidence              REAL,
    source_issue_id         TEXT,
    source_event_id         TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active'
)
"""

ALL_TABLES = [
    CREATE_MEMORY_EVENTS,
    CREATE_PLAN_VIEW,
    CREATE_CONSTRAINTS_VIEW,
    CREATE_ISSUES_VIEW,
    CREATE_DECISIONS_VIEW,
    CREATE_RESULTS_VIEW,
    CREATE_TASK_STATE_VIEW,
    CREATE_LEARNINGS_VIEW,
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist. Idempotent."""
    cursor = conn.cursor()
    for statement in ALL_TABLES:
        cursor.execute(statement)
    conn.commit()


def get_valid_buckets() -> list[str]:
    return ["plan", "constraints", "issues", "decisions", "results", "task_state", "learnings"]


def get_valid_operations() -> list[str]:
    return ["upsert", "append", "resolve", "invalidate"]