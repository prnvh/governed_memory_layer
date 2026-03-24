"""
benchmarks/trajectories/schema.py

Defines the Trajectory dataclass — the unit of input for the benchmark harness.

A Trajectory is a sequence of notes representing what an agent would write
to its working memory over a single run. The harness feeds these notes through
the real promotion pipeline (Interpreter → Validator → Inputter) and the scorer
checks the resulting shared memory state against the trajectory's expected outcomes.

Design principle: trajectories are declarative. They describe inputs and expected
outputs without knowing anything about pipeline internals. The harness and scorer
own the execution and evaluation logic respectively.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TrajectoryNote:
    """
    A single note to be added to WorkingMemory before the pipeline runs.

    source distinguishes between agent reasoning ("agent") and high-signal
    tool output ("tool_result") — mirrors WorkingMemory.add_note() and
    add_tool_result_note() respectively.
    """
    text: str
    source: str = "agent"  # "agent" | "tool_result"
    tool_name: Optional[str] = None  # populated when source == "tool_result"


@dataclass
class ExpectedOutcome:
    """
    A single assertion about the shared memory state after a trajectory runs.

    The scorer checks each ExpectedOutcome against the canonical shared_* tables.

    Fields:
        bucket      — which shared_* table to check (plan, issues, constraints, etc.)
        target_id   — the PK to look up in that table (used when match_by="target_id")
                      set to "" when match_by="fields"
        present     — if True, the row must exist; if False, it must not exist
        checks      — optional field-level assertions: {field_name: expected_value}
                      only evaluated when present=True and the row is found
        match_by    — "target_id": look up by exact slug (default)
                      "fields": find any row in the bucket where all checks pass,
                      regardless of what slug the interpreter chose. Use this when
                      slug consistency is not the property being tested.

    Example — assert a specific slug was used (tests interpreter consistency):
        ExpectedOutcome(
            bucket="plan",
            target_id="main",
            present=True,
            match_by="target_id",
        )

    Example — assert a resolved issue exists without caring about slug:
        ExpectedOutcome(
            bucket="issues",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "resolved"},
        )

    Example — assert a noisy note was NOT promoted:
        ExpectedOutcome(
            bucket="issues",
            target_id="thinking_out_loud",
            present=False,
            match_by="target_id",
        )
    """
    bucket: str
    target_id: str
    present: bool = True
    checks: dict[str, Any] = field(default_factory=dict)
    match_by: str = "target_id"  # "target_id" | "fields"


@dataclass
class FaultInjectionConfig:
    """
    Declarative fault injection spec for Family F (replay/projection robustness).

    Carried by the Trajectory and read by a FaultInjectionHarness that wraps
    the Inputter to simulate projection failures at controlled points.

    Fields:
        fail_at_note_indices — zero-based indices into trajectory.notes at which
                               the view write should fail (ledger row still commits,
                               applied_successfully=0). E.g. [2, 5] fails the
                               view writes for notes 2 and 5.
        fail_mode            — "view_write_failure": SharedMemoryWriter raises,
                               Inputter catches, sets applied_successfully=0.
                               Default and only supported mode in V1.
        replay_and_verify    — if True, the harness should replay events_memory
                               after the run and verify the reconstructed canonical
                               state matches the expected_outcomes. Tests that the
                               event ledger is sufficient for full recovery.

    Usage: only set on Family F trajectories. Ignored by GovernedMemoryHarness.
    The FaultInjectionHarness reads this field and injects failures accordingly.
    """
    fail_at_note_indices: list[int] = field(default_factory=list)
    fail_mode: str = "view_write_failure"  # only supported mode in V1
    replay_and_verify: bool = True


@dataclass
class Trajectory:
    """
    A complete benchmark trajectory: notes in, expected shared memory state out.

    Fields:
        id                — unique identifier, snake_case
        description       — one sentence explaining what this trajectory tests
        agent_id          — agent identity used when running (affects source_agent in events)
        notes             — ordered sequence of notes to add to WorkingMemory
        expected_outcomes — positive assertions: rows the scorer must find after the run
        forbidden_outcomes — negative assertions: rows that must NOT exist after the run.
                             These are checked independently of expected_outcomes.
                             Use for noise-heavy trajectories (A3, A4, D4) where FP
                             detection is load-bearing and snapshot-diffing is insufficient.
                             Same ExpectedOutcome shape with present=False semantics;
                             the scorer treats any match as a FP and records it separately
                             from the FN count derived from expected_outcomes misses.
        tags              — labels for grouping/filtering:
                            family (a|b|c|d|e|f), difficulty (l1–l4),
                            domain (software|ml|ops|policy), dominant failure mode
        fault_injection   — Family F only. Declarative spec for controlled projection
                            failures. Ignored by GovernedMemoryHarness; read by
                            FaultInjectionHarness. None on all non-F trajectories.

    The harness feeds all notes into a single WorkingMemory instance and runs
    the promotion pipeline once (trigger="end_of_step") after all notes are added.
    This mirrors a single agent step where the agent has accumulated several
    observations before promotion is triggered.
    """
    id: str
    description: str
    notes: list[TrajectoryNote]
    expected_outcomes: list[ExpectedOutcome]
    forbidden_outcomes: list[ExpectedOutcome] = field(default_factory=list)
    agent_id: str = "benchmark_agent"
    tags: list[str] = field(default_factory=list)
    fault_injection: Optional[FaultInjectionConfig] = None