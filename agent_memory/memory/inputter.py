# The official write layer.
# The only component allowed to write to the database.
# Appends to events_memory (always), then calls SharedMemoryWriter to update shared_* tables.
# Both happen inside a single transaction


import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from memory.interpreter import WriteRequest
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