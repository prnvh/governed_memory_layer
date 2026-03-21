"""
tests/test_core_pipeline.py

Component tests for the core memory pipeline.
No API calls — all interpreter interactions use FakeInterpreter via conftest.py.

Coverage:
    Validator  — rejects bad buckets, bad operations, missing payload fields,
                 empty target_id
    Projector  — correctly updates each shared_* table for every operation type
    Inputter   — writes to events_memory, sets applied_successfully flag,
                 handles projection failure gracefully
    Promotion  — routes accept/reject/invalid/error correctly, marks notes
                 as promoted, returns correct PromotionResult list
"""

import json
import pytest

from memory.interpreter import WriteRequest


def make_event(bucket, target_id, operation, payload, event_id="ev1", source_agent="agent_1"):
    """
    Build an event dict matching the format SharedMemoryWriter.write() actually receives
    from Inputter — payload is JSON-serialised, timestamp is present.
    """
    return {
        "event_id": event_id,
        "bucket": bucket,
        "target_id": target_id,
        "operation": operation,
        "payload_json": json.dumps(payload),
        "timestamp": "2024-01-01T00:00:00.000000",
        "source_agent": source_agent,
    }
from memory.validator import Validator, ValidationError
from memory.shared_memory_writer import SharedMemoryWriter
from memory.inputter import Inputter
from memory.working_memory import WorkingMemory
from memory.promotion import PromotionPipeline, PromotionResult


# ===========================================================================
# Helpers
# ===========================================================================

def make_write_request(**kwargs) -> WriteRequest:
    """Convenience builder — sensible defaults, override as needed."""
    defaults = dict(
        decision="accept",
        bucket="issues",
        target_id="test_issue",
        operation="upsert",
        payload={"title": "Test issue", "severity": "low"},
        rationale="test",
    )
    defaults.update(kwargs)
    return WriteRequest(**defaults)


def event_count(db_conn) -> int:
    return db_conn.execute("SELECT COUNT(*) FROM events_memory").fetchone()[0]


def fetch_one(db_conn, table: str, pk_col: str, pk_val: str):
    row = db_conn.execute(
        f"SELECT * FROM {table} WHERE {pk_col} = ?", (pk_val,)
    ).fetchone()
    return dict(row) if row else None


# ===========================================================================
# Validator tests
# ===========================================================================

class TestValidator:

    def setup_method(self):
        self.v = Validator()

    def test_valid_issues_upsert_passes(self):
        req = make_write_request()
        self.v.validate(req)  # should not raise

    def test_valid_plan_upsert_passes(self):
        req = make_write_request(
            bucket="plan",
            target_id="main",
            operation="upsert",
            payload={"plan_json": "step 1, step 2"},
        )
        self.v.validate(req)

    def test_valid_learnings_append_passes(self):
        req = make_write_request(
            bucket="learnings",
            target_id="pin_deps",
            operation="append",
            payload={"statement": "Always pin deps.", "title": "Pin deps"},
        )
        self.v.validate(req)

    def test_rejects_unknown_bucket(self):
        req = make_write_request(bucket="unknown_bucket")
        with pytest.raises(ValidationError, match="bucket"):
            self.v.validate(req)

    def test_rejects_operation_not_allowed_for_bucket(self):
        # plan only allows upsert — append is not valid
        req = make_write_request(
            bucket="plan",
            target_id="main",
            operation="append",
            payload={"plan_json": "..."},
        )
        with pytest.raises(ValidationError, match="Operation"):
            self.v.validate(req)

    def test_rejects_empty_target_id(self):
        req = make_write_request(target_id="")
        with pytest.raises(ValidationError, match="target_id"):
            self.v.validate(req)

    def test_rejects_target_id_with_spaces(self):
        req = make_write_request(target_id="has spaces")
        with pytest.raises(ValidationError, match="target_id"):
            self.v.validate(req)

    def test_rejects_missing_required_payload_field(self):
        # issues requires "title"
        req = make_write_request(payload={"severity": "low"})
        with pytest.raises(ValidationError, match="payload"):
            self.v.validate(req)

    def test_rejects_none_payload(self):
        req = make_write_request(payload=None)
        with pytest.raises(ValidationError, match="payload"):
            self.v.validate(req)

    def test_rejects_non_accept_decision(self):
        req = WriteRequest(decision="reject", rationale="already rejected")
        with pytest.raises(ValidationError, match="Validator received"):
            self.v.validate(req)

    def test_all_buckets_with_valid_minimum_payloads(self):
        """Smoke test: each bucket passes with its minimum required fields."""
        cases = [
            ("plan",        "main",       "upsert",     {"plan_json": "..."}),
            ("constraints", "no_writes",  "upsert",     {"text": "No external writes"}),
            ("issues",      "issue_1",    "upsert",     {"title": "Something broke"}),
            ("decisions",   "use_ds_b",   "append",     {"statement": "Use dataset B"}),
            ("results",     "run1_acc",   "append",     {"metric_name": "accuracy", "metric_value": "0.91"}),
            ("task_state",  "task_eval",  "upsert",     {"status": "in_progress"}),
            ("learnings",   "pin_deps",   "append",     {"statement": "Pin deps.", "title": "Pin deps"}),
        ]
        for bucket, target_id, operation, payload in cases:
            req = make_write_request(
                bucket=bucket, target_id=target_id,
                operation=operation, payload=payload,
            )
            self.v.validate(req)  # must not raise


# ===========================================================================
# Projector (SharedMemoryWriter) tests
# ===========================================================================

class TestSharedMemoryWriter:

    # ── plan ────────────────────────────────────────────────────────────────

    def test_project_plan_upsert_inserts_row(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(make_event("plan", "main", "upsert", {"plan_json": "step 1"}))
        db_conn.commit()
        row = fetch_one(db_conn, "shared_plan", "target_id", "main")
        assert row is not None
        assert row["plan_json"] == "step 1"
        assert row["version"] == 1

    def test_project_plan_upsert_increments_version(self, db_conn, shared_memory_writer):
        for i in range(1, 4):
            shared_memory_writer.write(
                make_event("plan", "main", "upsert", {"plan_json": f"step {i}"}, event_id=f"ev{i}")
            )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_plan", "target_id", "main")
        assert row["version"] == 3
        assert row["plan_json"] == "step 3"

    # ── constraints ─────────────────────────────────────────────────────────

    def test_project_constraints_upsert(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("constraints", "no_ext_writes", "upsert", {"text": "No external writes", "scope": None})
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_constraints", "constraint_id", "no_ext_writes")
        assert row["text"] == "No external writes"
        assert row["status"] == "active"

    def test_project_constraints_invalidate(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("constraints", "no_ext_writes", "upsert", {"text": "No external writes"}, event_id="ev1")
        )
        shared_memory_writer.write(
            make_event("constraints", "no_ext_writes", "invalidate", {}, event_id="ev2")
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_constraints", "constraint_id", "no_ext_writes")
        assert row["status"] == "invalidated"

    # ── issues ───────────────────────────────────────────────────────────────

    def test_project_issues_upsert(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("issues", "pandas_err", "upsert", {"title": "Pandas import error", "severity": "high"})
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_issues", "issue_id", "pandas_err")
        assert row["status"] == "open"
        assert row["severity"] == "high"
        assert row["first_seen_event_id"] == "ev1"

    def test_project_issues_upsert_preserves_first_seen(self, db_conn, shared_memory_writer):
        """Re-upserting an issue should NOT overwrite first_seen_event_id."""
        shared_memory_writer.write(
            make_event("issues", "pandas_err", "upsert", {"title": "Pandas error", "severity": "low"}, event_id="ev1")
        )
        shared_memory_writer.write(
            make_event("issues", "pandas_err", "upsert", {"title": "Pandas error", "severity": "high"}, event_id="ev2")
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_issues", "issue_id", "pandas_err")
        assert row["first_seen_event_id"] == "ev1"
        assert row["last_updated_event_id"] == "ev2"

    def test_project_issues_resolve(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("issues", "pandas_err", "upsert", {"title": "Pandas error", "severity": "high"}, event_id="ev1")
        )
        shared_memory_writer.write(
            make_event("issues", "pandas_err", "resolve", {}, event_id="ev2")
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_issues", "issue_id", "pandas_err")
        assert row["status"] == "resolved"

    # ── decisions ────────────────────────────────────────────────────────────

    def test_project_decisions_append(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("decisions", "use_ds_b", "append", {"statement": "Use dataset B", "rationale": None, "scope": None})
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_decisions", "decision_id", "use_ds_b")
        assert row["status"] == "active"
        assert row["statement"] == "Use dataset B"

    def test_project_decisions_invalidate(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("decisions", "use_ds_b", "append", {"statement": "Use dataset B"}, event_id="ev1")
        )
        shared_memory_writer.write(
            make_event("decisions", "use_ds_b", "invalidate", {}, event_id="ev2")
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_decisions", "decision_id", "use_ds_b")
        assert row["status"] == "superseded"

    # ── results ──────────────────────────────────────────────────────────────

    def test_project_results_append(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(make_event(
            "results", "run1_acc", "append",
            {"metric_name": "accuracy", "metric_value": "0.91", "baseline_value": "0.87", "experiment_id": "exp_1", "notes": None},
        ))
        db_conn.commit()
        row = fetch_one(db_conn, "shared_results", "result_id", "run1_acc")
        assert row["metric_value"] == "0.91"

    # ── task_state ───────────────────────────────────────────────────────────

    def test_project_task_state_upsert(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(
            make_event("task_state", "task_eval", "upsert", {"status": "in_progress", "phase": "eval", "blockers_json": None})
        )
        db_conn.commit()
        row = fetch_one(db_conn, "shared_task_state", "task_id", "task_eval")
        assert row["status"] == "in_progress"

    # ── learnings ────────────────────────────────────────────────────────────

    def test_project_learnings_append(self, db_conn, shared_memory_writer):
        shared_memory_writer.write(make_event(
            "learnings", "pin_deps", "append",
            {"statement": "Always pin deps.", "title": "Pin deps", "category": "ops", "confidence": 0.9, "source_issue_id": None},
        ))
        db_conn.commit()
        row = fetch_one(db_conn, "shared_learnings", "learning_id", "pin_deps")
        assert row["status"] == "active"
        assert row["confidence"] == 0.9


# ===========================================================================
# Inputter tests
# ===========================================================================

class TestInputter:

    def test_write_appends_to_events_memory(self, db_conn, inputter):
        req = make_write_request()
        event_id = inputter.write(req, source_agent="agent_1", raw_input="some note")
        assert event_count(db_conn) == 1
        row = fetch_one(db_conn, "events_memory", "event_id", event_id)
        assert row is not None
        assert row["source_agent"] == "agent_1"
        assert row["bucket"] == "issues"
        assert row["applied_successfully"] == 1

    def test_write_returns_unique_event_ids(self, db_conn, inputter):
        req1 = make_write_request(target_id="issue_a")
        req2 = make_write_request(target_id="issue_b")
        id1 = inputter.write(req1, source_agent="agent_1")
        id2 = inputter.write(req2, source_agent="agent_1")
        assert id1 != id2

    def test_write_also_updates_canonical_view(self, db_conn, inputter):
        req = make_write_request(
            bucket="issues",
            target_id="proj_test_issue",
            payload={"title": "Projection test", "severity": "medium"},
        )
        inputter.write(req, source_agent="agent_1")
        row = fetch_one(db_conn, "shared_issues", "issue_id", "proj_test_issue")
        assert row is not None
        assert row["title"] == "Projection test"

    def test_write_stores_payload_as_json(self, db_conn, inputter):
        payload = {"title": "JSON test", "severity": "low"}
        req = make_write_request(payload=payload)
        event_id = inputter.write(req, source_agent="agent_1")
        row = fetch_one(db_conn, "events_memory", "event_id", event_id)
        stored = json.loads(row["payload_json"])
        assert stored == payload

    def test_write_sets_applied_successfully_false_on_projection_failure(
        self, db_conn, shared_memory_writer, monkeypatch
    ):
        """
        If the writer raises, applied_successfully should be 0
        but the event should still be in events_memory.
        """
        def broken_write(event):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(shared_memory_writer, "write", broken_write)
        broken_inputter = Inputter(db_conn, shared_memory_writer)

        req = make_write_request()
        event_id = broken_inputter.write(req, source_agent="agent_1")

        assert event_count(db_conn) == 1
        row = fetch_one(db_conn, "events_memory", "event_id", event_id)
        assert row["applied_successfully"] == 0


# ===========================================================================
# Promotion pipeline tests
# ===========================================================================

class TestPromotionPipeline:

    def _make_wm(self, agent_id="test_agent") -> WorkingMemory:
        return WorkingMemory(agent_id=agent_id, run_id="run_001")

    def test_accept_path_writes_event_and_returns_result(
        self, db_conn, pipeline, fake_interpreter
    ):
        fake_interpreter.set_response(make_write_request(
            target_id="issue_promo",
            payload={"title": "Promoted issue", "severity": "high"},
        ))
        wm = self._make_wm()
        wm.add_note("benchmark failed with import error")

        results = pipeline.run(wm, trigger="end_of_step")

        assert len(results) == 1
        assert results[0].decision == "accept"
        assert results[0].event_id is not None
        assert results[0].bucket == "issues"
        assert event_count(db_conn) == 1

    def test_reject_path_writes_no_event(self, db_conn, pipeline, fake_interpreter):
        # FakeInterpreter default is reject — no set_response needed
        wm = self._make_wm()
        wm.add_note("I need to think about the next step.")

        results = pipeline.run(wm, trigger="end_of_step")

        assert len(results) == 1
        assert results[0].decision == "reject"
        assert results[0].event_id is None
        assert event_count(db_conn) == 0

    def test_invalid_path_does_not_write_event(self, db_conn, pipeline, fake_interpreter):
        # Accepted by interpreter but will fail validation (bad bucket)
        fake_interpreter.set_response(WriteRequest(
            decision="accept",
            bucket="not_a_real_bucket",
            target_id="some_target",
            operation="upsert",
            payload={"title": "x"},
            rationale="test",
        ))
        wm = self._make_wm()
        wm.add_note("something notable")

        results = pipeline.run(wm, trigger="end_of_step")

        assert results[0].decision == "invalid"
        assert event_count(db_conn) == 0

    def test_all_notes_marked_promoted_after_run(self, pipeline, fake_interpreter):
        """Even rejected notes should be marked as promoted so they aren't re-processed."""
        wm = self._make_wm()
        wm.add_note("note one")
        wm.add_note("note two")

        pipeline.run(wm, trigger="end_of_step")

        # get_promotion_candidates should now be empty
        assert wm.get_promotion_candidates() == []

    def test_multiple_notes_processed_independently(
        self, db_conn, pipeline, fake_interpreter
    ):
        """Each note gets its own interpret() call. Outcomes can differ."""
        fake_interpreter.set_response(make_write_request(
            target_id="issue_alpha",
            payload={"title": "Issue alpha", "severity": "low"},
        ))
        # Second note will use the default reject (queue exhausted)

        wm = self._make_wm()
        wm.add_note("import error blocking eval")
        wm.add_note("just thinking out loud")

        results = pipeline.run(wm)

        assert len(results) == 2
        assert results[0].decision == "accept"
        assert results[1].decision == "reject"
        assert event_count(db_conn) == 1

    def test_empty_working_memory_returns_empty_list(self, pipeline):
        wm = self._make_wm()
        results = pipeline.run(wm)
        assert results == []

    def test_interpreter_exception_recorded_as_error(
        self, db_conn, pipeline, fake_interpreter, monkeypatch
    ):
        def exploding_interpret(candidate_note, agent_id):
            raise RuntimeError("API is down")

        monkeypatch.setattr(fake_interpreter, "interpret", exploding_interpret)

        wm = self._make_wm()
        wm.add_note("some note")

        results = pipeline.run(wm)

        assert results[0].decision == "error"
        assert "interpreter_exception" in results[0].rationale
        assert event_count(db_conn) == 0