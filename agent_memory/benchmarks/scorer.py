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
import re
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

STATUS_FIELDS = {"status"}
METRIC_NAME_FIELDS = {"metric_name"}
SEMANTIC_TEXT_FIELDS = {"text", "statement", "title"}

STATUS_ALIASES = {
    "in progress": "in_progress",
    "in-progress": "in_progress",
}

METRIC_NAME_ALIASES = {
    "accuracy": "validation_accuracy",
    "val_accuracy": "validation_accuracy",
    "val_accuracy_final": "validation_accuracy",
    "val_accuracy_best": "validation_accuracy",
    "val_accuracy_metric": "validation_accuracy",
}

LEADING_FIELD_PREFIXES = (
    "constraint:",
    "decision:",
    "learning:",
    "plan:",
    "result:",
)

SEMANTIC_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "its", "of", "on", "or", "rather", "that", "the",
    "their", "them", "then", "this", "to", "use", "using", "we", "will",
    "with", "without",
}


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
    governance_accuracy: float
    false_positive_count: int
    false_negative_count: int
    field_mismatch_count: int
    surplus_row_count: int

    def summary_lines(self) -> list[str]:
        """Return a human-readable summary as a list of strings."""
        lines = [
            f"Trajectory : {self.trajectory_id}",
            f"Canonical  : {self.canonical_accuracy:.0%} ({self.passed}/{self.total})",
            f"Governance : {self.governance_accuracy:.0%}",
            f"False pos  : {self.false_positive_count}",
            f"False neg  : {self.false_negative_count}",
            f"Field miss : {self.field_mismatch_count}",
            f"Surplus    : {self.surplus_row_count}",
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

    def score(
        self,
        snapshot: dict,
        trajectory: Trajectory,
        include_surplus: bool = False,
    ) -> TrajectoryScore:
        """
        Check each ExpectedOutcome in the trajectory against the snapshot.
        Returns a TrajectoryScore with per-outcome results and aggregate metrics.
        """
        if "__scratchpad__" in snapshot:
            return self._score_scratchpad(snapshot["__scratchpad__"], trajectory)

        authored_results: list[OutcomeResult] = []

        for outcome in trajectory.expected_outcomes:
            result = self._check_outcome(outcome, snapshot)
            authored_results.append(result)

        for outcome in trajectory.forbidden_outcomes:
            result = self._check_outcome(outcome, snapshot)
            authored_results.append(result)

        surplus_results: list[OutcomeResult] = []
        if include_surplus and "family:a" in trajectory.tags:
            surplus_results = self._family_a_surplus_results(
                snapshot, trajectory, authored_results
            )

        total = len(authored_results)
        passed = sum(1 for r in authored_results if r.passed)
        failed = total - passed

        false_positive_count = sum(
            1 for r in authored_results
            if not r.passed and not r.outcome.present
        )
        false_negative_count = sum(
            1 for r in authored_results
            if not r.passed and r.outcome.present and r.actual_row is None
        )
        field_mismatch_count = sum(
            1 for r in authored_results
            if not r.passed and r.outcome.present and r.actual_row is not None
        )
        surplus_row_count = len(surplus_results)

        canonical_accuracy = passed / total if total > 0 else 0.0
        governance_denominator = total + surplus_row_count
        governance_accuracy = passed / governance_denominator if governance_denominator > 0 else 0.0

        return TrajectoryScore(
            trajectory_id=trajectory.id,
            outcome_results=authored_results + surplus_results,
            total=total,
            passed=passed,
            failed=failed,
            canonical_accuracy=canonical_accuracy,
            governance_accuracy=governance_accuracy,
            false_positive_count=false_positive_count,
            false_negative_count=false_negative_count,
            field_mismatch_count=field_mismatch_count,
            surplus_row_count=surplus_row_count,
        )

    def _score_scratchpad(self, scratchpad: str, trajectory: Trajectory) -> TrajectoryScore:
        authored_results: list[OutcomeResult] = []
        for outcome in trajectory.expected_outcomes:
            authored_results.append(self._check_outcome_in_scratchpad(outcome, scratchpad))
        for outcome in trajectory.forbidden_outcomes:
            authored_results.append(self._check_forbidden_outcome_in_scratchpad(outcome, scratchpad))

        total = len(authored_results)
        passed = sum(1 for r in authored_results if r.passed)
        failed = total - passed
        false_positive_count = sum(
            1 for r in authored_results if not r.passed and not r.outcome.present
        )
        false_negative_count = sum(
            1 for r in authored_results if not r.passed and r.outcome.present and r.actual_row is None
        )
        field_mismatch_count = sum(
            1 for r in authored_results if not r.passed and r.outcome.present and r.actual_row is not None
        )
        canonical_accuracy = passed / total if total > 0 else 0.0
        return TrajectoryScore(
            trajectory_id=trajectory.id,
            outcome_results=authored_results,
            total=total,
            passed=passed,
            failed=failed,
            canonical_accuracy=canonical_accuracy,
            governance_accuracy=canonical_accuracy,
            false_positive_count=false_positive_count,
            false_negative_count=false_negative_count,
            field_mismatch_count=field_mismatch_count,
            surplus_row_count=0,
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

    def _check_outcome_in_scratchpad(
        self, outcome: ExpectedOutcome, scratchpad: str
    ) -> OutcomeResult:
        lines = [line.strip() for line in scratchpad.splitlines() if line.strip()]
        matching_lines = self._scratchpad_matching_lines(outcome, lines)

        if not outcome.present:
            if matching_lines:
                return OutcomeResult(
                    outcome=outcome,
                    passed=False,
                    failure_reason=(
                        f"Found {len(matching_lines)} scratchpad line(s) matching this forbidden outcome"
                    ),
                    actual_row={"line": matching_lines[0]},
                )
            return OutcomeResult(outcome=outcome, passed=True)

        if not matching_lines:
            reason = (
                f"No scratchpad evidence found for {outcome.bucket}"
                if outcome.match_by == "fields" or not outcome.target_id
                else f"No scratchpad evidence found for '{outcome.target_id}' in {outcome.bucket}"
            )
            return OutcomeResult(
                outcome=outcome,
                passed=False,
                failure_reason=reason,
                actual_row=None,
            )

        return OutcomeResult(
            outcome=outcome,
            passed=True,
            actual_row={"line": matching_lines[0]},
        )

    def _check_forbidden_outcome_in_scratchpad(
        self, outcome: ExpectedOutcome, scratchpad: str
    ) -> OutcomeResult:
        """
        Scratchpad stores raw notes, including noise. A forbidden outcome should
        only fail when the scratchpad evidence would actually support retrieving
        the forbidden item as if it were canonical state.
        """
        lines = [line.strip() for line in scratchpad.splitlines() if line.strip()]
        matching_lines = self._scratchpad_matching_lines(outcome, lines)

        if not matching_lines:
            return OutcomeResult(outcome=outcome, passed=True)

        # Raw presence in the notebook is expected. Only fail if the line looks
        # like an explicit structured state assertion rather than incidental text.
        misleading_lines = [
            line for line in matching_lines
            if self._line_looks_like_explicit_state(outcome.bucket, line)
        ]
        if not misleading_lines:
            return OutcomeResult(outcome=outcome, passed=True)

        return OutcomeResult(
            outcome=outcome,
            passed=False,
            failure_reason=(
                f"Found {len(misleading_lines)} scratchpad line(s) that could be "
                f"misread as canonical {outcome.bucket} state"
            ),
            actual_row={"line": misleading_lines[0]},
        )

    def _family_a_surplus_results(
        self,
        snapshot: dict,
        trajectory: Trajectory,
        outcome_results: list[OutcomeResult],
    ) -> list[OutcomeResult]:
        """
        Family A is about selective promotion. If a system retains extra rows in a
        bucket beyond the authored canonical target count, that is a governance
        failure even when a positive row also exists.

        To avoid double-counting, we only synthesize a surplus failure for buckets
        that do not already have a failed forbidden outcome.
        """
        results: list[OutcomeResult] = []
        expected_counts = self._expected_bucket_counts(trajectory)

        for bucket, expected_count in expected_counts.items():
            actual_count = self._bucket_row_count(snapshot, bucket)
            if actual_count <= expected_count:
                continue

            already_failed_forbidden = any(
                (not r.passed) and (not r.outcome.present) and r.outcome.bucket == bucket
                for r in outcome_results
            )
            if already_failed_forbidden:
                continue

            synthetic_outcome = ExpectedOutcome(
                bucket=bucket,
                target_id="__surplus__",
                present=False,
                match_by="target_id",
            )
            results.append(
                OutcomeResult(
                    outcome=synthetic_outcome,
                    passed=False,
                    failure_reason=(
                        f"Found {actual_count - expected_count} extra row(s) in {bucket} "
                        f"beyond expected canonical count {expected_count}"
                    ),
                    actual_row={"row_count": actual_count},
                )
            )

        return results

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
            normalized_expected = self._normalize_field_value(field_name, expected_value)
            normalized_actual = self._normalize_field_value(field_name, actual_value)
            if field_name in SEMANTIC_TEXT_FIELDS:
                expected_text = str(normalized_expected)
                actual_text = str(normalized_actual)
                expected_tokens = self._semantic_tokens(expected_text)
                actual_tokens = self._semantic_tokens(actual_text)
                semantically_matches = (
                    actual_text == expected_text
                    or expected_text in actual_text
                    or actual_text in expected_text
                    or (expected_tokens and expected_tokens.issubset(actual_tokens))
                )
                if not semantically_matches:
                    mismatches.append(
                        f"{field_name}: expected '{expected_value}' got '{actual_value}'"
                    )
                continue

            if normalized_actual != normalized_expected:
                mismatches.append(
                    f"{field_name}: expected '{expected_value}' got '{actual_value}'"
                )
        return mismatches

    def _scratchpad_matching_lines(self, outcome: ExpectedOutcome, lines: list[str]) -> list[str]:
        matches: list[str] = []
        for line in lines:
            if self._scratchpad_line_matches(outcome, line):
                matches.append(line)
        return matches

    def _scratchpad_line_matches(self, outcome: ExpectedOutcome, line: str) -> bool:
        normalized_line = self._normalize_semantic_text(line)
        line_tokens = self._semantic_tokens(normalized_line)

        if outcome.bucket == "plan":
            if "plan:" not in line.lower():
                return False
            return outcome.target_id in {"", "main"}

        if outcome.checks:
            for field_name, expected_value in outcome.checks.items():
                if not self._scratchpad_field_matches(outcome.bucket, field_name, expected_value, line, normalized_line, line_tokens):
                    return False
            return True

        if outcome.target_id:
            target_phrase = outcome.target_id.replace("_", " ")
            target_tokens = self._semantic_tokens(target_phrase)
            if target_tokens:
                return target_tokens.issubset(line_tokens)
            return target_phrase in normalized_line

        return False

    def _scratchpad_field_matches(
        self,
        bucket: str,
        field_name: str,
        expected_value: Any,
        line: str,
        normalized_line: str,
        line_tokens: set[str],
    ) -> bool:
        if field_name in SEMANTIC_TEXT_FIELDS:
            expected_text = self._normalize_semantic_text(str(expected_value))
            expected_tokens = self._semantic_tokens(expected_text)
            return (
                expected_text in normalized_line
                or normalized_line in expected_text
                or (expected_tokens and expected_tokens.issubset(line_tokens))
            )

        if field_name in STATUS_FIELDS:
            expected_status = self._normalize_status(str(expected_value))
            line_status = self._infer_status_from_line(bucket, line)
            return line_status == expected_status

        if field_name in METRIC_NAME_FIELDS:
            expected_metric = self._normalize_field_value(field_name, expected_value)
            return str(expected_metric) in normalized_line.replace(" ", "_")

        expected_str = str(expected_value).strip().lower()
        return expected_str in normalized_line

    def _line_looks_like_explicit_state(self, bucket: str, line: str) -> bool:
        lowered = line.lower()
        if bucket == "plan":
            return "plan:" in lowered
        if bucket == "constraints":
            return "constraint:" in lowered
        if bucket == "decisions":
            return "decision:" in lowered
        if bucket == "learnings":
            return "learning:" in lowered
        if bucket == "task_state":
            return any(token in lowered for token in ["task state:", "status:", "task is ", "task complete", "task blocked"])
        if bucket == "results":
            return any(token in lowered for token in ["result:", "result for", "accuracy", "auc", "f1", "latency", "loss", "="])
        if bucket == "issues":
            return any(token in lowered for token in ["issue:", "error", "failed", "failure", "incident", "blocked", "root cause"])
        return False

    def _infer_status_from_line(self, bucket: str, line: str) -> str:
        lowered = line.lower()
        if bucket in {"constraints", "decisions", "learnings"}:
            if any(token in lowered for token in ["invalidated", "superseded", "reverted", "rolled back"]):
                return "invalidated"
            return "active"
        if bucket == "task_state":
            return self._normalize_status(line)
        if any(token in lowered for token in ["resolved", "fixed", "all checks passed", "green runs confirmed"]):
            return "resolved"
        if any(token in lowered for token in ["open", "failed", "error", "incident", "blocked", "blocking"]):
            return "open"
        return self._normalize_status(line)

    def _normalize_field_value(self, field_name: str, value: Any) -> Any:
        """Normalize known low-information formatting variants before comparison."""
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()

        if field_name in STATUS_FIELDS:
            return self._normalize_status(value)

        if field_name in METRIC_NAME_FIELDS:
            normalized = normalized.replace("-", "_").replace(" ", "_")
            return METRIC_NAME_ALIASES.get(normalized, normalized)

        if field_name in SEMANTIC_TEXT_FIELDS:
            return self._normalize_semantic_text(value)

        return value

    def _normalize_status(self, value: str) -> str:
        lowered = " ".join(value.strip().lower().split())
        collapsed = lowered.replace("-", "_").replace(" ", "_")

        if any(token in lowered for token in ["blocked", "cannot proceed"]):
            return "blocked"
        if any(token in lowered for token in ["failed", "failure"]):
            return "failed"
        if any(token in lowered for token in ["done", "complete", "completed", "closed"]):
            return "done"
        if "pending" in lowered:
            return "pending"
        if "progress" in lowered:
            return "in_progress"

        return STATUS_ALIASES.get(lowered, collapsed)

    def _normalize_semantic_text(self, value: str) -> str:
        """
        Normalize low-information phrasing differences for semantic text fields.
        This keeps the benchmark focused on state correctness rather than whether
        a system preserved leading markers like 'Constraint:' verbatim.
        """
        normalized = " ".join(value.strip().split())
        lowered = normalized.lower()

        for marker in ("Decision:", "Constraint:", "Learning:", "Plan:", "Result:"):
            if marker in normalized:
                normalized = normalized.split(marker, 1)[1].strip()
                lowered = normalized.lower()
                break

        for prefix in LEADING_FIELD_PREFIXES:
            if lowered.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break

        return normalized.lower()

    def _semantic_tokens(self, value: str) -> set[str]:
        words = re.findall(r"[a-z0-9_]+", value.lower())
        return {
            word for word in words
            if word not in SEMANTIC_STOPWORDS and len(word) > 1
        }

    def _expected_bucket_counts(self, trajectory: Trajectory) -> dict[str, int]:
        counts: dict[str, int] = {bucket: 0 for bucket in BUCKET_PK}
        for outcome in trajectory.expected_outcomes:
            if not outcome.present:
                continue
            if outcome.bucket in SINGLE_ROW_BUCKETS:
                counts[outcome.bucket] = 1
            else:
                counts[outcome.bucket] = counts.get(outcome.bucket, 0) + 1
        return counts

    def _bucket_row_count(self, snapshot: dict, bucket: str) -> int:
        bucket_data = snapshot.get(bucket)
        if bucket in SINGLE_ROW_BUCKETS:
            return 1 if isinstance(bucket_data, dict) else 0
        if isinstance(bucket_data, list):
            return len(bucket_data)
        return 0
