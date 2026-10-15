"""One run page for a CI job that gates several teams: an overview table first, then each team.

    aiquality ci-summary --output-dir aiquality-runs >> "$GITHUB_STEP_SUMMARY"

It reads the latest gate run of every team in the run records. Real teams come first; gate
self-tests (teams with 'expected_result') follow, each saying whether the gate gave the result it must.
"""

from pathlib import Path

from aiquality.errors import SetupError
from aiquality.reporting.github_summary_reporter import outcome, render_github_summary
from aiquality.reporting.run_record import RUN_RECORDS_FILE, RunRecord, load_run_records


def latest_gate_runs(output_dir) -> list[RunRecord]:
    path = Path(output_dir) / RUN_RECORDS_FILE
    if not path.is_file():
        raise SetupError(f"no run records at {path}: run the gates first")
    latest = {}
    for record in load_run_records(path):
        if record.gate_decision:
            latest[record.team] = record
    runs = list(latest.values())
    return [r for r in runs if not r.expected_result] + [r for r in runs if r.expected_result]


def render_ci_summary(output_dir, title: str = "Quality gates for this change") -> str:
    runs = latest_gate_runs(output_dir)
    lines = [f"# {title}", "", "| Gate | Result | Expected | What it is |", "|---|---|---|---|"]
    for record in runs:
        facts = outcome(record)
        expected = record.expected_result or "—"
        lines.append(f"| {record.team} | {facts['icon']} {facts['headline']} | {expected} | {record.description or ''} |")
    lines += ["", "Gate self-tests use a small demo agent with known answers: one that must pass and one with "
              "deliberate mistakes that must fail, so a broken gate shows up at once.", ""]
    return "\n".join(lines) + "\n" + "\n".join(render_github_summary(record) for record in runs)
