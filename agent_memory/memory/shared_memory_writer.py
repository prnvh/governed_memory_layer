# Shared memory writer.
# Takes a validated, persisted event and writes it to the correct shared_* table.
# No LLM calls. No reasoning. Pure SQL. Does NOT commit — Inputter owns the transaction.


import json
import logging
import re
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
            matched_target_id = self._matched_target_id(event, fallback=target_id)
            if matched_target_id != target_id:
                self.conn.execute(
                    "UPDATE shared_constraints SET constraint_id=? WHERE constraint_id=?",
                    (target_id, matched_target_id),
                )
            existing = self.conn.execute(
                "SELECT reference_memory_json FROM shared_constraints WHERE constraint_id=?",
                (target_id,),
            ).fetchone()
            reference_memory_json = self._merged_reference_memory_json(
                bucket="constraints",
                target_id=target_id,
                canonical_text=None,
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )
            self.conn.execute(
                """
                UPDATE shared_constraints
                SET status='invalidated', last_updated_event_id=?, reference_memory_json=?
                WHERE constraint_id=?
                """,
                (event_id, reference_memory_json, target_id),
            )
        else:  # upsert
            payload = json.loads(event["payload_json"])
            existing = self.conn.execute(
                "SELECT reference_memory_json FROM shared_constraints WHERE constraint_id = ?",
                (target_id,),
            ).fetchone()
            reference_memory_json = self._merged_reference_memory_json(
                bucket="constraints",
                target_id=target_id,
                canonical_text=payload["text"],
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO shared_constraints
                    (constraint_id, text, status, scope, reference_memory_json, source_event_id, last_updated_event_id)
                VALUES (?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    target_id,
                    payload["text"],
                    payload.get("scope"),
                    reference_memory_json,
                    event_id,
                    event_id,
                ),
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
            matched_target_id = self._matched_target_id(event, fallback=target_id)
            if matched_target_id != target_id:
                self.conn.execute(
                    "UPDATE shared_issues SET issue_id=? WHERE issue_id=?",
                    (target_id, matched_target_id),
                )
            existing = self.conn.execute(
                "SELECT reference_memory_json FROM shared_issues WHERE issue_id=?",
                (target_id,),
            ).fetchone()
            reference_memory_json = self._merged_reference_memory_json(
                bucket="issues",
                target_id=target_id,
                canonical_text=None,
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )
            self.conn.execute(
                """
                UPDATE shared_issues
                SET status='resolved', last_updated_event_id=?, reference_memory_json=?
                WHERE issue_id=?
                """,
                (event_id, reference_memory_json, target_id),
            )
        else:  # upsert
            payload = json.loads(event["payload_json"])

            # Preserve first_seen_event_id if row already exists
            existing = self.conn.execute(
                "SELECT first_seen_event_id, reference_memory_json FROM shared_issues WHERE issue_id = ?",
                (target_id,),
            ).fetchone()
            first_seen = existing["first_seen_event_id"] if existing else event_id
            reference_memory_json = self._merged_reference_memory_json(
                bucket="issues",
                target_id=target_id,
                canonical_text=payload["title"],
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )

            self.conn.execute(
                """
                INSERT OR REPLACE INTO shared_issues
                    (issue_id, title, description, status, severity,
                     entity_type, entity_id, reference_memory_json, first_seen_event_id, last_updated_event_id)
                VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    payload["title"],
                    payload.get("description"),
                    payload.get("severity"),
                    payload.get("entity_type"),
                    payload.get("entity_id"),
                    reference_memory_json,
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
            matched_target_id = self._matched_target_id(event, fallback=target_id)
            if matched_target_id != target_id:
                self.conn.execute(
                    "UPDATE shared_decisions SET decision_id=? WHERE decision_id=?",
                    (target_id, matched_target_id),
                )
            existing = self.conn.execute(
                "SELECT reference_memory_json FROM shared_decisions WHERE decision_id=?",
                (target_id,),
            ).fetchone()
            reference_memory_json = self._merged_reference_memory_json(
                bucket="decisions",
                target_id=target_id,
                canonical_text=None,
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )
            self.conn.execute(
                """
                UPDATE shared_decisions
                SET status='superseded', reference_memory_json=?
                WHERE decision_id=?
                """,
                (reference_memory_json, target_id),
            )
        else:  # append
            payload = json.loads(event["payload_json"])

            # If target_id already exists, prefer a deterministic sibling id based on
            # the new statement instead of falling back to an opaque event id.
            existing = self.conn.execute(
                "SELECT statement, reference_memory_json FROM shared_decisions WHERE decision_id = ?",
                (target_id,),
            ).fetchone()
            decision_id = target_id
            if existing:
                existing_statement = str(existing["statement"] or "").strip().lower()
                new_statement = str(payload.get("statement") or "").strip().lower()
                if existing_statement == new_statement:
                    decision_id = target_id
                else:
                    decision_id = self._dedupe_decision_id(
                        target_id=target_id,
                        statement=payload.get("statement"),
                        event_id=event_id,
                    )
            reference_memory_json = self._merged_reference_memory_json(
                bucket="decisions",
                target_id=decision_id,
                canonical_text=payload["statement"],
                event=event,
                existing_reference_memory_json=(
                    existing["reference_memory_json"] if existing else None
                ),
            )

            self.conn.execute(
                """
                INSERT INTO shared_decisions
                    (decision_id, statement, rationale, scope, status, reference_memory_json, source_event_id)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    decision_id,
                    payload["statement"],
                    payload.get("rationale"),
                    payload.get("scope"),
                    reference_memory_json,
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

    def _matched_target_id(self, event: dict, fallback: str) -> str:
        matched = event.get("matched_target_id")
        if matched:
            return matched

        source_ref = event.get("source_ref")
        if source_ref:
            try:
                parsed = json.loads(source_ref)
                if isinstance(parsed, dict) and parsed.get("matched_target_id"):
                    return str(parsed["matched_target_id"])
            except Exception:
                pass

        return fallback

    def _merged_reference_memory_json(
        self,
        bucket: str,
        target_id: str,
        canonical_text: str | None,
        event: dict,
        existing_reference_memory_json: str | None,
    ) -> str:
        memory = self._load_reference_memory(existing_reference_memory_json)
        if canonical_text:
            memory["canonical_text"] = canonical_text

        raw_input = str(event.get("raw_input") or "").strip()
        if raw_input and not memory.get("creation_note_text"):
            memory["creation_note_text"] = raw_input

        self._add_unique(memory["aliases"], target_id)
        for slug in self._explicit_slugs(raw_input):
            self._add_unique(memory["aliases"], slug)

        parsed_source_ref = self._parse_source_ref(event)
        reference_text = str(parsed_source_ref.get("reference_text") or "").strip()
        if reference_text:
            self._add_unique(memory["reference_phrases"], reference_text)
            self._add_unique(memory["seen_referring_expressions"], reference_text)
            for slug in self._explicit_slugs(reference_text):
                self._add_unique(memory["aliases"], slug)

        candidate_aliases = parsed_source_ref.get("candidate_aliases") or []
        if isinstance(candidate_aliases, list):
            for alias in candidate_aliases:
                alias_text = str(alias).strip()
                if alias_text:
                    self._add_unique(memory["aliases"], alias_text)

        if raw_input:
            self._add_unique(memory["seen_referring_expressions"], raw_input)

        payload = json.loads(event["payload_json"])
        for field in ("title", "statement", "text", "description", "rationale"):
            value = payload.get(field)
            if value:
                self._add_unique(memory["reference_phrases"], str(value))

        if canonical_text:
            self._add_unique(memory["reference_phrases"], canonical_text)

        memory["aliases"] = memory["aliases"][:12]
        memory["reference_phrases"] = memory["reference_phrases"][:16]
        memory["seen_referring_expressions"] = memory["seen_referring_expressions"][:10]
        return json.dumps(memory)

    def _load_reference_memory(self, raw_json: str | None) -> dict:
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    return {
                        "canonical_text": parsed.get("canonical_text"),
                        "creation_note_text": parsed.get("creation_note_text"),
                        "aliases": list(parsed.get("aliases") or []),
                        "reference_phrases": list(parsed.get("reference_phrases") or []),
                        "seen_referring_expressions": list(parsed.get("seen_referring_expressions") or []),
                    }
            except Exception:
                pass
        return {
            "canonical_text": None,
            "creation_note_text": None,
            "aliases": [],
            "reference_phrases": [],
            "seen_referring_expressions": [],
        }

    def _parse_source_ref(self, event: dict) -> dict:
        source_ref = event.get("source_ref")
        if not source_ref:
            return {}
        try:
            parsed = json.loads(source_ref)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {}

    def _explicit_slugs(self, text: str) -> list[str]:
        return re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text.lower())

    def _add_unique(self, items: list[str], value: str) -> None:
        value = value.strip()
        if value and value not in items:
            items.append(value)

    def _dedupe_decision_id(self, target_id: str, statement: str | None, event_id: str) -> str:
        slug = target_id
        if statement:
            candidate = re.sub(r"[^a-z0-9]+", "_", statement.lower()).strip("_")
            if candidate:
                slug = candidate[:64]

        candidate_id = slug
        suffix = 2
        while self.conn.execute(
            "SELECT 1 FROM shared_decisions WHERE decision_id = ?",
            (candidate_id,),
        ).fetchone():
            candidate_id = f"{slug}_{suffix}"
            suffix += 1

        if candidate_id == target_id and self.conn.execute(
            "SELECT 1 FROM shared_decisions WHERE decision_id = ?",
            (candidate_id,),
        ).fetchone():
            return f"{slug}_{event_id[:8]}"
        return candidate_id
