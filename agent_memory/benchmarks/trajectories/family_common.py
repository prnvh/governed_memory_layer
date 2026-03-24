"""
Shared helpers for benchmark trajectory families B-F.

These utilities keep the authoring style consistent across domains and
difficulties without forcing every family file to repeat note boilerplate.
"""

from benchmarks.trajectories.schema import TrajectoryNote


DOMAIN_FILLERS: dict[str, list[tuple[str, str, str | None]]] = {
    "software": [
        ("agent", "Checked the current release checklist and compared it against the last green build.", None),
        ("tool_result", "Repository audit complete. No unrelated config drift found in the surrounding files.", "repo_audit"),
        ("agent", "Keeping focus on the canonical blocker instead of opening side quests from incidental observations.", None),
        ("tool_result", "Diff review complete. Peripheral modules were unchanged during this run.", "code_review"),
        ("agent", "Documented the intermediate status for the team channel and continued the investigation.", None),
    ],
    "ml": [
        ("agent", "Logged the current experiment context so later notes stay anchored to the same run.", None),
        ("tool_result", "Environment check complete. CUDA and package versions match the pinned experiment image.", "env_check"),
        ("agent", "Skipping speculative tuning ideas until the main state transition is confirmed.", None),
        ("tool_result", "Dataset manifest review complete. No unrelated split changes were detected.", "data_check"),
        ("agent", "Recorded the interim observation in the experiment notebook and kept going.", None),
    ],
    "ops": [
        ("agent", "Reviewed the current incident timeline to make sure later updates stayed in order.", None),
        ("tool_result", "Dashboard sweep complete. Neighboring services remained within normal operating bands.", "monitoring"),
        ("agent", "Holding off on secondary hypotheses until the primary operational state is clear.", None),
        ("tool_result", "Runbook lookup complete. No unrelated escalation paths were triggered.", "runbook"),
        ("agent", "Posted an interim ops update and continued with the main remediation track.", None),
    ],
    "policy": [
        ("agent", "Reviewed the current policy draft and aligned the next note against the active review thread.", None),
        ("tool_result", "Document check complete. Adjacent sections did not introduce any independent obligations.", "policy_review"),
        ("agent", "Avoiding speculative policy expansion until the authoritative requirement is explicit.", None),
        ("tool_result", "Control mapping audit complete. No unrelated control owners were affected.", "control_map"),
        ("agent", "Noted the interim governance status and continued with the main compliance thread.", None),
    ],
}


DELAY_NOTE_COUNTS = {
    1: 0,
    2: 2,
    3: 8,
    4: 12,
}


def agent_note(text: str) -> TrajectoryNote:
    return TrajectoryNote(text=text, source="agent")


def tool_note(tool_name: str, text: str) -> TrajectoryNote:
    return TrajectoryNote(text=text, source="tool_result", tool_name=tool_name)


def build_delay_notes(domain: str, difficulty: int, variant: int) -> list[TrajectoryNote]:
    """
    Produce deterministic filler notes for delayed / high-noise trajectories.

    These are intended to preserve note-count scaling and time gaps without
    accidentally introducing extra state transitions.
    """
    count = DELAY_NOTE_COUNTS[difficulty]
    filler_bank = DOMAIN_FILLERS[domain]
    notes: list[TrajectoryNote] = []

    for idx in range(count):
        source, text, tool_name = filler_bank[(idx + variant) % len(filler_bank)]
        if source == "tool_result":
            notes.append(
                tool_note(
                    tool_name or "status_check",
                    f"{text} Reference checkpoint {variant}.{idx + 1}.",
                )
            )
        else:
            notes.append(agent_note(f"{text} Reference checkpoint {variant}.{idx + 1}."))

    return notes


def make_tags(
    family: str,
    difficulty: int,
    domain: str,
    dominant_failure_mode: str,
) -> list[str]:
    return [
        f"family:{family}",
        f"difficulty:l{difficulty}",
        f"domain:{domain}",
        f"failure_mode:{dominant_failure_mode}",
    ]
