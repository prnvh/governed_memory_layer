# Orchestrates the full promotion pipeline: WorkingMemory -> Interpreter -> Validator -> Inputter
# Called at end-of-step or on tool-result triggers. 
# Collects unpromoted working memory candidates, runs each through the pipeline, and handles failures without crashing. 


import logging
from dataclasses import dataclass, field
from typing import Optional

from memory.interpreter import Interpreter, WriteRequest
from memory.validator import Validator, ValidationError
from memory.inputter import Inputter
from memory.working_memory import WorkingMemory
from memory.shared_memory import SharedMemory

logger = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """
    Outcome of one promotion attempt for a single note.

    decision values:
        "accept"  — interpreter accepted, validator passed, event written
        "reject"  — interpreter returned decision="reject"
        "invalid" — interpreter accepted but validator raised ValidationError
        "error"   — unexpected exception at any stage
    """
    note_text: str
    decision: str                   # accept | reject | invalid | error
    event_id: Optional[str] = None  # set only if decision == "accept"
    bucket: Optional[str] = None    # set if interpreter accepted
    rationale: str = ""


class PromotionPipeline:
    """
    Orchestrates: WorkingMemory → Interpreter → Validator → Inputter

    One interpret() call per note. Notes are never batched together.
    All exceptions are caught and logged — a failing note must not
    affect subsequent notes or crash the agent.
    """

    def __init__(
        self,
        interpreter: Interpreter,
        validator: Validator,
        inputter: Inputter,
        shared_memory: Optional[SharedMemory] = None,
    ):
        self.interpreter = interpreter
        self.validator = validator
        self.inputter = inputter
        self.shared_memory = shared_memory

    def run(
        self,
        working_memory: WorkingMemory,
        trigger: str = "end_of_step",  # "end_of_step" | "tool_result" | "explicit"
    ) -> list[PromotionResult]:
        """
        Process all unpromoted notes from working_memory through the pipeline.

        Steps per note:
            1. Call interpreter.interpret(note_text, agent_id) → WriteRequest
            2. If reject  → log, record as "reject", skip
            3. If accept  → call validator.validate()
               a. ValidationError → log, record as "invalid", skip
               b. Valid           → call inputter.write(), record as "accept"
            4. On any unexpected exception → log, record as "error", continue

        After all notes are processed, marks them all as promoted in
        working_memory regardless of outcome — they have been seen by
        the pipeline and should not be re-processed.

        Returns a list of PromotionResult, one per candidate note.
        """
        candidates = working_memory.get_promotion_candidates()

        if not candidates:
            logger.debug(
                "[promotion] No unpromoted candidates (agent=%s, trigger=%s)",
                working_memory.agent_id,
                trigger,
            )
            return []

        logger.info(
            "[promotion] Running pipeline: agent=%s, trigger=%s, candidates=%d",
            working_memory.agent_id,
            trigger,
            len(candidates),
        )

        results: list[PromotionResult] = []
        promoted_indices: list[int] = []

        for idx, note in enumerate(candidates):
            note_text = note["text"]

            # Fetch current shared memory context before each note.
            # This gives the interpreter visibility into existing open issues
            # so it can resolve them correctly instead of creating duplicates.
            context = self._build_context()

            result = self._process_note(note_text, working_memory.agent_id, context)
            results.append(result)
            promoted_indices.append(idx)

            logger.info(
                "[promotion] note[%d] decision=%s bucket=%s rationale=%s",
                idx,
                result.decision,
                result.bucket or "-",
                result.rationale,
            )

        # Mark all processed notes as promoted regardless of outcome.
        # They have passed through the pipeline — do not re-process them.
        working_memory.mark_promoted(promoted_indices)

        accepted = sum(1 for r in results if r.decision == "accept")
        logger.info(
            "[promotion] Done: %d/%d accepted",
            accepted,
            len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_context(self) -> Optional[dict]:
        """
        Fetch relevant current state from shared memory to pass to the
        interpreter and validator before each note is processed.

        Returns None if no shared memory is wired.

        Only fetches state that can be transitioned — i.e. things the
        interpreter might need to resolve or invalidate:
            - open issues      (can be resolved)
            - active decisions (can be invalidated)
            - active constraints (can be invalidated)

        Fetched fresh per note so that a write from note N is visible
        to the interpreter when processing note N+1.
        """
        if self.shared_memory is None:
            return None
        return {
            "open_issues":         self.shared_memory.get_open_issues(),
            "active_decisions":    self.shared_memory.get_decisions(status="active"),
            "active_constraints":  self.shared_memory.get_active_constraints(),
        }

    def _process_note(
        self,
        note_text: str,
        agent_id: str,
        context: Optional[dict] = None,
    ) -> PromotionResult:
        """
        Run a single note through interpret → validate → write.
        Context is passed to both interpreter and validator.
        Returns a PromotionResult. Never raises.
        """
        try:
            write_request: WriteRequest = self.interpreter.interpret(
                candidate_note=note_text,
                agent_id=agent_id,
                context=context,
            )
        except Exception as exc:
            logger.exception("[promotion] Interpreter raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                rationale=f"interpreter_exception: {exc}",
            )

        # ── Rejected by interpreter ───────────────────────────────────
        if write_request.decision == "reject":
            return PromotionResult(
                note_text=note_text,
                decision="reject",
                rationale=write_request.rationale,
            )

        # ── Accepted — now validate ───────────────────────────────────
        try:
            self.validator.validate(write_request, context=context)
        except ValidationError as ve:
            logger.warning(
                "[promotion] Validation failed for note (bucket=%s): %s",
                write_request.bucket,
                ve,
            )
            return PromotionResult(
                note_text=note_text,
                decision="invalid",
                bucket=write_request.bucket,
                rationale=f"validation_error: {ve}",
            )
        except Exception as exc:
            logger.exception("[promotion] Validator raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                bucket=write_request.bucket,
                rationale=f"validator_exception: {exc}",
            )

        # ── Valid — write to shared memory ────────────────────────────
        try:
            event_id = self.inputter.write(
                write_request=write_request,
                source_agent=agent_id,
                raw_input=note_text,
            )
        except Exception as exc:
            logger.exception("[promotion] Inputter raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                bucket=write_request.bucket,
                rationale=f"inputter_exception: {exc}",
            )

        return PromotionResult(
            note_text=note_text,
            decision="accept",
            event_id=event_id,
            bucket=write_request.bucket,
            rationale=write_request.rationale,
        )