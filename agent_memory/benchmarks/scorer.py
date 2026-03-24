"""
Scores a SharedMemory snapshot against a Trajectory's expected outcomes.

Takes:
    - snapshot: dict returned by SharedMemory.snapshot()
    - trajectory: Trajectory with expected_outcomes

Produces:
    - TrajectoryScore: structured pass/fail results per outcome + aggregate metrics

The scorer is pure — no database access, no API calls, no side effects.
It only compares dicts against expected outcomes.

Metrics produced (per trajectory):
    canonical_accuracy      — fraction of expected outcomes that passed
    false_positive_count    — rows present that should not be (present=False outcomes that failed)
    false_negative_count    — rows absent that should be present (present=True outcomes that failed)
    field_mismatch_count    — rows present but with wrong field values
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from benchmarks.trajectories.schema import ExpectedOutcome, Trajectory


# ---------------------------------------------------------------------------
# PK column name per bucket
# Used to look up a specific row in a list by target_id
# ---------------------------------------------------------------------------

BUCKET_PK: dict[str, str] = {
    "plan":        "target_id",
    "constraints": "constraint_id",
    "issues":      "issue_id",
    "decisions":   "decision_id",
    "results":     "result_id",
    "task_state":  "task_id",
    "learnings":   "learning_id",
}

# Buckets where snapshot returns a single dict (or None) rather than a list
SINGLE_ROW_BUCKETS = {"plan"}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class OutcomeResult:
    """
    Result of checking one ExpectedOutcome against the snapshot.

    Fields:
        outcome         — the ExpectedOutcome that was checked
        passed          — True if the outcome matched the snapshot
        failure_reason  — human-readable explanation if passed=False, else ""
        actual_row      — the row found in the snapshot (or None if not found)
    """
    outcome: ExpectedOutcome
    passed: bool
    failure_reason: str = ""
    actual_row: Optional[dict] = None


@dataclass
class TrajectoryScore:
    """
    Aggregate score for one trajectory run.

    Fields:
        trajectory_id           — matches Trajectory.id
        outcome_results         — one OutcomeResult per ExpectedOutcome
        total                   — total number of expected outcomes checked
        passed                  — number that passed
        failed                  — number that failed
        canonical_accuracy      — passed / total (0.0–1.0)
        false_positive_count    — present=False outcomes that failed (row exists but shouldn't)
        false_negative_count    — present=True outcomes that failed due to missing row
        field_mismatch_count    — present=True outcomes that failed due to wrong field values
    """
    trajectory_id: str
    outcome_results: list[OutcomeResult]
    total: int
    passed: int
    failed: int
    canonical_accuracy: float
    false_positive_count: int
    false_negative_count: int
    field_mismatch_count: int

    def summary_lines(self) -> list[str]:
        """Return a human-readable summary as a list of strings."""
        lines = [
            f"Trajectory : {self.trajectory_id}",
            f"Accuracy   : {self.canonical_accuracy:.0%} ({self.passed}/{self.total})",
            f"False pos  : {self.false_positive_count}",
            f"False neg  : {self.false_negative_count}",
            f"Field miss : {self.field_mismatch_count}",
        ]
        for r in self.outcome_results:
            status = "PASS" if r.passed else "FAIL"
            label = f"  [{status}] {r.outcome.bucket}/{r.outcome.target_id}"
            if not r.passed:
                label += f" — {r.failure_reason}"
            lines.append(label)
        return lines


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class Scorer:
    """
    Pure scorer. No state between calls. Thread-safe.

    Usage:
        scorer = Scorer()
        score = scorer.score(snapshot, trajectory)
    """

    def score(self, snapshot: dict, trajectory: Trajectory) -> TrajectoryScore:
        """
        Check each ExpectedOutcome in the trajectory against the snapshot.
        Returns a TrajectoryScore with per-outcome results and aggregate metrics.
        """
        outcome_results: list[OutcomeResult] = []

        for outcome in trajectory.expected_outcomes:
            result = self._check_outcome(outcome, snapshot)
            outcome_results.append(result)

        for outcome in trajectory.forbidden_outcomes:
            result = self._check_outcome(outcome, snapshot)
            outcome_results.append(result)

        total = len(outcome_results)
        passed = sum(1 for r in outcome_results if r.passed)
        failed = total - passed

        false_positive_count = sum(
            1 for r in outcome_results
            if not r.passed and not r.outcome.present
        )
        false_negative_count = sum(
            1 for r in outcome_results
            if not r.passed and r.outcome.present and r.actual_row is None
        )
        field_mismatch_count = sum(
            1 for r in outcome_results
            if not r.passed and r.outcome.present and r.actual_row is not None
        )

        canonical_accuracy = passed / total if total > 0 else 0.0

        return TrajectoryScore(
            trajectory_id=trajectory.id,
            outcome_results=outcome_results,
            total=total,
            passed=passed,
            failed=failed,
            canonical_accuracy=canonical_accuracy,
            false_positive_count=false_positive_count,
            false_negative_count=false_negative_count,
            field_mismatch_count=field_mismatch_count,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_outcome(
        self, outcome: ExpectedOutcome, snapshot: dict
    ) -> OutcomeResult:
        """Check one ExpectedOutcome against the snapshot."""

        if outcome.match_by == "fields":
            return self._check_outcome_by_fields(outcome, snapshot)

        # Default: match_by="target_id"
        row = self._find_row(outcome.bucket, outcome.target_id, snapshot)

        # ── Case 1: row should NOT be present ─────────────────────────
        if not outcome.present:
            if row is None:
                return OutcomeResult(outcome=outcome, passed=True)
            else:
                return OutcomeResult(
                    outcome=outcome,
                    passed=False,
                    failure_reason=(
                        f"Row exists in {outcome.bucket} but should not be present"
                    ),
                    actual_row=row,
                )

        # ── Case 2: row SHOULD be present ─────────────────────────────
        if row is None:
            return OutcomeResult(
                outcome=outcome,
                passed=False,
                failure_reason=(
                    f"Row '{outcome.target_id}' not found in {outcome.bucket}"
                ),
                actual_row=None,
            )

        # Row exists — now check field-level assertions
        if not outcome.checks:
            return OutcomeResult(outcome=outcome, passed=True, actual_row=row)

        mismatches = self._check_fields(outcome.checks, row)
        if mismatches:
            return OutcomeResult(
                outcome=outcome,
                passed=False,
                failure_reason="; ".join(mismatches),
                actual_row=row,
            )

        return OutcomeResult(outcome=outcome, passed=True, actual_row=row)

    def _check_outcome_by_fields(
        self, outcome: ExpectedOutcome, snapshot: dict
    ) -> OutcomeResult:
        """
        match_by="fields": find any row in the bucket where all checks pass.
        Used when slug consistency is not the property being tested — only
        whether the right data landed anywhere in the bucket.
        """
        bucket_data = snapshot.get(outcome.bucket)

        if outcome.bucket in SINGLE_ROW_BUCKETS:
            rows = [bucket_data] if isinstance(bucket_data, dict) else []
        else:
            rows = bucket_data if isinstance(bucket_data, list) else []

        # ── Case 1: should NOT be present — no row should match checks ─
        if not outcome.present:
            matching = [r for r in rows if not self._check_fields(outcome.checks, r)]
            if matching:
                return OutcomeResult(
                    outcome=outcome,
                    passed=False,
                    failure_reason=(
                        f"Found {len(matching)} row(s) in {outcome.bucket} "
                        f"matching checks but none should exist"
                    ),
                    actual_row=matching[0],
                )
            return OutcomeResult(outcome=outcome, passed=True)

        # ── Case 2: SHOULD be present — at least one row must match ───
        if not rows:
            return OutcomeResult(
                outcome=outcome,
                passed=False,
                failure_reason=f"No rows found in {outcome.bucket}",
            )

        for row in rows:
            mismatches = self._check_fields(outcome.checks, row)
            if not mismatches:
                return OutcomeResult(outcome=outcome, passed=True, actual_row=row)

        # No row matched — report the closest miss (first row)
        mismatches = self._check_fields(outcome.checks, rows[0])
        return OutcomeResult(
            outcome=outcome,
            passed=False,
            failure_reason=f"No row matched checks: {'; '.join(mismatches)}",
            actual_row=rows[0],
        )

    def _find_row(
        self, bucket: str, target_id: str, snapshot: dict
    ) -> Optional[dict]:
        """
        Look up a row in the snapshot by bucket and target_id.
        Returns the row dict or None if not found.
        """
        bucket_data = snapshot.get(bucket)

        if bucket_data is None:
            return None

        # Single-row buckets (plan) — snapshot returns dict or None
        if bucket in SINGLE_ROW_BUCKETS:
            if isinstance(bucket_data, dict):
                pk_col = BUCKET_PK[bucket]
                if bucket_data.get(pk_col) == target_id:
                    return bucket_data
            return None

        # Multi-row buckets — snapshot returns list of dicts
        if not isinstance(bucket_data, list):
            return None

        pk_col = BUCKET_PK[bucket]
        for row in bucket_data:
            if row.get(pk_col) == target_id:
                return row

        return None

    def _check_fields(
        self, checks: dict[str, Any], row: dict
    ) -> list[str]:
        """
        Compare expected field values against the actual row.
        Returns a list of mismatch descriptions (empty if all match).
        """
        mismatches = []
        for field_name, expected_value in checks.items():
            actual_value = row.get(field_name)
            if actual_value != expected_value:
                mismatches.append(
                    f"{field_name}: expected '{expected_value}' got '{actual_value}'"
                )
        return mismatches
