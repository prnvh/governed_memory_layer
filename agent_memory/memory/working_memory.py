# Per-agent per-run output store. 
# Shared memory is used as source of truth for all agents
# Output is stored in working_memory until its promoted to shared memory.

from datetime import datetime, timezone

class WorkingMemory:
    """
    Per-agent working memory. Run-scoped. Stores NL notes/observations
    as a list of timestamped entries. Not shared. Not authoritative.
    """

    def __init__(self, agent_id: str, run_id: str):
        self.agent_id = agent_id
        self.run_id = run_id
        self._notes: list[dict] = []  # each: {timestamp, text, source, promoted}

# Append a NL note. source is 'agent' or 'tool_result'.
    def add_note(self, text: str, source: str = "agent") -> None:
        self._notes.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": text,
            "source": source,
            "promoted": False,
        })

    def add_tool_result_note(self, tool_name: str, result_summary: str) -> None:
        # Convenience: add a note tagged as a tool result.
        self.add_note(
            text=f"[tool:{tool_name}] {result_summary}",
            source="tool_result",
        )

# Return all notes, optionally filtered to only unpromoted ones.
    def get_notes(self, unpromoted_only: bool = False) -> list[dict]:
        if unpromoted_only:
            return [n for n in self._notes if not n["promoted"]]
        return list(self._notes)


# Return notes not yet sent to the promotion pipeline.
    def get_promotion_candidates(self) -> list[dict]:
        return self.get_notes(unpromoted_only=True)


# Mark specific notes as having been sent for promotion.
    def mark_promoted(self, note_indices: list[int]) -> None:
        for i in note_indices:
            self._notes[i]["promoted"] = True


# Clear all notes. Call at end of run.
    def clear(self) -> None:
        self._notes = []


# Return all notes as a single text block for feeding into the interpreter prompt.
    def to_text_block(self, unpromoted_only: bool = True) -> str:
        
        notes = self.get_notes(unpromoted_only=unpromoted_only)
        if not notes:
            return ""
        lines = []
        for note in notes:
            lines.append(f"[{note['timestamp']}] ({note['source']}) {note['text']}")
        return "\n".join(lines)