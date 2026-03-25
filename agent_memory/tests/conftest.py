"""
tests/conftest.py

Shared fixtures and test doubles for the memory pipeline test suite.

FakeInterpreter is the key test double — it replaces the real LLM-based
Interpreter with a controllable stub. All pipeline tests use this instead
of making real API calls.

Fixtures provided:
    db_conn          — fresh in-memory SQLite, schema initialised, per-test
    fake_interpreter — FakeInterpreter instance, per-test
    shared_memory_writer — SharedMemoryWriter wired to db_conn, per-test
    inputter         — Inputter wired to db_conn + shared_memory_writer, per-test
    pipeline         — PromotionPipeline wired with fake_interpreter, per-test
    shared_memory    — SharedMemory pointed at same db_conn, per-test
"""

import sqlite3
import pytest

from memory.interpreter import WriteRequest
from memory.validator import Validator
from memory.shared_memory_writer import SharedMemoryWriter
from memory.inputter import Inputter
from memory.shared_memory import SharedMemory
from memory.promotion import PromotionPipeline
from memory.db.schema import init_db


# ---------------------------------------------------------------------------
# FakeInterpreter
# ---------------------------------------------------------------------------

class FakeInterpreter:
    """
    Drop-in replacement for Interpreter. Returns canned WriteRequest responses
    without making any API calls.

    Usage:
        fake = FakeInterpreter()

        # Queue a single response — returned on the next interpret() call
        fake.set_response(WriteRequest(
            decision="accept",
            bucket="issues",
            target_id="pandas_import_error",
            operation="upsert",
            payload={"title": "Pandas import error", "severity": "high"},
            rationale="Clear blocking issue.",
        ))

        result = fake.interpret("some note text", "agent_001")
        # result is the WriteRequest above

    If set_response() has not been called and interpret() is invoked, a
    default reject is returned so tests that don't care about the response
    don't need to set one up.

    Supports multiple queued responses via repeated set_response() calls.
    Responses are consumed in FIFO order. If the queue runs out, returns
    the last set response (or a default reject if none was ever set).
    """

    def __init__(self):
        self._queue: list[WriteRequest] = []
        self._last: WriteRequest = WriteRequest(
            decision="reject",
            rationale="FakeInterpreter: no response configured",
        )

    def set_response(self, response: WriteRequest) -> None:
        """Queue a response to be returned by the next interpret() call."""
        self._queue.append(response)

    def interpret(
        self,
        candidate_note: str,
        agent_id: str,
        context=None,
    ) -> WriteRequest:
        """
        Return the next queued response if available.
        Once the queue is exhausted, always return a fresh default reject —
        never replay the last queued response.
        """
        if self._queue:
            return self._queue.pop(0)
        return WriteRequest(
            decision="reject",
            rationale="FakeInterpreter: queue exhausted",
        )

    def reset(self) -> None:
        """Clear the queue and reset to default reject."""
        self._queue.clear()
        self._last = WriteRequest(
            decision="reject",
            rationale="FakeInterpreter: no response configured",
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn():
    """
    Fresh in-memory SQLite connection with the full schema initialised.
    Uses sqlite3.Row as row_factory so columns are accessible by name.
    Closed automatically after each test.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def fake_interpreter():
    """Fresh FakeInterpreter with an empty response queue."""
    return FakeInterpreter()


@pytest.fixture
def shared_memory_writer(db_conn):
    """SharedMemoryWriter wired to the test db_conn."""
    return SharedMemoryWriter(db_conn)


@pytest.fixture
def inputter(db_conn, shared_memory_writer):
    """Inputter wired to db_conn and shared_memory_writer."""
    return Inputter(db_conn, shared_memory_writer)


@pytest.fixture
def pipeline(fake_interpreter, inputter):
    """
    Full PromotionPipeline using FakeInterpreter.
    No API calls will be made.
    """
    return PromotionPipeline(
        interpreter=fake_interpreter,
        validator=Validator(),
        inputter=inputter,
    )


@pytest.fixture
def shared_memory(db_conn):
    """SharedMemory pointed at the same in-memory db_conn."""
    return SharedMemory(db_conn)
