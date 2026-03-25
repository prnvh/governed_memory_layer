import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from memory.interpreter import WriteRequest


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingMemoryQueue:
    """
    Append-only pending/on-hold work queue for memory writes that were important
    enough to preserve but were not yet safe to commit to canonical memory.
    """

    RETRYABLE_STATUSES = ("open", "on_hold")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def enqueue(
        self,
        source_agent: str,
        raw_input: str,
        bucket: Optional[str],
        target_id: Optional[str],
        intended_operation: Optional[str],
        reference_text: Optional[str],
        payload_json: str,
        candidate_matches_json: str,
        reason: str,
        request_json: Optional[str] = None,
        candidate_aliases_json: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        pending_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO pending_memory_events
                (pending_id, timestamp, source_agent, raw_input, bucket, target_id,
                 intended_operation, reference_text, payload_json,
                 candidate_aliases_json, confidence, request_json,
                 candidate_matches_json, reason, status, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0)
            """,
            (
                pending_id,
                _utc_now_iso(),
                source_agent,
                raw_input,
                bucket,
                target_id,
                intended_operation,
                reference_text,
                payload_json,
                candidate_aliases_json,
                confidence,
                request_json,
                candidate_matches_json,
                reason,
            ),
        )
        self.conn.commit()
        return pending_id

    def get_retryable(self, limit: int = 25) -> list[dict]:
        placeholders = ",".join("?" for _ in self.RETRYABLE_STATUSES)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM pending_memory_events
            WHERE status IN ({placeholders})
            ORDER BY
                CASE WHEN last_retried_at IS NULL THEN 0 ELSE 1 END,
                last_retried_at ASC,
                retry_count ASC,
                timestamp ASC
            LIMIT ?
            """,
            (*self.RETRYABLE_STATUSES, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_on_hold(self, pending_id: str, reason: str) -> None:
        self._mark_retry_state(
            pending_id=pending_id,
            status="on_hold",
            reason=reason,
            resolved_event_id=None,
        )

    def mark_rejected(self, pending_id: str, reason: str) -> None:
        self._mark_retry_state(
            pending_id=pending_id,
            status="rejected",
            reason=reason,
            resolved_event_id=None,
        )

    def mark_committed(self, pending_id: str, event_id: str, reason: str) -> None:
        self._mark_retry_state(
            pending_id=pending_id,
            status="committed",
            reason=reason,
            resolved_event_id=event_id,
        )

    def rebuild_write_request(self, row: dict) -> WriteRequest:
        request_json = row.get("request_json")
        if request_json:
            return WriteRequest(**json.loads(request_json))

        aliases = row.get("candidate_aliases_json")
        payload_json = row.get("payload_json")
        return WriteRequest(
            decision="accept",
            bucket=row.get("bucket"),
            target_id=row.get("target_id"),
            operation=row.get("intended_operation"),
            payload=json.loads(payload_json) if payload_json else {},
            reference_text=row.get("reference_text"),
            candidate_aliases=json.loads(aliases) if aliases else None,
            confidence=row.get("confidence"),
            rationale=row.get("reason") or "pending_retry",
        )

    def _mark_retry_state(
        self,
        pending_id: str,
        status: str,
        reason: str,
        resolved_event_id: Optional[str],
    ) -> None:
        self.conn.execute(
            """
            UPDATE pending_memory_events
            SET status = ?,
                retry_count = retry_count + 1,
                last_retried_at = ?,
                last_retry_reason = ?,
                resolved_event_id = COALESCE(?, resolved_event_id)
            WHERE pending_id = ?
            """,
            (
                status,
                _utc_now_iso(),
                reason,
                resolved_event_id,
                pending_id,
            ),
        )
        self.conn.commit()
