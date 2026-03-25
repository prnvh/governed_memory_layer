import logging
from dataclasses import dataclass
from typing import Optional

from memory.inputter import Inputter
from memory.interpreter import Interpreter, WriteRequest
from memory.pending_memory import PendingMemoryQueue
from memory.resolver import Resolver
from memory.shared_memory import SharedMemory
from memory.validator import ValidationError, Validator
from memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """
    Outcome of one promotion attempt for a single note.

    decision values:
        "accept"       interpreter accepted, resolver committed, validator passed
        "provisional"  note preserved in pending memory, no canonical mutation
        "reject"       interpreter or resolver rejected the note
        "invalid"      resolver committed but validator raised ValidationError
        "error"        unexpected exception at any stage
    """

    note_text: str
    decision: str
    event_id: Optional[str] = None
    bucket: Optional[str] = None
    rationale: str = ""


class PromotionPipeline:
    """
    Orchestrates: WorkingMemory -> Interpreter -> Resolver -> Validator -> Inputter

    One interpret() call per note. Notes are never batched together.
    All exceptions are caught and logged so one bad note cannot crash the run.
    """

    def __init__(
        self,
        interpreter: Interpreter,
        validator: Validator,
        inputter: Inputter,
        shared_memory: Optional[SharedMemory] = None,
        resolver: Optional[Resolver] = None,
        pending_queue: Optional[PendingMemoryQueue] = None,
    ):
        self.interpreter = interpreter
        self.validator = validator
        self.inputter = inputter
        self.shared_memory = shared_memory
        self.resolver = resolver or Resolver()
        self.pending_queue = pending_queue or PendingMemoryQueue(inputter.conn)

    def run(
        self,
        working_memory: WorkingMemory,
        trigger: str = "end_of_step",
    ) -> list[PromotionResult]:
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
            context = self._build_context()
            result = self._process_note(note_text, working_memory.agent_id, context)
            results.append(result)
            promoted_indices.append(idx)

            if result.decision == "accept":
                self._drain_pending_after_commit(agent_id=working_memory.agent_id)

            logger.info(
                "[promotion] note[%d] decision=%s bucket=%s rationale=%s",
                idx,
                result.decision,
                result.bucket or "-",
                result.rationale,
            )

        working_memory.mark_promoted(promoted_indices)

        accepted = sum(1 for r in results if r.decision == "accept")
        provisional = sum(1 for r in results if r.decision == "provisional")
        rejected = sum(1 for r in results if r.decision == "reject")
        logger.info(
            "[promotion] Done: accepted=%d provisional=%d rejected=%d total=%d",
            accepted,
            provisional,
            rejected,
            len(results),
        )
        return results

    def _build_context(self) -> Optional[dict]:
        if self.shared_memory is None:
            return None
        return {
            "open_issues": self.shared_memory.get_open_issues(),
            "active_decisions": self.shared_memory.get_decisions(status="active"),
            "active_constraints": self.shared_memory.get_active_constraints(),
        }

    def _process_note(
        self,
        note_text: str,
        agent_id: str,
        context: Optional[dict] = None,
    ) -> PromotionResult:
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

        if write_request.decision == "reject":
            return PromotionResult(
                note_text=note_text,
                decision="reject",
                rationale=write_request.rationale,
            )

        try:
            resolved_write = self.resolver.resolve(
                write_request=write_request,
                raw_input=note_text,
                context=context,
            )
        except Exception as exc:
            logger.exception("[promotion] Resolver raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                bucket=write_request.bucket,
                rationale=f"resolver_exception: {exc}",
            )

        if resolved_write.decision == "reject":
            return PromotionResult(
                note_text=note_text,
                decision="reject",
                bucket=write_request.bucket,
                rationale=resolved_write.resolution_reason,
            )

        if resolved_write.decision == "provisional":
            try:
                pending_id = self.inputter.write_provisional(
                    resolved_write=resolved_write,
                    source_agent=agent_id,
                    raw_input=note_text,
                    write_request=write_request,
                )
            except Exception as exc:
                logger.exception("[promotion] Provisional inputter raised unexpectedly: %s", exc)
                return PromotionResult(
                    note_text=note_text,
                    decision="error",
                    bucket=resolved_write.bucket,
                    rationale=f"provisional_inputter_exception: {exc}",
                )

            return PromotionResult(
                note_text=note_text,
                decision="provisional",
                event_id=pending_id,
                bucket=resolved_write.bucket,
                rationale=resolved_write.resolution_reason,
            )

        try:
            self.validator.validate_resolved(resolved_write, context=context)
        except ValidationError as ve:
            logger.warning(
                "[promotion] Validation failed for note (bucket=%s): %s",
                resolved_write.bucket,
                ve,
            )
            return PromotionResult(
                note_text=note_text,
                decision="invalid",
                bucket=resolved_write.bucket,
                rationale=f"validation_error: {ve}",
            )
        except Exception as exc:
            logger.exception("[promotion] Validator raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                bucket=resolved_write.bucket,
                rationale=f"validator_exception: {exc}",
            )

        try:
            event_id = self.inputter.write_resolved(
                resolved_write=resolved_write,
                source_agent=agent_id,
                raw_input=note_text,
                write_request=write_request,
            )
        except Exception as exc:
            logger.exception("[promotion] Inputter raised unexpectedly: %s", exc)
            return PromotionResult(
                note_text=note_text,
                decision="error",
                bucket=resolved_write.bucket,
                rationale=f"inputter_exception: {exc}",
            )

        return PromotionResult(
            note_text=note_text,
            decision="accept",
            event_id=event_id,
            bucket=resolved_write.bucket,
            rationale=resolved_write.resolution_reason,
        )

    def retry_pending(
        self,
        agent_id: str = "system",
        max_items: int = 25,
        reason: str = "scheduled_retry",
    ) -> list[PromotionResult]:
        if self.shared_memory is None:
            return []

        pending_rows = self.pending_queue.get_retryable(limit=max_items)
        results: list[PromotionResult] = []

        for row in pending_rows:
            context = self._build_context()
            note_text = row.get("raw_input", "")
            pending_id = row["pending_id"]

            try:
                write_request = self.pending_queue.rebuild_write_request(row)
                resolved_write = self.resolver.resolve(
                    write_request=write_request,
                    raw_input=note_text,
                    context=context,
                )
            except Exception as exc:
                hold_reason = f"{reason}:retry_exception:{exc}"
                self.pending_queue.mark_on_hold(pending_id, hold_reason)
                results.append(
                    PromotionResult(
                        note_text=note_text,
                        decision="error",
                        bucket=row.get("bucket"),
                        rationale=hold_reason,
                    )
                )
                continue

            if resolved_write.decision == "reject":
                reject_reason = f"{reason}:{resolved_write.resolution_reason}"
                self.pending_queue.mark_rejected(pending_id, reject_reason)
                results.append(
                    PromotionResult(
                        note_text=note_text,
                        decision="reject",
                        bucket=row.get("bucket"),
                        rationale=reject_reason,
                    )
                )
                continue

            if resolved_write.decision == "provisional":
                hold_reason = f"{reason}:{resolved_write.resolution_reason}"
                self.pending_queue.mark_on_hold(pending_id, hold_reason)
                results.append(
                    PromotionResult(
                        note_text=note_text,
                        decision="provisional",
                        event_id=pending_id,
                        bucket=row.get("bucket"),
                        rationale=hold_reason,
                    )
                )
                continue

            try:
                self.validator.validate_resolved(resolved_write, context=context)
                event_id = self.inputter.write_resolved(
                    resolved_write=resolved_write,
                    source_agent=agent_id,
                    raw_input=note_text,
                    write_request=write_request,
                )
            except ValidationError as ve:
                hold_reason = f"{reason}:validation_error:{ve}"
                self.pending_queue.mark_on_hold(pending_id, hold_reason)
                results.append(
                    PromotionResult(
                        note_text=note_text,
                        decision="invalid",
                        bucket=row.get("bucket"),
                        rationale=hold_reason,
                    )
                )
                continue
            except Exception as exc:
                hold_reason = f"{reason}:inputter_exception:{exc}"
                self.pending_queue.mark_on_hold(pending_id, hold_reason)
                results.append(
                    PromotionResult(
                        note_text=note_text,
                        decision="error",
                        bucket=row.get("bucket"),
                        rationale=hold_reason,
                    )
                )
                continue

            commit_reason = f"{reason}:{resolved_write.resolution_reason}"
            self.pending_queue.mark_committed(pending_id, event_id, commit_reason)
            results.append(
                PromotionResult(
                    note_text=note_text,
                    decision="accept",
                    event_id=event_id,
                    bucket=resolved_write.bucket,
                    rationale=commit_reason,
                )
            )

        return results

    def _drain_pending_after_commit(
        self,
        agent_id: str,
        max_rounds: int = 3,
        max_items_per_round: int = 25,
    ) -> None:
        if self.shared_memory is None:
            return

        for _ in range(max_rounds):
            retry_results = self.retry_pending(
                agent_id=agent_id,
                max_items=max_items_per_round,
                reason="canonical_change",
            )
            if not any(result.decision == "accept" for result in retry_results):
                break
