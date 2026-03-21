"""
Shared memory writer.
Takes a validated, persisted event and writes it to the correct shared_* table.
No LLM calls. No reasoning. Pure SQL. Does NOT commit — Inputter owns the transaction.
"""

import json
import logging
import sqlite3

logger = logging.getLogger(__name__)


class SharedMemoryWriter:
    """
    Translates a validated event into a write on the correct shared_* table.
    Called by Inputter inside its transaction. Never commits directly.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def write(self, event: dict) -> bool:
        """
        Apply the event to the correct canonical view table.
        Returns True if successful, False if projection failed.
        Dispatches to _project_<bucket>(event) based on event["bucket"].
        Does NOT commit — Inputter manages the transaction.
        """
        bucket = event.get("bucket")
        dispatcher = {
            "plan":        self._write_plan,
            "constraints": self._write_constraints,
            "issues":      self._write_issues,
            "decisions":   self._write_decisions,
            "results":     self._write_results,
            "task_state":  self._write_task_state,
            "learnings":   self._write_learnings,
        }

        handler = dispatcher.get(bucket)
        if handler is None:
            logger.error("SharedMemoryWriter: unknown bucket '%s' for event %s", bucket, event.get("event_id"))
            return False

        try:
            handler(event)
            logger.debug("SharedMemoryWriter: wrote event %s → shared_%s/%s", event.get("event_id"), bucket, event.get("target_id"))
            return True
        except Exception as e:
            logger.error("SharedMemoryWriter: failed to write event %s — %s: %s", event.get("event_id"), type(e).__name__, e)
            return False

    # ------------------------------------------------------------------
    # Per-bucket projection methods
    # ------------------------------------------------------------------

    def _write_plan(self, event: dict) -> None:
        """
        operation: upsert only
        INSERT OR REPLACE into shared_plan using target_id as PK.
        Increments version if row already exists.
        """
        payload = json.loads(event["payload_json"])
        target_id = event["target_id"]
        event_id = event["event_id"]

        existing = self.conn.execute(
            "SELECT version FROM shared_plan WHERE target_id = ?", (target_id,)
        ).fetchone()

        version = (existing["version"] + 1) if existing else 1

        self.conn.execute(
            """
            INSERT OR REPLACE INTO shared_plan (target_id, version, plan_json, last_updated_event_id)
            VALUES (?, ?, ?, ?)
            """,
            (target_id, version, payload["plan_json"], event_id),
        )

    def _write_constraints(self, event: dict) -> None:
        """
        upsert: INSERT OR REPLACE into shared_constraints
        invalidate: UPDATE shared_constraints SET status='invalidated' WHERE constraint_id=target_id
        """
        operation = event["operation"]
        target_id = event["target_id"]
        event_id = event["event_id"]

        if operation == "invalidate":
            self.conn.execute(
                "UPDATE shared_constraints SET status='invalidated', last_updated_event_id=? WHERE constraint_id=?",
                (event_id, target_id),
            )
        else:  # upsert
            payload = json.loads(event["payload_json"])
            self.conn.execute(
                """
                INSERT OR REPLACE INTO shared_constraints
                    (constraint_id, text, status, scope, source_event_id, last_updated_event_id)
                VALUES (?, ?, 'active', ?, ?, ?)
                """,
                (target_id, payload["text"], payload.get("scope"), event_id, event_id),
            )

    def _write_issues(self, event: dict) -> None:
        """
        upsert: INSERT OR REPLACE into shared_issues, preserving first_seen_event_id if row exists
        resolve: UPDATE shared_issues SET status='resolved' WHERE issue_id=target_id
        """
        operation = event["operation"]
        target_id = event["target_id"]
        event_id = event["event_id"]

        if operation == "resolve":
            self.conn.execute(
                "UPDATE shared_issues SET status='resolved', last_updated_event_id=? WHERE issue_id=?",
                (event_id, target_id),
            )
        else:  # upsert
            payload = json.loads(event["payload_json"])

            # Preserve first_seen_event_id if row already exists
            existing = self.conn.execute(
                "SELECT first_seen_event_id FROM shared_issues WHERE issue_id = ?", (target_id,)
            ).fetchone()
            first_seen = existing["first_seen_event_id"] if existing else event_id

            self.conn.execute(
                """
                INSERT OR REPLACE INTO shared_issues
                    (issue_id, title, description, status, severity,
                     entity_type, entity_id, first_seen_event_id, last_updated_event_id)
                VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    payload["title"],
                    payload.get("description"),
                    payload.get("severity"),
                    payload.get("entity_type"),
                    payload.get("entity_id"),
                    first_seen,
                    event_id,
                ),
            )

    def _write_decisions(self, event: dict) -> None:
        """
        append: INSERT into shared_decisions (target_id as PK; uses event_id as fallback if collision)
        invalidate: UPDATE shared_decisions SET status='superseded' WHERE decision_id=target_id
        """
        operation = event["operation"]
        target_id = event["target_id"]
        event_id = event["event_id"]

        if operation == "invalidate":
            self.conn.execute(
                "UPDATE shared_decisions SET status='superseded' WHERE decision_id=?",
                (target_id,),
            )
        else:  # append
            payload = json.loads(event["payload_json"])

            # If target_id already exists, use event_id as the PK to avoid collision
            existing = self.conn.execute(
                "SELECT 1 FROM shared_decisions WHERE decision_id = ?", (target_id,)
            ).fetchone()
            decision_id = event_id if existing else target_id

            self.conn.execute(
                """
                INSERT INTO shared_decisions
                    (decision_id, statement, rationale, scope, status, source_event_id)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    decision_id,
                    payload["statement"],
                    payload.get("rationale"),
                    payload.get("scope"),
                    event_id,
                ),
            )

    def _write_results(self, event: dict) -> None:
        """
        append only: INSERT into shared_results.
        Use target_id as result_id. If collision, suffix with _<timestamp>.
        """
        payload = json.loads(event["payload_json"])
        target_id = event["target_id"]
        event_id = event["event_id"]

        existing = self.conn.execute(
            "SELECT 1 FROM shared_results WHERE result_id = ?", (target_id,)
        ).fetchone()
        result_id = f"{target_id}_{event['timestamp'].replace(':', '').replace('-', '').replace('.', '')}" if existing else target_id

        self.conn.execute(
            """
            INSERT INTO shared_results
                (result_id, experiment_id, metric_name, metric_value,
                 baseline_value, notes, source_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                payload.get("experiment_id"),
                payload["metric_name"],
                payload["metric_value"],
                payload.get("baseline_value"),
                payload.get("notes"),
                event_id,
            ),
        )

    def _write_task_state(self, event: dict) -> None:
        """
        upsert only: INSERT OR REPLACE into shared_task_state
        """
        payload = json.loads(event["payload_json"])
        target_id = event["target_id"]
        event_id = event["event_id"]

        self.conn.execute(
            """
            INSERT OR REPLACE INTO shared_task_state
                (task_id, status, phase, owner_agent, blockers_json, last_updated_event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                payload["status"],
                payload.get("phase"),
                event.get("source_agent"),
                payload.get("blockers_json"),
                event_id,
            ),
        )

    def _write_learnings(self, event: dict) -> None:
        """
        append only: INSERT into shared_learnings.
        Use target_id as learning_id. If collision, suffix with _<event_id>.
        """
        payload = json.loads(event["payload_json"])
        target_id = event["target_id"]
        event_id = event["event_id"]

        existing = self.conn.execute(
            "SELECT 1 FROM shared_learnings WHERE learning_id = ?", (target_id,)
        ).fetchone()
        learning_id = f"{target_id}_{event_id}" if existing else target_id

        self.conn.execute(
            """
            INSERT INTO shared_learnings
                (learning_id, title, statement, category, scope,
                 confidence, source_issue_id, source_event_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                learning_id,
                payload.get("title", target_id),
                payload["statement"],
                payload.get("category"),
                payload.get("scope"),
                payload.get("confidence"),
                payload.get("source_issue_id"),
                event_id,
            ),
        )