"""
CLI entrypoint for the benchmark harness.

Usage:
    python -m benchmarks.run
    python -m benchmarks.run --family c
    python -m benchmarks.run --system all
    python -m benchmarks.run --family d --system all
    python -m benchmarks.run --trajectory a1_software_01
    python -m benchmarks.run --output results.json

Requires OPENAI_API_KEY in environment (or .env file).
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.table import Table

from benchmarks.baselines import (
    AppendAllMemoryHarness,
    StatelessClassifierHarness,
)
from benchmarks.harness import FaultInjectionHarness, GovernedMemoryHarness
from benchmarks.scorer import Scorer, TrajectoryScore
from benchmarks.trajectories import ALL_TRAJECTORIES
from benchmarks.trajectories.schema import Trajectory

load_dotenv()

console = Console()
logger = logging.getLogger(__name__)
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s - %(message)s",
    )


def check_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY is not set. "
            "Add it to your environment or a .env file."
        )
        sys.exit(1)


def select_trajectories(
    trajectory_id: str | None,
    family: str | None,
) -> list[Trajectory]:
    trajectories = ALL_TRAJECTORIES

    if family is not None:
        family_tag = f"family:{family}"
        trajectories = [t for t in trajectories if family_tag in t.tags]
        if not trajectories:
            console.print(
                f"[bold red]Error:[/bold red] No trajectories found for family '{family}'."
            )
            sys.exit(1)

    if trajectory_id is None:
        return trajectories

    matches = [t for t in trajectories if t.id == trajectory_id]
    if not matches:
        available = ", ".join(t.id for t in trajectories)
        console.print(
            f"[bold red]Error:[/bold red] Unknown trajectory '{trajectory_id}'. "
            f"Available: {available}"
        )
        sys.exit(1)
    return matches


def print_header(
    trajectories: list[Trajectory],
    system_name: str,
    family: str | None,
) -> None:
    console.print()
    console.rule("[bold cyan]Governed Memory Benchmark[/bold cyan]")
    console.print(f"  Trajectories : [cyan]{len(trajectories)}[/cyan]")
    if family is not None:
        console.print(f"  Family       : [cyan]{family}[/cyan]")
    console.print(f"  System       : [cyan]{system_name}[/cyan]")
    console.print()


def print_trajectory_result(
    score: TrajectoryScore,
    harness_summary: list[str],
    verbose: bool,
) -> None:
    governance_color = "green" if score.governance_accuracy == 1.0 else (
        "yellow" if score.governance_accuracy >= 0.5 else "red"
    )
    console.print(
        f"[bold]{score.trajectory_id}[/bold]  "
        f"[{governance_color}]{score.governance_accuracy:.0%}[/{governance_color}] "
        f"(canonical {score.passed}/{score.total}, surplus {score.surplus_row_count}, pending {score.pending_backlog_count})"
    )

    for line in harness_summary[2:]:
        console.print(f"  {line}")

    surplus_buckets: list[str] = []
    for r in score.outcome_results:
        if r.outcome.target_id == "__surplus__":
            surplus_buckets.append(r.outcome.bucket)
            continue
        icon = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        label = f"{r.outcome.bucket}/{r.outcome.target_id}"
        if r.passed:
            console.print(f"  {icon} {label}")
        else:
            console.print(f"  {icon} {label}  [dim]{r.failure_reason}[/dim]")

    if surplus_buckets:
        bucket_counts: dict[str, int] = {}
        for bucket in surplus_buckets:
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        summary = ", ".join(
            f"{bucket}={count}" for bucket, count in sorted(bucket_counts.items())
        )
        console.print(f"  [yellow]SURPLUS[/yellow] {summary}")

    if verbose:
        console.print()


def print_summary_table(scores: list[TrajectoryScore]) -> None:
    console.print()
    console.rule("[bold cyan]Summary[/bold cyan]")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Trajectory", style="white")
    table.add_column("Govern", justify="right")
    table.add_column("Canon", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("False +", justify="right")
    table.add_column("False -", justify="right")
    table.add_column("Field miss", justify="right")
    table.add_column("Surplus", justify="right")
    table.add_column("Pending", justify="right")
    table.add_column("Replay", justify="right")

    overall_passed = 0
    overall_total = 0
    overall_surplus = 0
    overall_pending = 0

    for score in scores:
        governance_color = "green" if score.governance_accuracy == 1.0 else (
            "yellow" if score.governance_accuracy >= 0.5 else "red"
        )
        canonical_color = "green" if score.canonical_accuracy == 1.0 else (
            "yellow" if score.canonical_accuracy >= 0.5 else "red"
        )
        replay_color = "green" if score.replay_health == 1.0 else "yellow"
        table.add_row(
            score.trajectory_id,
            f"[{governance_color}]{score.governance_accuracy:.0%}[/{governance_color}]",
            f"[{canonical_color}]{score.canonical_accuracy:.0%}[/{canonical_color}]",
            f"{score.passed}/{score.total}",
            str(score.false_positive_count),
            str(score.false_negative_count),
            str(score.field_mismatch_count),
            str(score.surplus_row_count),
            str(score.pending_backlog_count),
            f"[{replay_color}]{score.replay_health:.0%}[/{replay_color}]",
        )
        overall_passed += score.passed
        overall_total += score.total
        overall_surplus += score.surplus_row_count
        overall_pending += score.pending_backlog_count

    overall_canonical = overall_passed / overall_total if overall_total > 0 else 0.0
    overall_governance = overall_passed / (overall_total + overall_surplus) if (overall_total + overall_surplus) > 0 else 0.0
    overall_governance_color = "green" if overall_governance == 1.0 else (
        "yellow" if overall_governance >= 0.5 else "red"
    )
    overall_canonical_color = "green" if overall_canonical == 1.0 else (
        "yellow" if overall_canonical >= 0.5 else "red"
    )
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold {overall_governance_color}]{overall_governance:.0%}[/bold {overall_governance_color}]",
        f"[bold {overall_canonical_color}]{overall_canonical:.0%}[/bold {overall_canonical_color}]",
        f"[bold]{overall_passed}/{overall_total}[/bold]",
        "",
        "",
        "",
        f"[bold]{overall_surplus}[/bold]",
        f"[bold]{overall_pending}[/bold]",
        "",
    )

    console.print(table)


def scores_to_dict(
    scores: list[TrajectoryScore],
    run_timestamp: str,
    system_name: str,
) -> dict:
    return {
        "run_timestamp": run_timestamp,
        "system": system_name,
        "trajectories": [
            {
                "trajectory_id": s.trajectory_id,
                "canonical_accuracy": s.canonical_accuracy,
                "governance_accuracy": s.governance_accuracy,
                "passed": s.passed,
                "total": s.total,
                "false_positive_count": s.false_positive_count,
                "false_negative_count": s.false_negative_count,
                "field_mismatch_count": s.field_mismatch_count,
                "surplus_row_count": s.surplus_row_count,
                "pending_backlog_count": s.pending_backlog_count,
                "replay_health": s.replay_health,
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


def default_output_path(
    run_timestamp: str,
    system_name: str,
    family: str | None,
    trajectory_id: str | None,
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_slug = (
        run_timestamp.replace(":", "")
        .replace("-", "")
        .replace("+00:00", "Z")
        .replace(".", "_")
    )
    family_part = family or "all_families"
    trajectory_part = trajectory_id or "all_trajectories"
    filename = f"{timestamp_slug}_{system_name}_{family_part}_{trajectory_part}.json"
    return RESULTS_DIR / filename


def write_output_file(output_path: Path, output_data: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)


def build_harness(system_name: str, trajectory: Trajectory):
    if system_name == "append_all":
        return AppendAllMemoryHarness()
    if system_name in {"stateless", "no_shared_context"}:
        return StatelessClassifierHarness()
    return (
        FaultInjectionHarness()
        if trajectory.fault_injection is not None
        else GovernedMemoryHarness()
    )


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
        "--family",
        type=str,
        default=None,
        choices=["a", "b", "c", "d", "e", "f"],
        help="Run only one benchmark family.",
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
    parser.add_argument(
        "--system",
        type=str,
        default="governed",
        choices=["governed", "append_all", "no_shared_context", "stateless", "all"],
        help="Which benchmark system to run. Use 'all' to run harness plus all baselines.",
    )
    args = parser.parse_args()

    configure_logging(args.verbose)
    check_api_key()

    effective_family = args.family
    baseline_systems = {"append_all", "no_shared_context", "stateless"}
    if effective_family is None and args.system in baseline_systems:
        effective_family = "a"

    requested_system = (
        "no_shared_context" if args.system == "stateless" else args.system
    )

    trajectories = select_trajectories(args.trajectory, effective_family)
    scorer = Scorer()
    run_timestamp = datetime.now(timezone.utc).isoformat()

    systems = (
        ["governed", "append_all", "no_shared_context"]
        if requested_system == "all"
        else [requested_system]
    )

    all_output_runs: list[dict] = []

    for system_name in systems:
        print_header(trajectories, system_name, effective_family)

        scores: list[TrajectoryScore] = []

        for trajectory in trajectories:
            console.print(f"[dim]Running[/dim] {trajectory.id} ...", end=" ")
            harness = build_harness(system_name, trajectory)
            harness_result = harness.run_trajectory(trajectory)

            if harness_result.error:
                console.print(f"[bold red]ERROR[/bold red] - {harness_result.error}")
                continue

            console.print("[dim]scoring...[/dim]", end=" ")
            score = scorer.score(
                harness_result.snapshot,
                trajectory,
                include_surplus=(system_name == "append_all"),
            )
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

        all_output_runs.append(scores_to_dict(scores, run_timestamp, system_name))

    if all_output_runs:
        output_data = (
            all_output_runs[0]
            if len(all_output_runs) == 1
            else {
                "run_timestamp": run_timestamp,
                "runs": all_output_runs,
            }
        )

        saved_paths: list[Path] = []

        auto_path = default_output_path(
            run_timestamp=run_timestamp,
            system_name=args.system,
            family=effective_family,
            trajectory_id=args.trajectory,
        )
        write_output_file(auto_path, output_data)
        saved_paths.append(auto_path)

        if args.output:
            explicit_path = Path(args.output)
            write_output_file(explicit_path, output_data)
            saved_paths.append(explicit_path)

        console.print()
        for path in saved_paths:
            console.print(f"[dim]Results saved to {path}[/dim]")


if __name__ == "__main__":
    main()
