# The official write layer.
# The only component allowed to write to the database.
# Appends to events_memory (always), then calls SharedMemoryWriter to update shared_* tables.
# Both happen inside a single transaction


import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from memory.interpreter import WriteRequest
from memory.pending_memory import PendingMemoryQueue
from memory.resolver import ResolvedWrite
from memory.shared_memory_writer import SharedMemoryWriter

logger = logging.getLogger(__name__)


class Inputter:
    """
    Deterministic write layer. The only component allowed to write to
    events_memory and shared_* tables.
    """

    def __init__(self, conn: sqlite3.Connection, shared_memory_writer: SharedMemoryWriter):
        self.conn = conn
        self.shared_memory_writer = shared_memory_writer
        self.pending_queue = PendingMemoryQueue(conn)

    def write(
        self,
        write_request: WriteRequest,
        source_agent: str,
        raw_input: str = "",
        source_ref: str = "",
    ) -> str:
        """
        Atomically:
        1. Generate a UUID event_id
        2. INSERT into events_memory
        3. Call shared_memory_writer.write(event)
        4. UPDATE events_memory SET applied_successfully=1/0
        5. Commit

        Returns the event_id.

        The event is always committed to events_memory even if the shared memory
        write fails — the audit trail is never lost. applied_successfully=0 marks failures.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(write_request.payload or {})

        event = {
            "event_id":     event_id,
            "timestamp":    timestamp,
            "source_agent": source_agent,
            "bucket":       write_request.bucket,
            "target_id":    write_request.target_id,
            "operation":    write_request.operation,
            "payload_json": payload_json,
            "raw_input":    raw_input,
            "source_ref":   source_ref,
        }

        # Step 2 — insert event into the ledger with applied_successfully=0 as safe default.
        # This write is unconditional — the audit trail must never be lost.
        self.conn.execute(
            """
            INSERT INTO events_memory
                (event_id, timestamp, source_agent, bucket, target_id,
                 operation, payload_json, raw_input, source_ref, applied_successfully)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                event_id, timestamp, source_agent,
                write_request.bucket, write_request.target_id,
                write_request.operation, payload_json,
                raw_input, source_ref,
            ),
        )

        # Step 3 — write to the correct shared_* table.
        # Failures here do not roll back the ledger — they just set applied_successfully=0.
        applied = False
        try:
            applied = self.shared_memory_writer.write(event)
        except Exception as e:
            logger.error(
                "Inputter: shared memory write failed for event %s — %s: %s",
                event_id, type(e).__name__, e,
            )

        # Step 4 — record whether the view write succeeded.
        self.conn.execute(
            "UPDATE events_memory SET applied_successfully=? WHERE event_id=?",
            (1 if applied else 0, event_id),
        )

        # Step 5 — commit. Always reaches here regardless of writer outcome.
        self.conn.commit()

        logger.info(
            "Inputter: wrote event %s | agent=%s bucket=%s target=%s applied=%s",
            event_id, source_agent, write_request.bucket,
            write_request.target_id, applied,
        )

        return event_id

    def write_resolved(
        self,
        resolved_write: ResolvedWrite,
        source_agent: str,
        raw_input: str = "",
        write_request: Optional[WriteRequest] = None,
    ) -> str:
        if resolved_write.decision != "commit":
            raise ValueError("write_resolved requires ResolvedWrite(decision='commit').")

        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(resolved_write.payload or {})
        source_ref = json.dumps(
            {
                "matched_target_id": resolved_write.matched_target_id,
                "candidate_matches": resolved_write.candidate_matches,
                "resolution_reason": resolved_write.resolution_reason,
                "reference_text": resolved_write.reference_text,
                "candidate_aliases": (
                    write_request.candidate_aliases
                    if write_request is not None and write_request.candidate_aliases is not None
                    else None
                ),
            }
        )

        event = {
            "event_id": event_id,
            "timestamp": timestamp,
            "source_agent": source_agent,
            "bucket": resolved_write.bucket,
            "target_id": resolved_write.resolved_target_id,
            "operation": resolved_write.operation,
            "payload_json": payload_json,
            "raw_input": raw_input,
            "source_ref": source_ref,
            "matched_target_id": resolved_write.matched_target_id,
        }

        self.conn.execute(
            """
            INSERT INTO events_memory
                (event_id, timestamp, source_agent, bucket, target_id,
                 operation, payload_json, raw_input, source_ref, applied_successfully)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                event_id,
                timestamp,
                source_agent,
                resolved_write.bucket,
                resolved_write.resolved_target_id,
                resolved_write.operation,
                payload_json,
                raw_input,
                source_ref,
            ),
        )

        applied = False
        try:
            applied = self.shared_memory_writer.write(event)
        except Exception as e:
            logger.error(
                "Inputter: resolved shared memory write failed for event %s - %s: %s",
                event_id,
                type(e).__name__,
                e,
            )

        self.conn.execute(
            "UPDATE events_memory SET applied_successfully=? WHERE event_id=?",
            (1 if applied else 0, event_id),
        )
        self.conn.commit()
        return event_id

    def write_provisional(
        self,
        resolved_write: ResolvedWrite,
        source_agent: str,
        raw_input: str,
        write_request: Optional[WriteRequest] = None,
    ) -> str:
        if resolved_write.decision != "provisional":
            raise ValueError("write_provisional requires ResolvedWrite(decision='provisional').")
        return self.pending_queue.enqueue(
            source_agent=source_agent,
            raw_input=raw_input,
            bucket=resolved_write.bucket,
            target_id=getattr(write_request, "target_id", None),
            intended_operation=resolved_write.operation,
            reference_text=resolved_write.reference_text,
            payload_json=json.dumps(resolved_write.payload or {}),
            candidate_matches_json=json.dumps(resolved_write.candidate_matches),
            reason=resolved_write.resolution_reason,
            request_json=self._serialize_write_request(write_request),
            candidate_aliases_json=(
                json.dumps(write_request.candidate_aliases)
                if write_request is not None and write_request.candidate_aliases is not None
                else None
            ),
            confidence=write_request.confidence if write_request is not None else None,
        )

    def _serialize_write_request(self, write_request: Optional[WriteRequest]) -> Optional[str]:
        if write_request is None:
            return None
        if hasattr(write_request, "model_dump_json"):
            return write_request.model_dump_json()
        return write_request.json()
