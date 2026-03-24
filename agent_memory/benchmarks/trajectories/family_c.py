"""
benchmarks/trajectories/family_c.py

Family C — Duplicate avoidance / identity resolution
What it tests: repeated notes should bind to one canonical object rather than
creating duplicates.

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
        "aliases": ["the pandas error", "the eval import blocker", "that import issue"],
        "duplicate_slugs": ["pandas_error", "eval_import_blocker", "import_issue"],
        "competitor_slug": "numpy_version_mismatch",
        "competitor_note": "A teammate briefly mentioned a possible NumPy version mismatch in a legacy notebook, but this is only background context and should not open a second issue in this trajectory.",
        "decision_slug": "use_feature_flag_rollout",
        "decision_statement": "Decision: use feature-flag rollout for the payment retry fix.",
        "decision_aliases": ["the feature-flag plan", "that rollout decision", "the gated rollout choice"],
        "decision_duplicate_slugs": ["feature_flag_plan", "rollout_decision", "gated_rollout_choice"],
        "constraint_slug": "require_migration_backup",
        "constraint_text": "Constraint: require a verified database backup before any migration runs.",
        "constraint_aliases": ["the backup rule", "that migration guardrail", "the pre-migration backup requirement"],
        "constraint_duplicate_slugs": ["backup_rule", "migration_guardrail", "pre_migration_backup_requirement"],
        "tool": "run_tests",
    },
    "ml": {
        "issue_slug": "label_leakage_issue",
        "issue_title": "Label leakage issue",
        "aliases": ["the leakage bug", "that contaminated feature problem", "the train-set leak"],
        "duplicate_slugs": ["leakage_bug", "contaminated_feature_problem", "train_set_leak"],
        "competitor_slug": "class_imbalance_issue",
        "competitor_note": "Severe class imbalance in the validation split came up as a possible side concern, but this note is only contextual and should not open a second issue.",
        "decision_slug": "use_focal_loss",
        "decision_statement": "Decision: use focal loss for the current classifier family.",
        "decision_aliases": ["the focal-loss choice", "that loss-function decision", "the reweighting plan"],
        "decision_duplicate_slugs": ["focal_loss_choice", "loss_function_decision", "reweighting_plan"],
        "constraint_slug": "freeze_eval_seed",
        "constraint_text": "Constraint: freeze the evaluation seed at 42 for all benchmark comparisons.",
        "constraint_aliases": ["the fixed-seed rule", "that reproducibility guardrail", "the seed lock"],
        "constraint_duplicate_slugs": ["fixed_seed_rule", "reproducibility_guardrail", "seed_lock"],
        "tool": "data_validate",
    },
    "ops": {
        "issue_slug": "payments_latency_incident",
        "issue_title": "Payments latency incident",
        "aliases": ["the high-latency outage", "that payments slowdown", "the p99 breach"],
        "duplicate_slugs": ["high_latency_outage", "payments_slowdown", "p99_breach"],
        "competitor_slug": "reporting_queue_backlog",
        "competitor_note": "Someone mentioned a reporting queue backlog as surrounding context, but this note is not establishing a separate tracked issue.",
        "decision_slug": "promote_replica_failover",
        "decision_statement": "Decision: promote the replica directly for the next failover exercise.",
        "decision_aliases": ["the replica-promotion plan", "that failover choice", "the direct promotion decision"],
        "decision_duplicate_slugs": ["replica_promotion_plan", "failover_choice", "direct_promotion_decision"],
        "constraint_slug": "freeze_non_emergency_changes",
        "constraint_text": "Constraint: freeze non-emergency changes during the incident stabilization window.",
        "constraint_aliases": ["the change freeze", "that stabilization guardrail", "the emergency-only rule"],
        "constraint_duplicate_slugs": ["change_freeze", "stabilization_guardrail", "emergency_only_rule"],
        "tool": "monitoring",
    },
    "policy": {
        "issue_slug": "retention_control_gap",
        "issue_title": "Retention control gap",
        "aliases": ["the retention weakness", "that deletion-policy gap", "the document retention issue"],
        "duplicate_slugs": ["retention_weakness", "deletion_policy_gap", "document_retention_issue"],
        "competitor_slug": "approval_logging_gap",
        "competitor_note": "Approval logging was mentioned as another possible gap, but this note is only background context and should not open a second issue.",
        "decision_slug": "centralize_exception_intake",
        "decision_statement": "Decision: centralize policy exception intake through the governance desk.",
        "decision_aliases": ["the centralized intake plan", "that exception-routing decision", "the governance-desk workflow"],
        "decision_duplicate_slugs": ["centralized_intake_plan", "exception_routing_decision", "governance_desk_workflow"],
        "constraint_slug": "require_dual_review",
        "constraint_text": "Constraint: require dual review on policy exceptions while the audit is open.",
        "constraint_aliases": ["the dual-review rule", "that audit guardrail", "the exception approval lock"],
        "constraint_duplicate_slugs": ["dual_review_rule", "audit_guardrail", "exception_approval_lock"],
        "tool": "policy_review",
    },
}


def _alias_for(level: int, aliases: list[str], offset: int) -> str:
    if level == 1:
        return aliases[0]
    if level == 2:
        return aliases[offset % len(aliases)]
    if level == 3:
        return aliases[(offset + 1) % len(aliases)]
    return aliases[(offset + 2) % len(aliases)]


def _issue_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    alias = _alias_for(difficulty, data["aliases"], 1)
    notes = [
        tool_note(data["tool"], f"Detected {data['issue_title']}. This is the main blocking issue for the current thread."),
        agent_note(f"Tracking the same problem again under a paraphrase: {alias}."),
    ]
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 1))
    if difficulty == 4:
        notes.append(tool_note(data["tool"], data["competitor_note"]))
    notes.append(tool_note(data["tool"], f"Installed the fix and closed {alias}. The underlying {data['issue_slug']} is resolved."))
    return Trajectory(
        id=f"c{difficulty}_{domain}_01",
        description="One issue is mentioned several ways and must stay a single canonical row.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(
                bucket="issues",
                target_id="",
                present=True,
                match_by="fields",
                checks={"title": data["issue_title"], "status": "resolved"},
            ),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="issues", target_id=slug, present=False, match_by="target_id")
            for slug in data["duplicate_slugs"]
        ] + (
            [ExpectedOutcome(bucket="issues", target_id=data["competitor_slug"], present=False, match_by="target_id")]
            if difficulty == 4
            else []
        ),
        agent_id="benchmark_agent",
        tags=make_tags("c", difficulty, domain, "issue_identity_resolution"),
    )


def _decision_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    alias = _alias_for(difficulty, data["decision_aliases"], 2)
    notes = [
        agent_note(data["decision_statement"]),
        agent_note(f"Referred to the same active choice again as {alias}. This is not a second decision."),
    ]
    if difficulty >= 3:
        notes.extend(build_delay_notes(domain, difficulty, 2))
    notes.append(agent_note(f"{alias} remains the active decision for this run."))
    return Trajectory(
        id=f"c{difficulty}_{domain}_02",
        description="A single decision is restated through aliases and should not duplicate.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(
                bucket="decisions",
                target_id="",
                present=True,
                match_by="fields",
                checks={"statement": data["decision_statement"].replace("Decision: ", ""), "status": "active"},
            ),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="decisions", target_id=slug, present=False, match_by="target_id")
            for slug in data["decision_duplicate_slugs"]
        ],
        agent_id="benchmark_agent",
        tags=make_tags("c", difficulty, domain, "decision_identity_resolution"),
    )


def _constraint_trajectory(domain: str, difficulty: int) -> Trajectory:
    data = DOMAIN_DATA[domain]
    alias = _alias_for(difficulty, data["constraint_aliases"], 3)
    notes = [
        agent_note(data["constraint_text"]),
        agent_note(f"The same constraint is being referenced again as {alias}; do not create a second constraint row."),
    ]
    if difficulty >= 2:
        notes.extend(build_delay_notes(domain, difficulty, 3))
    if difficulty == 4:
        notes.append(agent_note(f"Separate requirement exists too, but {alias} still refers to the original {data['constraint_slug']} only."))
    notes.append(agent_note(f"{alias} remains active for the rest of this task."))
    return Trajectory(
        id=f"c{difficulty}_{domain}_03",
        description="A single constraint is referenced multiple ways and should stay one row.",
        notes=notes,
        expected_outcomes=[
            ExpectedOutcome(
                bucket="constraints",
                target_id="",
                present=True,
                match_by="fields",
                checks={"text": data["constraint_text"].replace("Constraint: ", ""), "status": "active"},
            ),
        ],
        forbidden_outcomes=[
            ExpectedOutcome(bucket="constraints", target_id=slug, present=False, match_by="target_id")
            for slug in data["constraint_duplicate_slugs"]
        ],
        agent_id="benchmark_agent",
        tags=make_tags("c", difficulty, domain, "constraint_identity_resolution"),
    )


ALL_TRAJECTORIES: list[Trajectory] = []

for _difficulty in range(1, 5):
    for _domain in ("software", "ml", "ops", "policy"):
        ALL_TRAJECTORIES.extend(
            [
                _issue_trajectory(_domain, _difficulty),
                _decision_trajectory(_domain, _difficulty),
                _constraint_trajectory(_domain, _difficulty),
            ]
        )
