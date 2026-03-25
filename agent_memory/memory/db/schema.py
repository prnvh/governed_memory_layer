# Table definitions and database initialization for the shared memory layer. 


import sqlite3


CREATE_EVENTS_MEMORY = """
CREATE TABLE IF NOT EXISTS events_memory (
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

CREATE_PENDING_MEMORY_EVENTS = """
CREATE TABLE IF NOT EXISTS pending_memory_events (
    pending_id               TEXT PRIMARY KEY,
    timestamp                TEXT NOT NULL,
    source_agent             TEXT NOT NULL,
    raw_input                TEXT NOT NULL,
    bucket                   TEXT,
    target_id                TEXT,
    intended_operation       TEXT,
    reference_text           TEXT,
    payload_json             TEXT,
    candidate_aliases_json   TEXT,
    confidence               REAL,
    request_json             TEXT,
    candidate_matches_json   TEXT,
    reason                   TEXT NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'open',
    retry_count              INTEGER NOT NULL DEFAULT 0,
    last_retried_at          TEXT,
    last_retry_reason        TEXT,
    resolved_event_id        TEXT
)
"""

CREATE_SHARED_PLAN = """
CREATE TABLE IF NOT EXISTS shared_plan (
    target_id               TEXT PRIMARY KEY,
    version                 INTEGER NOT NULL DEFAULT 1,
    plan_json               TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_SHARED_CONSTRAINTS = """
CREATE TABLE IF NOT EXISTS shared_constraints (
    constraint_id           TEXT PRIMARY KEY,
    text                    TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active',
    scope                   TEXT,
    reference_memory_json   TEXT,
    source_event_id         TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_SHARED_ISSUES = """
CREATE TABLE IF NOT EXISTS shared_issues (
    issue_id                TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    description             TEXT,
    status                  TEXT NOT NULL DEFAULT 'open',
    severity                TEXT,
    entity_type             TEXT,
    entity_id               TEXT,
    reference_memory_json   TEXT,
    first_seen_event_id     TEXT NOT NULL,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_SHARED_DECISIONS = """
CREATE TABLE IF NOT EXISTS shared_decisions (
    decision_id             TEXT PRIMARY KEY,
    statement               TEXT NOT NULL,
    rationale               TEXT,
    scope                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'active',
    reference_memory_json   TEXT,
    source_event_id         TEXT NOT NULL
)
"""

CREATE_SHARED_RESULTS = """
CREATE TABLE IF NOT EXISTS shared_results (
    result_id               TEXT PRIMARY KEY,
    experiment_id           TEXT,
    metric_name             TEXT NOT NULL,
    metric_value            TEXT NOT NULL,
    baseline_value          TEXT,
    notes                   TEXT,
    source_event_id         TEXT NOT NULL
)
"""

CREATE_SHARED_TASK_STATE = """
CREATE TABLE IF NOT EXISTS shared_task_state (
    task_id                 TEXT PRIMARY KEY,
    status                  TEXT NOT NULL,
    phase                   TEXT,
    owner_agent             TEXT,
    blockers_json           TEXT,
    last_updated_event_id   TEXT NOT NULL
)
"""

CREATE_SHARED_LEARNINGS = """
CREATE TABLE IF NOT EXISTS shared_learnings (
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
    CREATE_EVENTS_MEMORY,
    CREATE_PENDING_MEMORY_EVENTS,
    CREATE_SHARED_PLAN,
    CREATE_SHARED_CONSTRAINTS,
    CREATE_SHARED_ISSUES,
    CREATE_SHARED_DECISIONS,
    CREATE_SHARED_RESULTS,
    CREATE_SHARED_TASK_STATE,
    CREATE_SHARED_LEARNINGS,
]

# Create all tables if they don't exist. Idempotent.
def init_db(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    for statement in ALL_TABLES:
        cursor.execute(statement)
    _ensure_pending_memory_columns(conn)
    _ensure_reference_memory_columns(conn)
    conn.commit()


def _ensure_pending_memory_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(pending_memory_events)").fetchall()
    }
    required_columns = {
        "target_id": "TEXT",
        "candidate_aliases_json": "TEXT",
        "confidence": "REAL",
        "request_json": "TEXT",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "last_retried_at": "TEXT",
        "last_retry_reason": "TEXT",
        "resolved_event_id": "TEXT",
    }
    for column_name, column_type in required_columns.items():
        if column_name not in existing:
            conn.execute(
                f"ALTER TABLE pending_memory_events ADD COLUMN {column_name} {column_type}"
            )


def _ensure_reference_memory_columns(conn: sqlite3.Connection) -> None:
    table_columns = {
        "shared_constraints": {"reference_memory_json": "TEXT"},
        "shared_issues": {"reference_memory_json": "TEXT"},
        "shared_decisions": {"reference_memory_json": "TEXT"},
    }
    for table_name, required_columns in table_columns.items():
        existing = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in required_columns.items():
            if column_name not in existing:
                conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )


def get_valid_buckets() -> list[str]:
    return ["plan", "constraints", "issues", "decisions", "results", "task_state", "learnings"]


def get_valid_operations() -> list[str]:
    return ["upsert", "append", "resolve", "invalidate"]
