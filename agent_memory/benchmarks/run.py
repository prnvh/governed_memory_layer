"""
CLI entrypoint for the benchmark harness.

Usage:
    # Run all trajectories through the governed system:
    python -m benchmarks.run

    # Run a specific trajectory:
    python -m benchmarks.run --trajectory current_state_tracking

    # Run and save results to JSON:
    python -m benchmarks.run --output results.json

    # Run with verbose per-note output:
    python -m benchmarks.run --verbose

Requires OPENAI_API_KEY in environment (or .env file).
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

from benchmarks.harness import GovernedMemoryHarness
from benchmarks.scorer import Scorer, TrajectoryScore
from benchmarks.trajectories.examples import ALL_TRAJECTORIES
from benchmarks.trajectories.schema import Trajectory

load_dotenv()

console = Console()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s — %(message)s",
    )


def check_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY is not set. "
            "Add it to your environment or a .env file."
        )
        sys.exit(1)


def select_trajectories(trajectory_id: str | None) -> list[Trajectory]:
    if trajectory_id is None:
        return ALL_TRAJECTORIES
    matches = [t for t in ALL_TRAJECTORIES if t.id == trajectory_id]
    if not matches:
        available = ", ".join(t.id for t in ALL_TRAJECTORIES)
        console.print(
            f"[bold red]Error:[/bold red] Unknown trajectory '{trajectory_id}'. "
            f"Available: {available}"
        )
        sys.exit(1)
    return matches


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_header(trajectories: list[Trajectory]) -> None:
    console.print()
    console.rule("[bold cyan]Governed Memory Benchmark[/bold cyan]")
    console.print(
        f"  Trajectories : [cyan]{len(trajectories)}[/cyan]"
    )
    console.print(
        f"  System       : [cyan]governed[/cyan]"
    )
    console.print()


def print_trajectory_result(
    score: TrajectoryScore,
    harness_summary: list[str],
    verbose: bool,
) -> None:
    # Header
    accuracy_color = "green" if score.canonical_accuracy == 1.0 else (
        "yellow" if score.canonical_accuracy >= 0.5 else "red"
    )
    console.print(
        f"[bold]{score.trajectory_id}[/bold]  "
        f"[{accuracy_color}]{score.canonical_accuracy:.0%}[/{accuracy_color}] "
        f"({score.passed}/{score.total} outcomes passed)"
    )

    # Harness summary (duration, accepted/rejected counts)
    for line in harness_summary[2:]:  # skip system/trajectory lines already shown
        console.print(f"  {line}")

    # Per-outcome results
    for r in score.outcome_results:
        icon = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
        label = f"{r.outcome.bucket}/{r.outcome.target_id}"
        if not r.passed:
            console.print(f"  {icon} {label}  [dim]{r.failure_reason}[/dim]")
        else:
            console.print(f"  {icon} {label}")

    # Verbose: show per-note promotion decisions
    if verbose:
        console.print()


def print_summary_table(scores: list[TrajectoryScore]) -> None:
    console.print()
    console.rule("[bold cyan]Summary[/bold cyan]")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Trajectory", style="white")
    table.add_column("Accuracy", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("False +", justify="right")
    table.add_column("False -", justify="right")
    table.add_column("Field miss", justify="right")

    overall_passed = 0
    overall_total = 0

    for score in scores:
        accuracy_color = "green" if score.canonical_accuracy == 1.0 else (
            "yellow" if score.canonical_accuracy >= 0.5 else "red"
        )
        table.add_row(
            score.trajectory_id,
            f"[{accuracy_color}]{score.canonical_accuracy:.0%}[/{accuracy_color}]",
            f"{score.passed}/{score.total}",
            str(score.false_positive_count),
            str(score.false_negative_count),
            str(score.field_mismatch_count),
        )
        overall_passed += score.passed
        overall_total += score.total

    overall_accuracy = overall_passed / overall_total if overall_total > 0 else 0.0
    overall_color = "green" if overall_accuracy == 1.0 else (
        "yellow" if overall_accuracy >= 0.5 else "red"
    )
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold {overall_color}]{overall_accuracy:.0%}[/bold {overall_color}]",
        f"[bold]{overall_passed}/{overall_total}[/bold]",
        "", "", "",
    )

    console.print(table)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def scores_to_dict(
    scores: list[TrajectoryScore],
    run_timestamp: str,
) -> dict:
    """Serialise results to a JSON-compatible dict for --output."""
    return {
        "run_timestamp": run_timestamp,
        "system": "governed",
        "trajectories": [
            {
                "trajectory_id": s.trajectory_id,
                "canonical_accuracy": s.canonical_accuracy,
                "passed": s.passed,
                "total": s.total,
                "false_positive_count": s.false_positive_count,
                "false_negative_count": s.false_negative_count,
                "field_mismatch_count": s.field_mismatch_count,
                "outcomes": [
                    {
                        "bucket": r.outcome.bucket,
                        "target_id": r.outcome.target_id,
                        "passed": r.passed,
                        "failure_reason": r.failure_reason,
                    }
                    for r in s.outcome_results
                ],
            }
            for s in scores
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the governed memory benchmark."
    )
    parser.add_argument(
        "--trajectory",
        type=str,
        default=None,
        help="Run a single trajectory by ID. Omit to run all.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save results as JSON to this path.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-note promotion decisions.",
    )
    args = parser.parse_args()

    configure_logging(args.verbose)
    check_api_key()

    trajectories = select_trajectories(args.trajectory)
    harness = GovernedMemoryHarness()
    scorer = Scorer()
    run_timestamp = datetime.now(timezone.utc).isoformat()

    print_header(trajectories)

    scores: list[TrajectoryScore] = []

    for trajectory in trajectories:
        console.print(f"[dim]Running[/dim] {trajectory.id} ...", end=" ")

        harness_result = harness.run_trajectory(trajectory)

        if harness_result.error:
            console.print(f"[bold red]ERROR[/bold red] — {harness_result.error}")
            continue

        console.print("[dim]scoring...[/dim]", end=" ")
        score = scorer.score(harness_result.snapshot, trajectory)
        scores.append(score)

        console.print()
        print_trajectory_result(
            score,
            harness_result.summary_lines(),
            args.verbose,
        )
        console.print()

    if scores:
        print_summary_table(scores)

    if args.output and scores:
        output_data = scores_to_dict(scores, run_timestamp)
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        console.print(f"\n[dim]Results saved to {args.output}[/dim]")


if __name__ == "__main__":
    main()