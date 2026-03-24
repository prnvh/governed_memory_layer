"""
benchmarks/trajectories/family_e.py

Family E — Cross-bucket coherence
What it tests: issues, decisions, results, learnings, constraints, and task
state should end in a coherent combined snapshot.

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
        "issue_slug": "staging_migration_blocker",
        "issue_open": "Deployment failed because a duplicate migration column already exists. The staging_migration_blocker is open.",
        "issue_resolved": "Migration state was reconciled and the staging_migration_blocker is resolved.",
        "decision_slug": "quarantine_migration_42",
        "decision_note": "Decision: quarantine migration 0042 from the main release path until its backfill check is verified.",
        "result_slug": "migration_rehearsal_result",
        "result_metric": "deploy_rehearsal_success",
        "result_value": "true",
        "learning_slug": "reconcile_partial_migrations",
        "learning_note": "Learning: partial database migrations must be reconciled before release retries.",
        "constraint_slug": "freeze_schema_rollout",
        "constraint_note": "Constraint: freeze new schema rollout while the migration reconciliation is active.",
        "task_id": "staging_release",
        "tool": "deploy",
    },
    "ml": {
        "issue_slug": "eval_contamination_issue",
        "issue_open": "Near-duplicate contamination was found between train and eval. The eval_contamination_issue is open.",
        "issue_resolved": "Removed the near-duplicates and the eval_contamination_issue is resolved.",
        "decision_slug": "dedup_before_benchmarking",
        "decision_note": "Decision: run train-vs-eval deduplication before every benchmark release.",
        "result_slug": "post_dedup_accuracy",
        "result_metric": "validation_accuracy",
        "result_value": "0.851",
        "learning_slug": "dedup_is_required",
        "learning_note": "Learning: benchmark metrics are inflated unless eval data is deduplicated against training data.",
        "constraint_slug": "freeze_eval_set",
        "constraint_note": "Constraint: freeze the current eval set until contamination checks complete.",
        "task_id": "benchmark_refresh",
        "tool": "eval",
    },
    "ops": {
        "issue_slug": "payments_latency_incident",
        "issue_open": "Payments p99 latency breached the SLO. The payments_latency_incident is open.",
        "issue_resolved": "The missing index was added and the payments_latency_incident is resolved.",
        "decision_slug": "add_latency_index_monitor",
        "decision_note": "Decision: add an index-health monitor for the payments query path.",
        "result_slug": "post_fix_p99",
        "result_metric": "p99_latency_ms",
        "result_value": "380",
        "learning_slug": "watch_high_cardinality_indexes",
        "learning_note": "Learning: high-cardinality query paths need explicit index coverage checks before traffic spikes.",
        "constraint_slug": "freeze_non_emergency_changes",
        "constraint_note": "Constraint: freeze non-emergency changes during incident mitigation.",
        "task_id": "incident_recovery",
        "tool": "monitoring",
    },
    "policy": {
        "issue_slug": "retention_control_gap",
        "issue_open": "The external audit found a retention_control_gap in the deletion workflow.",
        "issue_resolved": "The deletion workflow now enforces the approved retention period and the retention_control_gap is resolved.",
        "decision_slug": "centralize_retention_review",
        "decision_note": "Decision: centralize retention exception review under the governance committee.",
        "result_slug": "control_test_result",
        "result_metric": "control_test_passed",
        "result_value": "true",
        "learning_slug": "audit_controls_must_match_ops",
        "learning_note": "Learning: retention controls fail when policy text and operational workflows drift apart.",
        "constraint_slug": "freeze_exception_approvals",
        "constraint_note": "Constraint: freeze new retention exceptions while remediation is in progress.",
        "task_id": "audit_remediation",
        "tool": "policy_review",
    },
}


def _variant_one(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        tool_note(data["tool"], data["issue_open"]),
        agent_note("Task is now blocked."),
    ]
    if difficulty >= 2:
        notes.append(agent_note(data["decision_note"]))
    if difficulty >= 3:
        notes.extend(
            [
                tool_note(data["tool"], data["issue_resolved"]),
                agent_note(data["learning_note"]),
                agent_note("Task is now done."),
            ]
        )
    if difficulty == 4:
        notes.append(agent_note("Late correction: a stale blocker summary should not reopen the issue. The remediation task remains done."))
    return Trajectory(
        id=f"e{difficulty}_{domain}_01",
        description="Issue-driven workflow that expands from two buckets to a multi-bucket coherent state.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=True, match_by="target_id", checks={"status": "open" if difficulty == 1 else "open" if difficulty == 2 else "resolved"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "blocked" if difficulty < 3 else "done"}),
        ] + (
            [ExpectedOutcome(bucket="decisions", target_id=data["decision_slug"], present=True, match_by="target_id", checks={"status": "active"})]
            if difficulty >= 2
            else []
        ) + (
            [ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"statement": data["learning_note"].replace("Learning: ", ""), "status": "active"})]
            if difficulty >= 3
            else []
        ),
        forbidden_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=False, match_by="fields", checks={"status": "open"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=False, match_by="fields", checks={"status": "blocked"}),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("e", difficulty, domain, "issue_coherence"),
    )


def _variant_two(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(f"Constraint: {data['constraint_note'].replace('Constraint: ', '')}"),
        agent_note("Task is now in progress."),
    ]
    if difficulty >= 2:
        notes.append(agent_note(data["decision_note"]))
    if difficulty >= 3:
        notes.extend(
            [
                tool_note(data["tool"], f"Result: {data['result_metric']}={data['result_value']}."),
                agent_note("Task is now done."),
            ]
        )
    if difficulty == 4:
        notes.append(agent_note(f"Late correction: {data['constraint_slug']} was temporary and should now be invalidated. Keep the result and decision, and keep the task done."))
    return Trajectory(
        id=f"e{difficulty}_{domain}_02",
        description="Constraint-led workflow that must stay coherent with decision, result, and task state.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=True, match_by="target_id", checks={"status": "invalidated" if difficulty == 4 else "active"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress" if difficulty < 3 else "done"}),
        ] + (
            [ExpectedOutcome(bucket="decisions", target_id=data["decision_slug"], present=True, match_by="target_id", checks={"status": "active"})]
            if difficulty >= 2
            else []
        ) + (
            [ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_name": data["result_metric"], "metric_value": data["result_value"]})]
            if difficulty >= 3
            else []
        ),
        forbidden_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=False, match_by="fields", checks={"status": "active"}),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("e", difficulty, domain, "constraint_coherence"),
    )


def _variant_three(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        tool_note(data["tool"], data["issue_open"]),
        agent_note(data["decision_note"]),
    ]
    if difficulty >= 2:
        notes.append(agent_note(f"Constraint: {data['constraint_note'].replace('Constraint: ', '')}"))
    if difficulty >= 3:
        notes.extend(
            [
                tool_note(data["tool"], data["issue_resolved"]),
                tool_note(data["tool"], f"Result: {data['result_metric']}={data['result_value']}."),
                agent_note(data["learning_note"]),
                agent_note("Task is now done."),
            ]
        )
    if difficulty == 4:
        notes.extend(build_delay_notes(domain, difficulty, 3)[:2])
        notes.append(agent_note(f"Late correction: the issue remains resolved, the decision and result still stand, and {data['constraint_slug']} was temporary and should now be invalidated."))
    return Trajectory(
        id=f"e{difficulty}_{domain}_03",
        description="Full multi-bucket workflow with optional late correction that should revise only one bucket.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=True, match_by="target_id", checks={"status": "open" if difficulty < 3 else "resolved"}),
            ExpectedOutcome(bucket="decisions", target_id=data["decision_slug"], present=True, match_by="target_id", checks={"status": "active"}),
        ] + (
            [ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=True, match_by="target_id", checks={"status": "invalidated" if difficulty == 4 else "active"})]
            if difficulty >= 2
            else []
        ) + (
            [
                ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_name": data["result_metric"], "metric_value": data["result_value"]}),
                ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"statement": data["learning_note"].replace("Learning: ", ""), "status": "active"}),
                ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
            ]
            if difficulty >= 3
            else []
        ),
        forbidden_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=False, match_by="fields", checks={"status": "active"}),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("e", difficulty, domain, "multi_bucket_coherence"),
    )


ALL_TRAJECTORIES: list[Trajectory] = []

for _difficulty in range(1, 5):
    for _domain in ("software", "ml", "ops", "policy"):
        ALL_TRAJECTORIES.extend(
            [
                _variant_one(_domain, _difficulty),
                _variant_two(_domain, _difficulty),
                _variant_three(_domain, _difficulty),
            ]
        )
