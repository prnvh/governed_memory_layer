# Read-only interface to canonical shared memory.
# Agents use this to access current state. not raw SQL, not the event ledger.

# All reads go against the shared_* canonical view tables.
# get_event_history() is the only method that touches events_memory,
# and it is intended for provenance/debugging only, not regular agent use.


import sqlite3
from typing import Optional


class SharedMemory:
    """
    Read-only interface to canonical shared memory.
    Agents use this — not raw SQL, not the event ledger.

    All methods return plain dicts (via sqlite3.Row → dict conversion).
    Returns None for single-row lookups that find nothing.
    Returns [] for multi-row lookups that find nothing.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict."""
        return dict(row)

    def _rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict]:
        """Convert a list of sqlite3.Row objects to plain dicts."""
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    def get_plan(self, target_id: str = "main") -> Optional[dict]:
        """
        Return the current plan for target_id, or None if no plan exists yet.
        In V1, target_id is always "main".
        """
        cursor = self.conn.execute(
            "SELECT * FROM shared_plan WHERE target_id = ?",
            (target_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def get_active_constraints(self) -> list[dict]:
        """
        Return all constraints with status='active'.
        Returns an empty list if none exist.
        """
        cursor = self.conn.execute(
            "SELECT * FROM shared_constraints WHERE status = 'active'"
        )
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def get_open_issues(self, severity: Optional[str] = None) -> list[dict]:
        """
        Return all issues with status='open'.
        Optionally filter by severity: low|medium|high|critical.
        Returns an empty list if none exist.
        For agent use — agents only care about active blockers.
        """
        if severity is not None:
            cursor = self.conn.execute(
                "SELECT * FROM shared_issues WHERE status = 'open' AND severity = ?",
                (severity,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM shared_issues WHERE status = 'open'"
            )
        return self._rows_to_dicts(cursor.fetchall())

    def get_all_issues(self) -> list[dict]:
        """
        Return all issues regardless of status (open, resolved, wont_fix).
        For benchmark evaluation and provenance — not regular agent use.
        Agents should use get_open_issues() instead.
        """
        cursor = self.conn.execute("SELECT * FROM shared_issues")
        return self._rows_to_dicts(cursor.fetchall())

    def get_issue(self, issue_id: str) -> Optional[dict]:
        """
        Return a single issue by ID regardless of status, or None if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM shared_issues WHERE issue_id = ?",
            (issue_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def get_decisions(self, status: str = "active") -> list[dict]:
        """
        Return decisions filtered by status.
        Valid statuses: active|superseded|invalidated.
        Returns an empty list if none exist.
        For agent use — agents only care about active decisions.
        """
        cursor = self.conn.execute(
            "SELECT * FROM shared_decisions WHERE status = ?",
            (status,),
        )
        return self._rows_to_dicts(cursor.fetchall())

    def get_all_decisions(self) -> list[dict]:
        """
        Return all decisions regardless of status (active, superseded, invalidated).
        For benchmark evaluation and provenance — not regular agent use.
        Agents should use get_decisions() instead.
        """
        cursor = self.conn.execute("SELECT * FROM shared_decisions")
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def get_results(self, experiment_id: Optional[str] = None) -> list[dict]:
        """
        Return results, optionally filtered by experiment_id.
        Returns an empty list if none exist.
        """
        if experiment_id is not None:
            cursor = self.conn.execute(
                "SELECT * FROM shared_results WHERE experiment_id = ?",
                (experiment_id,),
            )
        else:
            cursor = self.conn.execute("SELECT * FROM shared_results")
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Task state
    # ------------------------------------------------------------------

    def get_task_state(self, task_id: str) -> Optional[dict]:
        """
        Return current state for a specific task, or None if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM shared_task_state WHERE task_id = ?",
            (task_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def get_all_tasks(self) -> list[dict]:
        """
        Return all task state records.
        Returns an empty list if none exist.
        """
        cursor = self.conn.execute("SELECT * FROM shared_task_state")
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Learnings
    # ------------------------------------------------------------------

    def get_learnings(self, category: Optional[str] = None) -> list[dict]:
        """
        Return active learnings (status='active'), optionally filtered by category.
        Returns an empty list if none exist.
        """
        if category is not None:
            cursor = self.conn.execute(
                "SELECT * FROM shared_learnings WHERE status = 'active' AND category = ?",
                (category,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM shared_learnings WHERE status = 'active'"
            )
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Event history (provenance / debugging only)
    # ------------------------------------------------------------------

    def get_event_history(
        self,
        bucket: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Read from events_memory for provenance and debugging.
        NOT for regular agent use — agents should read canonical views instead.

        Filterable by bucket and/or target_id.
        Results are ordered by timestamp descending (most recent first).
        """
        conditions = []
        params: list = []

        if bucket is not None:
            conditions.append("bucket = ?")
            params.append(bucket)

        if target_id is not None:
            conditions.append("target_id = ?")
            params.append(target_id)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        params.append(limit)

        cursor = self.conn.execute(
            f"SELECT * FROM events_memory {where_clause} ORDER BY timestamp DESC LIMIT ?",
            params,
        )
        return self._rows_to_dicts(cursor.fetchall())

    # ------------------------------------------------------------------
    # Snapshot (debugging / benchmark evaluation)
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Return a full snapshot of all canonical views as a dict.
        Keys match the logical bucket names.
        Useful for debugging and benchmark evaluation.

        Structure:
        {
            "plan":        dict | None,
            "constraints": list[dict],
            "issues":      list[dict],
            "decisions":   list[dict],
            "results":     list[dict],
            "task_state":  list[dict],
            "learnings":   list[dict],
        }
        """
        return {
            "plan":        self.get_plan(),
            "constraints": self.get_active_constraints(),
            "issues":      self.get_all_issues(),
            "decisions":   self.get_all_decisions(),
            "results":     self.get_results(),
            "task_state":  self.get_all_tasks(),
            "learnings":   self.get_learnings(),
        }