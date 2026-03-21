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
    conn.commit()


def get_valid_buckets() -> list[str]:
    return ["plan", "constraints", "issues", "decisions", "results", "task_state", "learnings"]


def get_valid_operations() -> list[str]:
    return ["upsert", "append", "resolve", "invalidate"]