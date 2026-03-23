"""
benchmarks/trajectories/examples.py

Three concrete benchmark trajectories covering the three task families:

    1. current_state_tracking   — plan + issue lifecycle + noise rejection
    2. contradiction_and_update — plan supersession + decision invalidation
    3. learning_extraction      — issue resolution → reusable learning

Each trajectory has:
    - realistic note text that the real Interpreter should classify correctly
    - gold ExpectedOutcomes representing what SharedMemory.snapshot() should
      look like after a correct run

These are the ground truth for the scorer. They were authored by hand against
the bucket/operation contracts in interpreter.py and validator.py.

Notes on authoring:
    - Note text is written to be unambiguous for the Interpreter — clear signal,
      minimal noise. Harder trajectories (noisy, ambiguous) come in a later set.
    - target_id slugs match what a well-behaved Interpreter should produce.
      If the real Interpreter produces a different slug, the scorer will flag it
      as a miss — that is useful signal, not a bug in the trajectory.
    - ExpectedOutcome.checks only asserts fields that are load-bearing for the
      research claims (status, severity, category etc). It does not assert
      auto-generated fields like event_ids.
"""

from benchmarks.trajectories.schema import (
    Trajectory,
    TrajectoryNote,
    ExpectedOutcome,
)


# ===========================================================================
# Trajectory 1 — Current-state tracking
#
# Task family: can the system maintain correct current state through a sequence
# of updates including plan creation, issue lifecycle, and noise?
#
# What this tests:
#   - plan lands in shared_plan
#   - issue opens in shared_issues
#   - issue resolves (status flips to resolved)
#   - a noisy reasoning note does NOT get promoted
# ===========================================================================

TRAJECTORY_CURRENT_STATE_TRACKING = Trajectory(
    id="current_state_tracking",
    description=(
        "Agent sets a plan, encounters a blocking issue, resolves it, "
        "and produces a noisy internal note that should not be promoted."
    ),
    agent_id="benchmark_agent",
    tags=["current_state", "issue_lifecycle", "noise_rejection"],
    notes=[
        TrajectoryNote(
            text=(
                "The plan for this benchmark run is: "
                "Step 1 — install dependencies. "
                "Step 2 — run the evaluation suite. "
                "Step 3 — collect results and write summary."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Attempted to run the evaluation suite but hit an import error: "
                "ModuleNotFoundError: No module named 'pandas'. "
                "This is blocking step 2 — cannot proceed until resolved."
            ),
            source="tool_result",
            tool_name="run_eval",
        ),
        TrajectoryNote(
            text="I should think carefully about what the root cause might be here.",
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Installed pandas via pip. Re-ran the evaluation suite successfully. "
                "The pandas import error is now resolved."
            ),
            source="tool_result",
            tool_name="run_eval",
        ),
    ],
    expected_outcomes=[
        # Plan was set
        ExpectedOutcome(
            bucket="plan",
            target_id="main",
            present=True,
            checks={},
        ),
        # Issue was opened and resolved — match by field values, not slug.
        # The interpreter may choose any slug for this issue; what matters
        # is that exactly one resolved issue exists in the bucket.
        ExpectedOutcome(
            bucket="issues",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "resolved"},
        ),
        # The noisy internal reasoning note should NOT have been promoted
        # We can't assert a specific target_id for it since it was rejected,
        # but we assert that total issues count is 1 (checked in harness, not here).
        # What we CAN assert: no issue with a "thinking" slug exists.
        ExpectedOutcome(
            bucket="issues",
            target_id="think_carefully",
            present=False,
        ),
    ],
)


# ===========================================================================
# Trajectory 2 — Contradiction and update
#
# Task family: does the system correctly handle supersession — a plan revision
# that overwrites the old plan, and a decision that gets invalidated?
#
# What this tests:
#   - initial plan lands
#   - revised plan supersedes it (version increments, content updates)
#   - a decision is made
#   - the decision is later invalidated
#   - active decisions list is empty after invalidation
# ===========================================================================

TRAJECTORY_CONTRADICTION_AND_UPDATE = Trajectory(
    id="contradiction_and_update",
    description=(
        "Agent sets an initial plan, then revises it after discovering a constraint. "
        "A decision is made then invalidated when new information arrives."
    ),
    agent_id="benchmark_agent",
    tags=["contradiction", "plan_supersession", "decision_invalidation"],
    notes=[
        TrajectoryNote(
            text=(
                "Initial plan: use dataset A for the evaluation. "
                "Run baseline model, collect accuracy and latency metrics."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Decision: use dataset A for all evaluation runs in this session. "
                "Rationale: it is the standard benchmark dataset for this task."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Discovered that dataset A has a licensing restriction — "
                "it cannot be used for published results. "
                "Must switch to dataset B instead."
            ),
            source="tool_result",
            tool_name="check_license",
        ),
        TrajectoryNote(
            text=(
                "Revised plan: use dataset B for the evaluation instead of dataset A. "
                "Dataset A is off-limits due to licensing. "
                "All other steps remain the same."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "The earlier decision to use dataset A is now invalid — "
                "superseded by the licensing discovery. Dataset B is the correct choice."
            ),
            source="agent",
        ),
    ],
    expected_outcomes=[
        # Plan exists and was updated (we check presence, harness checks version=2)
        ExpectedOutcome(
            bucket="plan",
            target_id="main",
            present=True,
            checks={},
        ),
        # A decision was made then superseded — match by field values, not slug.
        # The interpreter may choose any slug; what matters is that a superseded
        # decision exists in the bucket after the invalidation note.
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "superseded"},
        ),
    ],
)


# ===========================================================================
# Trajectory 3 — Learning extraction
#
# Task family: after an issue is resolved, does the system correctly distil
# a reusable learning that persists in shared memory?
#
# What this tests:
#   - issue opens
#   - issue resolves
#   - a learning is extracted from the resolution
#   - the learning is present in shared_learnings with correct category
#   - task state reflects completion
# ===========================================================================

TRAJECTORY_LEARNING_EXTRACTION = Trajectory(
    id="learning_extraction",
    description=(
        "Agent encounters a dependency issue, resolves it, and extracts a "
        "reusable learning about pinning dependencies before evaluation runs."
    ),
    agent_id="benchmark_agent",
    tags=["learning_extraction", "issue_resolution", "task_state"],
    notes=[
        TrajectoryNote(
            text=(
                "Starting evaluation run for experiment exp_003. "
                "Task is now in progress."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Evaluation crashed immediately: ImportError on numpy. "
                "Dependencies were not pinned — numpy version mismatch between "
                "dev environment and eval environment."
            ),
            source="tool_result",
            tool_name="run_eval",
        ),
        TrajectoryNote(
            text=(
                "Fixed by pinning numpy==1.26.4 in requirements.txt and "
                "rebuilding the eval environment. Evaluation now runs successfully. "
                "The numpy version mismatch issue is resolved."
            ),
            source="tool_result",
            tool_name="run_eval",
        ),
        TrajectoryNote(
            text=(
                "Learning from this: always pin exact dependency versions in "
                "requirements.txt before starting an evaluation run. "
                "Version mismatches between environments cause silent failures "
                "that are expensive to debug. This applies to all future eval runs."
            ),
            source="agent",
        ),
        TrajectoryNote(
            text=(
                "Experiment exp_003 evaluation completed successfully. "
                "Task is now done."
            ),
            source="agent",
        ),
    ],
    expected_outcomes=[
        # Issue was opened and resolved — match by status, not slug
        ExpectedOutcome(
            bucket="issues",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "resolved"},
        ),
        # Learning was extracted and is active — match by status, not slug
        ExpectedOutcome(
            bucket="learnings",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "active"},
        ),
        # Task state reflects completion — match by status, not slug
        ExpectedOutcome(
            bucket="task_state",
            target_id="",
            present=True,
            match_by="fields",
            checks={"status": "done"},
        ),
    ],
)


# ===========================================================================
# Registry — all trajectories in one list for the harness to iterate over
# ===========================================================================

ALL_TRAJECTORIES: list[Trajectory] = [
    TRAJECTORY_CURRENT_STATE_TRACKING,
    TRAJECTORY_CONTRADICTION_AND_UPDATE,
    TRAJECTORY_LEARNING_EXTRACTION,
]