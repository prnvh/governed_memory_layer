"""
benchmarks/harness.py

Runs trajectories through a memory system and returns structured results
for the scorer to evaluate.

The harness is responsible for:
    - setting up a fresh isolated environment for each trajectory run
    - feeding trajectory notes into the system
    - capturing the shared memory snapshot after the run
    - recording per-note promotion outcomes and timing

The harness is NOT responsible for scoring. It returns raw HarnessResult
objects. The scorer evaluates them.

Design:
    BaseHarness defines the interface all system variants must implement.
    GovernedMemoryHarness is the first concrete implementation — the full
    governed pipeline (Interpreter → Validator → Inputter).

    Baselines (scratchpad, vector retrieval, running summary, no memory)
    will be additional BaseHarness subclasses with the same interface,
    enabling apples-to-apples comparison in run.py.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from memory.db.schema import init_db
from memory.db.connection import get_connection
from memory.interpreter import Interpreter
from memory.validator import Validator
from memory.shared_memory_writer import SharedMemoryWriter
from memory.inputter import Inputter
from memory.shared_memory import SharedMemory
from memory.working_memory import WorkingMemory
from memory.promotion import PromotionPipeline, PromotionResult

from benchmarks.trajectories.schema import Trajectory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HarnessResult — what every harness run produces
# ---------------------------------------------------------------------------

@dataclass
class NoteOutcome:
    """
    What happened to a single trajectory note during the promotion run.
    Mirrors PromotionResult but decoupled from the pipeline internals
    so baseline systems can produce compatible records.
    """
    note_text: str
    decision: str           # accept | reject | invalid | error | n/a
    bucket: Optional[str]   # set if accepted
    event_id: Optional[str] # set if written to events_memory
    rationale: str


@dataclass
class HarnessResult:
    """
    Full result of running one trajectory through one system.

    Fields:
        trajectory_id       — matches Trajectory.id
        system_name         — which system variant produced this result
        snapshot            — SharedMemory.snapshot() after the run
                              (or equivalent dict for baseline systems)
        note_outcomes       — per-note record of what happened
        events_written      — how many events landed in the ledger (0 for baselines
                              without a ledger)
        accepted_count      — notes accepted by the system
        rejected_count      — notes rejected by the system
        run_duration_seconds — wall time for the full run
        error               — set if the run itself failed (not a per-note failure)
    """
    trajectory_id: str
    system_name: str
    snapshot: dict
    note_outcomes: list[NoteOutcome]
    events_written: int
    accepted_count: int
    rejected_count: int
    run_duration_seconds: float
    error: Optional[str] = None

    def summary_lines(self) -> list[str]:
        lines = [
            f"System     : {self.system_name}",
            f"Trajectory : {self.trajectory_id}",
            f"Duration   : {self.run_duration_seconds:.2f}s",
            f"Accepted   : {self.accepted_count}",
            f"Rejected   : {self.rejected_count}",
            f"Events     : {self.events_written}",
        ]
        if self.error:
            lines.append(f"ERROR      : {self.error}")
        return lines


# ---------------------------------------------------------------------------
# BaseHarness — interface all system variants implement
# ---------------------------------------------------------------------------

class BaseHarness(ABC):
    """
    Abstract base for all system variants.
    Subclasses implement run_trajectory() with the same signature.
    """

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Short identifier for this system variant, e.g. 'governed', 'scratchpad'."""

    @abstractmethod
    def run_trajectory(self, trajectory: Trajectory) -> HarnessResult:
        """
        Run the full trajectory through this system.
        Each call must use a completely fresh isolated environment —
        no state bleeds between trajectory runs.
        Returns a HarnessResult.
        """


# ---------------------------------------------------------------------------
# GovernedMemoryHarness — the full governed pipeline
# ---------------------------------------------------------------------------

class GovernedMemoryHarness(BaseHarness):
    """
    Runs trajectories through the full governed memory pipeline:
        WorkingMemory → Interpreter → Validator → Inputter → SharedMemory

    Uses a fresh in-memory SQLite database for each trajectory run.
    Uses the real Interpreter (calls OpenAI API).
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model

    @property
    def system_name(self) -> str:
        return "governed"

    def run_trajectory(self, trajectory: Trajectory) -> HarnessResult:
        """
        1. Set up fresh in-memory DB + pipeline
        2. Add all trajectory notes to WorkingMemory
        3. Run promotion pipeline once (trigger="end_of_step")
        4. Snapshot SharedMemory
        5. Return HarnessResult
        """
        start = time.perf_counter()

        try:
            # Fresh isolated environment for this run
            conn = get_connection(":memory:")
            init_db(conn)

            interpreter = Interpreter(model=self.model)
            validator = Validator()
            writer = SharedMemoryWriter(conn)
            inputter = Inputter(conn, writer)
            shared_memory = SharedMemory(conn)
            pipeline = PromotionPipeline(interpreter, validator, inputter, shared_memory=shared_memory)

            # Feed all notes into working memory
            wm = WorkingMemory(
                agent_id=trajectory.agent_id,
                run_id=trajectory.id,
            )
            for note in trajectory.notes:
                if note.source == "tool_result" and note.tool_name:
                    wm.add_tool_result_note(note.tool_name, note.text)
                else:
                    wm.add_note(note.text, source=note.source)

            logger.info(
                "[harness] Running trajectory '%s' — %d notes",
                trajectory.id,
                len(trajectory.notes),
            )

            # Run the promotion pipeline once over all notes
            promotion_results: list[PromotionResult] = pipeline.run(
                wm, trigger="end_of_step"
            )

            # Snapshot current shared memory state
            snapshot = shared_memory.snapshot()

            # Count events written to the ledger
            events_written = conn.execute(
                "SELECT COUNT(*) FROM events_memory"
            ).fetchone()[0]

            conn.close()

        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.exception(
                "[harness] Trajectory '%s' failed: %s", trajectory.id, exc
            )
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

        # Convert PromotionResults to NoteOutcomes
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

        accepted_count = sum(1 for r in promotion_results if r.decision == "accept")
        rejected_count = sum(1 for r in promotion_results if r.decision == "reject")

        logger.info(
            "[harness] Done '%s' — accepted=%d rejected=%d events=%d duration=%.2fs",
            trajectory.id,
            accepted_count,
            rejected_count,
            events_written,
            elapsed,
        )

        return HarnessResult(
            trajectory_id=trajectory.id,
            system_name=self.system_name,
            snapshot=snapshot,
            note_outcomes=note_outcomes,
            events_written=events_written,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            run_duration_seconds=elapsed,
        )