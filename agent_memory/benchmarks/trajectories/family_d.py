"""
benchmarks/trajectories/family_d.py

Family D — Conflict handling / authoritative override
What it tests: conflicting later notes should invalidate or supersede earlier
authoritative state rather than leaving stale active state behind.

48 trajectories: 4 difficulties × 4 domains × 3 trajectories per cell.
"""

from benchmarks.trajectories.schema import ExpectedOutcome, Trajectory
from benchmarks.trajectories.family_common import (
    agent_note,
    build_delay_notes,
    make_tags,
    tool_note,
)


DOMAIN_DATA = {
    "software": {
        "decision_old_slug": "use_blue_green_release",
        "decision_old": "Decision: use blue-green release for the next checkout deployment.",
        "decision_new_slug": "use_canary_release",
        "decision_new": "Decision: use canary release instead because the rehearsal exposed rollback drift.",
        "decision_invalidate": "The use_blue_green_release decision is superseded by the canary plan.",
        "constraint_slug": "freeze_schema_changes",
        "constraint_text": "Constraint: freeze schema changes during this release hardening window.",
        "constraint_override": "A validated migration rehearsal completed successfully. The freeze_schema_changes constraint should be invalidated.",
        "task_id": "checkout_release",
        "task_open": "Checkout release work is in progress.",
        "task_done": "Checkout release work is done.",
        "task_blocked": "Checkout release work is blocked pending rollback verification.",
        "tool": "deploy",
    },
    "ml": {
        "decision_old_slug": "use_class_weights",
        "decision_old": "Decision: use class-weighted loss for this model family.",
        "decision_new_slug": "use_focal_loss",
        "decision_new": "Decision: switch to focal loss because the later ablation beat class weighting.",
        "decision_invalidate": "The use_class_weights decision is superseded by the focal loss result.",
        "constraint_slug": "freeze_batch_size_16",
        "constraint_text": "Constraint: keep batch size at 16 while training stays on the small-memory budget.",
        "constraint_override": "Training moved to a larger-memory budget. The freeze_batch_size_16 constraint should be invalidated.",
        "task_id": "model_eval",
        "task_open": "Model evaluation is in progress.",
        "task_done": "Model evaluation is done.",
        "task_blocked": "Model evaluation is blocked pending ablation results.",
        "tool": "eval",
    },
    "ops": {
        "decision_old_slug": "use_blue_green_failover",
        "decision_old": "Decision: use blue-green failover for the next maintenance window.",
        "decision_new_slug": "use_replica_promotion",
        "decision_new": "Decision: use replica promotion because the blue-green test exposed cutover risk.",
        "decision_invalidate": "The use_blue_green_failover decision is superseded by replica promotion.",
        "constraint_slug": "freeze_non_emergency_changes",
        "constraint_text": "Constraint: freeze non-emergency changes until the payments incident is stabilized.",
        "constraint_override": "The service has stabilized and the review is complete. The freeze_non_emergency_changes constraint should be invalidated.",
        "task_id": "incident_followup",
        "task_open": "Incident follow-up is in progress.",
        "task_done": "Incident follow-up is done.",
        "task_blocked": "Incident follow-up is blocked pending the latest cutover review.",
        "tool": "monitoring",
    },
    "policy": {
        "decision_old_slug": "centralize_exception_intake",
        "decision_old": "Decision: centralize policy exception intake through the governance desk.",
        "decision_new_slug": "product_led_exception_workflow",
        "decision_new": "Decision: move exception intake to a product-led workflow with governance checkpoints.",
        "decision_invalidate": "The centralize_exception_intake decision is superseded by the product-led workflow.",
        "constraint_slug": "require_dual_review",
        "constraint_text": "Constraint: require dual review on all exceptions while the audit is open.",
        "constraint_override": "The audit closed and the temporary requirement should end. The require_dual_review constraint must be invalidated.",
        "task_id": "policy_refresh",
        "task_open": "Policy refresh is in progress.",
        "task_done": "Policy refresh is done.",
        "task_blocked": "Policy refresh is blocked waiting on final governance sign-off.",
        "tool": "policy_review",
    },
}


def _decision_conflict(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["decision_old"]),
    ]
    if difficulty >= 2:
        notes.append(agent_note("There is some pressure to revisit that choice if later evidence changes the risk picture."))
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 1))
    if difficulty == 4:
        notes.append(agent_note("A stale note from yesterday still mentions the earlier choice, but it is not authoritative anymore."))
    notes.extend(
        [
            tool_note(data["tool"], data["decision_new"]),
            agent_note(data["decision_invalidate"]),
        ]
    )
    return Trajectory(
        id=f"d{difficulty}_{domain}_01",
        description="Later conflicting decision should supersede the earlier active decision.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=data["decision_old_slug"], present=True, match_by="target_id", checks={"status": "superseded"}),
            ExpectedOutcome(bucket="decisions", target_id=data["decision_new_slug"], present=True, match_by="target_id", checks={"status": "active"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=data["decision_old_slug"], present=False, match_by="fields", checks={"status": "active"}),
        ],
        agent_id="benchmark_agent",
        tags=make_tags("d", difficulty, domain, "decision_override"),
    )


def _constraint_conflict(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["constraint_text"]),
    ]
    if difficulty >= 2:
        notes.append(agent_note("Someone asked whether that rule is still necessary, but no valid override exists yet."))
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 2))
    notes.append(tool_note(data["tool"], data["constraint_override"]))
    if difficulty == 4:
        notes.append(agent_note("An older stale note still repeats the freeze, but it should not remain canonically active after the override."))
    return Trajectory(
        id=f"d{difficulty}_{domain}_02",
        description="Later authoritative evidence invalidates an earlier active constraint.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=True, match_by="target_id", checks={"status": "invalidated"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=False, match_by="fields", checks={"status": "active"}),
        ],
        agent_id="benchmark_agent",
        tags=make_tags("d", difficulty, domain, "constraint_override"),
    )


def _task_state_conflict(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["task_open"]),
    ]
    if difficulty >= 2:
        notes.append(agent_note("A temporary blocker appeared while the work was still progressing."))
    notes.append(agent_note(data["task_blocked"]))
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 3))
    if difficulty == 4:
        notes.append(agent_note("A stale operational summary still says the task is blocked, but a newer update follows."))
    notes.append(agent_note(data["task_done"]))
    return Trajectory(
        id=f"d{difficulty}_{domain}_03",
        description="Latest task state should replace stale earlier status values.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="task_state", target_id="", present=False, match_by="fields", checks={"status": "blocked"}),
        ],
        agent_id="benchmark_agent",
        tags=make_tags("d", difficulty, domain, "task_state_override"),
    )


ALL_TRAJECTORIES: list[Trajectory] = []

for _difficulty in range(1, 5):
    for _domain in ("software", "ml", "ops", "policy"):
        ALL_TRAJECTORIES.extend(
            [
                _decision_conflict(_domain, _difficulty),
                _constraint_conflict(_domain, _difficulty),
                _task_state_conflict(_domain, _difficulty),
            ]
        )
