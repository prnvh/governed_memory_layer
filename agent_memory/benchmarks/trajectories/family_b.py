"""
benchmarks/trajectories/family_b.py

Family B — Lifecycle transitions
What it tests: open → resolve, active → invalidate / supersede, and latest task
state replacement under varying reference difficulty.

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
        "issue_slug": "pandas_import_blocker",
        "issue_title": "Pandas import blocker",
        "issue_open": "Eval run failed with ModuleNotFoundError: No module named 'pandas'. The pandas import blocker is now open and it is blocking the release verification task.",
        "issue_resolve_exact": "Installed pandas into the active virtualenv and re-ran the eval suite. The pandas import blocker is resolved.",
        "issue_resolve_para": "The eval import failure is cleared now that the missing dependency was installed. That earlier blocker is no longer open.",
        "issue_competitor_slug": "numpy_version_mismatch",
        "issue_competitor": "There might also be a separate NumPy version mismatch in an older notebook, but this note is only flagging it as a possible side thread. Do not open or update any second issue from this note.",
        "constraint_slug": "freeze_schema_migrations",
        "constraint_text": "Do not ship new schema migrations while production schema drift remains unresolved.",
        "constraint_invalidate_exact": "Production schema drift was reconciled. The freeze_schema_migrations constraint no longer applies and should be invalidated.",
        "constraint_invalidate_para": "Now that the drift is gone, the earlier migration freeze can be lifted.",
        "constraint_competitor_slug": "freeze_frontend_rollout",
        "constraint_competitor": "A teammate wondered whether the frontend rollout freeze still matters here, but this is only an aside and not a new constraint to record.",
        "decision_slug": "nightly_cache_warmup",
        "decision_old": "Decision: use nightly cache warmup jobs before release verification.",
        "decision_new": "Decision: switch to on-demand cache warmup triggered only for affected services.",
        "decision_invalidate_exact": "The nightly_cache_warmup decision is superseded by the new on-demand warmup policy.",
        "decision_invalidate_para": "The earlier nightly warmup choice is no longer the active approach; the just-in-time policy replaces it.",
        "decision_competitor_slug": "nightly_db_snapshot",
        "decision_competitor": "Someone mentioned nightly database snapshots as a neighboring topic, but this note is not recording a separate decision for this trajectory.",
        "task_id": "release_readiness",
        "task_start": "Release readiness review is now in progress.",
        "task_end": "Release readiness review is done.",
        "tool": "run_tests",
    },
    "ml": {
        "issue_slug": "label_leakage_issue",
        "issue_title": "Label leakage issue",
        "issue_open": "Data audit found label leakage in the training features. The label_leakage_issue is open and blocks benchmark publication.",
        "issue_resolve_exact": "Removed the leaked feature columns and rebuilt the training set. The label_leakage_issue is resolved.",
        "issue_resolve_para": "The contamination in the feature set has been removed, so that earlier benchmarking blocker is closed.",
        "issue_competitor_slug": "class_imbalance_issue",
        "issue_competitor": "There may also be class imbalance in the validation split, but this is only a possible side concern and should not open a second issue in this trajectory.",
        "constraint_slug": "freeze_batch_size_16",
        "constraint_text": "Keep batch size at or below 16 while this experiment stays on the current A100 budget.",
        "constraint_invalidate_exact": "The run moved to a larger memory budget. The freeze_batch_size_16 constraint should be invalidated.",
        "constraint_invalidate_para": "Because the memory cap changed, the old batch-size limit no longer applies.",
        "constraint_competitor_slug": "freeze_eval_seed",
        "constraint_competitor": "The fixed evaluation seed came up as background context, but this note is not establishing a separate active constraint.",
        "decision_slug": "train_with_class_weights",
        "decision_old": "Decision: use class-weighted loss for all runs in this experiment family.",
        "decision_new": "Decision: switch to focal loss after the ablation outperformed class weights.",
        "decision_invalidate_exact": "The train_with_class_weights decision is superseded by the focal loss result.",
        "decision_invalidate_para": "The earlier class-weight choice is not the active plan anymore; focal loss replaces it.",
        "decision_competitor_slug": "use_mixed_precision",
        "decision_competitor": "Mixed precision was mentioned as related context, but this note does not set or restate a separate decision.",
        "task_id": "benchmark_publication",
        "task_start": "Benchmark publication prep is in progress.",
        "task_end": "Benchmark publication prep is done.",
        "tool": "data_validate",
    },
    "ops": {
        "issue_slug": "payments_latency_incident",
        "issue_title": "Payments latency incident",
        "issue_open": "p99 latency on the payments service breached the SLO. The payments_latency_incident is open and the on-call task is blocked.",
        "issue_resolve_exact": "Added the missing payments.transaction_id index and latency returned to normal. The payments_latency_incident is resolved.",
        "issue_resolve_para": "The high-latency outage is cleared now that the index fix is live. That earlier incident is closed.",
        "issue_competitor_slug": "reporting_queue_backlog",
        "issue_competitor": "People briefly mentioned a reporting queue backlog, but it is only background chatter here and should not become a second tracked issue.",
        "constraint_slug": "freeze_non_emergency_changes",
        "constraint_text": "Do not deploy non-emergency changes while the payments incident review is still open.",
        "constraint_invalidate_exact": "The incident review is complete. The freeze_non_emergency_changes constraint should be invalidated.",
        "constraint_invalidate_para": "Now that the review closed, the earlier deployment freeze can be lifted.",
        "constraint_competitor_slug": "freeze_failover_tests",
        "constraint_competitor": "Quarter-end traffic cautions came up in discussion, but this note is not creating a separate failover-test constraint.",
        "decision_slug": "use_blue_green_failover",
        "decision_old": "Decision: use blue-green failover for the next database maintenance window.",
        "decision_new": "Decision: switch to replica promotion because the blue-green rehearsal exposed cutover risk.",
        "decision_invalidate_exact": "The use_blue_green_failover decision is superseded by replica promotion.",
        "decision_invalidate_para": "The earlier blue-green plan is no longer active; replica promotion replaces it.",
        "decision_competitor_slug": "retain_pager_rotation",
        "decision_competitor": "The current pager rotation was mentioned for context, but this note is not asserting a separate active decision about it.",
        "task_id": "incident_review",
        "task_start": "Incident review is in progress.",
        "task_end": "Incident review is done.",
        "tool": "monitoring",
    },
    "policy": {
        "issue_slug": "retention_control_gap",
        "issue_title": "Retention control gap",
        "issue_open": "The audit found a retention_control_gap in the document deletion workflow. The compliance review is blocked until it is closed.",
        "issue_resolve_exact": "The deletion workflow now enforces the approved retention period. The retention_control_gap is resolved.",
        "issue_resolve_para": "The retention weakness has been corrected, so that earlier compliance blocker is now closed.",
        "issue_competitor_slug": "approval_logging_gap",
        "issue_competitor": "Approval logging also came up as a possible gap, but this note is only acknowledging the possibility and should not open a second issue.",
        "constraint_slug": "require_dual_review",
        "constraint_text": "Require dual review on all policy exceptions while the external audit remains open.",
        "constraint_invalidate_exact": "The external audit closed. The require_dual_review constraint should be invalidated.",
        "constraint_invalidate_para": "With the audit finished, the temporary dual-review rule no longer applies.",
        "constraint_competitor_slug": "require_legal_signoff",
        "constraint_competitor": "Cross-border legal signoff was mentioned as standing background policy, but this note is not adding a separate constraint for the trajectory.",
        "decision_slug": "centralize_exception_intake",
        "decision_old": "Decision: centralize all policy exception intake through the governance desk.",
        "decision_new": "Decision: move exception intake to a product-led workflow with governance approval checkpoints.",
        "decision_invalidate_exact": "The centralize_exception_intake decision is superseded by the product-led workflow.",
        "decision_invalidate_para": "The earlier governance-desk intake choice is no longer active; the new workflow replaces it.",
        "decision_competitor_slug": "retain_quarterly_review",
        "decision_competitor": "Quarterly review cadence was referenced as background governance context, but this note is not recording a separate active decision.",
        "task_id": "compliance_review",
        "task_start": "Compliance review is in progress.",
        "task_end": "Compliance review is done.",
        "tool": "policy_review",
    },
}


def _issue_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["task_start"]),
        tool_note(data["tool"], data["issue_open"]),
    ]
    if difficulty == 4:
        notes.append(tool_note(data["tool"], data["issue_competitor"]))
    notes.extend(build_delay_notes(domain, difficulty, 1))
    if difficulty in (1, 2):
        notes.append(tool_note(data["tool"], data["issue_resolve_exact"]))
    else:
        notes.append(tool_note(data["tool"], data["issue_resolve_para"]))
    notes.append(agent_note(data["task_end"]))
    return Trajectory(
        id=f"b{difficulty}_{domain}_01",
        description="Issue lifecycle with later resolution and latest task state replacement.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_slug"], present=True, match_by="target_id", checks={"status": "resolved"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=data["issue_competitor_slug"], present=False, match_by="target_id"),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("b", difficulty, domain, "issue_lifecycle"),
    )


def _constraint_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(f"Constraint: {data['constraint_text']}"),
    ]
    if difficulty == 4:
        notes.append(agent_note(f"Constraint: {data['constraint_competitor']}"))
    notes.extend(build_delay_notes(domain, difficulty, 2))
    if difficulty in (1, 2):
        notes.append(agent_note(data["constraint_invalidate_exact"]))
    else:
        notes.append(agent_note(data["constraint_invalidate_para"]))
    return Trajectory(
        id=f"b{difficulty}_{domain}_02",
        description="Constraint lifecycle with invalidation after the temporary condition ends.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_slug"], present=True, match_by="target_id", checks={"status": "invalidated"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=data["constraint_competitor_slug"], present=False, match_by="target_id"),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("b", difficulty, domain, "constraint_lifecycle"),
    )


def _decision_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    notes = [
        agent_note(data["task_start"]),
        agent_note(data["decision_old"]),
    ]
    if difficulty == 4:
        notes.append(agent_note(data["decision_competitor"]))
    notes.extend(build_delay_notes(domain, difficulty, 3))
    notes.append(agent_note(data["decision_new"]))
    if difficulty in (1, 2):
        notes.append(agent_note(data["decision_invalidate_exact"]))
    else:
        notes.append(agent_note(data["decision_invalidate_para"]))
    notes.append(agent_note(data["task_end"]))
    return Trajectory(
        id=f"b{difficulty}_{domain}_03",
        description="Decision supersession with latest task state only.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=data["decision_slug"], present=True, match_by="target_id", checks={"status": "superseded"}),
            ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=data["decision_competitor_slug"], present=False, match_by="target_id"),
        ] if difficulty == 4 else [],
        agent_id="benchmark_agent",
        tags=make_tags("b", difficulty, domain, "decision_supersession"),
    )


ALL_TRAJECTORIES: list[Trajectory] = []

for _difficulty in range(1, 5):
    for _domain in ("software", "ml", "ops", "policy"):
        ALL_TRAJECTORIES.extend(
            [
                _issue_trajectory(_domain, _difficulty),
                _constraint_trajectory(_domain, _difficulty),
                _decision_trajectory(_domain, _difficulty),
            ]
        )
