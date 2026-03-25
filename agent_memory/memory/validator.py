import logging
import re
from typing import Optional

from memory.db.schema import get_valid_buckets
from memory.interpreter import WriteRequest
from memory.resolver import ResolvedWrite

logger = logging.getLogger(__name__)

SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


class ValidationError(Exception):
    pass


class Validator:
    """
    Structural validator for committed writes.
    """

    BUCKET_REQUIRED_PAYLOAD_FIELDS: dict[str, list[str]] = {
        "plan": ["plan_json"],
        "constraints": ["text"],
        "issues": ["title"],
        "decisions": ["statement"],
        "results": ["metric_name", "metric_value"],
        "task_state": ["status"],
        "learnings": ["statement"],
    }

    BUCKET_ALLOWED_OPERATIONS: dict[str, list[str]] = {
        "plan": ["upsert"],
        "constraints": ["upsert", "invalidate"],
        "issues": ["upsert", "resolve"],
        "decisions": ["append", "invalidate"],
        "results": ["append"],
        "task_state": ["upsert"],
        "learnings": ["append"],
    }

    def validate(
        self,
        write_request: WriteRequest,
        context: Optional[dict] = None,
        matched_target_id: Optional[str] = None,
    ) -> None:
        if write_request.decision != "accept":
            raise ValidationError(
                "Validator received a rejected WriteRequest - only accepted requests should be validated. "
                f"rationale: {write_request.rationale}"
            )

        valid_buckets = get_valid_buckets()
        if write_request.bucket not in valid_buckets:
            raise ValidationError(
                f"Unknown bucket '{write_request.bucket}'. Valid buckets: {valid_buckets}"
            )

        allowed_ops = self.BUCKET_ALLOWED_OPERATIONS[write_request.bucket]
        if write_request.operation not in allowed_ops:
            raise ValidationError(
                f"Operation '{write_request.operation}' is not allowed for bucket "
                f"'{write_request.bucket}'. Allowed: {allowed_ops}"
            )

        if not write_request.target_id or not write_request.target_id.strip():
            raise ValidationError("target_id must be a non-empty string.")
        if not SLUG_PATTERN.match(write_request.target_id):
            raise ValidationError(
                f"target_id '{write_request.target_id}' is not a valid slug. "
                "Use only alphanumeric characters, underscores, or hyphens - no spaces."
            )

        if write_request.payload is None:
            if write_request.operation not in ("resolve", "invalidate"):
                raise ValidationError(
                    f"payload is required for operation '{write_request.operation}' "
                    f"on bucket '{write_request.bucket}'."
                )
        elif not isinstance(write_request.payload, dict):
            raise ValidationError("payload must be a dict.")

        if write_request.operation not in ("resolve", "invalidate"):
            required_fields = self.BUCKET_REQUIRED_PAYLOAD_FIELDS[write_request.bucket]
            missing = [
                field
                for field in required_fields
                if field not in (write_request.payload or {})
                or (write_request.payload or {}).get(field) is None
            ]
            if missing:
                raise ValidationError(
                    f"payload for bucket '{write_request.bucket}' is missing required fields: {missing}"
                )

        if write_request.operation == "resolve" and write_request.bucket == "issues":
            if context is not None:
                open_issues = context.get("open_issues", [])
                known_ids = {issue.get("issue_id") for issue in open_issues}
                target_id = matched_target_id or write_request.target_id
                if target_id not in known_ids:
                    raise ValidationError(
                        f"resolve target '{target_id}' does not match any "
                        f"open issue in context. Known open issue ids: {sorted(known_ids)}"
                    )

        if write_request.operation == "invalidate" and write_request.bucket == "decisions":
            if context is not None:
                active_decisions = context.get("active_decisions", [])
                known_ids = {decision.get("decision_id") for decision in active_decisions}
                target_id = matched_target_id or write_request.target_id
                if target_id not in known_ids:
                    raise ValidationError(
                        f"invalidate target '{target_id}' does not match any "
                        f"active decision in context. Known active decision ids: {sorted(known_ids)}"
                    )

        if write_request.operation == "invalidate" and write_request.bucket == "constraints":
            if context is not None:
                active_constraints = context.get("active_constraints", [])
                known_ids = {
                    constraint.get("constraint_id") for constraint in active_constraints
                }
                target_id = matched_target_id or write_request.target_id
                if target_id not in known_ids:
                    raise ValidationError(
                        f"invalidate target '{target_id}' does not match any "
                        f"active constraint in context. Known active constraint ids: {sorted(known_ids)}"
                    )

        logger.debug(
            "Validator passed: bucket=%s operation=%s target_id=%s",
            write_request.bucket,
            write_request.operation,
            write_request.target_id,
        )

    def validate_resolved(
        self,
        resolved_write: ResolvedWrite,
        context: Optional[dict] = None,
    ) -> None:
        if resolved_write.decision != "commit":
            raise ValidationError(
                "validate_resolved only accepts ResolvedWrite(decision='commit')."
            )

        write_request = WriteRequest(
            decision="accept",
            bucket=resolved_write.bucket,
            target_id=resolved_write.resolved_target_id,
            operation=resolved_write.operation,
            payload=resolved_write.payload,
            rationale=resolved_write.resolution_reason,
        )
        self.validate(
            write_request,
            context=context,
            matched_target_id=resolved_write.matched_target_id,
        )
