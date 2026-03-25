"""
Baseline benchmark systems.

These are kept separate from the governed harness so the core harness module
stays focused on the primary architecture and its fault-injected variant.
"""

import logging
import json
import re
import time
from typing import Optional

from benchmarks.harness import BaseHarness, HarnessResult, NoteOutcome
from benchmarks.trajectories.schema import Trajectory
from memory.db.connection import get_connection
from memory.db.schema import init_db
from memory.inputter import Inputter
from memory.interpreter import Interpreter, WriteRequest
from memory.promotion import PromotionPipeline, PromotionResult
from memory.shared_memory import SharedMemory
from memory.shared_memory_writer import SharedMemoryWriter
from memory.validator import Validator
from memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


def _slugify(text: str, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not slug:
        slug = "item"
    return f"{prefix}_{slug[:40]}".strip("_")


class AppendAllInterpreter:
    """
    Deterministic append-all baseline.

    Every note is promoted with shallow local heuristics only:
    - no LLM call
    - no reject path
    - no context lookup
    - no transition logic
    """

    def __init__(self, model: str = "gpt-4.1"):
        # model is accepted only to preserve the harness signature
        self.model = model

    def interpret(
        self,
        candidate_note: str,
        agent_id: str,
        context: Optional[dict] = None,
        source: str = "agent",
        tool_name: Optional[str] = None,
    ) -> WriteRequest:
        bucket = self._classify_bucket(candidate_note, source=source, tool_name=tool_name)
        operation = {
            "plan": "upsert",
            "constraints": "upsert",
            "issues": "upsert",
            "decisions": "append",
            "results": "append",
            "task_state": "upsert",
            "learnings": "append",
        }[bucket]
        repaired = WriteRequest(
            decision="accept",
            bucket=bucket,
            target_id=self._default_target_id(bucket, candidate_note),
            operation=operation,
            payload=self._build_payload(bucket, candidate_note),
            rationale=f"append_all_promote:{bucket}",
        )
        logger.info(
            "AppendAllInterpreter [%s] -> accept | bucket=%s | rationale=%s",
            agent_id,
            repaired.bucket,
            repaired.rationale,
        )
        return repaired

    def _classify_bucket(self, text: str, source: str, tool_name: Optional[str]) -> str:
        lowered = text.strip().lower()

        if lowered.startswith("plan:") or lowered.startswith("plan for"):
            return "plan"
        if lowered.startswith("constraint:"):
            return "constraints"
        if lowered.startswith("decision:"):
            return "decisions"
        if lowered.startswith("learning:"):
            return "learnings"
        if lowered.startswith("result for") or lowered.startswith("result:"):
            return "results"

        if self._looks_like_task_state(lowered):
            return "task_state"
        if source == "tool_result" and self._looks_like_result(text):
            return "results"
        if self._looks_like_issue(lowered):
            return "issues"
        if self._looks_like_constraint(lowered):
            return "constraints"
        if self._looks_like_decision(lowered):
            return "decisions"
        if source == "tool_result":
            return "results"
        return "learnings"

    def _build_payload(self, bucket: str, candidate_note: str) -> dict:
        text = candidate_note.strip()

        if bucket == "plan":
            return {"plan_json": self._strip_known_prefix(text)}
        if bucket == "constraints":
            return {"text": self._strip_known_prefix(text), "scope": None}
        if bucket == "issues":
            return {
                "title": self._issue_title(text),
                "description": text,
                "severity": self._infer_severity(text),
            }
        if bucket == "decisions":
            return {"statement": self._strip_known_prefix(text), "rationale": None, "scope": None}
        if bucket == "results":
            metric_name, metric_value = self._infer_result_fields(text)
            return {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "baseline_value": None,
                "experiment_id": self._infer_experiment_id(text),
                "notes": text,
            }
        if bucket == "task_state":
            return {
                "status": self._infer_task_status(text),
                "phase": None,
                "blockers_json": None,
            }
        return {
            "statement": self._strip_known_prefix(text),
            "title": self._learning_title(text),
            "category": None,
            "confidence": None,
            "source_issue_id": None,
        }

    def _default_target_id(self, bucket: str, candidate_note: str) -> str:
        if bucket == "plan":
            return "main"
        prefix_map = {
            "constraints": "constraint",
            "issues": "issue",
            "decisions": "decision",
            "results": "result",
            "task_state": "task",
            "learnings": "learning",
        }
        return _slugify(candidate_note, prefix_map.get(bucket, "item"))

    def _infer_severity(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["critical", "sev0", "sev-0"]):
            return "critical"
        if any(token in lowered for token in ["blocking", "blocked", "failure", "error", "incident", "breach"]):
            return "high"
        if any(token in lowered for token in ["warning", "degraded", "flaky", "drift"]):
            return "medium"
        return "low"

    def _infer_task_status(self, text: str) -> str:
        lowered = text.lower()
        if "blocked" in lowered or "cannot proceed" in lowered:
            return "blocked"
        if "failed" in lowered or "failure" in lowered:
            return "failed"
        if any(token in lowered for token in ["done", "task complete", "task is complete", "completed", "closed"]):
            return "done"
        if "pending" in lowered:
            return "pending"
        return "in_progress"

    def _infer_result_fields(self, text: str) -> tuple[str, str]:
        lowered = text.lower()

        metric_patterns = [
            (r"(?:val(?:idation)?[_ ]accuracy|best val accuracy|primary task accuracy|accuracy)\s*[:=]?\s*([0-9]*\.[0-9]+|[0-9]+)", "validation_accuracy"),
            (r"(?:val[_ ]auc|auc)\s*[:=]?\s*([0-9]*\.[0-9]+|[0-9]+)", "val_auc"),
            (r"(?:macro[_ -]?f1|f1)\s*[:=]?\s*([0-9]*\.[0-9]+|[0-9]+)", "macro_f1"),
            (r"(?:val[_ ]loss|loss)\s*[:=]?\s*([0-9]*\.[0-9]+|[0-9]+)", "val_loss"),
            (r"(?:p99 latency|p95 latency|latency)\s*[:=]?\s*([0-9]*\.[0-9]+|[0-9]+)", "latency"),
        ]

        for pattern, metric_name in metric_patterns:
            match = re.search(pattern, lowered)
            if match:
                return metric_name, match.group(1)

        match = re.search(r"([a-zA-Z_]+)\s*[:=]\s*([0-9]*\.[0-9]+|[0-9]+|true|false)", text)
        if match:
            return match.group(1).lower(), match.group(2)
        return "note_capture", text[:120]

    def _infer_experiment_id(self, text: str) -> Optional[str]:
        match = re.search(r"\bexp[_ -]?(\d+)\b", text.lower())
        if match:
            return f"exp_{match.group(1)}"
        return None

    def _strip_known_prefix(self, text: str) -> str:
        for prefix in ("Plan:", "Constraint:", "Decision:", "Learning:", "Result:"):
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return text.strip()

    def _learning_title(self, text: str) -> str:
        stripped = self._strip_known_prefix(text)
        return stripped[:80] if stripped else "Append-all note"

    def _issue_title(self, text: str) -> str:
        stripped = self._strip_known_prefix(text)
        stripped = stripped.split(".")[0].strip()
        return stripped[:160] if stripped else "Issue"

    def _looks_like_task_state(self, lowered: str) -> bool:
        return any(
            phrase in lowered for phrase in [
                "task is complete",
                "task complete",
                "task is now in progress",
                "task is blocked",
                "task blocked",
                "cannot proceed",
                "kicked off",
                "in progress",
                "handoff complete",
                "incident closed",
            ]
        )

    def _looks_like_result(self, text: str) -> bool:
        lowered = text.lower()
        return (
            bool(re.search(r"([a-zA-Z_]+)\s*[:=]\s*([0-9]*\.[0-9]+|[0-9]+|true|false)", text))
            or any(token in lowered for token in [
                "accuracy",
                "auc",
                "f1",
                "latency",
                "duration",
                "eta",
                "utilization",
                "green runs",
                "all checks passed",
                "published",
                "complete",
            ])
        )

    def _looks_like_issue(self, lowered: str) -> bool:
        return any(
            token in lowered for token in [
                "error",
                "failed",
                "failure",
                "issue",
                "incident",
                "alert",
                "blocked",
                "breach",
                "drift",
                "oom",
                "problem",
                "root cause",
            ]
        )

    def _looks_like_constraint(self, lowered: str) -> bool:
        return any(
            token in lowered for token in [
                "must ",
                "must not",
                "required",
                "requirement",
                "no production",
                "no pre-ticked",
                "do not merge",
                "at least one",
                "deadline",
                "no exceptions",
            ]
        )

    def _looks_like_decision(self, lowered: str) -> bool:
        return any(
            token in lowered for token in [
                "we will",
                "use ",
                "schedule ",
                "classify ",
                "convert ",
                "rebuild ",
                "quarantine ",
                "rotate ",
            ]
        )


class ScratchpadExtractor(Interpreter):
    """
    Extract a final structured snapshot from one rolling scratchpad document.
    """

    SYSTEM_PROMPT = """You will be given the final contents of a raw private
scratchpad that contains all notes written during one run. Infer the final
shared memory state as best you can from the scratchpad contents alone.

Output ONLY valid JSON with exactly this structure:
{
  "plan": dict|null,
  "constraints": [dict, ...],
  "issues": [dict, ...],
  "decisions": [dict, ...],
  "results": [dict, ...],
  "task_state": [dict, ...],
  "learnings": [dict, ...]
}

Use the same field names expected by the benchmark scorer:
- plan: target_id, plan_json
- constraints: constraint_id, text, status, scope
- issues: issue_id, title, description, status, severity, entity_type, entity_id
- decisions: decision_id, statement, rationale, scope, status
- results: result_id, experiment_id, metric_name, metric_value, baseline_value, notes
- task_state: task_id, status, phase, owner_agent, blockers_json
- learnings: learning_id, title, statement, category, scope, confidence, source_issue_id, status

Status vocabulary is strict:
- issues.status must be one of: open, resolved
- constraints.status must be one of: active, invalidated
- decisions.status must be one of: active, invalidated
- learnings.status must be one of: active, invalidated
- task_state.status must be one of: pending, in_progress, blocked, done, failed

Preserve explicit plan notes as plan.target_id="main" when a plan is present.
Do not invent alternate status labels such as implemented, confirmed, validated,
accepted, approved, complete, or closed.

Infer the final state as best you can from the scratchpad. Omit rows you are not
confident about rather than inventing extra fields."""

    def extract_snapshot(self, scratchpad: str, agent_id: str) -> dict:
        user_message = f"Agent: {agent_id}\n\nScratchpad:\n{scratchpad}"
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw_text = response.choices[0].message.content.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        parsed = json.loads(raw_text)
        return self._normalize_snapshot(parsed)

    def _normalize_snapshot(self, parsed: dict) -> dict:
        plan = parsed.get("plan")
        if isinstance(plan, dict) and not plan.get("target_id"):
            plan["target_id"] = "main"

        return {
            "plan": plan,
            "constraints": [
                self._normalize_row_status(row, "constraints")
                for row in parsed.get("constraints", [])
                if isinstance(row, dict)
            ],
            "issues": [
                self._normalize_row_status(row, "issues")
                for row in parsed.get("issues", [])
                if isinstance(row, dict)
            ],
            "decisions": [
                self._normalize_row_status(row, "decisions")
                for row in parsed.get("decisions", [])
                if isinstance(row, dict)
            ],
            "results": [row for row in parsed.get("results", []) if isinstance(row, dict)],
            "task_state": [
                self._normalize_row_status(row, "task_state")
                for row in parsed.get("task_state", [])
                if isinstance(row, dict)
            ],
            "learnings": [
                self._normalize_row_status(row, "learnings")
                for row in parsed.get("learnings", [])
                if isinstance(row, dict)
            ],
        }

    def _normalize_row_status(self, row: dict, bucket: str) -> dict:
        normalized = dict(row)
        status = str(normalized.get("status", "")).strip().lower()
        if not status:
            return normalized

        if bucket == "issues":
            if status in {"closed", "fixed", "done", "complete", "completed", "confirmed", "validated"}:
                normalized["status"] = "resolved"
            elif status in {"active", "investigating", "pending", "in_progress", "blocked"}:
                normalized["status"] = "open"
            return normalized

        if bucket in {"constraints", "decisions", "learnings"}:
            if status in {"implemented", "accepted", "approved", "confirmed", "validated", "applied"}:
                normalized["status"] = "active"
            elif status in {"closed", "done", "complete", "completed"}:
                normalized["status"] = "invalidated"
            return normalized

        if bucket == "task_state":
            task_map = {
                "complete": "done",
                "completed": "done",
                "closed": "done",
                "approved": "done",
                "accepted": "done",
                "active": "in_progress",
                "open": "in_progress",
                "resolved": "done",
                "confirmed": "done",
                "validated": "done",
            }
            normalized["status"] = task_map.get(status, status)
            return normalized

        return normalized


class StatelessClassifierHarness(BaseHarness):
    """
    Same note-by-note classification task, but the interpreter never sees
    shared-memory context.
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model

    @property
    def system_name(self) -> str:
        return "no_shared_context"

    def run_trajectory(self, trajectory: Trajectory) -> HarnessResult:
        start = time.perf_counter()

        try:
            conn = get_connection(":memory:")
            init_db(conn)

            interpreter = Interpreter(model=self.model)
            validator = Validator()
            writer = SharedMemoryWriter(conn)
            inputter = Inputter(conn, writer)
            shared_memory = SharedMemory(conn)
            pipeline = PromotionPipeline(
                interpreter, validator, inputter, shared_memory=None
            )

            wm = WorkingMemory(agent_id=trajectory.agent_id, run_id=trajectory.id)
            for note in trajectory.notes:
                if note.source == "tool_result" and note.tool_name:
                    wm.add_tool_result_note(note.tool_name, note.text)
                else:
                    wm.add_note(note.text, source=note.source)

            promotion_results = pipeline.run(wm, trigger="end_of_step")
            snapshot = shared_memory.snapshot()
            events_written = conn.execute(
                "SELECT COUNT(*) FROM events_memory"
            ).fetchone()[0]
            conn.close()

        except Exception as exc:
            elapsed = time.perf_counter() - start
            return HarnessResult(
                trajectory_id=trajectory.id,
                system_name=self.system_name,
                snapshot={},
                note_outcomes=[],
                events_written=0,
                accepted_count=0,
                rejected_count=0,
                run_duration_seconds=elapsed,
                error=str(exc),
            )

        elapsed = time.perf_counter() - start
        note_outcomes = [
            NoteOutcome(
                note_text=r.note_text,
                decision=r.decision,
                bucket=r.bucket,
                event_id=r.event_id,
                rationale=r.rationale,
            )
            for r in promotion_results
        ]

        return HarnessResult(
            trajectory_id=trajectory.id,
            system_name=self.system_name,
            snapshot=snapshot,
            note_outcomes=note_outcomes,
            events_written=events_written,
            accepted_count=sum(1 for r in promotion_results if r.decision == "accept"),
            rejected_count=sum(1 for r in promotion_results if r.decision == "reject"),
            run_duration_seconds=elapsed,
        )


class AppendAllMemoryHarness(BaseHarness):
    """
    Naive baseline: every note is forced into shared memory with no reject path
    and no shared-state context.
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model

    @property
    def system_name(self) -> str:
        return "append_all"

    def run_trajectory(self, trajectory: Trajectory) -> HarnessResult:
        start = time.perf_counter()

        try:
            conn = get_connection(":memory:")
            init_db(conn)

            interpreter = AppendAllInterpreter(model=self.model)
            writer = SharedMemoryWriter(conn)
            inputter = Inputter(conn, writer)
            shared_memory = SharedMemory(conn)
            promotion_results: list[PromotionResult] = []

            for note in trajectory.notes:
                write_request = interpreter.interpret(
                    candidate_note=note.text,
                    agent_id=trajectory.agent_id,
                    context=None,
                    source=note.source,
                    tool_name=note.tool_name,
                )
                if write_request.decision != "accept":
                    write_request = WriteRequest(
                        decision="accept",
                        bucket="learnings",
                        target_id=_slugify(note.text, "append_all"),
                        operation="append",
                        payload={
                            "statement": note.text,
                            "title": "Append-all note",
                        },
                        rationale="append_all_manual_fallback",
                    )

                try:
                    event_id = inputter.write(
                        write_request=write_request,
                        source_agent=trajectory.agent_id,
                        raw_input=note.text,
                    )
                    promotion_results.append(
                        PromotionResult(
                            note_text=note.text,
                            decision="accept",
                            event_id=event_id,
                            bucket=write_request.bucket,
                            rationale=write_request.rationale,
                        )
                    )
                except Exception:
                    fallback = WriteRequest(
                        decision="accept",
                        bucket="learnings",
                        target_id=_slugify(note.text, "append_all"),
                        operation="append",
                        payload={
                            "statement": note.text,
                            "title": "Append-all note",
                        },
                        rationale="append_all_write_fallback",
                    )
                    event_id = inputter.write(
                        write_request=fallback,
                        source_agent=trajectory.agent_id,
                        raw_input=note.text,
                    )
                    promotion_results.append(
                        PromotionResult(
                            note_text=note.text,
                            decision="accept",
                            event_id=event_id,
                            bucket=fallback.bucket,
                            rationale=fallback.rationale,
                        )
                    )

            snapshot = shared_memory.snapshot()
            events_written = conn.execute(
                "SELECT COUNT(*) FROM events_memory"
            ).fetchone()[0]
            conn.close()

        except Exception as exc:
            elapsed = time.perf_counter() - start
            return HarnessResult(
                trajectory_id=trajectory.id,
                system_name=self.system_name,
                snapshot={},
                note_outcomes=[],
                events_written=0,
                accepted_count=0,
                rejected_count=0,
                run_duration_seconds=elapsed,
                error=str(exc),
            )

        elapsed = time.perf_counter() - start
        note_outcomes = [
            NoteOutcome(
                note_text=r.note_text,
                decision=r.decision,
                bucket=r.bucket,
                event_id=r.event_id,
                rationale=r.rationale,
            )
            for r in promotion_results
        ]

        return HarnessResult(
            trajectory_id=trajectory.id,
            system_name=self.system_name,
            snapshot=snapshot,
            note_outcomes=note_outcomes,
            events_written=events_written,
            accepted_count=sum(1 for r in promotion_results if r.decision == "accept"),
            rejected_count=sum(1 for r in promotion_results if r.decision == "reject"),
            run_duration_seconds=elapsed,
        )


class ScratchpadMemoryHarness(BaseHarness):
    """
    Raw private scratchpad baseline.

    Every note is appended verbatim to one scratchpad. No interpreter,
    validator, or shared-memory lifecycle logic runs during the write path.
    A final extraction pass then tries to recover benchmark state from the
    scratchpad alone.
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model

    @property
    def system_name(self) -> str:
        return "scratchpad"

    def run_trajectory(self, trajectory: Trajectory) -> HarnessResult:
        start = time.perf_counter()

        try:
            scratchpad_lines: list[str] = []
            note_outcomes: list[NoteOutcome] = []

            for idx, note in enumerate(trajectory.notes, start=1):
                prefix = f"[{idx}] {note.source}"
                if note.tool_name:
                    prefix += f"::{note.tool_name}"
                scratchpad_lines.append(f"{prefix} {note.text}")
                note_outcomes.append(
                    NoteOutcome(
                        note_text=note.text,
                        decision="accept",
                        bucket=None,
                        event_id=None,
                        rationale="appended_to_scratchpad",
                    )
                )
            snapshot = {"__scratchpad__": "\n".join(scratchpad_lines)}

        except Exception as exc:
            elapsed = time.perf_counter() - start
            return HarnessResult(
                trajectory_id=trajectory.id,
                system_name=self.system_name,
                snapshot={},
                note_outcomes=[],
                events_written=0,
                accepted_count=0,
                rejected_count=0,
                run_duration_seconds=elapsed,
                error=str(exc),
            )

        elapsed = time.perf_counter() - start
        return HarnessResult(
            trajectory_id=trajectory.id,
            system_name=self.system_name,
            snapshot=snapshot,
            note_outcomes=note_outcomes,
            events_written=0,
            accepted_count=len(note_outcomes),
            rejected_count=0,
            run_duration_seconds=elapsed,
        )
