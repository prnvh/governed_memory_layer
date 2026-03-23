# LLM-based promotion classifier.
# Takes a candidate note from working memory and decides whether it should be promoted to shared memory
# If promoted, produces a structured write request to be validated and operated into shared memory.


import json
import logging
import os
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
For accept: { "decision": "accept", "bucket": "...", "target_id": "...", "operation": "...", "payload": {...}, "rationale": "..." }
For reject: { "decision": "reject", "rationale": "..." }

target_id must be a short snake_case slug with no spaces.
For plan: target_id must ALWAYS be exactly "main" (no exceptions).
Include ALL required payload fields for the chosen bucket.

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