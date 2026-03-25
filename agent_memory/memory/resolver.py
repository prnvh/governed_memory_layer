import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from memory.interpreter import WriteRequest


TOKEN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "by", "can",
    "do", "does", "for", "from", "has", "have", "in", "into", "is", "it",
    "its", "no", "not", "now", "of", "on", "or", "should", "that", "the",
    "their", "them", "this", "to", "was", "while", "with",
}

SNAKE_CASE_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


class ResolvedWrite(BaseModel):
    decision: Literal["commit", "provisional", "reject"]
    bucket: Optional[str] = None
    operation: Optional[str] = None
    resolved_target_id: Optional[str] = None
    matched_target_id: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    reference_text: Optional[str] = None
    candidate_matches: list[dict[str, Any]] = Field(default_factory=list)
    resolution_reason: str


class Resolver:
    """
    Deterministic policy layer between interpreter and canonical mutation.

    The interpreter decides what a note means. The resolver decides whether that
    meaning safely binds to an existing entity, should create a new entity, or
    should be preserved provisionally without mutating canonical memory.
    """

    def resolve(
        self,
        write_request: WriteRequest,
        raw_input: str,
        context: Optional[dict] = None,
    ) -> ResolvedWrite:
        if write_request.decision != "accept":
            return ResolvedWrite(
                decision="reject",
                resolution_reason=write_request.rationale,
            )

        context = context or {}
        bucket = write_request.bucket
        operation = write_request.operation

        if bucket == "issues":
            return self._resolve_issues(write_request, raw_input, context)
        if bucket == "constraints":
            return self._resolve_constraints(write_request, raw_input, context)
        if bucket == "decisions":
            return self._resolve_decisions(write_request, raw_input, context)

        return ResolvedWrite(
            decision="commit",
            bucket=bucket,
            operation=operation,
            resolved_target_id=write_request.target_id,
            matched_target_id=write_request.target_id,
            payload=write_request.payload,
            reference_text=self._reference_text(write_request, raw_input),
            resolution_reason="resolver_passthrough",
        )

    def _resolve_issues(
        self,
        write_request: WriteRequest,
        raw_input: str,
        context: dict,
    ) -> ResolvedWrite:
        reference = self._reference_text(write_request, raw_input)
        open_issues = context.get("open_issues", [])
        requested_target_id = self._requested_target_id(write_request, reference)
        direct_match = self._direct_id_match(
            requested_target_id,
            candidates=open_issues,
            id_key="issue_id",
        )
        if write_request.operation == "resolve" and direct_match is not None:
            return ResolvedWrite(
                decision="commit",
                bucket="issues",
                operation="resolve",
                resolved_target_id=requested_target_id,
                matched_target_id=direct_match["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=[direct_match],
                resolution_reason="direct_issue_target_match",
            )
        candidate_matches = self._score_candidates(
            reference,
            candidates=open_issues,
            id_key="issue_id",
            text_fields=["title", "description"],
            alias_hints=self._alias_hints(write_request),
            requested_target_id=requested_target_id,
        )

        if write_request.operation == "resolve":
            explicit_target = self._match_explicit_target(
                write_request.target_id,
                open_issues,
                id_key="issue_id",
            )
            if explicit_target is not None:
                return ResolvedWrite(
                    decision="commit",
                    bucket="issues",
                    operation="resolve",
                    resolved_target_id=explicit_target,
                    matched_target_id=explicit_target,
                    payload=write_request.payload or {},
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    resolution_reason="resolved_issue_explicit_target",
                )
            matched = self._choose_match(candidate_matches)
            if matched is None:
                return self._provisional(
                    bucket="issues",
                    operation="resolve",
                    payload=write_request.payload,
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    reason="unresolved_issue_reference",
                )
            final_id = self._preferred_target_id(
                requested_target_id,
                reference,
                matched["candidate_id"],
            )
            return ResolvedWrite(
                decision="commit",
                bucket="issues",
                operation="resolve",
                resolved_target_id=final_id,
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="resolved_issue_match",
            )

        explicit_slug = requested_target_id or self._single_explicit_slug(reference)
        if explicit_slug:
            return ResolvedWrite(
                decision="commit",
                bucket="issues",
                operation=write_request.operation,
                resolved_target_id=explicit_slug,
                matched_target_id=explicit_slug,
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="explicit_issue_identifier",
            )

        matched = self._choose_match(candidate_matches, min_score=2.5)
        if matched is not None and self._should_bind_existing_create(
            write_request=write_request,
            matched=matched,
            requested_target_id=requested_target_id,
        ):
            return ResolvedWrite(
                decision="commit",
                bucket="issues",
                operation=write_request.operation,
                resolved_target_id=matched["candidate_id"],
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="bind_existing_issue",
            )

        return ResolvedWrite(
            decision="commit",
            bucket="issues",
            operation=write_request.operation,
            resolved_target_id=self._creation_target_id(write_request, reference, "issue"),
            matched_target_id=self._creation_target_id(write_request, reference, "issue"),
            payload=write_request.payload,
            reference_text=reference,
            candidate_matches=candidate_matches,
            resolution_reason="create_issue_passthrough",
        )

    def _resolve_constraints(
        self,
        write_request: WriteRequest,
        raw_input: str,
        context: dict,
    ) -> ResolvedWrite:
        reference = self._reference_text(write_request, raw_input)
        active_constraints = context.get("active_constraints", [])
        requested_target_id = self._requested_target_id(write_request, reference)
        direct_match = self._direct_id_match(
            requested_target_id,
            candidates=active_constraints,
            id_key="constraint_id",
        )
        if write_request.operation == "invalidate" and direct_match is not None:
            return ResolvedWrite(
                decision="commit",
                bucket="constraints",
                operation="invalidate",
                resolved_target_id=requested_target_id,
                matched_target_id=direct_match["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=[direct_match],
                resolution_reason="direct_constraint_target_match",
            )
        candidate_matches = self._score_candidates(
            reference,
            candidates=active_constraints,
            id_key="constraint_id",
            text_fields=["text"],
            alias_hints=self._alias_hints(write_request),
            requested_target_id=requested_target_id,
        )

        if write_request.operation == "invalidate":
            explicit_target = self._match_explicit_target(
                write_request.target_id,
                active_constraints,
                id_key="constraint_id",
            )
            if explicit_target is not None:
                return ResolvedWrite(
                    decision="commit",
                    bucket="constraints",
                    operation="invalidate",
                    resolved_target_id=explicit_target,
                    matched_target_id=explicit_target,
                    payload=write_request.payload or {},
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    resolution_reason="resolved_constraint_explicit_target",
                )
            matched = self._choose_match(candidate_matches)
            if matched is None:
                return self._provisional(
                    bucket="constraints",
                    operation="invalidate",
                    payload=write_request.payload,
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    reason="unresolved_constraint_reference",
                )
            final_id = self._preferred_target_id(
                requested_target_id,
                reference,
                matched["candidate_id"],
            )
            return ResolvedWrite(
                decision="commit",
                bucket="constraints",
                operation="invalidate",
                resolved_target_id=final_id,
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="resolved_constraint_match",
            )

        explicit_slug = requested_target_id or self._single_explicit_slug(reference)
        if explicit_slug:
            return ResolvedWrite(
                decision="commit",
                bucket="constraints",
                operation=write_request.operation,
                resolved_target_id=explicit_slug,
                matched_target_id=explicit_slug,
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="explicit_constraint_identifier",
            )

        matched = self._choose_match(candidate_matches, min_score=2.5)
        if matched is not None and self._should_bind_existing_create(
            write_request=write_request,
            matched=matched,
            requested_target_id=requested_target_id,
        ):
            return ResolvedWrite(
                decision="commit",
                bucket="constraints",
                operation=write_request.operation,
                resolved_target_id=matched["candidate_id"],
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="bind_existing_constraint",
            )

        return ResolvedWrite(
            decision="commit",
            bucket="constraints",
            operation=write_request.operation,
            resolved_target_id=self._creation_target_id(write_request, reference, "constraint"),
            matched_target_id=self._creation_target_id(write_request, reference, "constraint"),
            payload=write_request.payload,
            reference_text=reference,
            candidate_matches=candidate_matches,
            resolution_reason="create_constraint_passthrough",
        )

    def _resolve_decisions(
        self,
        write_request: WriteRequest,
        raw_input: str,
        context: dict,
    ) -> ResolvedWrite:
        reference = self._reference_text(write_request, raw_input)
        active_decisions = context.get("active_decisions", [])
        requested_target_id = self._requested_target_id(write_request, reference)
        direct_match = self._direct_id_match(
            requested_target_id,
            candidates=active_decisions,
            id_key="decision_id",
        )
        if write_request.operation == "invalidate" and direct_match is not None:
            return ResolvedWrite(
                decision="commit",
                bucket="decisions",
                operation="invalidate",
                resolved_target_id=requested_target_id,
                matched_target_id=direct_match["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=[direct_match],
                resolution_reason="direct_decision_target_match",
            )
        candidate_matches = self._score_candidates(
            reference,
            candidates=active_decisions,
            id_key="decision_id",
            text_fields=["statement", "rationale"],
            alias_hints=self._alias_hints(write_request),
            requested_target_id=requested_target_id,
        )

        if write_request.operation == "invalidate":
            explicit_target = self._match_explicit_target(
                write_request.target_id,
                active_decisions,
                id_key="decision_id",
            )
            if explicit_target is not None:
                return ResolvedWrite(
                    decision="commit",
                    bucket="decisions",
                    operation="invalidate",
                    resolved_target_id=explicit_target,
                    matched_target_id=explicit_target,
                    payload=write_request.payload or {},
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    resolution_reason="resolved_decision_explicit_target",
                )
            matched = self._choose_match(candidate_matches)
            if matched is None:
                return self._provisional(
                    bucket="decisions",
                    operation="invalidate",
                    payload=write_request.payload,
                    reference_text=reference,
                    candidate_matches=candidate_matches,
                    reason="unresolved_decision_reference",
                )
            final_id = self._preferred_target_id(
                requested_target_id,
                reference,
                matched["candidate_id"],
            )
            return ResolvedWrite(
                decision="commit",
                bucket="decisions",
                operation="invalidate",
                resolved_target_id=final_id,
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload or {},
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="resolved_decision_match",
            )

        explicit_slug = requested_target_id or self._single_explicit_slug(reference)
        if explicit_slug:
            return ResolvedWrite(
                decision="commit",
                bucket="decisions",
                operation=write_request.operation,
                resolved_target_id=explicit_slug,
                matched_target_id=explicit_slug,
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="explicit_decision_identifier",
            )

        matched = self._choose_match(candidate_matches, min_score=3.0)
        if matched is not None and self._should_bind_existing_create(
            write_request=write_request,
            matched=matched,
            requested_target_id=requested_target_id,
        ):
            return ResolvedWrite(
                decision="commit",
                bucket="decisions",
                operation=write_request.operation,
                resolved_target_id=matched["candidate_id"],
                matched_target_id=matched["candidate_id"],
                payload=write_request.payload,
                reference_text=reference,
                candidate_matches=candidate_matches,
                resolution_reason="bind_existing_decision",
            )

        return ResolvedWrite(
            decision="commit",
            bucket="decisions",
            operation=write_request.operation,
            resolved_target_id=self._creation_target_id(write_request, reference, "decision"),
            matched_target_id=self._creation_target_id(write_request, reference, "decision"),
            payload=write_request.payload,
            reference_text=reference,
            candidate_matches=candidate_matches,
            resolution_reason="create_decision_passthrough",
        )

    def _provisional(
        self,
        bucket: str,
        operation: str,
        payload: Optional[dict[str, Any]],
        reference_text: str,
        candidate_matches: list[dict[str, Any]],
        reason: str,
    ) -> ResolvedWrite:
        return ResolvedWrite(
            decision="provisional",
            bucket=bucket,
            operation=operation,
            payload=payload,
            reference_text=reference_text,
            candidate_matches=candidate_matches,
            resolution_reason=reason,
        )

    def _reference_text(self, write_request: WriteRequest, raw_input: str) -> str:
        ref = str(getattr(write_request, "reference_text", "") or "").strip()
        raw = str(raw_input or "").strip()
        if ref and raw:
            if ref.lower() in raw.lower():
                return raw
            return f"{ref}\n{raw}"
        return ref or raw

    def _requested_target_id(
        self,
        write_request: WriteRequest,
        reference_text: str,
    ) -> Optional[str]:
        if write_request.target_id:
            return str(write_request.target_id)
        return self._single_explicit_slug(reference_text)

    def _direct_id_match(
        self,
        requested_target_id: Optional[str],
        candidates: list[dict[str, Any]],
        id_key: str,
    ) -> Optional[dict[str, Any]]:
        if not requested_target_id:
            return None
        for candidate in candidates:
            candidate_id = str(candidate.get(id_key, "") or "")
            if candidate_id == requested_target_id:
                return {
                    "candidate_id": candidate_id,
                    "score": 10.0,
                    "reasons": ["direct_requested_target_id"],
                }
        return None

    def _single_explicit_slug(self, text: str) -> Optional[str]:
        slugs = list(dict.fromkeys(self._explicit_slugs(text)))
        if len(slugs) == 1:
            return slugs[0]
        return None

    def _preferred_target_id(
        self,
        requested_target_id: Optional[str],
        text: str,
        fallback_id: str,
    ) -> str:
        if requested_target_id:
            return requested_target_id
        explicit_slug = self._single_explicit_slug(text)
        return explicit_slug or fallback_id

    def _explicit_slugs(self, text: str) -> list[str]:
        return [match.group(0) for match in SNAKE_CASE_PATTERN.finditer(text.lower())]

    def _alias_hints(self, write_request: WriteRequest) -> list[str]:
        aliases = getattr(write_request, "candidate_aliases", None) or []
        return [str(alias) for alias in aliases if str(alias).strip()]

    def _creation_target_id(
        self,
        write_request: WriteRequest,
        reference: str,
        prefix: str,
    ) -> str:
        if write_request.target_id:
            return write_request.target_id

        explicit_slug = self._single_explicit_slug(reference)
        if explicit_slug:
            return explicit_slug

        payload = write_request.payload or {}
        for field in ("statement", "text", "title", "metric_name", "status"):
            value = payload.get(field)
            if value:
                return self._slugify(str(value), prefix)

        return self._slugify(reference, prefix)

    def _score_candidates(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        id_key: str,
        text_fields: list[str],
        alias_hints: Optional[list[str]] = None,
        requested_target_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        lowered = text.lower()
        explicit_slugs = set(self._explicit_slugs(lowered))
        alias_hints = alias_hints or []
        alias_text = " ".join(alias_hints).lower()
        text_tokens = self._tokens(f"{lowered} {alias_text}".strip())
        requested_tokens = self._tokens((requested_target_id or "").replace("_", " "))
        matches: list[dict[str, Any]] = []

        for candidate in candidates:
            candidate_id = str(candidate.get(id_key, "") or "")
            score = 0.0
            reasons: list[str] = []
            reference_memory = self._reference_memory(candidate)
            candidate_aliases = {
                str(alias).lower()
                for alias in reference_memory.get("aliases", [])
                if str(alias).strip()
            }

            if candidate_id and candidate_id in explicit_slugs:
                score += 3.0
                reasons.append("explicit_id")
            if explicit_slugs and candidate_aliases.intersection(explicit_slugs):
                score += 2.5
                reasons.append("explicit_alias")
            if requested_target_id and candidate_id == requested_target_id:
                score += 4.0
                reasons.append("requested_target_id")

            candidate_text_parts = [candidate_id.replace("_", " ")]
            for field in text_fields:
                value = candidate.get(field)
                if value:
                    candidate_text_parts.append(str(value))
            candidate_text_parts.extend(
                self._reference_memory_text_parts(reference_memory)
            )
            candidate_text = " ".join(candidate_text_parts).lower()
            candidate_tokens = self._tokens(candidate_text)

            overlap = len(text_tokens & candidate_tokens)
            if overlap:
                score += overlap / max(len(candidate_tokens), 1)
                reasons.append(f"token_overlap={overlap}")

            requested_overlap = len(requested_tokens & candidate_tokens)
            if requested_overlap:
                score += (2.0 * requested_overlap) / max(len(requested_tokens), 1)
                reasons.append(f"requested_overlap={requested_overlap}")

            if candidate_id and candidate_id in lowered:
                score += 1.0
                reasons.append("id_in_text")
            if any(alias and alias in lowered for alias in candidate_aliases):
                score += 0.8
                reasons.append("alias_in_text")

            if score > 0:
                matches.append(
                    {
                        "candidate_id": candidate_id,
                        "score": round(score, 3),
                        "reasons": reasons,
                    }
                )

        matches.sort(key=lambda item: (-item["score"], item["candidate_id"]))
        return matches

    def _choose_match(
        self,
        candidate_matches: list[dict[str, Any]],
        min_score: float = 0.5,
        min_gap: float = 0.2,
    ) -> Optional[dict[str, Any]]:
        if not candidate_matches:
            return None

        top = candidate_matches[0]
        if top["score"] < min_score:
            return None

        if len(candidate_matches) > 1:
            second = candidate_matches[1]
            if (top["score"] - second["score"]) < min_gap:
                return None

        return top

    def _match_explicit_target(
        self,
        target_id: Optional[str],
        candidates: list[dict[str, Any]],
        id_key: str,
    ) -> Optional[str]:
        if not target_id:
            return None

        for candidate in candidates:
            candidate_id = candidate.get(id_key)
            if candidate_id == target_id:
                return str(candidate_id)

        return None

    def _tokens(self, text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return {token for token in tokens if token not in TOKEN_STOPWORDS}

    def _slugify(self, text: str, prefix: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        if not slug:
            slug = "item"
        return f"{prefix}_{slug[:40]}"

    def _should_bind_existing_create(
        self,
        write_request: WriteRequest,
        matched: dict[str, Any],
        requested_target_id: Optional[str],
    ) -> bool:
        if requested_target_id and matched["candidate_id"] == requested_target_id:
            return True
        if write_request.bucket == "decisions":
            return matched["score"] >= 4.0
        return matched["score"] >= 3.0

    def _reference_memory(self, candidate: dict[str, Any]) -> dict[str, Any]:
        raw_json = candidate.get("reference_memory_json")
        if not raw_json:
            return {}
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {}

    def _reference_memory_text_parts(self, reference_memory: dict[str, Any]) -> list[str]:
        parts: list[str] = []
        for key in (
            "canonical_text",
            "creation_note_text",
        ):
            value = reference_memory.get(key)
            if value:
                parts.append(str(value))

        for key in ("aliases", "reference_phrases", "seen_referring_expressions"):
            values = reference_memory.get(key) or []
            if isinstance(values, list):
                parts.extend(str(value) for value in values if str(value).strip())
        return parts
