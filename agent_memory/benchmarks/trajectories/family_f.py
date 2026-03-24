"""
benchmarks/trajectories/family_f.py

Family F — Replay / projection robustness
What it tests: event ledger truth survives projection failures and canonical
state can be reconstructed by replay.

48 trajectories: 4 difficulties × 4 domains × 3 trajectories per cell.
"""

from benchmarks.trajectories.schema import (
    ExpectedOutcome,
    FaultInjectionConfig,
    Trajectory,
)
from benchmarks.trajectories.family_common import agent_note, build_delay_notes, make_tags, tool_note


DOMAIN_DATA = {
    "software": {
        "issue_slug": "staging_migration_blocker",
        "issue_open": "Deployment failed because a duplicate migration column already exists. The staging_migration_blocker is open.",
        "issue_resolved": "Migration state was reconciled manually. The staging_migration_blocker is resolved.",
        "constraint_slug": "freeze_schema_rollout",
        "constraint_text": "Constraint: freeze new schema rollout while migration reconciliation is active.",
        "constraint_lift": "The reconciliation finished. The freeze_schema_rollout constraint should be invalidated.",
        "decision_slug": "quarantine_migration_42",
        "decision_note": "Decision: quarantine migration 0042 from the main release path.",
        "task_id": "staging_release",
        "tool": "deploy",
    },
    "ml": {
        "issue_slug": "eval_contamination_issue",
        "issue_open": "Near-duplicate contamination was found between train and eval. The eval_contamination_issue is open.",
        "issue_resolved": "Removed the contaminated examples. The eval_contamination_issue is resolved.",
        "constraint_slug": "freeze_eval_set",
        "constraint_text": "Constraint: freeze the eval set until contamination checks complete.",
        "constraint_lift": "Contamination checks are complete. The freeze_eval_set constraint should be invalidated.",
        "decision_slug": "dedup_before_benchmarking",
        "decision_note": "Decision: run train-vs-eval deduplication before every benchmark release.",
        "task_id": "benchmark_refresh",
        "tool": "eval",
    },
    "ops": {
        "issue_slug": "payments_latency_incident",
        "issue_open": "Payments p99 latency breached the SLO. The payments_latency_incident is open.",
        "issue_resolved": "The missing index was added and the payments_latency_incident is resolved.",
        "constraint_slug": "freeze_non_emergency_changes",
        "constraint_text": "Constraint: freeze non-emergency changes during incident mitigation.",
        "constraint_lift": "Incident mitigation is complete. The freeze_non_emergency_changes constraint should be invalidated.",
        "decision_slug": "add_latency_index_monitor",
        "decision_note": "Decision: add an index-health monitor for the payments query path.",
        "task_id": "incident_recovery",
        "tool": "monitoring",
    },
    "policy": {
        "issue_slug": "retention_control_gap",
        "issue_open": "The external audit found a retention_control_gap in the deletion workflow.",
        "issue_resolved": "The deletion workflow now enforces the approved retention period. The retention_control_gap is resolved.",
        "constraint_slug": "freeze_exception_approvals",
        "constraint_text": "Constraint: freeze new retention exceptions while remediation is in progress.",
        "constraint_lift": "Remediation is complete. The freeze_exception_approvals constraint should be invalidated.",
        "decision_slug": "centralize_retention_review",
        "decision_note": "Decision: centralize retention exception review under the governance committee.",
        "task_id": "audit_remediation",
        "tool": "policy_review",
    },
}


def _single_failure(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        tool_note(data["tool"], data["issue_open"]),
        agent_note("Task is now blocked."),
    ]
    if difficulty >= 2:
        notes.extend(build_delay_notes(domain, difficulty, 1))
    notes.append(tool_note(data["tool"], data["issue_resolved"]))
    notes.append(agent_note("Task is now done."))
    return Trajectory(
        id=f"f{difficulty}_{domain}_01",
        description="One projection failure on an issue event should still be recoverable by replay.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=True, match_by="target_id", checks={"status": "resolved"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
        ],
        fault_injection=FaultInjectionConfig(
            fail_at_note_indices=[0],
            replay_and_verify=True,
        ),
        agent_id="benchmark_agent",
        tags=make_tags("f", difficulty, domain, "single_projection_failure"),
    )


def _repeated_failures(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["constraint_text"]),
    ]
    if difficulty >= 2:
        notes.extend(build_delay_notes(domain, difficulty, 2))
    notes.append(agent_note(data["constraint_lift"]))
    return Trajectory(
        id=f"f{difficulty}_{domain}_02",
        description="Repeated projection failures on the same bucket should still replay to the correct terminal state.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=True, match_by="target_id", checks={"status": "invalidated"}),
        ],
        fault_injection=FaultInjectionConfig(
            fail_at_note_indices=[0, len(notes) - 1] if difficulty >= 2 else [0],
            replay_and_verify=True,
        ),
        agent_id="benchmark_agent",
        tags=make_tags("f", difficulty, domain, "repeated_bucket_failures"),
    )


def _mixed_replay(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["decision_note"]),
        tool_note(data["tool"], data["issue_open"]),
    ]
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 3))
    notes.extend(
        [
            tool_note(data["tool"], data["issue_resolved"]),
            agent_note("Task is now done."),
        ]
    )
    return Trajectory(
        id=f"f{difficulty}_{domain}_03",
        description="Mixed success and failure events should replay into a coherent final snapshot.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=data["decision_slug"], present=True, match_by="target_id", checks={"status": "active"}),
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=True, match_by="target_id", checks={"status": "resolved"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
        ],
        fault_injection=FaultInjectionConfig(
            fail_at_note_indices=[1] if difficulty <= 2 else [1, len(notes) - 2],
            replay_and_verify=True,
        ),
        agent_id="benchmark_agent",
        tags=make_tags("f", difficulty, domain, "mixed_replay"),
    )


ALL_TRAJECTORIES: list[Trajectory] = []

for _difficulty in range(1, 5):
    for _domain in ("software", "ml", "ops", "policy"):
        ALL_TRAJECTORIES.extend(
            [
                _single_failure(_domain, _difficulty),
                _repeated_failures(_domain, _difficulty),
                _mixed_replay(_domain, _difficulty),
            ]
        )
