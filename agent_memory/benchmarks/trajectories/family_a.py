"""
benchmarks/trajectories/family_a.py

Family A — Promotion filtering
What it tests: can the system reject noise and only promote state-bearing notes?

64 trajectories: 4 difficulties × 4 domains × 4 trajectories per cell.

Difficulty ladder:
    L1 (A1): 20% noise — 8–12 notes,  ~2 noise notes (clear vague reasoning / transient output)
    L2 (A2): 40% noise — 12–18 notes, ~6 noise notes (paraphrases, restatements, hedged duplicates)
    L3 (A3): 60% noise — 18–28 notes, ~14 noise notes (conflicting candidates, speculation, near-misses)
    L4 (A4): 70% noise — 28–40 notes, ~22 adversarial notes (phrased like state but structurally invalid)

Domains: software | ml | ops | policy

Noise placement is deliberately varied across trajectories within each cell:
noise-early, noise-late, noise-interspersed, noise-clustered.

forbidden_outcomes become load-bearing at L3/L4 and are set accordingly.

PATCH NOTES (3 fixes vs original generation):
  a1_ml_04 — removed metric_name from result checks.
              'accuracy' is a valid synonym of 'validation_accuracy'; asserting
              the exact string was penalising a naming choice, not a correctness error.
  a4_ml_02 — same: removed metric_name check. 'p99 inference latency' (spaces) vs
              'p99_inference_latency' (underscores) is LLM formatting noise, not wrong.
  a4_ml_04 — same: 'primary task accuracy' vs 'primary_task_accuracy'.
  All other failures are genuine interpreter signal and left intact.
"""

from benchmarks.trajectories.schema import (
    Trajectory,
    TrajectoryNote,
    ExpectedOutcome,
)


# ===========================================================================
# A1 — L1 — SOFTWARE
# ===========================================================================

A1_SOFTWARE_01 = Trajectory(
    id="a1_software_01",
    description="Pandas import error opens and resolves during an eval run; one vague reasoning note is noise at the top.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:software", "noise:reasoning", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="I should think carefully about whether this is an environment issue or a code issue before diving in.",
            source="agent",
        ),
        TrajectoryNote(
            text="Plan: reproduce the import failure, identify root cause, fix, and verify the fix passes the full suite.",
            source="agent",
        ),
        TrajectoryNote(
            text="Ran test suite. Got: ModuleNotFoundError: No module named 'pandas'. Blocking all downstream eval steps.",
            source="tool_result",
            tool_name="run_tests",
        ),
        TrajectoryNote(
            text="Checked requirements.txt — pandas is listed but not installed in the current virtualenv. Installing now.",
            source="tool_result",
            tool_name="shell",
        ),
        TrajectoryNote(
            text="Re-ran the test suite after installing dependencies. All 142 tests pass. The pandas import error is resolved.",
            source="tool_result",
            tool_name="run_tests",
        ),
        TrajectoryNote(
            text="Learning: always verify virtualenv has all dependencies installed before starting a debug session. Prevents wasted time re-diagnosing environment issues.",
            source="agent",
        ),
        TrajectoryNote(
            text="Task is complete — root cause identified and fixed.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="think_carefully", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="learnings", target_id="think_carefully", present=False, match_by="target_id"),
    ],
)

A1_SOFTWARE_02 = Trajectory(
    id="a1_software_02",
    description="Flaky CI gate: constraint and quarantine decision set; one clean-pass monitoring output is noise in the middle.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:software", "noise:transient_tool_output", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Plan: audit CI config, identify the flaky test, quarantine it, and re-enable the PR gate on main.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: do not merge any PRs to main until CI is green and stable for at least 3 consecutive runs.",
            source="agent",
        ),
        TrajectoryNote(
            text="CI run completed on latest main. Exit code 0. Duration 2m14s. No failures.",
            source="tool_result",
            tool_name="ci_check",
        ),
        TrajectoryNote(
            text="Identified the flaky test: test_integration_db_connection. It relies on a live external service with no mock. Decision: quarantine it to the nightly suite only, remove from PR gate.",
            source="agent",
        ),
        TrajectoryNote(
            text="CI re-enabled on main after quarantine. Three consecutive green runs confirmed.",
            source="tool_result",
            tool_name="ci_check",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "do not merge any PRs to main until CI is green and stable for at least 3 consecutive runs.",
            },
        ),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "quarantine it to the nightly suite only, remove from PR gate.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "ci_duration"}),
        ExpectedOutcome(bucket="issues", target_id="ci_pass", present=False, match_by="target_id"),
        ExpectedOutcome(
            bucket="issues",
            target_id="",
            present=False,
            match_by="fields",
            checks={"title": "ci run completed on latest main", "status": "open"},
        ),
    ],
)

A1_SOFTWARE_03 = Trajectory(
    id="a1_software_03",
    description="Code review finds missing input sanitization; constraint and learning extracted; one speculative reference is noise at the end.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:software", "noise:speculation", "noise_placement:late"],
    notes=[
        TrajectoryNote(
            text="Reviewed PR #412. The file upload endpoint accepts user-supplied filenames with no sanitization before use in file operations.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: all user-supplied filenames must be sanitized before use in any file operation. No exceptions.",
            source="agent",
        ),
        TrajectoryNote(
            text="Sanitization added to the upload handler. PR updated. Re-review passed — constraint is now enforced.",
            source="tool_result",
            tool_name="code_review",
        ),
        TrajectoryNote(
            text="Learning: file operation endpoints must sanitize user-supplied path components. This should be a standard item in the code review checklist.",
            source="agent",
        ),
        TrajectoryNote(
            text="This might also connect to the path traversal incident from last quarter, but I'm not sure — probably unrelated.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "all user-supplied filenames must be sanitized before use in any file operation. No exceptions.",
            },
        ),
        ExpectedOutcome(
            bucket="learnings",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "file operation endpoints must sanitize user-supplied path components. This should be a standard item in the code review checklist.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="path_traversal", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="path_traversal_incident", present=False, match_by="target_id"),
        ExpectedOutcome(
            bucket="learnings",
            target_id="",
            present=False,
            match_by="fields",
            checks={"statement": "This might also connect to the path traversal incident from last quarter, but I'm not sure â€” probably unrelated.", "status": "active"},
        ),
    ],
)

A1_SOFTWARE_04 = Trajectory(
    id="a1_software_04",
    description="Staging deployment blocked by a duplicate migration column; issue opens unresolved; one internal diagnostic musing is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:software", "noise:internal_musing", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Starting deployment to staging environment for v2.5.0.",
            source="agent",
        ),
        TrajectoryNote(
            text="Deployment failed. Migration step errored: ERROR: column 'user_preferences' of relation 'users' already exists.",
            source="tool_result",
            tool_name="deploy",
        ),
        TrajectoryNote(
            text="I need to understand why the migration was written without an IF NOT EXISTS guard. Need to trace the migration history.",
            source="agent",
        ),
        TrajectoryNote(
            text="Root cause confirmed: migration 0042 was partially applied in a previous failed deployment and never rolled back. Column exists in DB but migration table does not reflect it.",
            source="tool_result",
            tool_name="db_inspect",
        ),
        TrajectoryNote(
            text="Cannot proceed — deployment is blocked until migration state is reconciled manually by the DBA team.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "open"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "blocked"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="migration_history", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="migration_history", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A1 — L1 — ML
# ===========================================================================

A1_ML_01 = Trajectory(
    id="a1_ml_01",
    description="Experiment setup with plan and GPU memory constraint; one speculative note about mixed precision is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ml", "noise:speculation", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Plan for exp_007: fine-tune BERT-base on MNLI, evaluate on dev set, record accuracy and macro-F1.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: batch size must not exceed 16. A100 instance has 40GB VRAM; model + optimizer state consumes ~35GB at batch size 16.",
            source="agent",
        ),
        TrajectoryNote(
            text="I wonder if we could squeeze a larger batch size with mixed precision training. Might revisit later.",
            source="agent",
        ),
        TrajectoryNote(
            text="Environment check passed: CUDA available, 40GB VRAM confirmed, all dependencies installed.",
            source="tool_result",
            tool_name="env_check",
        ),
        TrajectoryNote(
            text="Exp_007 is now in progress.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="mixed_precision", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="mixed_precision", present=False, match_by="target_id"),
    ],
)

A1_ML_02 = Trajectory(
    id="a1_ml_02",
    description="Training run completes; result and learning extracted; one GPU telemetry note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ml", "noise:transient_tool_output", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="Training started. GPU utilization: 94%. ETA: 4h 22m.",
            source="tool_result",
            tool_name="train",
        ),
        TrajectoryNote(
            text="Training run for exp_007 complete. Final val accuracy: 0.843. Baseline from prior run: 0.812.",
            source="tool_result",
            tool_name="train",
        ),
        TrajectoryNote(
            text="Early stopping triggered at epoch 8 of 20 — val loss plateaued for 3 consecutive epochs.",
            source="tool_result",
            tool_name="train",
        ),
        TrajectoryNote(
            text="Learning: for this dataset and model size, early stopping at patience=3 is sufficient. Training beyond epoch 8 does not improve val accuracy.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_name": "validation_accuracy"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "gpu_utilization"}),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "training_eta"}),
    ],
)

A1_ML_03 = Trajectory(
    id="a1_ml_03",
    description="Class imbalance issue found during data validation and resolved via class weighting; one deliberation note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ml", "noise:deliberation", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Running data validation on the training split for exp_008.",
            source="agent",
        ),
        TrajectoryNote(
            text="Data validation complete. Class distribution: negative=82%, positive=18%. This imbalance will bias the model toward the majority class.",
            source="tool_result",
            tool_name="data_validate",
        ),
        TrajectoryNote(
            text="There are a few ways to handle this — oversampling, undersampling, class weights. Need to pick one.",
            source="agent",
        ),
        TrajectoryNote(
            text="Applied class weighting in the loss function: positive_weight=4.56 (inverse class frequency). Class imbalance issue is now addressed.",
            source="tool_result",
            tool_name="train",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="oversampling", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="undersampling", present=False, match_by="target_id"),
    ],
)

# PATCH: removed checks={"metric_name": "validation_accuracy"} → checks={}
# 'accuracy' is a valid synonym; asserting the exact string was penalising
# a naming choice, not a correctness failure.
A1_ML_04 = Trajectory(
    id="a1_ml_04",
    description="LR sweep finds best learning rate; decision and result logged; one intermediate checkpoint note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ml", "noise:intermediate_checkpoint", "noise_placement:late"],
    notes=[
        TrajectoryNote(
            text="Running LR sweep for exp_009: candidates [1e-5, 3e-5, 5e-5, 1e-4].",
            source="agent",
        ),
        TrajectoryNote(
            text="Sweep complete. LR=1e-5: 0.791. LR=3e-5: 0.834. LR=5e-5: 0.829. LR=1e-4: 0.801.",
            source="tool_result",
            tool_name="lr_sweep",
        ),
        TrajectoryNote(
            text="Decision: use LR=3e-5 for all subsequent runs of this model family. Consistently highest val accuracy across the sweep.",
            source="agent",
        ),
        TrajectoryNote(
            text="Result for exp_009: best val accuracy 0.834 at LR=3e-5.",
            source="agent",
        ),
        TrajectoryNote(
            text="Mid-sweep checkpoint at LR=3e-5 epoch 4: val_acc=0.812. Still training at time of note.",
            source="tool_result",
            tool_name="lr_sweep",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "use LR=3e-5 for all subsequent runs of this model family.",
            },
        ),
        # PATCHED: checks={} — metric_name string is a naming choice, not correctness signal
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_value": "0.834"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "checkpoint_accuracy"}),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_value": "0.812"}),
    ],
)


# ===========================================================================
# A1 — L1 — OPS
# ===========================================================================

A1_OPS_01 = Trajectory(
    id="a1_ops_01",
    description="Payments service latency incident: issue opens and resolves after index added; one within-SLA p95 reading is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ops", "noise:transient_tool_output", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="Monitoring alert: p99 latency on payments service exceeded 2000ms for 5 consecutive minutes. SLA is 2000ms.",
            source="tool_result",
            tool_name="monitoring",
        ),
        TrajectoryNote(
            text="Current metrics — p95: 850ms (within SLA). p99: 2340ms (SLA breach).",
            source="tool_result",
            tool_name="metrics",
        ),
        TrajectoryNote(
            text="Root cause: missing index on payments.transaction_id. Full table scans on all high-cardinality queries.",
            source="tool_result",
            tool_name="db_analyze",
        ),
        TrajectoryNote(
            text="Index created. p99 latency now 380ms. SLA restored. Payments latency issue is resolved.",
            source="tool_result",
            tool_name="monitoring",
        ),
        TrajectoryNote(
            text="Incident closed. Task complete.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "p95_latency"}),
        ExpectedOutcome(bucket="issues", target_id="p95_latency", present=False, match_by="target_id"),
    ],
)

A1_OPS_02 = Trajectory(
    id="a1_ops_02",
    description="Sprint planning: plan and capacity constraint set; one rough estimate note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ops", "noise:rough_estimate", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Plan for sprint 24: deliver user notification service, complete API rate limiting, fix top 3 support tickets.",
            source="agent",
        ),
        TrajectoryNote(
            text="Rough estimate: notifications ~5 days, rate limiting ~3 days, tickets ~2 days. Might be tight given capacity.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: maximum capacity this sprint is 8 engineer-days — one team member is on leave for the full week.",
            source="agent",
        ),
        TrajectoryNote(
            text="Sprint 24 kicked off. Task is now in progress.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="rough_estimate", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="sprint_estimate", present=False, match_by="target_id"),
    ],
)

A1_OPS_03 = Trajectory(
    id="a1_ops_03",
    description="Production deployment scheduled around freeze window; constraint and decision set; one readiness ping is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ops", "noise:status_ping", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Constraint: no production deployments between Friday 17:00 and Monday 09:00. Change freeze window per operations policy.",
            source="agent",
        ),
        TrajectoryNote(
            text="Pre-flight readiness check complete. All checks passed.",
            source="tool_result",
            tool_name="deploy_check",
        ),
        TrajectoryNote(
            text="Decision: schedule v2.4.1 release for Tuesday 10:00 to clear the weekend freeze window and allow Monday QA sign-off.",
            source="agent",
        ),
        TrajectoryNote(
            text="v2.4.1 deployed successfully at Tuesday 10:14. No rollback needed.",
            source="tool_result",
            tool_name="deploy",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "no production deployments between Friday 17:00 and Monday 09:00. Change freeze window per operations policy.",
            },
        ),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "schedule v2.4.1 release for Tuesday 10:00 to clear the weekend freeze window and allow Monday QA sign-off.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "preflight_check"}),
        ExpectedOutcome(
            bucket="results",
            target_id="",
            present=False,
            match_by="fields",
            checks={"metric_value": "passed"},
        ),
    ],
)

A1_OPS_04 = Trajectory(
    id="a1_ops_04",
    description="On-call rotation decision and learning from a prior coverage gap; one bare acknowledgment note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:ops", "noise:acknowledgment", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="Noted.",
            source="agent",
        ),
        TrajectoryNote(
            text="Decision: rotate on-call responsibility weekly between three engineers. No engineer on-call more than one week per month.",
            source="agent",
        ),
        TrajectoryNote(
            text="Learning: the Q3 incident response delay was caused by a single engineer on-call for three consecutive weeks without backup. The rotation policy prevents this recurrence.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "rotate on-call responsibility weekly between three engineers. No engineer on-call more than one week per month.",
            },
        ),
        ExpectedOutcome(
            bucket="learnings",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "the Q3 incident response delay was caused by a single engineer on-call for three consecutive weeks without backup. The rotation policy prevents this recurrence.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="noted", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="noted", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="", present=False, match_by="fields", checks={"statement": "Noted.", "status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=False, match_by="fields", checks={"statement": "Noted.", "status": "active"}),
    ],
)


# ===========================================================================
# A1 — L1 — POLICY
# ===========================================================================

A1_POLICY_01 = Trajectory(
    id="a1_policy_01",
    description="GDPR audit finds over-long data retention; constraint set, issue resolved; one background history note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:policy", "noise:background_context", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="GDPR audit finding: user data retention logs kept for 7 years. GDPR Article 5(1)(e) requires data not be kept longer than necessary.",
            source="tool_result",
            tool_name="audit",
        ),
        TrajectoryNote(
            text="GDPR has been in effect since May 2018. Our DPA was last reviewed in 2021 and covers all EU data subjects.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: user data retention logs must not exceed 3 years, per legal counsel guidance issued today.",
            source="agent",
        ),
        TrajectoryNote(
            text="Retention policy updated. Automated deletion job scheduled for records older than 3 years. GDPR finding is remediated and resolved.",
            source="tool_result",
            tool_name="policy_update",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="dpa_review", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="gdpr_history", present=False, match_by="target_id"),
    ],
)

A1_POLICY_02 = Trajectory(
    id="a1_policy_02",
    description="Security review mandates MFA; constraint and TOTP decision set; one admin housekeeping note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:policy", "noise:administrative", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="Security review board meeting concluded. Minutes filed.",
            source="agent",
        ),
        TrajectoryNote(
            text="Constraint: all internal admin portals must enforce MFA by end of Q2. This is a mandatory security requirement.",
            source="agent",
        ),
        TrajectoryNote(
            text="Decision: use TOTP-based MFA (Google Authenticator / Authy) rather than SMS MFA, due to known SIM-swapping vulnerabilities.",
            source="agent",
        ),
        TrajectoryNote(
            text="Policy documentation updated. Engineering teams notified.",
            source="tool_result",
            tool_name="policy_publish",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "all internal admin portals must enforce MFA by end of Q2. This is a mandatory security requirement.",
            },
        ),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "use TOTP-based MFA rather than SMS MFA.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="task_state", target_id="minutes_filed", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="minutes_filed", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="", present=False, match_by="fields", checks={"statement": "Security review board meeting concluded. Minutes filed.", "status": "active"}),
    ],
)

A1_POLICY_03 = Trajectory(
    id="a1_policy_03",
    description="Access audit finds privilege creep; learning extracted; one lookup-in-progress note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:policy", "noise:lookup_action", "noise_placement:early"],
    notes=[
        TrajectoryNote(
            text="Checking current role assignments for the data engineering team.",
            source="agent",
        ),
        TrajectoryNote(
            text="Access audit complete: 6 of 12 data engineering accounts have production write access but only require read access for their current role.",
            source="tool_result",
            tool_name="access_audit",
        ),
        TrajectoryNote(
            text="Production write access revoked for the 6 over-privileged accounts. Principle of least privilege now enforced.",
            source="tool_result",
            tool_name="access_update",
        ),
        TrajectoryNote(
            text="Learning: quarterly access audits are necessary to catch privilege creep. Ad-hoc access grants accumulate over time without formal review cycles.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="learnings",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "quarterly access audits are necessary to catch privilege creep. Ad-hoc access grants accumulate over time without formal review cycles.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="task_state", target_id="checking_roles", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="checking_roles", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="learnings", target_id="", present=False, match_by="fields", checks={"statement": "Checking current role assignments for the data engineering team.", "status": "active"}),
    ],
)

A1_POLICY_04 = Trajectory(
    id="a1_policy_04",
    description="Vendor compliance check finds missing DPA; issue opens and task blocked; one background context note is noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l1", "domain:policy", "noise:background_context", "noise_placement:middle"],
    notes=[
        TrajectoryNote(
            text="Initiating vendor security review for third-party analytics provider.",
            source="agent",
        ),
        TrajectoryNote(
            text="We have used this vendor since 2020. They process EU personal data on our behalf under a legacy agreement.",
            source="agent",
        ),
        TrajectoryNote(
            text="Compliance check failed: no Data Processing Agreement (DPA) on file. GDPR Article 28 requires a signed DPA before a processor handles personal data.",
            source="tool_result",
            tool_name="compliance_check",
        ),
        TrajectoryNote(
            text="Cannot proceed with vendor renewal until DPA is signed. Task is blocked pending legal team.",
            source="agent",
        ),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "open"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "blocked"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="legacy_agreement", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="vendor_history", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A2 — L2 — SOFTWARE
# ===========================================================================

A2_SOFTWARE_01 = Trajectory(
    id="a2_software_01",
    description="Memory leak investigation: issue opens and constraint set; ~6 noise notes include paraphrases and intermediate diagnostics.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:software", "noise:paraphrase", "noise:intermediate"],
    notes=[
        TrajectoryNote(text="Starting memory investigation for the worker service. Heap usage has been growing over time.", source="agent"),
        TrajectoryNote(text="The worker service seems to be using more memory than it should. Worth investigating.", source="agent"),
        TrajectoryNote(text="Profiler output: heap is growing ~8MB per 1000 requests. Growth is linear, consistent with a leak.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="So the heap is growing by about 8MB per 1000 requests, which does suggest a memory leak.", source="agent"),
        TrajectoryNote(text="Narrowing down the leak source. Checking the request handler.", source="agent"),
        TrajectoryNote(text="Request handler looks clean. Checking connection pool.", source="agent"),
        TrajectoryNote(text="Found it: the database connection pool is creating new connections on every request but never releasing them. This is the memory leak.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="The root cause is that connections are never being released — they accumulate over the lifetime of the worker.", source="agent"),
        TrajectoryNote(text="Constraint: the connection pool must release connections after each request. Using context managers or explicit close calls is required.", source="agent"),
        TrajectoryNote(text="Fix applied: connection pool now uses context managers. Testing in progress.", source="tool_result", tool_name="shell"),
        TrajectoryNote(text="Heap growth rate is now 0 after fix. Memory leak confirmed resolved.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="So the memory leak issue has been fixed. The connection pool fix resolved it.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=False, match_by="fields", checks={"title": "heap growing", "status": "open"}),
        ExpectedOutcome(bucket="issues", target_id="heap_growth", present=False, match_by="target_id"),
    ],
)

A2_SOFTWARE_02 = Trajectory(
    id="a2_software_02",
    description="Auth token expiry bug: issue opened, decision made on TTL; noise includes hedged observations and a redundant status note.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:software", "noise:hedged_observation", "noise:redundant_status"],
    notes=[
        TrajectoryNote(text="User reports: session expires after 5 minutes even when 'remember me' is checked. Expected TTL is 30 days.", source="tool_result", tool_name="bug_report"),
        TrajectoryNote(text="This could be a TTL misconfiguration or a cookie flag issue. Not sure yet.", source="agent"),
        TrajectoryNote(text="Checked the session config. TTL for remember_me tokens is set to 300 seconds — should be 30 days (2592000 seconds).", source="tool_result", tool_name="config_read"),
        TrajectoryNote(text="The TTL is set to 300 seconds which is definitely wrong for a 30-day remember-me session.", source="agent"),
        TrajectoryNote(text="So the problem is clearly a misconfigured TTL value in the session config.", source="agent"),
        TrajectoryNote(text="Decision: set remember_me token TTL to 2592000 seconds (30 days) and add a config validation test to prevent future regressions.", source="agent"),
        TrajectoryNote(text="Config updated. Deployed to staging. Remember-me sessions now persist for 30 days as expected. Auth token expiry bug is resolved.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="Auth token expiry issue has been resolved by the TTL config fix.", source="agent"),
        TrajectoryNote(text="So we fixed the session expiry problem. The TTL update resolved everything.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="cookie_flag", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="ttl_wrong", present=False, match_by="target_id"),
    ],
)

A2_SOFTWARE_03 = Trajectory(
    id="a2_software_03",
    description="Low test coverage on the payments module: plan and learning set; noise includes progress pings and redundant restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:software", "noise:progress_ping", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Plan: audit test coverage on the payments module, identify untested paths, add unit tests for the top 5 critical paths.", source="agent"),
        TrajectoryNote(text="Running coverage analysis on the payments module.", source="agent"),
        TrajectoryNote(text="Coverage analysis done. Payments module: 34% line coverage. Critical paths around refund and dispute handling have zero tests.", source="tool_result", tool_name="coverage"),
        TrajectoryNote(text="34% is very low. The refund and dispute paths being uncovered is a significant risk.", source="agent"),
        TrajectoryNote(text="Writing tests for the refund path.", source="agent"),
        TrajectoryNote(text="Refund path tests complete: 8 new tests added.", source="tool_result", tool_name="test_run"),
        TrajectoryNote(text="Writing tests for the dispute handling path.", source="agent"),
        TrajectoryNote(text="Dispute path tests complete: 6 new tests added. All pass.", source="tool_result", tool_name="test_run"),
        TrajectoryNote(text="Coverage analysis re-run. Payments module now at 71% coverage.", source="tool_result", tool_name="coverage"),
        TrajectoryNote(text="So coverage went from 34% to 71%, which is a good improvement.", source="agent"),
        TrajectoryNote(text="Learning: critical financial paths (refund, dispute) must reach 80% unit test coverage before being considered shippable. Add to the PR checklist.", source="agent"),
        TrajectoryNote(text="Task complete. Coverage improved and learning captured.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "line_coverage_before"}),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "coverage_improved"}),
    ],
)

A2_SOFTWARE_04 = Trajectory(
    id="a2_software_04",
    description="Webpack to Vite migration: plan and constraint set; noise includes multiple thinking and process notes.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:software", "noise:process_narration"],
    notes=[
        TrajectoryNote(text="Starting the build system migration from Webpack to Vite.", source="agent"),
        TrajectoryNote(text="I should think through what plugins we currently use in Webpack and whether they have Vite equivalents.", source="agent"),
        TrajectoryNote(text="Plan: audit Webpack plugin dependencies, map them to Vite equivalents, migrate config, run full build and test suite.", source="agent"),
        TrajectoryNote(text="Let me look through the webpack.config.js to catalog all plugins.", source="agent"),
        TrajectoryNote(text="Webpack config audit complete: 7 plugins in use. 5 have direct Vite equivalents. 2 (webpack-bundle-analyzer, dll-plugin) require manual migration.", source="tool_result", tool_name="config_audit"),
        TrajectoryNote(text="So we have 7 plugins total and 2 of them need manual work. That's manageable.", source="agent"),
        TrajectoryNote(text="Constraint: the migration must not break the existing source map generation — it is required for production error tracking.", source="agent"),
        TrajectoryNote(text="Working through the plugin migrations one by one.", source="agent"),
        TrajectoryNote(text="All 5 direct-equivalent plugins migrated. Starting the two manual ones.", source="agent"),
        TrajectoryNote(text="Bundle analyzer and DLL plugin successfully replaced with Vite equivalents. Full build passes. Source maps confirmed present.", source="tool_result", tool_name="build"),
        TrajectoryNote(text="Migration is done. The build works and source maps are preserved.", source="agent"),
        TrajectoryNote(text="Task complete. Vite migration successful.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="plugin_audit", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="manageable", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A2 — L2 — ML
# ===========================================================================

A2_ML_01 = Trajectory(
    id="a2_ml_01",
    description="Overfitting detected mid-training; constraint and decision set; noise includes intermediate epoch logs and restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ml", "noise:intermediate_epoch", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Training exp_012. Epoch 3/15: train_loss=0.41, val_loss=0.44. Normal so far.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="Epoch 6/15: train_loss=0.29, val_loss=0.51. Gap is widening — possible overfitting.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="The validation loss is going up while training loss is going down. That's overfitting.", source="agent"),
        TrajectoryNote(text="Epoch 9/15: train_loss=0.18, val_loss=0.63. Confirmed overfitting. Training diverging from validation.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="So the gap between train_loss=0.18 and val_loss=0.63 at epoch 9 confirms we're overfitting badly.", source="agent"),
        TrajectoryNote(text="Stopping training early. Overfitting is severe enough that continuing will only make the validation performance worse.", source="agent"),
        TrajectoryNote(text="Constraint: for this model architecture and dataset, training must not exceed 6 epochs. Beyond epoch 6, overfitting dominates.", source="agent"),
        TrajectoryNote(text="Decision: add dropout=0.3 to all attention layers in the next training run to regularize.", source="agent"),
        TrajectoryNote(text="So the plan is: add dropout and cap training at 6 epochs.", source="agent"),
        TrajectoryNote(text="Re-training with dropout=0.3 and epoch cap=6. Val loss stable at 0.47 through epoch 6.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="Result for exp_012 final run: val_loss=0.47, val_accuracy=0.861.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_name": "val_accuracy"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "train_loss_epoch3"}),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "train_loss_epoch6"}),
        ExpectedOutcome(bucket="issues", target_id="overfitting_confirmed", present=False, match_by="target_id"),
    ],
)

A2_ML_02 = Trajectory(
    id="a2_ml_02",
    description="Feature selection decision for a tabular model; ~6 noise notes are restatements and hedging.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ml", "noise:hedging", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Running feature importance analysis on the 42-feature tabular dataset for exp_015.", source="agent"),
        TrajectoryNote(text="Feature importance scores computed. Top 10 features account for 89% of the model's predictive power.", source="tool_result", tool_name="feature_analysis"),
        TrajectoryNote(text="So the top 10 features are responsible for most of the predictive signal.", source="agent"),
        TrajectoryNote(text="The remaining 32 features contribute about 11% combined, which might not be worth the added dimensionality.", source="agent"),
        TrajectoryNote(text="It seems like reducing to 10 features might be a good idea, though there could be edge cases where the others help.", source="agent"),
        TrajectoryNote(text="Ran ablation with 10-feature vs 42-feature model. 10-feature: val_AUC=0.891. 42-feature: val_AUC=0.893.", source="tool_result", tool_name="ablation"),
        TrajectoryNote(text="The difference is only 0.002 AUC, which is essentially noise given the dataset size.", source="agent"),
        TrajectoryNote(text="So the 42-feature model is only 0.002 AUC better, which is negligible.", source="agent"),
        TrajectoryNote(text="Decision: use top 10 features only for all runs in this project. The 0.002 AUC difference does not justify 32 extra features in production.", source="agent"),
        TrajectoryNote(text="Result for exp_015 feature ablation: 10-feature model val_AUC=0.891.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "use top 10 features only for all runs in this project. The 0.002 AUC difference does not justify 32 extra features in production.",
            },
        ),
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={"metric_name": "val_auc"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="might_be_good_idea", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="edge_cases", present=False, match_by="target_id"),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=False,
            match_by="fields",
            checks={
                "statement": "It seems like reducing to 10 features might be a good idea, though there could be edge cases where the others help.",
                "status": "active",
            },
        ),
    ],
)

A2_ML_03 = Trajectory(
    id="a2_ml_03",
    description="Data drift detection for a production model; issue opened and constraint set; noise includes monitoring pings and restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ml", "noise:monitoring_ping", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Daily drift check completed. PSI score: 0.08. Within normal range.", source="tool_result", tool_name="drift_monitor"),
        TrajectoryNote(text="Daily drift check completed. PSI score: 0.11. Slightly elevated but within threshold.", source="tool_result", tool_name="drift_monitor"),
        TrajectoryNote(text="Daily drift check completed. PSI score: 0.28. Threshold is 0.20. Significant feature distribution shift detected on 'account_age_days'.", source="tool_result", tool_name="drift_monitor"),
        TrajectoryNote(text="The PSI jumped to 0.28 which is above our 0.20 threshold. That's a real drift signal.", source="agent"),
        TrajectoryNote(text="So account_age_days is drifting. This is probably because we expanded to a new market segment last month.", source="agent"),
        TrajectoryNote(text="Constraint: if PSI exceeds 0.20 on any top-10 feature, model must be retrained before the next scheduled deployment.", source="agent"),
        TrajectoryNote(text="The drift is significant enough that we need to retrain. The model was trained on a different distribution.", source="agent"),
        TrajectoryNote(text="Retraining initiated with data from the past 90 days including the new market segment.", source="agent"),
        TrajectoryNote(text="Retraining complete. New model PSI on account_age_days: 0.07. Data drift issue is resolved.", source="tool_result", tool_name="drift_monitor"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "psi_score_0.08"}),
        ExpectedOutcome(bucket="issues", target_id="psi_0_11", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="distribution_shift", present=False, match_by="target_id"),
    ],
)

A2_ML_04 = Trajectory(
    id="a2_ml_04",
    description="GPU OOM crash during training; constraint and fix decision made; noise includes multiple redundant crash echoes.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ml", "noise:redundant_error_echo"],
    notes=[
        TrajectoryNote(text="Training crashed. CUDA OOM: tried to allocate 3.2GB, only 1.8GB available.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="Training failed again. Same OOM error. CUDA out of memory on forward pass.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="The training is OOM-ing. We need to reduce memory usage somehow.", source="agent"),
        TrajectoryNote(text="The OOM is happening because the batch size is too large for the available VRAM.", source="agent"),
        TrajectoryNote(text="Constraint: batch size for this model on this GPU must not exceed 8. The model requires 2.1GB at batch size 8, within the 4GB available.", source="agent"),
        TrajectoryNote(text="Decision: reduce batch size to 8 and use gradient accumulation over 4 steps to maintain effective batch size of 32.", source="agent"),
        TrajectoryNote(text="Training restarted at batch size 8. Epoch 1 completed without OOM.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="So the OOM error is now fixed with batch size 8.", source="agent"),
        TrajectoryNote(text="Training completed successfully. OOM issue resolved.", source="tool_result", tool_name="train"),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "batch size for this model on this GPU must not exceed 8. The model requires 2.1GB at batch size 8, within the 4GB available.",
            },
        ),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "reduce batch size to 8 and use gradient accumulation over 4 steps to maintain effective batch size of 32.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=False, match_by="fields", checks={"title": "training failed again", "status": "open"}),
        ExpectedOutcome(bucket="issues", target_id="oom_again", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="learnings", target_id="", present=False, match_by="fields", checks={"statement": "The training is OOM-ing. We need to reduce memory usage somehow.", "status": "active"}),
    ],
)


# ===========================================================================
# A2 — L2 — OPS
# ===========================================================================

A2_OPS_01 = Trajectory(
    id="a2_ops_01",
    description="Auto-scaling failure under load; issue opened, constraint and decision set; noise includes status pings and restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ops", "noise:status_ping", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Load test initiated. Ramping to 500 concurrent users over 10 minutes.", source="agent"),
        TrajectoryNote(text="At 200 users: response time p99=340ms. Normal.", source="tool_result", tool_name="load_test"),
        TrajectoryNote(text="At 350 users: response time p99=1240ms. Auto-scaling should have triggered by now.", source="tool_result", tool_name="load_test"),
        TrajectoryNote(text="Auto-scaling has not triggered despite exceeding the CPU threshold. Something is wrong with the scaling policy.", source="agent"),
        TrajectoryNote(text="Auto-scaling is clearly broken — the CPU is high but no new instances are being provisioned.", source="agent"),
        TrajectoryNote(text="Root cause found: the IAM role for the auto-scaling group is missing ec2:RunInstances permission. Scale-out requests are silently failing.", source="tool_result", tool_name="cloudwatch"),
        TrajectoryNote(text="So the scaling wasn't working because of a missing IAM permission for ec2:RunInstances.", source="agent"),
        TrajectoryNote(text="Constraint: the auto-scaling IAM role must include ec2:RunInstances, ec2:DescribeInstances, and ec2:TerminateInstances.", source="agent"),
        TrajectoryNote(text="Decision: run monthly IAM permission audits against the auto-scaling policy to prevent silent permission drift.", source="agent"),
        TrajectoryNote(text="IAM permission added. Auto-scaling verified at 500 users — 2 new instances provisioned correctly. Issue resolved.", source="tool_result", tool_name="load_test"),
        TrajectoryNote(text="The auto-scaling is working now. The IAM fix resolved it.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "p99_at_200_users"}),
        ExpectedOutcome(bucket="issues", target_id="scaling_clearly_broken", present=False, match_by="target_id"),
    ],
)

A2_OPS_02 = Trajectory(
    id="a2_ops_02",
    description="On-call handoff: plan and constraint set; noise includes context-setting notes and process narration.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ops", "noise:context_narration"],
    notes=[
        TrajectoryNote(text="Beginning on-call handoff for the infrastructure team.", source="agent"),
        TrajectoryNote(text="Current team size is 4 engineers. We've been covering on-call in pairs since Q2.", source="agent"),
        TrajectoryNote(text="The previous on-call rotation had some coverage gaps. I'm reviewing those now.", source="agent"),
        TrajectoryNote(text="Coverage gap identified: two incidents last month had response times over 45 minutes because both on-call engineers were unavailable simultaneously.", source="tool_result", tool_name="incident_review"),
        TrajectoryNote(text="So the problem is that the on-call pairing isn't ensuring at least one person is always reachable.", source="agent"),
        TrajectoryNote(text="Plan for this handoff period: establish a primary/secondary on-call structure so there is always one actively monitoring engineer and one backup.", source="agent"),
        TrajectoryNote(text="Constraint: at least one on-call engineer must respond to P1 incidents within 15 minutes, 24/7.", source="agent"),
        TrajectoryNote(text="The 15-minute SLA for P1 incidents is important — it's what the SLA with customers requires.", source="agent"),
        TrajectoryNote(text="Handoff schedule published. Primary/secondary pairs assigned for the next 4 weeks.", source="tool_result", tool_name="schedule_publish"),
        TrajectoryNote(text="Handoff complete. The new structure is in place.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "at least one on-call engineer must respond to P1 incidents within 15 minutes, 24/7.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="coverage_gap_review", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="sla_context", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="", present=False, match_by="fields", checks={"title": "coverage gap identified", "status": "open"}),
    ],
)

A2_OPS_03 = Trajectory(
    id="a2_ops_03",
    description="Release rollback due to error rate spike; issue opened and decision made; noise includes repeated error rate readings.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ops", "noise:repeated_metric"],
    notes=[
        TrajectoryNote(text="Release v3.1.0 deployed to production at 14:00.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="Error rate at 14:05: 0.3%. Normal baseline.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="Error rate at 14:10: 2.1%. Elevated.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="Error rate at 14:15: 4.7%. Significantly above baseline of 0.3%.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="The error rate is clearly spiking after the release. Now at 4.7% vs 0.3% baseline.", source="agent"),
        TrajectoryNote(text="Error rate at 14:20: 5.2%. Still climbing.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="Rolling back v3.1.0. Error rate is 5.2% and still climbing — not acceptable.", source="agent"),
        TrajectoryNote(text="Decision: v3.1.0 must not be re-deployed until the root cause of the error rate spike is identified and fixed.", source="agent"),
        TrajectoryNote(text="Rollback to v3.0.9 complete. Error rate returned to 0.3%. Issue resolved.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="So the rollback fixed the error rate. Issue is resolved.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "error_rate_2_1"}),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "error_rate_baseline"}),
    ],
)

A2_OPS_04 = Trajectory(
    id="a2_ops_04",
    description="Cost optimization review; decision made on reserved instances; noise includes cost narration and deliberation notes.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:ops", "noise:deliberation", "noise:cost_narration"],
    notes=[
        TrajectoryNote(text="Monthly AWS cost review. Current spend: $42,000/month.", source="tool_result", tool_name="cost_report"),
        TrajectoryNote(text="EC2 spend is $28,000 of the $42,000 total. That's the biggest line item.", source="agent"),
        TrajectoryNote(text="Looking at EC2 utilization. 18 of 24 instances have been running continuously for over 6 months.", source="tool_result", tool_name="cost_report"),
        TrajectoryNote(text="18 long-running instances means we're probably overpaying for on-demand pricing.", source="agent"),
        TrajectoryNote(text="Reserved instances would be cheaper for consistently running workloads. Might save 30-40%.", source="agent"),
        TrajectoryNote(text="Reserved instance analysis: converting 18 on-demand instances to 1-year reserved would save ~$9,800/month.", source="tool_result", tool_name="cost_report"),
        TrajectoryNote(text="So $9,800/month savings is significant. That's about 35% reduction on the EC2 line.", source="agent"),
        TrajectoryNote(text="Decision: convert the 18 long-running EC2 instances to 1-year reserved instances. Expected savings: $9,800/month.", source="agent"),
        TrajectoryNote(text="Reserved instance purchase approved by finance. Conversion scheduled.", source="tool_result", tool_name="aws_console"),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "convert the 18 long-running EC2 instances to 1-year reserved instances. Expected savings: $9,800/month.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="might_save", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="results", target_id="", present=False, match_by="fields", checks={"metric_name": "monthly_aws_spend"}),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=False,
            match_by="fields",
            checks={
                "statement": "Reserved instances would be cheaper for consistently running workloads. Might save 30-40%.",
                "status": "active",
            },
        ),
    ],
)


# ===========================================================================
# A2 — L2 — POLICY
# ===========================================================================

A2_POLICY_01 = Trajectory(
    id="a2_policy_01",
    description="SOC 2 audit prep: plan and constraints set; noise includes process narration, restatements, and administrative pings.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:policy", "noise:process_narration", "noise:restatement"],
    notes=[
        TrajectoryNote(text="Beginning SOC 2 Type II audit preparation for the Q4 audit window.", source="agent"),
        TrajectoryNote(text="SOC 2 Type II covers a 6-month observation period. Our window starts November 1.", source="agent"),
        TrajectoryNote(text="Reviewing the prior year's audit findings to identify persistent gaps.", source="agent"),
        TrajectoryNote(text="Prior audit gap review complete. Two recurring findings: (1) access review not documented quarterly, (2) change management approvals missing for 14% of changes.", source="tool_result", tool_name="audit_review"),
        TrajectoryNote(text="So we have two recurring gaps from last year — access review documentation and change management approvals.", source="agent"),
        TrajectoryNote(text="Plan: close both recurring gaps before November 1. Implement quarterly access review process and enforce approval gates in the change management workflow.", source="agent"),
        TrajectoryNote(text="Constraint: all production changes must have documented approval from a second engineer before deployment. No exceptions starting November 1.", source="agent"),
        TrajectoryNote(text="The approval gate constraint is critical — it directly addresses the 14% undocumented changes finding.", source="agent"),
        TrajectoryNote(text="Constraint: access reviews must be completed and documented by the last business day of each quarter.", source="agent"),
        TrajectoryNote(text="Both constraints are now documented and being communicated to engineering leads.", source="agent"),
        TrajectoryNote(text="Audit prep task is now in progress. First milestone is change management tooling by October 15.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="audit_window", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="learnings", target_id="approval_gate_critical", present=False, match_by="target_id"),
    ],
)

A2_POLICY_02 = Trajectory(
    id="a2_policy_02",
    description="Third-party vendor risk assessment; decision made on acceptable risk tier; noise includes assessment narration and restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:policy", "noise:assessment_narration"],
    notes=[
        TrajectoryNote(text="Initiating risk assessment for new CRM vendor (Salesforce replacement candidate).", source="agent"),
        TrajectoryNote(text="Requesting SOC 2 Type II report and DPA from the vendor.", source="agent"),
        TrajectoryNote(text="SOC 2 report received. Covers period Jan-Dec 2023. Zero qualified opinions.", source="tool_result", tool_name="vendor_review"),
        TrajectoryNote(text="The vendor has a clean SOC 2. That's the first box checked.", source="agent"),
        TrajectoryNote(text="DPA received. Standard EU SCCs included. Data residency: EU-West region only.", source="tool_result", tool_name="vendor_review"),
        TrajectoryNote(text="Data residency is EU-West only, which aligns with our GDPR obligations.", source="agent"),
        TrajectoryNote(text="Penetration test summary received. Last test: March 2024. No critical or high findings outstanding.", source="tool_result", tool_name="vendor_review"),
        TrajectoryNote(text="Clean pentest results from March 2024. No outstanding criticals or highs.", source="agent"),
        TrajectoryNote(text="Decision: classify this vendor as Tier 2 (standard risk). Full security review required annually. No further blocking items.", source="agent"),
        TrajectoryNote(text="Vendor approved for procurement. Risk assessment complete.", source="tool_result", tool_name="vendor_review"),
        TrajectoryNote(text="So the vendor assessment is done and they're approved at Tier 2.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "classify this vendor as Tier 2 (standard risk). Full security review required annually. No further blocking items.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="soc2_clean", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="data_residency_eu", present=False, match_by="target_id"),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=False,
            match_by="fields",
            checks={"statement": "So the vendor assessment is done and they're approved at Tier 2.", "status": "active"},
        ),
    ],
)

A2_POLICY_03 = Trajectory(
    id="a2_policy_03",
    description="Employee data access incident: issue opened and learning extracted; noise includes investigation narration and restatements.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:policy", "noise:investigation_narration"],
    notes=[
        TrajectoryNote(text="Investigating an anomalous access event: a sales engineer queried the HR salary table directly.", source="agent"),
        TrajectoryNote(text="Looking into the DB permission setup for the sales engineering role.", source="agent"),
        TrajectoryNote(text="DB permission audit: the sales engineering role was granted SELECT on all tables as part of a bulk permission grant in January. This included the HR tables.", source="tool_result", tool_name="db_audit"),
        TrajectoryNote(text="So the bulk permission grant in January gave sales engineers access to HR tables by mistake.", source="agent"),
        TrajectoryNote(text="The access was unintentional — the bulk grant was a shortcut that bypassed the principle of least privilege.", source="agent"),
        TrajectoryNote(text="The underlying issue is that the bulk grant bypassed access controls that should have been applied per-table.", source="agent"),
        TrajectoryNote(text="Revoking SELECT on HR tables from all non-HR roles. Audit confirmed: HR table access removed for 23 affected accounts.", source="tool_result", tool_name="db_audit"),
        TrajectoryNote(text="Access to HR tables has been restricted. The inappropriate access incident is now resolved.", source="agent"),
        TrajectoryNote(text="Learning: bulk permission grants must be reviewed at the table level before being applied. Any grant covering sensitive tables (HR, finance, legal) requires explicit approval from the data owner.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="bulk_grant_shortcut", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="underlying_issue", present=False, match_by="target_id"),
    ],
)

A2_POLICY_04 = Trajectory(
    id="a2_policy_04",
    description="Cookie consent policy update for PECR compliance; constraint set and decision made; noise includes legal context narration.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l2", "domain:policy", "noise:legal_context"],
    notes=[
        TrajectoryNote(text="Reviewing our cookie consent implementation against PECR 2003 and the ICO's updated guidance.", source="agent"),
        TrajectoryNote(text="PECR was enacted in 2003 and amended in 2011. It requires informed consent for non-essential cookies.", source="agent"),
        TrajectoryNote(text="The ICO updated its enforcement stance in 2023 — it now actively fines sites that use pre-ticked consent boxes.", source="agent"),
        TrajectoryNote(text="Current implementation audit: our consent banner uses pre-ticked analytics cookies by default. This is non-compliant.", source="tool_result", tool_name="compliance_audit"),
        TrajectoryNote(text="So our banner is pre-ticking analytics cookies, which the ICO now actively enforces against.", source="agent"),
        TrajectoryNote(text="Constraint: all non-essential cookies must be opt-in only. No pre-ticked checkboxes. No cookies set before explicit consent.", source="agent"),
        TrajectoryNote(text="Decision: rebuild the consent banner using an opt-in-only architecture. Deadline: 30 days from today.", source="agent"),
        TrajectoryNote(text="The 30-day deadline is important because we have a scheduled ICO renewal check coming.", source="agent"),
        TrajectoryNote(text="Engineering ticket created. Banner rebuild is in progress.", source="tool_result", tool_name="ticketing"),
    ],
    expected_outcomes=[
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "text": "all non-essential cookies must be opt-in only. No pre-ticked checkboxes. No cookies set before explicit consent.",
            },
        ),
        ExpectedOutcome(
            bucket="decisions",
            target_id="",
            present=True,
            match_by="fields",
            checks={
                "status": "active",
                "statement": "rebuild the consent banner using an opt-in-only architecture. Deadline: 30 days from today.",
            },
        ),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="pecr_2003", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="ico_enforcement", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="ico_renewal_check", present=False, match_by="target_id"),
        ExpectedOutcome(
            bucket="constraints",
            target_id="",
            present=False,
            match_by="fields",
            checks={"text": "PECR was enacted in 2003 and amended in 2011. It requires informed consent for non-essential cookies.", "status": "active"},
        ),
    ],
)


# ===========================================================================
# A3 — L3 — SOFTWARE
# ===========================================================================

A3_SOFTWARE_01 = Trajectory(
    id="a3_software_01",
    description="Performance regression: two competing hypotheses debated at length; one root cause confirmed; constraint and decision set amid heavy noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:software", "noise:conflicting_hypothesis"],
    notes=[
        TrajectoryNote(text="Users reporting the dashboard page is slow. Anecdotally 5–10 seconds to load.", source="tool_result", tool_name="support_ticket"),
        TrajectoryNote(text="This could be a database query issue or it could be the rendering layer. Hard to say without profiling.", source="agent"),
        TrajectoryNote(text="Running a quick profiling pass on the dashboard endpoint.", source="agent"),
        TrajectoryNote(text="Profiler output: total response time 8.4s. DB query time: 6.1s. Render time: 2.3s.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="So the DB is taking 6.1s, which is the dominant cost. But the rendering is also 2.3s which seems high.", source="agent"),
        TrajectoryNote(text="Maybe the rendering is the real issue? 2.3s to render a dashboard seems excessive.", source="agent"),
        TrajectoryNote(text="Checking the DB query: it's a join across 4 tables with no index on the foreign key in the largest table.", source="tool_result", tool_name="db_explain"),
        TrajectoryNote(text="The missing index on the FK is a clear problem. But is it the only problem?", source="agent"),
        TrajectoryNote(text="Render profiling: the 2.3s render time is due to synchronous API calls inside the component tree. Each widget calls the API independently.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="So there are two separate issues: the missing DB index and the synchronous API calls in the render.", source="agent"),
        TrajectoryNote(text="Actually, looking more carefully: the synchronous API calls ARE the dashboard loading the same data that the DB query is serving. If we fix the DB query, the API calls speed up too.", source="agent"),
        TrajectoryNote(text="So maybe it's all the same root cause after all. The missing DB index causes slow API responses which causes slow rendering.", source="agent"),
        TrajectoryNote(text="Let me verify: with the index added in a test environment, the render time dropped to 0.4s. Confirmed: the missing index is the root cause of both.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="Constraint: all foreign key columns in tables with more than 10,000 rows must have indexes. This will be enforced in the migration linter.", source="agent"),
        TrajectoryNote(text="Decision: add a migration linter rule to fail any migration that adds an unindexed FK on a large table.", source="agent"),
        TrajectoryNote(text="Index added in production. Dashboard load time now 0.8s. Performance regression is resolved.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="So the render time being 2.3s earlier was a symptom of the same root cause, not a separate issue.", source="agent"),
        TrajectoryNote(text="Task complete. Index added, linter rule in progress.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="render_time", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="synchronous_api_calls", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="hard_to_say", present=False, match_by="target_id"),
    ],
)

A3_SOFTWARE_02 = Trajectory(
    id="a3_software_02",
    description="Intermittent 500 errors in production: many conflicting theories circulate before one constraint and one issue land.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:software", "noise:conflicting_theory"],
    notes=[
        TrajectoryNote(text="Support escalation: users getting intermittent 500 errors on the checkout endpoint. Rate roughly 0.4% of requests.", source="tool_result", tool_name="support_ticket"),
        TrajectoryNote(text="0.4% error rate on checkout is serious. Could be a db connection issue, could be a timeout, could be a bug in the new discount logic.", source="agent"),
        TrajectoryNote(text="Checking the error logs for patterns.", source="agent"),
        TrajectoryNote(text="Error log sample: 60% of 500s are ConnectionResetError, 40% are timeout-related.", source="tool_result", tool_name="log_analysis"),
        TrajectoryNote(text="ConnectionResetError pattern makes me think it's the payment gateway connection pool.", source="agent"),
        TrajectoryNote(text="But the timeouts could also be the gateway itself being slow, not us.", source="agent"),
        TrajectoryNote(text="Checking payment gateway status page.", source="agent"),
        TrajectoryNote(text="Gateway status: no incidents reported. Latency within normal range.", source="tool_result", tool_name="status_check"),
        TrajectoryNote(text="So it's probably not the gateway. Maybe it's the database after all.", source="agent"),
        TrajectoryNote(text="DB connection pool metrics: avg connections in use = 48/50. Sometimes hitting the cap.", source="tool_result", tool_name="db_metrics"),
        TrajectoryNote(text="The pool is nearly full at 48/50. When it hits 50, new requests fail. That explains both the ConnectionResetErrors and the timeouts.", source="agent"),
        TrajectoryNote(text="This might also be related to the batch job that runs every night — it holds connections open for long periods.", source="agent"),
        TrajectoryNote(text="Actually I'm not sure the batch job is related. Let me stay focused on the pool cap issue.", source="agent"),
        TrajectoryNote(text="Constraint: the database connection pool for the checkout service must be sized to at least 100 connections to handle peak traffic.", source="agent"),
        TrajectoryNote(text="Pool size increased to 100. Error rate dropped from 0.4% to 0.02% over 30 minutes. Intermittent 500 issue is resolved.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="Task complete. Pool resized. Monitoring for 24 hours to confirm.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="discount_logic", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="timeout_related", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="batch_job", present=False, match_by="target_id"),
    ],
)

A3_SOFTWARE_03 = Trajectory(
    id="a3_software_03",
    description="Webhook delivery failures: competing network and config theories; single issue and learning land after confirmation.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:software", "noise:unconfirmed_hypothesis"],
    notes=[
        TrajectoryNote(text="Webhook delivery failure rate jumped from 2% to 31% starting at 09:14 this morning.", source="tool_result", tool_name="webhook_monitor"),
        TrajectoryNote(text="31% is very high. This could be a network issue on the receiver side, a TLS cert problem, or our sender logic broke.", source="agent"),
        TrajectoryNote(text="Checking TLS cert validity for the webhook endpoint.", source="agent"),
        TrajectoryNote(text="TLS cert: valid, not expired, chains correctly. Cert is not the issue.", source="tool_result", tool_name="cert_check"),
        TrajectoryNote(text="TLS is fine. Probably a network issue then. Or maybe the receiver is down.", source="agent"),
        TrajectoryNote(text="Checking receiver endpoint health directly.", source="agent"),
        TrajectoryNote(text="Receiver endpoint returns 200 on health check. It's up.", source="tool_result", tool_name="health_check"),
        TrajectoryNote(text="Receiver is up. So it's either our sender logic or something in between.", source="agent"),
        TrajectoryNote(text="Checking our sender logs. Something changed at 09:14.", source="agent"),
        TrajectoryNote(text="Found it: a config push at 09:12 changed the webhook retry policy from 3 retries to 0. Failed deliveries are not being retried at all.", source="tool_result", tool_name="config_audit"),
        TrajectoryNote(text="So the config change silently removed retries. That's the cause — not network, not TLS.", source="agent"),
        TrajectoryNote(text="The 'it might be network' hypothesis was wrong. Good to have eliminated it early.", source="agent"),
        TrajectoryNote(text="Config reverted: retry count restored to 3. Webhook failure rate back to 2.1%.", source="tool_result", tool_name="webhook_monitor"),
        TrajectoryNote(text="Webhook delivery issue is resolved. Retry policy restored.", source="agent"),
        TrajectoryNote(text="Learning: config changes to retry policies must require a second approval. Silent removal of retries is a high-impact misconfiguration.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="tls_cert", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="network_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="receiver_down", present=False, match_by="target_id"),
    ],
)

A3_SOFTWARE_04 = Trajectory(
    id="a3_software_04",
    description="Search relevance degradation: three theories explored; plan, constraint, and decision emerge; heavy speculative noise throughout.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:software", "noise:speculation", "noise:premature_conclusion"],
    notes=[
        TrajectoryNote(text="Search quality metrics degraded. NDCG@10 dropped from 0.74 to 0.61 after last week's indexing change.", source="tool_result", tool_name="search_metrics"),
        TrajectoryNote(text="Plan: bisect the indexing change to find the exact commit that caused the regression, then fix or revert.", source="agent"),
        TrajectoryNote(text="This might be a tokenization issue introduced by the new analyzer config.", source="agent"),
        TrajectoryNote(text="Or it could be the boost weights — someone changed the title vs body field weighting.", source="agent"),
        TrajectoryNote(text="There's also a chance it's the synonym dictionary update that went out at the same time.", source="agent"),
        TrajectoryNote(text="Bisecting the indexing changes from last week.", source="agent"),
        TrajectoryNote(text="Bisect result: the degradation is attributable to a single commit — boost weight change from title:10 to title:2.", source="tool_result", tool_name="git_bisect"),
        TrajectoryNote(text="So it's the boost weights, not the tokenizer or the synonyms.", source="agent"),
        TrajectoryNote(text="The synonym dictionary change didn't affect relevance — it was a no-op for most queries.", source="agent"),
        TrajectoryNote(text="Wait — actually, can I be certain the synonym change was a no-op? Let me check.", source="agent"),
        TrajectoryNote(text="Synonym impact test: synonym queries account for 3% of searches. NDCG for those queries is unchanged. Synonyms confirmed not the issue.", source="tool_result", tool_name="search_metrics"),
        TrajectoryNote(text="Confirmed: the boost weight change is the sole cause. Synonyms and tokenizer are clean.", source="agent"),
        TrajectoryNote(text="Constraint: search field boost weights must be validated against the NDCG@10 baseline before merging. A drop of more than 0.05 should fail CI.", source="agent"),
        TrajectoryNote(text="Decision: revert the title field boost to 10. The 2x reduction was not justified by any evaluation data.", source="agent"),
        TrajectoryNote(text="Revert merged. NDCG@10 back to 0.73. Search relevance regression is resolved.", source="tool_result", tool_name="search_metrics"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="tokenization_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="synonym_dictionary", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="synonym_uncertainty", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A3 — L3 — ML
# ===========================================================================

A3_ML_01 = Trajectory(
    id="a3_ml_01",
    description="Accuracy drop on production model: three candidate causes explored; one confirmed; constraint and learning set amid speculative noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ml", "noise:conflicting_hypothesis"],
    notes=[
        TrajectoryNote(text="Production model accuracy dropped from 0.91 to 0.84 over the past two weeks. No code changes deployed.", source="tool_result", tool_name="model_monitor"),
        TrajectoryNote(text="No code changes means this is probably data drift. But could also be label drift or a data pipeline bug.", source="agent"),
        TrajectoryNote(text="Checking feature distributions over the past 30 days.", source="agent"),
        TrajectoryNote(text="Feature drift analysis: 3 features have PSI > 0.25. The drifted features are: session_length, items_viewed, cart_abandonment_rate.", source="tool_result", tool_name="drift_monitor"),
        TrajectoryNote(text="PSI > 0.25 on 3 features is significant. Data drift is the likely cause.", source="agent"),
        TrajectoryNote(text="But wait — could the pipeline have a bug that's corrupting these specific features?", source="agent"),
        TrajectoryNote(text="Pipeline integrity check: raw data matches expected schema. No nulls introduced. Feature computation looks correct.", source="tool_result", tool_name="pipeline_check"),
        TrajectoryNote(text="Pipeline is clean. So it is data drift, not a bug.", source="agent"),
        TrajectoryNote(text="What about label drift? If the label distribution changed, that would also explain accuracy drops.", source="agent"),
        TrajectoryNote(text="Label distribution check: labels stable at 23% positive over the period. No label drift.", source="tool_result", tool_name="drift_monitor"),
        TrajectoryNote(text="Labels are stable. Root cause confirmed as feature drift on the three session-related features.", source="agent"),
        TrajectoryNote(text="The session_length drift is probably because we launched a new mobile app which has different session patterns.", source="agent"),
        TrajectoryNote(text="The items_viewed drift might be seasonal or might be related to the mobile launch too.", source="agent"),
        TrajectoryNote(text="Constraint: model must be retrained whenever any top-10 feature exceeds PSI=0.20. Monthly retraining is insufficient.", source="agent"),
        TrajectoryNote(text="Retraining initiated with 90-day rolling window including the new mobile traffic data.", source="agent"),
        TrajectoryNote(text="Retrained model deployed. Production accuracy back to 0.89. Feature drift issue is resolved.", source="tool_result", tool_name="model_monitor"),
        TrajectoryNote(text="Learning: model performance monitoring must include feature drift alerts, not just accuracy alerts. Accuracy drops lag the underlying drift by days.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="label_drift", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="pipeline_bug", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="mobile_launch_drift", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="seasonal_drift", present=False, match_by="target_id"),
    ],
)

A3_ML_02 = Trajectory(
    id="a3_ml_02",
    description="Training instability (loss NaN): multiple gradient/LR theories explored; constraint and decision confirmed after diagnosis.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ml", "noise:competing_diagnosis"],
    notes=[
        TrajectoryNote(text="Training for exp_021 diverged. Loss became NaN at epoch 3, step 847.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="NaN loss usually means exploding gradients or a bad learning rate. Could also be a data issue.", source="agent"),
        TrajectoryNote(text="Checking the gradient norms at the point of divergence.", source="agent"),
        TrajectoryNote(text="Gradient norm at step 845: 14.2. Step 846: 893.4. Step 847: NaN. Clear gradient explosion.", source="tool_result", tool_name="gradient_monitor"),
        TrajectoryNote(text="Gradient explosion confirmed. The norm jumped from 14 to 893 in one step.", source="agent"),
        TrajectoryNote(text="Was it the LR that caused this or a bad batch of data?", source="agent"),
        TrajectoryNote(text="Batch at step 846 inspected. No outliers, no NaN values in inputs. The batch itself looks clean.", source="tool_result", tool_name="data_inspect"),
        TrajectoryNote(text="Clean batch. So it's the LR schedule — might be too aggressive.", source="agent"),
        TrajectoryNote(text="Actually, maybe we should try gradient clipping first before changing the LR.", source="agent"),
        TrajectoryNote(text="Or maybe the issue is the optimizer — we switched from Adam to AdamW for this run.", source="agent"),
        TrajectoryNote(text="Testing: added gradient clipping at max_norm=1.0. Training ran to epoch 10 without NaN.", source="tool_result", tool_name="train"),
        TrajectoryNote(text="Gradient clipping resolved the instability. AdamW with LR=3e-5 is stable when clipping is applied.", source="agent"),
        TrajectoryNote(text="Constraint: all training runs for this model family must use gradient clipping with max_norm=1.0.", source="agent"),
        TrajectoryNote(text="Decision: do not revert to Adam. AdamW with gradient clipping is more stable than Adam without it.", source="agent"),
        TrajectoryNote(text="Exp_021 completed successfully with gradient clipping. Training instability issue resolved.", source="tool_result", tool_name="train"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="bad_batch", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="lr_schedule_aggressive", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="optimizer_adamw", present=False, match_by="target_id"),
    ],
)

A3_ML_03 = Trajectory(
    id="a3_ml_03",
    description="Evaluation benchmark mismatch: preprocessing differences between train and eval explored; one issue and one learning land.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ml", "noise:alternative_explanation"],
    notes=[
        TrajectoryNote(text="Evaluation run on the public STS-B benchmark: Spearman=0.71. Internal validation gives Spearman=0.88. That's a large gap.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="0.71 vs 0.88 is a big gap. Could be overfitting to our internal validation set.", source="agent"),
        TrajectoryNote(text="Or it could be a preprocessing mismatch — our tokenizer config differs from the reference implementation.", source="agent"),
        TrajectoryNote(text="Let me check if the internal validation set overlaps with training data.", source="agent"),
        TrajectoryNote(text="Overlap check: 0 examples from the internal validation set appear in training data. No leakage.", source="tool_result", tool_name="data_inspect"),
        TrajectoryNote(text="No leakage. So it's not overfitting to validation data.", source="agent"),
        TrajectoryNote(text="Let me check the preprocessing pipeline for STS-B vs our internal evaluation.", source="agent"),
        TrajectoryNote(text="Preprocessing diff found: STS-B uses lowercase and strip punctuation. Our internal eval uses original casing and includes punctuation. The model was trained with original casing.", source="tool_result", tool_name="preprocess_diff"),
        TrajectoryNote(text="That's the problem. The benchmark applies lowercase but our model was trained without it.", source="agent"),
        TrajectoryNote(text="Though the gap of 0.17 Spearman seems large for just lowercasing. Are there other differences?", source="agent"),
        TrajectoryNote(text="Further diff: STS-B also truncates to 64 tokens; our internal eval uses 128. That's another difference.", source="tool_result", tool_name="preprocess_diff"),
        TrajectoryNote(text="So there are two preprocessing differences: lowercasing and truncation length. Both contribute.", source="agent"),
        TrajectoryNote(text="Re-running STS-B with matched preprocessing (no lowercase, 128 tokens): Spearman=0.86. Gap closes to 0.02.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="The gap was preprocessing, not model quality. Spearman=0.86 with matched preprocessing.", source="agent"),
        TrajectoryNote(text="Learning: always document and match preprocessing configs exactly when comparing across benchmark implementations. Small differences in tokenization and truncation can cause large apparent performance gaps.", source="agent"),
        TrajectoryNote(text="Benchmark mismatch issue is resolved. Evaluation with matched preprocessing is now the standard.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="overfitting", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="data_leakage", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="lowercasing_doubt", present=False, match_by="target_id"),
    ],
)

A3_ML_04 = Trajectory(
    id="a3_ml_04",
    description="Inference latency regression post-quantization: conflicting profiling outputs; single constraint and decision land after noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ml", "noise:profiling_confusion"],
    notes=[
        TrajectoryNote(text="Post-quantization inference latency: 124ms p99 on CPU. Pre-quantization was 68ms p99. That's worse, not better.", source="tool_result", tool_name="benchmark"),
        TrajectoryNote(text="Quantization making things slower is unexpected. Could be a wrong quantization config.", source="agent"),
        TrajectoryNote(text="Or it could be the benchmark setup — maybe we're measuring something different.", source="agent"),
        TrajectoryNote(text="Let me verify the benchmark is measuring the same thing: same input shapes, same batch size.", source="agent"),
        TrajectoryNote(text="Benchmark verification: pre and post runs use identical inputs. The 124ms vs 68ms is a real regression.", source="tool_result", tool_name="benchmark"),
        TrajectoryNote(text="Okay it's real. Checking the quantization config.", source="agent"),
        TrajectoryNote(text="Quantization config: dynamic quantization applied to all layers including embedding layers. Embedding quantization on CPU typically adds overhead.", source="tool_result", tool_name="config_inspect"),
        TrajectoryNote(text="Embedding quantization is the culprit. It's not beneficial on CPU.", source="agent"),
        TrajectoryNote(text="Though it could also be the specific CPU instruction set — maybe this CPU doesn't support the quantized ops well.", source="agent"),
        TrajectoryNote(text="CPU capability check: AVX2 and VNNI are supported. The CPU should handle quantized int8 ops efficiently.", source="tool_result", tool_name="cpu_check"),
        TrajectoryNote(text="CPU supports the right instruction sets. It's the embedding quantization config, not the hardware.", source="agent"),
        TrajectoryNote(text="Retested with embeddings excluded from quantization: p99 latency is now 51ms. Better than pre-quantization.", source="tool_result", tool_name="benchmark"),
        TrajectoryNote(text="Constraint: do not apply dynamic quantization to embedding layers on CPU deployment targets.", source="agent"),
        TrajectoryNote(text="Decision: update the quantization pipeline to exclude embedding layers by default.", source="agent"),
        TrajectoryNote(text="Quantization regression is resolved. p99 latency now 51ms with corrected config.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="benchmark_setup", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="cpu_instruction_set", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A3 — L3 — OPS
# ===========================================================================

A3_OPS_01 = Trajectory(
    id="a3_ops_01",
    description="Database failover failed during a test; competing explanations; one issue, constraint, and learning land.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ops", "noise:competing_root_cause"],
    notes=[
        TrajectoryNote(text="Scheduled failover test for the primary database. Initiating controlled failover.", source="agent"),
        TrajectoryNote(text="Failover did not complete. Standby did not promote to primary within the 30-second window.", source="tool_result", tool_name="db_failover"),
        TrajectoryNote(text="Failover timeout could be a replication lag issue, a network partition between primary and standby, or a misconfigured promotion script.", source="agent"),
        TrajectoryNote(text="Checking replication lag at the time of the test.", source="agent"),
        TrajectoryNote(text="Replication lag at failover time: 0.3 seconds. Within acceptable range for promotion.", source="tool_result", tool_name="db_metrics"),
        TrajectoryNote(text="Lag was fine. Probably not replication.", source="agent"),
        TrajectoryNote(text="Checking network connectivity between primary and standby during the test window.", source="agent"),
        TrajectoryNote(text="Network logs: no packet loss or latency spikes between primary and standby. Network is healthy.", source="tool_result", tool_name="network_logs"),
        TrajectoryNote(text="Network is clean too. Must be the promotion script.", source="agent"),
        TrajectoryNote(text="Actually, could it be a quorum issue? We have 3 nodes — primary, standby, and the arbiter.", source="agent"),
        TrajectoryNote(text="Arbiter status at failover time: arbiter was unreachable for 45 seconds starting 3 minutes before the test. Quorum was lost.", source="tool_result", tool_name="db_metrics"),
        TrajectoryNote(text="The arbiter was down. Without quorum, the standby couldn't safely promote.", source="agent"),
        TrajectoryNote(text="So it wasn't the replication, the network, or the script. It was the arbiter availability.", source="agent"),
        TrajectoryNote(text="The arbiter being down might have been a coincidence or it might indicate a reliability issue with the arbiter node.", source="agent"),
        TrajectoryNote(text="Constraint: all three nodes (primary, standby, arbiter) must be healthy and reachable before initiating a failover test.", source="agent"),
        TrajectoryNote(text="Learning: arbiter availability is a prerequisite for failover, not just a nice-to-have. Add arbiter health check to the failover pre-flight checklist.", source="agent"),
        TrajectoryNote(text="Failover test will be re-run next week after validating arbiter reliability. Incident closed.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "open"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="replication_lag", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="network_partition", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="promotion_script", present=False, match_by="target_id"),
    ],
)

A3_OPS_02 = Trajectory(
    id="a3_ops_02",
    description="Capacity planning for a peak event: many speculative forecasts; one plan and one constraint land.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ops", "noise:speculative_forecast"],
    notes=[
        TrajectoryNote(text="Planning infrastructure capacity for the Black Friday sale. Last year's peak was 4,200 rpm.", source="agent"),
        TrajectoryNote(text="This year's user base is 40% larger, so maybe 5,900 rpm?", source="agent"),
        TrajectoryNote(text="But the new mobile app might drive higher session frequency — could be 7,000 rpm.", source="agent"),
        TrajectoryNote(text="On the other hand, the new CDN might offload 20% of requests — maybe 4,700 rpm.", source="agent"),
        TrajectoryNote(text="Traffic forecast analysis complete using 90th percentile model with mobile multiplier and CDN deflection: expected peak 6,100 rpm, p99 scenario 7,800 rpm.", source="tool_result", tool_name="capacity_model"),
        TrajectoryNote(text="So the model says 6,100 rpm expected, 7,800 rpm worst case. That's what we should plan for.", source="agent"),
        TrajectoryNote(text="Though I wonder if even 7,800 is conservative enough for a 2-hour sale window.", source="agent"),
        TrajectoryNote(text="Let me check what our current infrastructure tops out at.", source="agent"),
        TrajectoryNote(text="Load test at 8,000 rpm: all services stable. p99 latency 340ms. Headroom exists up to approximately 9,500 rpm.", source="tool_result", tool_name="load_test"),
        TrajectoryNote(text="Current infra handles 9,500 rpm. Worst case forecast is 7,800 rpm. We have headroom.", source="agent"),
        TrajectoryNote(text="But what if we get a sudden spike? Should we pre-provision extra capacity as a buffer?", source="agent"),
        TrajectoryNote(text="Pre-provisioning 2 extra app servers for the sale window would cover up to 11,000 rpm.", source="agent"),
        TrajectoryNote(text="Plan: pre-provision 2 extra app servers starting 2 hours before the sale window. Scale down 4 hours after.", source="agent"),
        TrajectoryNote(text="Constraint: minimum capacity during the Black Friday sale window must support 10,000 rpm based on the worst-case forecast plus 25% safety margin.", source="agent"),
        TrajectoryNote(text="Capacity plan documented and approved by engineering leadership.", source="tool_result", tool_name="approval"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="5900_rpm", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="maybe_7000_rpm", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="4700_rpm", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="conservative_enough", present=False, match_by="target_id"),
    ],
)

A3_OPS_03 = Trajectory(
    id="a3_ops_03",
    description="Kubernetes pod crash loop: OOMKilled; many competing theories before memory limit constraint and decision confirmed.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ops", "noise:competing_diagnosis"],
    notes=[
        TrajectoryNote(text="Alert: api-worker pods entering crash loop. 3 of 5 pods currently in CrashLoopBackoff.", source="tool_result", tool_name="k8s_monitor"),
        TrajectoryNote(text="Crash loops can be OOMKilled, a bad liveness probe, a startup error, or a dependency being down.", source="agent"),
        TrajectoryNote(text="Checking pod logs for the crashing pods.", source="agent"),
        TrajectoryNote(text="Pod logs: last exit code was 137 (OOMKilled). Memory was hitting the limit.", source="tool_result", tool_name="kubectl"),
        TrajectoryNote(text="OOMKilled confirmed. The pods are being killed for exceeding memory limits.", source="agent"),
        TrajectoryNote(text="But why is memory usage higher now? Something must have changed.", source="agent"),
        TrajectoryNote(text="Maybe it's the new caching layer that was added last week — it might be holding more data in memory than expected.", source="agent"),
        TrajectoryNote(text="Or it could be a memory leak in the latest deployment.", source="agent"),
        TrajectoryNote(text="Memory profile of a stable pod vs a crashing pod: crashing pod shows linear growth in the Redis client connection pool. Not from the caching layer.", source="tool_result", tool_name="memory_profile"),
        TrajectoryNote(text="Redis client connection pool is leaking. Not the caching layer.", source="agent"),
        TrajectoryNote(text="Actually, is the Redis pool leak causing the OOM, or is it just a symptom of something else?", source="agent"),
        TrajectoryNote(text="Timeline correlation: the pool growth started exactly at the last deployment. The leak is in the new connection initialization code.", source="tool_result", tool_name="memory_profile"),
        TrajectoryNote(text="The deployment introduced the Redis pool leak. Root cause is clear.", source="agent"),
        TrajectoryNote(text="Constraint: memory limit for api-worker pods must be set to 1.5GB (current 512MB is insufficient; realistic usage is 800MB for normal workload).", source="agent"),
        TrajectoryNote(text="Decision: roll back the latest deployment immediately. Fix the Redis connection pool leak before re-deploying.", source="agent"),
        TrajectoryNote(text="Rollback complete. Pod crash loop resolved. All 5 pods running.", source="tool_result", tool_name="k8s_monitor"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="caching_layer", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="liveness_probe", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="dependency_down", present=False, match_by="target_id"),
    ],
)

A3_OPS_04 = Trajectory(
    id="a3_ops_04",
    description="Disk usage alert with multiple teams contributing: root cause isolated; constraint and learning set; competing blame avoidance.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:ops", "noise:blame_deflection"],
    notes=[
        TrajectoryNote(text="Alert: /var/log disk usage at 89% on app-server-04. Threshold is 85%.", source="tool_result", tool_name="monitoring"),
        TrajectoryNote(text="This could be application logs, system logs, or an rogue cron job.", source="agent"),
        TrajectoryNote(text="Checking what's consuming the disk.", source="agent"),
        TrajectoryNote(text="du output: /var/log/app/debug.log is 47GB. It has not been rotated in 6 months.", source="tool_result", tool_name="shell"),
        TrajectoryNote(text="47GB debug log is the problem. No log rotation configured.", source="agent"),
        TrajectoryNote(text="Who owns the log rotation config? This might be the platform team's responsibility, not ours.", source="agent"),
        TrajectoryNote(text="Or it could be that the app team disabled log rotation when they added the debug level logging.", source="agent"),
        TrajectoryNote(text="Actually it doesn't matter who caused it — we need to fix the disk space first.", source="agent"),
        TrajectoryNote(text="Log rotation config check: logrotate.d config for this service is missing. It was never created when the service was deployed.", source="tool_result", tool_name="config_audit"),
        TrajectoryNote(text="No logrotate config was ever set up for this service. The omission is the root cause.", source="agent"),
        TrajectoryNote(text="But there's also a question of why debug-level logging is enabled in production at all.", source="agent"),
        TrajectoryNote(text="Application log level: DEBUG. This was set during a previous incident and never reverted.", source="tool_result", tool_name="config_audit"),
        TrajectoryNote(text="Two problems confirmed: no log rotation and debug logging in production.", source="agent"),
        TrajectoryNote(text="Constraint: all production services must have logrotate configs that rotate daily and retain 7 days maximum.", source="agent"),
        TrajectoryNote(text="Logrotate config deployed for this service. Debug log rotated and compressed. Disk usage now 12%.", source="tool_result", tool_name="shell"),
        TrajectoryNote(text="Learning: production log level must be reset to INFO after any incident where DEBUG logging was temporarily enabled. Add a reminder to the incident playbook.", source="agent"),
        TrajectoryNote(text="Disk usage issue resolved. Logrotate deployed.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="platform_team_responsibility", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="app_team_disabled_rotation", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="who_owns", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A3 — L3 — POLICY
# ===========================================================================

A3_POLICY_01 = Trajectory(
    id="a3_policy_01",
    description="Regulatory scope ambiguity around CCPA vs GDPR; competing interpretations; one constraint lands after legal clarification.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:policy", "noise:regulatory_ambiguity"],
    notes=[
        TrajectoryNote(text="Need to determine whether our new EU analytics product is subject to GDPR only, CCPA only, or both.", source="agent"),
        TrajectoryNote(text="The product is hosted in the EU and primarily targets EU customers. GDPR seems most relevant.", source="agent"),
        TrajectoryNote(text="But we also have California-based enterprise customers accessing the product. That might trigger CCPA.", source="agent"),
        TrajectoryNote(text="CCPA applies to for-profit businesses that collect personal data from California residents. We do have CA users.", source="agent"),
        TrajectoryNote(text="But CCPA's B2B exemption might apply here — if data subjects are employees of business customers, they may be exempt.", source="agent"),
        TrajectoryNote(text="Actually the CCPA B2B exemption expired and was partially restored. The status is ambiguous.", source="agent"),
        TrajectoryNote(text="External counsel opinion received: GDPR applies unambiguously. CCPA applies to the California-resident end users of the enterprise customers — the B2B exemption does not cover them.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="So both apply. Both GDPR and CCPA are in scope.", source="agent"),
        TrajectoryNote(text="The question now is whether our privacy policy and consent flows adequately cover both frameworks.", source="agent"),
        TrajectoryNote(text="Privacy policy review: current policy covers GDPR but does not include CCPA-required disclosures (right to opt-out of sale, right to know).", source="tool_result", tool_name="policy_review"),
        TrajectoryNote(text="The CCPA gap is the actionable finding here. The GDPR coverage is fine.", source="agent"),
        TrajectoryNote(text="Although — the GDPR consent records might not meet CCPA's specific documentation requirements either.", source="agent"),
        TrajectoryNote(text="Follow-up legal review: consent records format is acceptable for CCPA purposes. The gap is only in the privacy policy disclosures.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="Constraint: the privacy policy must include CCPA-required disclosures — right to opt-out, right to know, and right to delete — before the product is made available to California users.", source="agent"),
        TrajectoryNote(text="Privacy policy update in progress. Legal counsel is drafting the CCPA addendum.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="ccpa_b2b_exemption", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="gdpr_only", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="ccpa_ambiguity", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="consent_records_doubt", present=False, match_by="target_id"),
    ],
)

A3_POLICY_02 = Trajectory(
    id="a3_policy_02",
    description="Open source license conflict investigation: competing GPL vs LGPL interpretations; one constraint and one decision land.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:policy", "noise:license_ambiguity"],
    notes=[
        TrajectoryNote(text="Dependency audit flagged a potential license conflict: one of our dependencies uses GPL-3.0.", source="tool_result", tool_name="license_scanner"),
        TrajectoryNote(text="GPL-3.0 is copyleft — if we link against it, our code might need to be GPL too.", source="agent"),
        TrajectoryNote(text="But maybe it's LGPL-3.0, not GPL-3.0? LGPL has an exception for dynamic linking.", source="agent"),
        TrajectoryNote(text="Checking the specific dependency license file.", source="agent"),
        TrajectoryNote(text="License file confirmed: it is GPL-3.0, not LGPL. No dynamic linking exception.", source="tool_result", tool_name="license_scanner"),
        TrajectoryNote(text="GPL-3.0 confirmed. This is a real conflict if we distribute the software.", source="agent"),
        TrajectoryNote(text="Are we even distributing this software? If it's internal-only, GPL might not be triggered.", source="agent"),
        TrajectoryNote(text="The product is a SaaS offering — users access it over a network. GPL's distribution clause is not triggered by network access (that's the rationale behind AGPL vs GPL distinction).", source="agent"),
        TrajectoryNote(text="So if it's SaaS-only, we might be fine under GPL. But we also have an on-premise deployment option.", source="agent"),
        TrajectoryNote(text="Legal counsel opinion: the on-premise deployment does constitute distribution. Our proprietary code combined with a GPL-3.0 dependency must be released under GPL-3.0 for on-premise builds.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="On-premise builds are the problem. SaaS builds are fine.", source="agent"),
        TrajectoryNote(text="We could also just remove the dependency and replace it. That would solve it without the license issue.", source="agent"),
        TrajectoryNote(text="Or we could seek a commercial license from the dependency maintainer.", source="agent"),
        TrajectoryNote(text="Constraint: no GPL-3.0 (or any strong copyleft) dependencies may be included in the on-premise build artifact.", source="agent"),
        TrajectoryNote(text="Decision: replace the GPL-3.0 dependency with the MIT-licensed alternative identified by the team. Do not seek a commercial license — the alternative is functionally equivalent.", source="agent"),
        TrajectoryNote(text="Replacement dependency integrated. License scanner re-run: no GPL conflicts in on-premise build. License conflict issue is resolved.", source="tool_result", tool_name="license_scanner"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="commercial_license", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="saas_only_fine", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="lgpl_exception", present=False, match_by="target_id"),
    ],
)

A3_POLICY_03 = Trajectory(
    id="a3_policy_03",
    description="Incident response policy gap: blame attribution ambiguous; single learning and constraint land after noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:policy", "noise:blame_attribution"],
    notes=[
        TrajectoryNote(text="Post-mortem for the October 15 outage is underway. The outage lasted 3 hours and affected 40% of users.", source="agent"),
        TrajectoryNote(text="The outage might have been caused by the deployment team pushing without running smoke tests.", source="agent"),
        TrajectoryNote(text="Or the monitoring team might not have had alerting configured for this specific failure mode.", source="agent"),
        TrajectoryNote(text="There's also a chance the on-call engineer was not properly briefed on the new architecture.", source="agent"),
        TrajectoryNote(text="Post-mortem timeline reconstructed. The root cause was a config change deployed without smoke tests. Detection took 47 minutes because the alert threshold was too high.", source="tool_result", tool_name="post_mortem"),
        TrajectoryNote(text="So it was both: no smoke tests and an overly high alert threshold.", source="agent"),
        TrajectoryNote(text="Who was on-call during the outage? If they didn't respond quickly enough, that's also a factor.", source="agent"),
        TrajectoryNote(text="On-call response time: 12 minutes from first alert. That's within SLA.", source="tool_result", tool_name="post_mortem"),
        TrajectoryNote(text="On-call response was fine. Not a people issue.", source="agent"),
        TrajectoryNote(text="The engineering lead says this was a process gap, not an individual failure.", source="agent"),
        TrajectoryNote(text="Agreed — the process didn't require smoke tests before production deploys.", source="agent"),
        TrajectoryNote(text="Constraint: all production deployments must pass a mandatory smoke test suite before being marked as complete. This is now enforced in the deployment pipeline.", source="agent"),
        TrajectoryNote(text="Learning: alert thresholds that are set too high to reduce noise result in slow detection. Alert tuning must balance noise and sensitivity — err on the side of sensitivity for P1 services.", source="agent"),
        TrajectoryNote(text="Post-mortem actions assigned. Constraint and learning are the key outputs.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="deployment_team", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="monitoring_team", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="oncall_briefing", present=False, match_by="target_id"),
    ],
)

A3_POLICY_04 = Trajectory(
    id="a3_policy_04",
    description="Data residency dispute for a new enterprise customer: multiple jurisdictional interpretations; one constraint lands.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l3", "domain:policy", "noise:jurisdictional_ambiguity"],
    notes=[
        TrajectoryNote(text="Enterprise customer contract review: the customer requires that all data processing occur within the EU.", source="agent"),
        TrajectoryNote(text="We process data in EU-West-1 primarily, but our backup replication goes to US-East-1. That might be a problem.", source="agent"),
        TrajectoryNote(text="Or maybe not — Standard Contractual Clauses (SCCs) allow data transfer to the US under GDPR.", source="agent"),
        TrajectoryNote(text="But the customer's contract says 'all processing' not 'all storage'. Replication might not count as processing.", source="agent"),
        TrajectoryNote(text="Legal interpretation: backups are processed in the destination region when being written and indexed. This does constitute processing.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="So backups are processing. The US-East-1 replication violates the customer's data residency requirement.", source="agent"),
        TrajectoryNote(text="Could we just exclude this customer's data from US replication?", source="agent"),
        TrajectoryNote(text="Or could we negotiate a modified SCC with the customer to cover the US replication?", source="agent"),
        TrajectoryNote(text="Customer's legal team response: they will not accept SCCs for this contract. Full EU residency is required, no exceptions.", source="tool_result", tool_name="customer_legal"),
        TrajectoryNote(text="No SCCs accepted. We need to either exclude their data from US replication or stand up EU-only infrastructure.", source="agent"),
        TrajectoryNote(text="We could also turn down this customer, but that's a commercial decision, not a policy one.", source="agent"),
        TrajectoryNote(text="Technical feasibility check: per-tenant replication region control is supported by our data platform.", source="tool_result", tool_name="arch_review"),
        TrajectoryNote(text="Constraint: for any enterprise customer with an EU data residency requirement, all backup replication must be routed to EU-West-2 only. US-East-1 replication must be excluded for these tenants.", source="agent"),
        TrajectoryNote(text="Customer-specific replication policy configured. Contract condition now met.", source="tool_result", tool_name="config_update"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="sccs_allow", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="backups_not_processing", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="turn_down_customer", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A4 — L4 — SOFTWARE
# ===========================================================================

A4_SOFTWARE_01 = Trajectory(
    id="a4_software_01",
    description="API rate limiting implementation: 2 constraints and 1 decision land amid 22 adversarial notes spanning all failure modes.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:software", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="We should probably add some kind of rate limiting to the API.", source="agent"),
        TrajectoryNote(text="It might be worth opening an issue about this.", source="agent"),
        TrajectoryNote(text="Let me think about what the right rate limit should be.", source="agent"),
        TrajectoryNote(text="Constraint: the public API must enforce rate limiting of 1000 requests per minute per API key.", source="agent"),
        TrajectoryNote(text="That constraint might need to be different for different customer tiers.", source="agent"),
        TrajectoryNote(text="I wonder if 1000 rpm is too low for enterprise customers.", source="agent"),
        TrajectoryNote(text="We should probably document this somewhere.", source="agent"),
        TrajectoryNote(text="This feels like a decision that needs stakeholder input.", source="agent"),
        TrajectoryNote(text="Resolve the rate_limiting_issue please.", source="agent"),
        TrajectoryNote(text="API rate limit implementation complete. Token bucket algorithm deployed. The implementation now enforces 1000 rpm per API key.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="Seems like it might be working. Hard to tell without load testing.", source="agent"),
        TrajectoryNote(text="Load testing is something we should consider doing at some point.", source="agent"),
        TrajectoryNote(text="Load test complete: rate limiting correctly rejects requests beyond 1000 rpm. Returns 429 with Retry-After header.", source="tool_result", tool_name="load_test"),
        TrajectoryNote(text="That's good. The 429 with Retry-After is the right behavior.", source="agent"),
        TrajectoryNote(text="We should also think about logging rejected requests.", source="agent"),
        TrajectoryNote(text="Maybe log to a separate rejected_requests table or something.", source="agent"),
        TrajectoryNote(text="Decision: rejected rate limit requests must be logged with the API key, endpoint, and timestamp. This enables abuse detection.", source="agent"),
        TrajectoryNote(text="Logging sounds good. We should implement that.", source="agent"),
        TrajectoryNote(text="This is probably something that could be a constraint or a decision.", source="agent"),
        TrajectoryNote(text="Or maybe it should be in the plan. Not sure.", source="agent"),
        TrajectoryNote(text="Constraint: all rate limit rejections must be logged with api_key, endpoint, and timestamp. Retention: 90 days.", source="agent"),
        TrajectoryNote(text="Good. That's now set. Implementation is in progress.", source="agent"),
        TrajectoryNote(text="We should track this as a task.", source="agent"),
        TrajectoryNote(text="There's probably also something to do about documentation.", source="agent"),
        TrajectoryNote(text="The documentation could be a separate task.", source="agent"),
        TrajectoryNote(text="Task complete when logging and rate limiting are both deployed.", source="agent"),
        TrajectoryNote(text="Rate limit logging deployed. Both constraints satisfied. Task is done.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="Good. Everything is implemented.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="rate_limiting_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="", present=False, match_by="fields", checks={"status": "resolved", "title": "rate limiting"}),
        ExpectedOutcome(bucket="constraints", target_id="enterprise_tier", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="documentation", present=False, match_by="target_id"),
    ],
)

A4_SOFTWARE_02 = Trajectory(
    id="a4_software_02",
    description="Security audit of an authentication module: 1 issue and 1 constraint land amid dense adversarial distractors.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:software", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Starting security audit of the authentication module.", source="agent"),
        TrajectoryNote(text="There are probably some issues with password hashing.", source="agent"),
        TrajectoryNote(text="We should look at the session management too.", source="agent"),
        TrajectoryNote(text="Session tokens might be too long or too short — not sure what the right length is.", source="agent"),
        TrajectoryNote(text="Maybe there's a vulnerability in the token generation.", source="agent"),
        TrajectoryNote(text="Audit finding: password hashing is using MD5. MD5 is cryptographically broken and must not be used for passwords.", source="tool_result", tool_name="security_audit"),
        TrajectoryNote(text="MD5 is definitely bad for passwords. This is a real finding.", source="agent"),
        TrajectoryNote(text="We should probably track this as an issue.", source="agent"),
        TrajectoryNote(text="The session token length looks fine — 256 bits. No finding there.", source="tool_result", tool_name="security_audit"),
        TrajectoryNote(text="Good, session tokens are fine. That was a false concern.", source="agent"),
        TrajectoryNote(text="What about brute force protection?", source="agent"),
        TrajectoryNote(text="We might want to add rate limiting to the login endpoint.", source="agent"),
        TrajectoryNote(text="Or we could use CAPTCHA. Or maybe account lockout.", source="agent"),
        TrajectoryNote(text="Brute force audit: no rate limiting on the /login endpoint. Up to 10,000 requests per second accepted.", source="tool_result", tool_name="security_audit"),
        TrajectoryNote(text="No rate limiting on login is also a real finding.", source="agent"),
        TrajectoryNote(text="So we have two findings: MD5 passwords and no login rate limiting.", source="agent"),
        TrajectoryNote(text="Password hashing replaced with bcrypt (cost factor 12). MD5 issue resolved.", source="tool_result", tool_name="security_fix"),
        TrajectoryNote(text="MD5 issue is now fixed. bcrypt is the right choice.", source="agent"),
        TrajectoryNote(text="We should probably make this a constraint going forward.", source="agent"),
        TrajectoryNote(text="Constraint: password hashing must use bcrypt with cost factor >= 12 or an equivalent modern KDF. MD5, SHA1, and SHA256 are not acceptable for password storage.", source="agent"),
        TrajectoryNote(text="Good constraint. This should be in the coding standards.", source="agent"),
        TrajectoryNote(text="The login rate limiting issue still needs to be fixed.", source="agent"),
        TrajectoryNote(text="Login rate limiting added: max 10 attempts per 15 minutes per IP.", source="tool_result", tool_name="security_fix"),
        TrajectoryNote(text="Both findings are now resolved.", source="agent"),
        TrajectoryNote(text="Task is complete.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="password_hashing_speculation", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="token_generation", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="captcha", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="account_lockout", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="should_probably", present=False, match_by="target_id"),
    ],
)

A4_SOFTWARE_03 = Trajectory(
    id="a4_software_03",
    description="Database schema migration planning: plan and 1 constraint land; heavy imperative and speculative adversarial noise.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:software", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="We need to migrate the users table from PostgreSQL 13 to 15.", source="agent"),
        TrajectoryNote(text="This should probably be tracked somewhere.", source="agent"),
        TrajectoryNote(text="Plan: run pg_upgrade in-place on a staging clone, validate, then schedule production migration during the next maintenance window.", source="agent"),
        TrajectoryNote(text="There might be some constraints around the maintenance window.", source="agent"),
        TrajectoryNote(text="I think we need to have a constraint about downtime.", source="agent"),
        TrajectoryNote(text="The maintenance window is usually Sunday 02:00–06:00.", source="agent"),
        TrajectoryNote(text="That's probably the right time to do the migration.", source="agent"),
        TrajectoryNote(text="Constraint: production database migrations must only occur during the Sunday 02:00–06:00 UTC maintenance window and require 48-hour advance notice to the on-call team.", source="agent"),
        TrajectoryNote(text="Good. That constraint is now set.", source="agent"),
        TrajectoryNote(text="Staging migration test complete. pg_upgrade ran in 4 minutes on a 200GB replica.", source="tool_result", tool_name="db_migrate"),
        TrajectoryNote(text="That's fast. Production migration shouldn't be a problem.", source="agent"),
        TrajectoryNote(text="We should also think about rolling back if something goes wrong.", source="agent"),
        TrajectoryNote(text="A rollback plan would be useful. We might want to document that.", source="agent"),
        TrajectoryNote(text="Actually maybe we should track the rollback plan as a decision.", source="agent"),
        TrajectoryNote(text="Or it could just be part of the plan document.", source="agent"),
        TrajectoryNote(text="We should also test extensions compatibility — not sure all extensions support PG15.", source="agent"),
        TrajectoryNote(text="Extension compatibility check: all 7 extensions currently in use are PG15-compatible. No action needed.", source="tool_result", tool_name="db_migrate"),
        TrajectoryNote(text="Extensions are fine. Good.", source="agent"),
        TrajectoryNote(text="The migration is basically ready to schedule.", source="agent"),
        TrajectoryNote(text="We should probably open a ticket for scheduling.", source="agent"),
        TrajectoryNote(text="Or just coordinate over Slack with the DBA team.", source="agent"),
        TrajectoryNote(text="Migration scheduled for next Sunday 02:00 UTC. DBA team notified.", source="tool_result", tool_name="calendar"),
        TrajectoryNote(text="Task is in progress — waiting for the migration window.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="rollback_plan", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="coordinate_slack", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="extensions_compatibility", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="probably_a_constraint", present=False, match_by="target_id"),
    ],
)

A4_SOFTWARE_04 = Trajectory(
    id="a4_software_04",
    description="GraphQL N+1 query performance fix: 1 decision and 1 learning land; 22 adversarial notes include incomplete payload distractors.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:software", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Something is slow in the GraphQL layer. Not sure what.", source="agent"),
        TrajectoryNote(text="This might be worth investigating. Could open an issue for it.", source="agent"),
        TrajectoryNote(text="The slowness might be N+1 queries or maybe the resolver is doing extra work.", source="agent"),
        TrajectoryNote(text="N+1 queries are common in GraphQL. Might be that.", source="agent"),
        TrajectoryNote(text="Profiler output: resolving a list of 100 orders triggers 101 DB queries — 1 for the list and 1 per order for the customer relationship.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="Classic N+1. The customer relationship is not being batched.", source="agent"),
        TrajectoryNote(text="We should fix this.", source="agent"),
        TrajectoryNote(text="DataLoader would solve this — it batches resolver calls.", source="agent"),
        TrajectoryNote(text="Or we could use a JOIN at the database level instead.", source="agent"),
        TrajectoryNote(text="DataLoader is the idiomatic GraphQL approach.", source="agent"),
        TrajectoryNote(text="Decision: use DataLoader for all list-type resolvers that fetch related entities. DataLoader will batch and cache calls within a single request lifecycle.", source="agent"),
        TrajectoryNote(text="That's the right decision. DataLoader is the standard fix.", source="agent"),
        TrajectoryNote(text="Should this also be a constraint? Probably.", source="agent"),
        TrajectoryNote(text="DataLoader implementation complete. 101 queries → 2 queries for the orders list.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="2 queries instead of 101. That's the expected result.", source="agent"),
        TrajectoryNote(text="We should probably add a test that would catch N+1 regressions.", source="agent"),
        TrajectoryNote(text="A test that counts query executions would work.", source="agent"),
        TrajectoryNote(text="That would be a good guard. We should add it.", source="agent"),
        TrajectoryNote(text="Learning: all list-type GraphQL resolvers that load related entities must use DataLoader or equivalent batching. Add a query-count assertion test for each list resolver.", source="agent"),
        TrajectoryNote(text="Good learning. Now it's documented.", source="agent"),
        TrajectoryNote(text="Task is done once the DataLoader refactor is merged.", source="agent"),
        TrajectoryNote(text="DataLoader refactor merged. All list resolvers now batch correctly. Task is complete.", source="tool_result", tool_name="deploy"),
        TrajectoryNote(text="Good. Everything is done.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="graphql_slow", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="join_approach", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="should_also_be_constraint", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A4 — L4 — ML
# ===========================================================================

A4_ML_01 = Trajectory(
    id="a4_ml_01",
    description="Experiment pipeline redesign: 1 plan, 1 constraint land amid 22 adversarial notes including vague directives and incomplete state-like notes.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ml", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="The experiment pipeline is getting unwieldy. We should redesign it.", source="agent"),
        TrajectoryNote(text="It would be good to track what the plan is for this.", source="agent"),
        TrajectoryNote(text="There should probably be a constraint about reproducibility.", source="agent"),
        TrajectoryNote(text="Plan: redesign the experiment pipeline to be fully reproducible, config-driven, and logged to MLflow.", source="agent"),
        TrajectoryNote(text="Reproducibility is important. We should make it mandatory.", source="agent"),
        TrajectoryNote(text="Maybe we need a constraint that all experiments must log hyperparameters.", source="agent"),
        TrajectoryNote(text="Or we could make it a decision that we're adopting MLflow.", source="agent"),
        TrajectoryNote(text="Both seem right. Hard to decide which bucket.", source="agent"),
        TrajectoryNote(text="Constraint: all experiment runs must log the following to MLflow: hyperparameters, dataset hash, model checkpoint path, and all eval metrics. No exceptions.", source="agent"),
        TrajectoryNote(text="Good. That's now a constraint.", source="agent"),
        TrajectoryNote(text="We should probably also decide on the directory structure for model artifacts.", source="agent"),
        TrajectoryNote(text="The directory structure is probably also a constraint.", source="agent"),
        TrajectoryNote(text="Or a decision. Or part of the plan.", source="agent"),
        TrajectoryNote(text="I'll just say it's a decision — that seems right.", source="agent"),
        TrajectoryNote(text="We might want to open an issue for the pipeline being slow.", source="agent"),
        TrajectoryNote(text="MLflow integration scaffolding complete. All new runs will log automatically.", source="tool_result", tool_name="mlflow_setup"),
        TrajectoryNote(text="Great. The scaffolding is in place.", source="agent"),
        TrajectoryNote(text="There's probably also something about data versioning.", source="agent"),
        TrajectoryNote(text="Data versioning might need a constraint too.", source="agent"),
        TrajectoryNote(text="Or we could track it as an issue that needs to be addressed.", source="agent"),
        TrajectoryNote(text="DVC integration for dataset versioning is probably the right approach.", source="agent"),
        TrajectoryNote(text="But that might be scope creep. Let's focus on MLflow for now.", source="agent"),
        TrajectoryNote(text="Pilot experiment run logged to MLflow successfully. All fields captured correctly.", source="tool_result", tool_name="mlflow_setup"),
        TrajectoryNote(text="Pipeline redesign complete. Task is done.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="directory_structure", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="pipeline_slow", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="data_versioning", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="dvc_integration", present=False, match_by="target_id"),
    ],
)

# PATCH: removed checks={"metric_name": "p99_inference_latency"} → checks={}
# 'p99 inference latency' (with spaces) is a valid naming choice by the interpreter;
# asserting underscores vs spaces is formatting noise, not a correctness failure.
A4_ML_02 = Trajectory(
    id="a4_ml_02",
    description="Model serving latency investigation: 1 constraint and 1 result land; adversarial notes mimic result and constraint forms.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ml", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Inference latency on the serving cluster seems high. Should investigate.", source="agent"),
        TrajectoryNote(text="Maybe it's the model size. Or the hardware.", source="agent"),
        TrajectoryNote(text="We should probably benchmark this.", source="agent"),
        TrajectoryNote(text="Benchmark: p99 inference latency 340ms. Baseline target is 100ms.", source="tool_result", tool_name="benchmark"),
        TrajectoryNote(text="340ms is way over the 100ms target. This is clearly a problem.", source="agent"),
        TrajectoryNote(text="We might want to track the 340ms as a result somehow.", source="agent"),
        TrajectoryNote(text="Profiling the inference path.", source="agent"),
        TrajectoryNote(text="Profiler: 280ms of the 340ms is in the tokenization step. The model forward pass is only 60ms.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="Tokenization is 82% of the latency. That's unexpected.", source="agent"),
        TrajectoryNote(text="The tokenizer might be doing something inefficient.", source="agent"),
        TrajectoryNote(text="Or maybe we're tokenizing on CPU while the GPU is idle.", source="agent"),
        TrajectoryNote(text="Tokenization config: running on single-threaded CPU. The tokenizer is not parallelized.", source="tool_result", tool_name="profiler"),
        TrajectoryNote(text="Single-threaded tokenization is the issue.", source="agent"),
        TrajectoryNote(text="We should probably have a constraint about parallelizing tokenization.", source="agent"),
        TrajectoryNote(text="Parallelized tokenization with 4 threads: p99 latency now 87ms. Under the 100ms target.", source="tool_result", tool_name="benchmark"),
        TrajectoryNote(text="87ms is under target. That's the fix.", source="agent"),
        TrajectoryNote(text="We should record this as a result.", source="agent"),
        TrajectoryNote(text="Result for serving optimization: p99 inference latency 87ms after parallelized tokenization. Baseline was 340ms.", source="agent"),
        TrajectoryNote(text="Good. Result is now logged.", source="agent"),
        TrajectoryNote(text="Constraint: tokenization in the serving pipeline must use at least 4 parallel threads. Single-threaded tokenization is not acceptable for production serving.", source="agent"),
        TrajectoryNote(text="Constraint set. This should be enforced in the serving config.", source="agent"),
        TrajectoryNote(text="Maybe there's also a constraint about the hardware tier.", source="agent"),
        TrajectoryNote(text="Hardware tier is probably an ops decision, not a model constraint.", source="agent"),
        TrajectoryNote(text="Latency issue is resolved. Task done.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        # PATCHED: checks={} — spaces vs underscores in metric_name is formatting noise
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={}),
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="results", target_id="340ms_result", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="hardware_tier", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="maybe_model_size", present=False, match_by="target_id"),
    ],
)

A4_ML_03 = Trajectory(
    id="a4_ml_03",
    description="Evaluation dataset contamination check: 1 issue and 1 learning land; adversarial notes attempt to resolve non-existent issues.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ml", "noise:adversarial", "noise:spurious_resolve"],
    notes=[
        TrajectoryNote(text="We should check whether any of our eval data leaked into training.", source="agent"),
        TrajectoryNote(text="There might be a contamination issue. Should resolve the contamination_issue.", source="agent"),
        TrajectoryNote(text="Actually, we haven't confirmed there is one yet.", source="agent"),
        TrajectoryNote(text="Running deduplication check between training and eval splits.", source="agent"),
        TrajectoryNote(text="0 exact duplicate examples found across train and eval.", source="tool_result", tool_name="dedup_check"),
        TrajectoryNote(text="No exact duplicates. But near-duplicates could still be a problem.", source="agent"),
        TrajectoryNote(text="Running fuzzy match at 90% similarity threshold.", source="agent"),
        TrajectoryNote(text="Fuzzy match: 147 near-duplicate pairs found between train and eval sets.", source="tool_result", tool_name="dedup_check"),
        TrajectoryNote(text="147 near-duplicates is a real contamination issue.", source="agent"),
        TrajectoryNote(text="We should track this as an issue.", source="agent"),
        TrajectoryNote(text="Maybe it's not that bad — 147 out of how many total examples?", source="agent"),
        TrajectoryNote(text="Total eval examples: 10,000. 147 near-duplicates = 1.47% contamination.", source="tool_result", tool_name="dedup_check"),
        TrajectoryNote(text="1.47% is meaningful. The eval performance might be inflated.", source="agent"),
        TrajectoryNote(text="We should resolve the dataset_quality issue.", source="agent"),
        TrajectoryNote(text="Wait — no such issue is open yet. Don't resolve something that isn't open.", source="agent"),
        TrajectoryNote(text="The 147 near-duplicates removed from eval set. Recalculating metrics.", source="tool_result", tool_name="dedup_check"),
        TrajectoryNote(text="Metrics recalculated: accuracy dropped 0.8 points after removing contaminated examples. Contamination issue resolved.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="0.8 point accuracy inflation from contamination. That's significant.", source="agent"),
        TrajectoryNote(text="Learning: deduplication against training data must be run on any eval set before it is used for benchmarking. Near-duplicate checking at 90% similarity is the minimum threshold.", source="agent"),
        TrajectoryNote(text="Good learning. Now documented.", source="agent"),
        TrajectoryNote(text="Task done. Contamination removed and metrics corrected.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="contamination_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="dataset_quality", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="maybe_not_that_bad", present=False, match_by="target_id"),
    ],
)

# PATCH: removed checks={"metric_name": "primary_task_accuracy"} → checks={}
# 'primary task accuracy' (with spaces) is a valid interpreter naming choice.
A4_ML_04 = Trajectory(
    id="a4_ml_04",
    description="Multi-task learning experiment: 1 decision and 1 result land; adversarial notes have incomplete payload fields.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ml", "noise:adversarial", "noise:incomplete_payload"],
    notes=[
        TrajectoryNote(text="We should probably decide whether to use multi-task or single-task training.", source="agent"),
        TrajectoryNote(text="Multi-task might help. Or it might hurt. Hard to say.", source="agent"),
        TrajectoryNote(text="There's a consideration around loss weighting.", source="agent"),
        TrajectoryNote(text="The loss weighting is something that needs to be handled carefully.", source="agent"),
        TrajectoryNote(text="Running multi-task vs single-task ablation for exp_031.", source="agent"),
        TrajectoryNote(text="Multi-task: primary task accuracy=0.887, auxiliary task accuracy=0.741.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="Single-task: primary task accuracy=0.861.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="Multi-task improves primary task by 2.6 points. That's meaningful.", source="agent"),
        TrajectoryNote(text="The result should be tracked somewhere.", source="agent"),
        TrajectoryNote(text="We might want to record a result for this experiment.", source="agent"),
        TrajectoryNote(text="Result for exp_031: multi-task training primary task accuracy=0.887 vs single-task baseline=0.861. Delta: +0.026.", source="agent"),
        TrajectoryNote(text="Good. Result is now captured.", source="agent"),
        TrajectoryNote(text="The loss weighting decision needs to be made.", source="agent"),
        TrajectoryNote(text="We used equal weighting in this experiment. Maybe task-proportional would be better.", source="agent"),
        TrajectoryNote(text="Or maybe uncertainty weighting.", source="agent"),
        TrajectoryNote(text="Uncertainty weighting ablation: primary task accuracy=0.883. Slightly worse than equal weighting.", source="tool_result", tool_name="eval"),
        TrajectoryNote(text="Equal weighting is better. That should be the decision.", source="agent"),
        TrajectoryNote(text="Decision: use equal loss weighting for multi-task training in this project. Uncertainty weighting and task-proportional weighting both underperformed in ablation.", source="agent"),
        TrajectoryNote(text="Decision set. Equal weighting is the standard now.", source="agent"),
        TrajectoryNote(text="Maybe we also need a constraint here. Something about minimum auxiliary task performance.", source="agent"),
        TrajectoryNote(text="That would be a constraint. We should probably have one.", source="agent"),
        TrajectoryNote(text="Task done. Ablation complete, decision recorded.", source="agent"),
    ],
    expected_outcomes=[
        # PATCHED: checks={} — spaces vs underscores in metric_name is formatting noise
        ExpectedOutcome(bucket="results", target_id="", present=True, match_by="fields", checks={}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="loss_weighting_consideration", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="minimum_auxiliary_performance", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="uncertainty_weighting", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="task_proportional", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A4 — L4 — OPS
# ===========================================================================

A4_OPS_01 = Trajectory(
    id="a4_ops_01",
    description="SLO definition for a new service: 1 constraint and 1 decision land; adversarial notes use imperative and hypothetical forms.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ops", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="We need to define SLOs for the new notification service.", source="agent"),
        TrajectoryNote(text="SLOs should probably be tracked somewhere.", source="agent"),
        TrajectoryNote(text="There might be a constraint about availability.", source="agent"),
        TrajectoryNote(text="99.9% availability is typical. Or maybe we need 99.95%.", source="agent"),
        TrajectoryNote(text="Depends on how critical notifications are to the user experience.", source="agent"),
        TrajectoryNote(text="Product review: push notifications are user-facing but not safety-critical. 99.9% availability is appropriate.", source="tool_result", tool_name="product_review"),
        TrajectoryNote(text="99.9% is confirmed. That should be the constraint.", source="agent"),
        TrajectoryNote(text="There should also be a latency SLO. Notifications should be fast.", source="agent"),
        TrajectoryNote(text="Maybe we should set a p95 latency target.", source="agent"),
        TrajectoryNote(text="Or p99. Depends on what we're optimizing for.", source="agent"),
        TrajectoryNote(text="Constraint: the notification service must maintain 99.9% availability (monthly) and p95 delivery latency under 500ms.", source="agent"),
        TrajectoryNote(text="Constraint is set. Good.", source="agent"),
        TrajectoryNote(text="We should also decide who owns the SLO review process.", source="agent"),
        TrajectoryNote(text="Ownership could be the platform team or the product team.", source="agent"),
        TrajectoryNote(text="Or shared ownership, which usually means no real ownership.", source="agent"),
        TrajectoryNote(text="Shared ownership is a bad pattern. We should avoid it.", source="agent"),
        TrajectoryNote(text="Decision: the platform team owns the SLO definition and monthly review for the notification service. Product team is consulted but not the owner.", source="agent"),
        TrajectoryNote(text="Ownership decision recorded.", source="agent"),
        TrajectoryNote(text="We might also want to decide on error budget policy.", source="agent"),
        TrajectoryNote(text="Error budget burn rate alerting would be useful.", source="agent"),
        TrajectoryNote(text="This could be another constraint. Or a decision. Or an action item.", source="agent"),
        TrajectoryNote(text="Let me not over-complicate this. The core SLOs are set.", source="agent"),
        TrajectoryNote(text="SLO documentation published. Task is complete.", source="tool_result", tool_name="docs_publish"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="maybe_99_95", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="shared_ownership", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="error_budget", present=False, match_by="target_id"),
    ],
)

A4_OPS_02 = Trajectory(
    id="a4_ops_02",
    description="Runbook update for a database failover procedure: 1 plan and 1 learning land; adversarial notes include imperative spurious resolves.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ops", "noise:adversarial", "noise:spurious_resolve"],
    notes=[
        TrajectoryNote(text="The database failover runbook is outdated. We should update it.", source="agent"),
        TrajectoryNote(text="Resolve the runbook_outdated issue.", source="agent"),
        TrajectoryNote(text="Wait — there's no such issue open. The runbook being outdated is just a known gap.", source="agent"),
        TrajectoryNote(text="Plan: audit the current runbook, identify gaps from the last three failover incidents, and update with correct procedures.", source="agent"),
        TrajectoryNote(text="Starting the runbook audit.", source="agent"),
        TrajectoryNote(text="The runbook should probably reference the new monitoring dashboard.", source="agent"),
        TrajectoryNote(text="And it probably needs to be updated for the new DB cluster topology.", source="agent"),
        TrajectoryNote(text="Runbook audit complete. Four gaps identified: missing arbiter health check, outdated connection string, wrong rollback command syntax, missing escalation contacts.", source="tool_result", tool_name="runbook_audit"),
        TrajectoryNote(text="Four gaps. That's significant. All need to be fixed.", source="agent"),
        TrajectoryNote(text="The arbiter health check gap is the most dangerous one.", source="agent"),
        TrajectoryNote(text="We should resolve the arbiter_health_issue.", source="agent"),
        TrajectoryNote(text="That issue doesn't exist. This is a runbook gap, not a tracked issue.", source="agent"),
        TrajectoryNote(text="All four runbook gaps addressed. Arbiter health check section added. Connection string updated. Rollback command corrected. Escalation contacts updated.", source="tool_result", tool_name="runbook_update"),
        TrajectoryNote(text="Runbook is now accurate and up to date.", source="agent"),
        TrajectoryNote(text="We should track a learning from this about how runbooks get out of date.", source="agent"),
        TrajectoryNote(text="Learning: runbooks must be reviewed and re-validated after every major infrastructure change (cluster topology, tooling updates, personnel changes). A runbook that doesn't reflect the current system is worse than no runbook.", source="agent"),
        TrajectoryNote(text="Learning captured.", source="agent"),
        TrajectoryNote(text="Task complete.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="plan", target_id="main", present=True, match_by="target_id", checks={}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="runbook_outdated", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="arbiter_health_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="reference_dashboard", present=False, match_by="target_id"),
    ],
)

A4_OPS_03 = Trajectory(
    id="a4_ops_03",
    description="Cloud cost anomaly investigation: 1 issue and 1 decision land; adversarial notes mimic both and include meta-commentary.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ops", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Monthly cloud cost anomaly detected. Something seems off.", source="agent"),
        TrajectoryNote(text="There might be an issue worth opening here.", source="agent"),
        TrajectoryNote(text="Or we should just investigate first.", source="agent"),
        TrajectoryNote(text="Cost report: EC2 spend up 340% month-over-month. $8,400 in unexpected compute charges.", source="tool_result", tool_name="cost_report"),
        TrajectoryNote(text="340% increase is massive. This is definitely a real issue.", source="agent"),
        TrajectoryNote(text="Could be orphaned instances, a runaway autoscaler, or a configuration error.", source="agent"),
        TrajectoryNote(text="Checking for orphaned instances.", source="agent"),
        TrajectoryNote(text="Found 17 EC2 instances with no tags and no traffic. Running since a failed deployment 3 weeks ago.", source="tool_result", tool_name="ec2_audit"),
        TrajectoryNote(text="17 orphaned instances from a failed deployment. Root cause found.", source="agent"),
        TrajectoryNote(text="That explains most of the cost overrun.", source="agent"),
        TrajectoryNote(text="We should probably also check if the autoscaler is misconfigured.", source="agent"),
        TrajectoryNote(text="Autoscaler config looks correct. Scale-down policy is properly set.", source="tool_result", tool_name="ec2_audit"),
        TrajectoryNote(text="Autoscaler is fine. Orphaned instances are the sole cause.", source="agent"),
        TrajectoryNote(text="We should terminate the orphaned instances.", source="agent"),
        TrajectoryNote(text="17 orphaned instances terminated. EC2 spend is back to baseline.", source="tool_result", tool_name="ec2_console"),
        TrajectoryNote(text="Cost anomaly is resolved.", source="agent"),
        TrajectoryNote(text="We should decide something about preventing this in the future.", source="agent"),
        TrajectoryNote(text="A lifecycle policy that automatically terminates untagged instances after 24 hours would help.", source="agent"),
        TrajectoryNote(text="Decision: implement an EC2 lifecycle policy that terminates any untagged instance older than 24 hours. Notifications sent at 12 and 23 hours before termination.", source="agent"),
        TrajectoryNote(text="Good decision. That prevents future orphaned instances.", source="agent"),
        TrajectoryNote(text="Maybe we also need a constraint about tagging.", source="agent"),
        TrajectoryNote(text="A tagging constraint might overlap with existing policy.", source="agent"),
        TrajectoryNote(text="Let's not create duplicate policy. The lifecycle decision is sufficient.", source="agent"),
        TrajectoryNote(text="Task complete.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="", present=True, match_by="fields", checks={"status": "resolved"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="something_seems_off", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="autoscaler_misconfigured", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="tagging_constraint", present=False, match_by="target_id"),
    ],
)

A4_OPS_04 = Trajectory(
    id="a4_ops_04",
    description="Incident comms process gap: 1 constraint and 1 learning land; adversarial notes are mostly vague directives and ownership ambiguity.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:ops", "noise:adversarial", "noise:ownership_ambiguity"],
    notes=[
        TrajectoryNote(text="The incident communications process needs to be reviewed.", source="agent"),
        TrajectoryNote(text="There might be a constraint we should add about customer comms.", source="agent"),
        TrajectoryNote(text="Or maybe it's a decision about who owns the comms.", source="agent"),
        TrajectoryNote(text="We should probably open an issue for this process gap.", source="agent"),
        TrajectoryNote(text="Incident post-mortem review: customer notifications were sent 2 hours after detection during the last P1 incident. SLA requires 30-minute customer notification.", source="tool_result", tool_name="post_mortem"),
        TrajectoryNote(text="2 hours vs 30 minutes is a real gap. This is a compliance issue.", source="agent"),
        TrajectoryNote(text="Who was responsible for sending the notifications?", source="agent"),
        TrajectoryNote(text="The comms lead said it was the on-call's job. The on-call said it was the comms lead's job.", source="agent"),
        TrajectoryNote(text="Unclear ownership is the real problem.", source="agent"),
        TrajectoryNote(text="We should resolve the comms_ownership issue.", source="agent"),
        TrajectoryNote(text="There's no such issue open. This is the diagnosis, not a resolution.", source="agent"),
        TrajectoryNote(text="The root cause is unambiguously unclear ownership combined with no documented procedure.", source="tool_result", tool_name="post_mortem"),
        TrajectoryNote(text="So we need both a constraint about timing and a decision about ownership.", source="agent"),
        TrajectoryNote(text="Constraint: for any P1 incident, customer notification must be sent within 30 minutes of detection. The on-call incident commander is responsible.", source="agent"),
        TrajectoryNote(text="Constraint set. Now the ownership is baked into the constraint.", source="agent"),
        TrajectoryNote(text="Do we also need a separate decision about the comms process?", source="agent"),
        TrajectoryNote(text="Or is the constraint sufficient?", source="agent"),
        TrajectoryNote(text="The constraint covers the timing and ownership. A process doc is an implementation detail.", source="agent"),
        TrajectoryNote(text="Learning: incident response runbooks must explicitly name a single owner for every customer-facing communication. Shared or assumed ownership leads to notification failures under pressure.", source="agent"),
        TrajectoryNote(text="Learning captured. Constraint and learning are the outputs of this review.", source="agent"),
        TrajectoryNote(text="Task complete.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="comms_ownership", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="comms_process_doc", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="process_gap", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# A4 — L4 — POLICY
# ===========================================================================

A4_POLICY_01 = Trajectory(
    id="a4_policy_01",
    description="AI model procurement policy: 1 constraint and 1 decision land amid adversarial meta-commentary and vague directives.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:policy", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="We need to define a policy for procuring and deploying third-party AI models.", source="agent"),
        TrajectoryNote(text="This is probably something that needs a constraint.", source="agent"),
        TrajectoryNote(text="Or maybe a decision. Or both. Hard to know without more context.", source="agent"),
        TrajectoryNote(text="There are a few risks: IP infringement from training data, GDPR from processing personal data, bias from unaudited models.", source="agent"),
        TrajectoryNote(text="We should probably track each of those as an issue.", source="agent"),
        TrajectoryNote(text="Actually, they're not issues yet — they're risk categories.", source="agent"),
        TrajectoryNote(text="Legal and DPO review complete: GDPR is the highest-priority risk. Any AI model that processes personal data must have a DPIA completed before deployment.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="DPIA requirement is clear. That should be a constraint.", source="agent"),
        TrajectoryNote(text="The IP and bias risks are lower priority but worth tracking.", source="agent"),
        TrajectoryNote(text="Or maybe we don't need to track them yet — they're hypothetical.", source="agent"),
        TrajectoryNote(text="Constraint: any third-party AI model that processes personal data must have a completed and approved DPIA before being deployed to production.", source="agent"),
        TrajectoryNote(text="Good. Constraint is set.", source="agent"),
        TrajectoryNote(text="We also need to decide who approves AI model procurement.", source="agent"),
        TrajectoryNote(text="It could be engineering, legal, or a joint committee.", source="agent"),
        TrajectoryNote(text="Joint committees are slow. Legal-only is also slow. Engineering-only misses risk.", source="agent"),
        TrajectoryNote(text="DPO recommendation: engineering lead + DPO sign-off required for any AI model handling personal data. Single reviewer for models that don't.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="That's the right governance structure. Should be a decision.", source="agent"),
        TrajectoryNote(text="Decision: AI model procurement requires engineering lead + DPO approval for models handling personal data, and engineering lead approval only for models that do not.", source="agent"),
        TrajectoryNote(text="Decision recorded.", source="agent"),
        TrajectoryNote(text="Maybe we also need something about model documentation requirements.", source="agent"),
        TrajectoryNote(text="Documentation requirements could be a constraint or part of the DPIA process.", source="agent"),
        TrajectoryNote(text="Let's keep scope tight. The DPIA constraint covers documentation implicitly.", source="agent"),
        TrajectoryNote(text="Policy document drafted. Task complete.", source="tool_result", tool_name="policy_publish"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="ip_infringement", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="bias_risk", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="documentation_requirements", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="joint_committee", present=False, match_by="target_id"),
    ],
)

A4_POLICY_02 = Trajectory(
    id="a4_policy_02",
    description="Whistleblower policy gap: 1 constraint and 1 learning land; adversarial notes include unresolvable spurious actions.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:policy", "noise:adversarial", "noise:spurious_resolve"],
    notes=[
        TrajectoryNote(text="HR flagged a gap: we don't have a formal whistleblower protection policy.", source="agent"),
        TrajectoryNote(text="We should resolve the whistleblower_policy issue.", source="agent"),
        TrajectoryNote(text="No such issue is open. This is the initial finding.", source="agent"),
        TrajectoryNote(text="A whistleblower policy is probably legally required in some jurisdictions.", source="agent"),
        TrajectoryNote(text="Or maybe it's just best practice. Not sure.", source="agent"),
        TrajectoryNote(text="Legal review: EU Whistleblowing Directive (2019/1937) requires formal internal reporting channels for companies with 50+ employees. We have 200.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="It's legally required. That settles it.", source="agent"),
        TrajectoryNote(text="The policy needs to cover: anonymous reporting, non-retaliation, investigation timelines, and escalation paths.", source="agent"),
        TrajectoryNote(text="Or maybe not all of those — some might be optional.", source="agent"),
        TrajectoryNote(text="Legal clarification: all four elements are required under the Directive.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="All four are required. Good.", source="agent"),
        TrajectoryNote(text="We should probably also close the whistleblower_gap issue.", source="agent"),
        TrajectoryNote(text="There's still no open issue by that name.", source="agent"),
        TrajectoryNote(text="Constraint: the company must maintain a formal whistleblower reporting channel that meets EU Directive 2019/1937 requirements: anonymous reporting, non-retaliation guarantee, 7-day acknowledgment, and 3-month investigation timeline.", source="agent"),
        TrajectoryNote(text="Constraint is set.", source="agent"),
        TrajectoryNote(text="Learning: regulatory compliance gaps are not automatically tracked unless someone explicitly creates an issue or constraint for them. The gap existed for 2 years without being flagged.", source="agent"),
        TrajectoryNote(text="Good learning.", source="agent"),
        TrajectoryNote(text="Policy drafting in progress. Task is in progress.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="learnings", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "in_progress"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="whistleblower_policy", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="issues", target_id="whistleblower_gap", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="maybe_optional", present=False, match_by="target_id"),
    ],
)

A4_POLICY_03 = Trajectory(
    id="a4_policy_03",
    description="Supplier diversity policy: 1 decision lands amid adversarial deliberation and competing framings.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:policy", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Board requested a supplier diversity policy. Need to define what this means operationally.", source="agent"),
        TrajectoryNote(text="This could be a target, a constraint, or a reporting requirement.", source="agent"),
        TrajectoryNote(text="Or it could be aspirational rather than binding.", source="agent"),
        TrajectoryNote(text="Aspirational policies are often ignored. We should make it binding.", source="agent"),
        TrajectoryNote(text="Or maybe binding is too strong given the market constraints.", source="agent"),
        TrajectoryNote(text="Industry benchmarks reviewed: 30% diverse supplier spend is the median for companies our size and sector.", source="tool_result", tool_name="benchmark_review"),
        TrajectoryNote(text="30% seems achievable. We're currently at 12%.", source="agent"),
        TrajectoryNote(text="We could set 20% as a near-term target and 30% as a 3-year target.", source="agent"),
        TrajectoryNote(text="Or we could just set 30% directly and give ourselves 3 years.", source="agent"),
        TrajectoryNote(text="Setting two targets is confusing. One target is cleaner.", source="agent"),
        TrajectoryNote(text="Procurement team input: 30% in 3 years is achievable without disrupting existing supplier relationships.", source="tool_result", tool_name="procurement_review"),
        TrajectoryNote(text="30% in 3 years is confirmed achievable.", source="agent"),
        TrajectoryNote(text="Decision: set a binding target of 30% diverse supplier spend by end of 2027. Progress to be reported in the annual sustainability report.", source="agent"),
        TrajectoryNote(text="Decision recorded.", source="agent"),
        TrajectoryNote(text="We might also need a constraint about how 'diverse supplier' is defined.", source="agent"),
        TrajectoryNote(text="Or that could be handled in the policy documentation rather than as a constraint.", source="agent"),
        TrajectoryNote(text="Let's keep the schema clean. The decision is the key output.", source="agent"),
        TrajectoryNote(text="Policy approved by board. Task complete.", source="tool_result", tool_name="board_approval"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="decisions", target_id="20_percent_target", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="diverse_supplier_definition", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="aspirational", present=False, match_by="target_id"),
    ],
)

A4_POLICY_04 = Trajectory(
    id="a4_policy_04",
    description="Export control compliance review: 1 constraint lands; adversarial notes include unresolvable imperatives and category confusion.",
    agent_id="benchmark_agent",
    tags=["family:a", "difficulty:l4", "domain:policy", "noise:adversarial"],
    notes=[
        TrajectoryNote(text="Legal flagged that our software might be subject to US export controls (EAR).", source="agent"),
        TrajectoryNote(text="We should probably track this as an issue.", source="agent"),
        TrajectoryNote(text="Or it might be a constraint. Not sure which.", source="agent"),
        TrajectoryNote(text="Export controls are complex. I don't know if EAR applies to us.", source="agent"),
        TrajectoryNote(text="We should resolve the export_control_issue.", source="agent"),
        TrajectoryNote(text="No such issue exists. We need to investigate first.", source="agent"),
        TrajectoryNote(text="EAR classification review: our core product includes encryption functionality (AES-256). This triggers EAR classification under ECCN 5E002.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="We're in scope for EAR. That's confirmed.", source="agent"),
        TrajectoryNote(text="What does that mean operationally? Do we need a license?", source="agent"),
        TrajectoryNote(text="Or is there an exemption for widely available software?", source="agent"),
        TrajectoryNote(text="Legal opinion: mass-market encryption software may qualify for License Exception ENC, but requires annual self-classification and a notification filing with BIS.", source="tool_result", tool_name="legal_review"),
        TrajectoryNote(text="We can use the exception but we need to file annually. That's a process requirement.", source="agent"),
        TrajectoryNote(text="This seems like a constraint. We must file annually.", source="agent"),
        TrajectoryNote(text="Or it could be a decision — we're deciding to use the ENC exception.", source="agent"),
        TrajectoryNote(text="It's both. But the constraint is more durable than the decision.", source="agent"),
        TrajectoryNote(text="Constraint: the company must complete an annual EAR self-classification and file a BIS notification to maintain License Exception ENC eligibility for all products containing AES-256 encryption.", source="agent"),
        TrajectoryNote(text="Constraint is set. Legal team will own the annual filing.", source="agent"),
        TrajectoryNote(text="Maybe there's also something about employee training on export controls.", source="agent"),
        TrajectoryNote(text="Training is a good idea but probably out of scope for this task.", source="agent"),
        TrajectoryNote(text="Task complete. Constraint documented.", source="agent"),
    ],
    expected_outcomes=[
        ExpectedOutcome(bucket="constraints", target_id="", present=True, match_by="fields", checks={"status": "active"}),
        ExpectedOutcome(bucket="task_state", target_id="", present=True, match_by="fields", checks={"status": "done"}),
    ],
    forbidden_outcomes=[
        ExpectedOutcome(bucket="issues", target_id="export_control_issue", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="decisions", target_id="enc_exception", present=False, match_by="target_id"),
        ExpectedOutcome(bucket="constraints", target_id="employee_training", present=False, match_by="target_id"),
    ],
)


# ===========================================================================
# Registry
# ===========================================================================

ALL_TRAJECTORIES: list[Trajectory] = [
    # A1 — L1
    A1_SOFTWARE_01, A1_SOFTWARE_02, A1_SOFTWARE_03, A1_SOFTWARE_04,
    A1_ML_01, A1_ML_02, A1_ML_03, A1_ML_04,
    A1_OPS_01, A1_OPS_02, A1_OPS_03, A1_OPS_04,
    A1_POLICY_01, A1_POLICY_02, A1_POLICY_03, A1_POLICY_04,
    # A2 — L2
    A2_SOFTWARE_01, A2_SOFTWARE_02, A2_SOFTWARE_03, A2_SOFTWARE_04,
    A2_ML_01, A2_ML_02, A2_ML_03, A2_ML_04,
    A2_OPS_01, A2_OPS_02, A2_OPS_03, A2_OPS_04,
    A2_POLICY_01, A2_POLICY_02, A2_POLICY_03, A2_POLICY_04,
    # A3 — L3
    A3_SOFTWARE_01, A3_SOFTWARE_02, A3_SOFTWARE_03, A3_SOFTWARE_04,
    A3_ML_01, A3_ML_02, A3_ML_03, A3_ML_04,
    A3_OPS_01, A3_OPS_02, A3_OPS_03, A3_OPS_04,
    A3_POLICY_01, A3_POLICY_02, A3_POLICY_03, A3_POLICY_04,
    # A4 — L4
    A4_SOFTWARE_01, A4_SOFTWARE_02, A4_SOFTWARE_03, A4_SOFTWARE_04,
    A4_ML_01, A4_ML_02, A4_ML_03, A4_ML_04,
    A4_OPS_01, A4_OPS_02, A4_OPS_03, A4_OPS_04,
    A4_POLICY_01, A4_POLICY_02, A4_POLICY_03, A4_POLICY_04,
]
