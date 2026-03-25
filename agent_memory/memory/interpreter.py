# LLM-based promotion classifier.
# Takes a candidate note from working memory and decides whether it should be promoted to shared memory
# If promoted, produces a structured write request to be validated and operated into shared memory.


import json
import logging
import os
import re
from typing import Any, Literal, Optional

import openai
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WriteRequest(BaseModel):
    decision: Literal["accept", "reject"]
    bucket: Optional[str] = None       # plan, constraints, issues, decisions, results, task_state, learnings
    target_id: Optional[str] = None    # e.g. "main", "issue_7", slug from content
    operation: Optional[str] = None    # upsert, append, resolve, invalidate
    payload: Optional[dict[str, Any]] = None
    reference_text: Optional[str] = None
    candidate_aliases: Optional[list[str]] = None
    confidence: Optional[float] = None
    rationale: str                     # why accept or reject. used for logging


class Interpreter:
    """
    LLM-based governor. Takes ONE candidate note and returns ONE WriteRequest
    (accept or reject). The promotion pipeline calls this once per note.
    """

    SYSTEM_PROMPT = """You are a memory interpreter for a multi-agent system.
You will be given a SINGLE note from an agent's working memory.
Your job: decide if this note is important enough to promote to shared canonical memory, and if so, produce exactly one structured write request.

Shared memory buckets and their required payload fields:
- plan        → { "plan_json": str }                         op: upsert
- constraints → { "text": str, "scope": str|null }           op: upsert|invalidate
- issues      → { "title": str, "description": str|null,
                  "severity": low|medium|high|critical }     op: upsert|resolve
- decisions   → { "statement": str, "rationale": str|null,
                  "scope": str|null }                        op: append|invalidate
- results     → { "metric_name": str, "metric_value": str,
                  "baseline_value": str|null,
                  "experiment_id": str|null,
                  "notes": str|null }                        op: append
- task_state  → { "status": pending|in_progress|blocked|done|failed,
                  "phase": str|null,
                  "blockers_json": str|null }                op: upsert
- learnings   → { "statement": str, "title": str,
                  "category": str|null,
                  "confidence": float 0-1|null,
                  "source_issue_id": str|null }              op: append

Output ONLY valid JSON. No explanation outside the JSON.
For accept: { "decision": "accept", "bucket": "...", "target_id": "...", "operation": "...", "payload": {...}, "reference_text": "...", "candidate_aliases": ["..."], "confidence": 0.0-1.0, "rationale": "..." }
For reject: { "decision": "reject", "rationale": "..." }

target_id must be a short snake_case slug with no spaces when you provide it.
For plan: target_id must ALWAYS be exactly "main" (no exceptions).
Include ALL required payload fields for the chosen bucket.
reference_text is optional but strongly preferred for lifecycle notes that refer
to an earlier issue / constraint / decision. It should capture the earlier thing
being referred to in natural language or exact slug form.
candidate_aliases is optional and can include short alternate handles that would
help match the same entity later.
confidence is optional and should reflect how certain you are in the write.

If OPEN ISSUES are provided in the context below, you must check them before
classifying a note about issues. Specifically:
- If the note says something is fixed/resolved/done and it matches an open issue,
  use operation "resolve" and set target_id to that issue's exact issue_id.
- If the note describes a new issue not in the list, use operation "upsert" with
  a new snake_case target_id.
- Do NOT create a new issue row for something that is already tracked as open.

If ACTIVE DECISIONS are provided in the context below, you must check them before
classifying a note about decisions. Specifically:
- If the note says a prior decision is wrong, invalid, or superseded, use operation
  "invalidate" and set target_id to that decision's exact decision_id.
- If the note introduces a genuinely new decision, use operation "append" with a
  new snake_case target_id.
- Do NOT append a new decision for something that is already tracked as active.

If ACTIVE CONSTRAINTS are provided in the context below, you must check them before
classifying a note about constraints. Specifically:
- If the note says a constraint no longer applies, use operation "invalidate" and
  set target_id to that constraint's exact constraint_id.
- If the note introduces a new constraint, use operation "upsert" with a new
  snake_case target_id.

Important:
- Your primary job is to classify the note's meaning correctly.
- Do NOT invent a precise existing target_id if you are unsure.
- For lifecycle notes, if you are uncertain about the exact existing id, still
  emit the correct bucket and operation, include reference_text, and use a
  best-effort target_id only if you have one.
- Prefer preserving a strong reference_text over hallucinating a wrong id.

Reject if:
- The note is vague thinking, not a concrete fact/decision/result/issue
- The note does not contain enough information to fill required payload fields
- The note is a duplicate of something that would already be in shared memory
- The note is a transient observation with no lasting relevance"""

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self._client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY")
        )

# Take one candidate note, return one write request (accept or reject with rationale) 
    def interpret(
        self,
        candidate_note: str,
        agent_id: str,
        context: Optional[dict] = None,
    ) -> WriteRequest:
        """
        Takes ONE candidate note and optional context from shared memory.
        Context should contain relevant current state — currently open issues.
        Returns ONE WriteRequest (accept or reject).
        """
        heuristic = self._heuristic_structured_write(candidate_note)
        if heuristic is not None:
            logger.info(
                "Interpreter [%s] -> %s | bucket=%s | rationale=%s",
                agent_id,
                heuristic.decision,
                heuristic.bucket,
                heuristic.rationale,
            )
            return heuristic

        context_block = ""
        if context:
            sections = []

            open_issues = context.get("open_issues", [])
            if open_issues:
                lines = ["OPEN ISSUES (already tracked in shared memory):"]
                for issue in open_issues:
                    lines.append(
                        f"  - issue_id: {issue.get('issue_id')} | "
                        f"title: {issue.get('title')} | "
                        f"severity: {issue.get('severity')}"
                    )
                sections.append("\n".join(lines))

            active_decisions = context.get("active_decisions", [])
            if active_decisions:
                lines = ["ACTIVE DECISIONS (already tracked in shared memory):"]
                for decision in active_decisions:
                    lines.append(
                        f"  - decision_id: {decision.get('decision_id')} | "
                        f"statement: {decision.get('statement')}"
                    )
                sections.append("\n".join(lines))

            active_constraints = context.get("active_constraints", [])
            if active_constraints:
                lines = ["ACTIVE CONSTRAINTS (already tracked in shared memory):"]
                for constraint in active_constraints:
                    lines.append(
                        f"  - constraint_id: {constraint.get('constraint_id')} | "
                        f"text: {constraint.get('text')}"
                    )
                sections.append("\n".join(lines))

            if sections:
                context_block = "\n\n" + "\n\n".join(sections)

        user_message = (
            f"Agent: {agent_id}"
            f"{context_block}"
            f"\n\nNote to evaluate:\n{candidate_note}"
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw_text = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
            write_request = WriteRequest(**parsed)

            logger.info(
                "Interpreter [%s] → %s | bucket=%s | rationale=%s",
                agent_id,
                write_request.decision,
                write_request.bucket,
                write_request.rationale,
            )
            return write_request

        except json.JSONDecodeError as e:
            rationale = f"parse_error: invalid JSON from LLM — {e}"
            logger.warning("Interpreter [%s] parse error: %s", agent_id, rationale)
            return WriteRequest(decision="reject", rationale=rationale)

        except Exception as e:
            rationale = f"parse_error: {type(e).__name__}: {e}"
            logger.warning("Interpreter [%s] error: %s", agent_id, rationale)
            return WriteRequest(decision="reject", rationale=rationale)

    def _heuristic_structured_write(self, candidate_note: str) -> Optional[WriteRequest]:
        """
        Fast path for extremely explicit structured notes. This avoids spending an
        LLM call on obvious state-bearing notes and reduces false rejects on
        straightforward updates like plans, learnings, and explicit task-state
        transitions. Lifecycle-heavy notes such as constraints and decisions are
        intentionally left to the LLM so they can use shared-memory context.
        """
        text = candidate_note.strip()
        lowered = text.lower()
        explicit_slugs = re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", lowered)

        if lowered.startswith("plan:") or lowered.startswith("plan for "):
            return WriteRequest(
                decision="accept",
                bucket="plan",
                target_id="main",
                operation="upsert",
                payload={"plan_json": text.split(":", 1)[1].strip() if ":" in text else text},
                rationale="heuristic_plan",
            )

        if "learning:" in lowered:
            statement = text.split("Learning:", 1)[1].strip()
            return WriteRequest(
                decision="accept",
                bucket="learnings",
                target_id=self._slugify_local(statement, "learning"),
                operation="append",
                payload={
                    "statement": statement,
                    "title": statement[:80] if statement else "Learning",
                    "category": None,
                    "confidence": None,
                    "source_issue_id": None,
                },
                rationale="heuristic_learning",
            )

        if lowered.startswith("constraint:"):
            constraint_text = text.split(":", 1)[1].strip()
            target_id = explicit_slugs[0] if len(explicit_slugs) == 1 else self._slugify_local(constraint_text, "constraint")
            return WriteRequest(
                decision="accept",
                bucket="constraints",
                target_id=target_id,
                operation="upsert",
                payload={
                    "text": constraint_text,
                    "scope": None,
                },
                rationale="heuristic_constraint",
            )

        if lowered.startswith("decision:"):
            statement = text.split(":", 1)[1].strip()
            target_id = explicit_slugs[0] if len(explicit_slugs) == 1 else self._slugify_local(statement, "decision")
            return WriteRequest(
                decision="accept",
                bucket="decisions",
                target_id=target_id,
                operation="append",
                payload={
                    "statement": statement,
                    "rationale": None,
                    "scope": None,
                },
                rationale="heuristic_decision",
            )

        issue_like_note = any(
            phrase in lowered for phrase in (
                " is open",
                " issue is open",
                " incident is open",
                " blocker is open",
                " is resolved",
                " incident is resolved",
                " incident is closed",
            )
        )
        if issue_like_note:
            return None

        if len(explicit_slugs) == 1:
            explicit_slug = explicit_slugs[0]

            if (
                "constraint" in lowered
                and any(
                    phrase in lowered for phrase in (
                        "no longer applies",
                        "should be invalidated",
                        "must be invalidated",
                        "can be lifted",
                        "can be removed",
                    )
                )
            ):
                return WriteRequest(
                    decision="accept",
                    bucket="constraints",
                    target_id=explicit_slug,
                    operation="invalidate",
                    payload={},
                    reference_text=explicit_slug,
                    candidate_aliases=[explicit_slug],
                    rationale="heuristic_constraint_invalidate",
                )

            if any(
                phrase in lowered for phrase in (
                    "decision is superseded",
                    "decision is no longer active",
                    "is superseded by",
                    "replaces it",
                    "replaces the earlier",
                )
            ):
                return WriteRequest(
                    decision="accept",
                    bucket="decisions",
                    target_id=explicit_slug,
                    operation="invalidate",
                    payload={},
                    reference_text=explicit_slug,
                    candidate_aliases=[explicit_slug],
                    rationale="heuristic_decision_invalidate",
                )

            if any(
                phrase in lowered for phrase in (
                    "is resolved",
                    "is now resolved",
                    "is closed",
                    "no longer open",
                )
            ):
                return WriteRequest(
                    decision="accept",
                    bucket="issues",
                    target_id=explicit_slug,
                    operation="resolve",
                    payload={},
                    reference_text=explicit_slug,
                    candidate_aliases=[explicit_slug],
                    rationale="heuristic_issue_resolve",
                )

        status = None
        if re.search(r"\bis now in progress\b|\bin progress\b|\bkicked off\b", lowered):
            status = "in_progress"
        elif re.search(r"\btask is blocked\b|\bblocked pending\b|\bcannot proceed\b", lowered):
            status = "blocked"
        elif re.search(
            r"\bis done\b|\btask is done\b|\btask is complete\b|\btask complete\b|"
            r"\bincident closed\b|\bcomplete\.\b",
            lowered,
        ):
            status = "done"

        if status is None:
            return None

        return WriteRequest(
            decision="accept",
            bucket="task_state",
            target_id="main",
            operation="upsert",
            payload={
                "status": status,
                "phase": None,
                "blockers_json": None,
            },
            rationale="heuristic_task_state",
        )

    def _slugify_local(self, text: str, prefix: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        if not slug:
            slug = "item"
        return f"{prefix}_{slug[:40]}"
