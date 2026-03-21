# Schema and rule validator for interpreter WriteRequests.
# Runs before any write happens. Rejects malformed or structurally invalid requests.
# V1: structural checks only. No semantic, duplicate, or contradiction checks.


import logging
import re

from memory.interpreter import WriteRequest
from memory.db.schema import get_valid_buckets, get_valid_operations

logger = logging.getLogger(__name__)

SLUG_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')


class ValidationError(Exception):
    pass


class Validator:
    """
    Schema/rule validator for interpreter WriteRequests.
    V1: structural checks only. No semantic/duplicate/contradiction checks.
    """

    BUCKET_REQUIRED_PAYLOAD_FIELDS: dict[str, list[str]] = {
        "plan":        ["plan_json"],
        "constraints": ["text"],
        "issues":      ["title"],
        "decisions":   ["statement"],
        "results":     ["metric_name", "metric_value"],
        "task_state":  ["status"],
        "learnings":   ["statement"],
    }

    BUCKET_ALLOWED_OPERATIONS: dict[str, list[str]] = {
        "plan":        ["upsert"],
        "constraints": ["upsert", "invalidate"],
        "issues":      ["upsert", "resolve"],
        "decisions":   ["append", "invalidate"],
        "results":     ["append"],
        "task_state":  ["upsert"],
        "learnings":   ["append"],
    }

    def validate(self, write_request: WriteRequest) -> None:
        """
        Raises ValidationError if the write request fails any check.
        Passes silently if valid.

        Checks:
        1. decision == "accept" (rejects should not reach validator)
        2. bucket is a known valid bucket
        3. operation is allowed for that bucket
        4. target_id is non-empty and a valid slug (no spaces, alphanumeric + _ -)
        5. payload is a non-None dict
        6. payload contains all required fields for the bucket
        """
        # 1. Must be an accepted request
        if write_request.decision != "accept":
            raise ValidationError(
                f"Validator received a rejected WriteRequest — only accepted requests should be validated. "
                f"rationale: {write_request.rationale}"
            )

        # 2. Bucket must be known
        valid_buckets = get_valid_buckets()
        if write_request.bucket not in valid_buckets:
            raise ValidationError(
                f"Unknown bucket '{write_request.bucket}'. Valid buckets: {valid_buckets}"
            )

        # 3. Operation must be allowed for this bucket
        allowed_ops = self.BUCKET_ALLOWED_OPERATIONS[write_request.bucket]
        if write_request.operation not in allowed_ops:
            raise ValidationError(
                f"Operation '{write_request.operation}' is not allowed for bucket "
                f"'{write_request.bucket}'. Allowed: {allowed_ops}"
            )

        # 4. target_id must be a non-empty slug
        if not write_request.target_id or not write_request.target_id.strip():
            raise ValidationError("target_id must be a non-empty string.")
        if not SLUG_PATTERN.match(write_request.target_id):
            raise ValidationError(
                f"target_id '{write_request.target_id}' is not a valid slug. "
                "Use only alphanumeric characters, underscores, or hyphens — no spaces."
            )

        # 5. payload must be a non-None dict
        # For resolve/invalidate operations, payload is allowed to be empty but must still be a dict
        if write_request.payload is None:
            if write_request.operation in ("resolve", "invalidate"):
                # Allow None payload for resolve/invalidate — no fields required
                return
            raise ValidationError(
                f"payload is required for operation '{write_request.operation}' "
                f"on bucket '{write_request.bucket}'."
            )

        if not isinstance(write_request.payload, dict):
            raise ValidationError("payload must be a dict.")

        # 6. Required payload fields must be present and non-None
        # Skip required field checks for resolve/invalidate
        if write_request.operation in ("resolve", "invalidate"):
            return

        required_fields = self.BUCKET_REQUIRED_PAYLOAD_FIELDS[write_request.bucket]
        missing = [f for f in required_fields if f not in write_request.payload or write_request.payload[f] is None]
        if missing:
            raise ValidationError(
                f"payload for bucket '{write_request.bucket}' is missing required fields: {missing}"
            )

        logger.debug(
            "Validator passed: bucket=%s operation=%s target_id=%s",
            write_request.bucket,
            write_request.operation,
            write_request.target_id,
        )