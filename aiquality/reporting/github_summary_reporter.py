"""A Markdown summary for the GitHub Actions run page, written for someone reading it cold.

Each team's summary leads with the answer (PASS, PASS with open problems, or FAIL, and for a gate
self-test whether that was the expected result), then four numbers that explain it, and keeps the
detail (check tables, findings, versions) folded underneath. 'aiquality ci-summary' puts an overview
table of every team on top.

Inside GitHub Actions the summary is appended to $GITHUB_STEP_SUMMARY; it is always also written to
<output_dir>/<team>-summary.md.
"""

import os
from pathlib import Path

from aiquality.reporting.report_data import (accepted_pairs, check_rows, findings, percent, rate_text,
                                             result_text, verdict, version_text)
from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord

MAX_FINDINGS = 30


@register_reporter("github_summary")
class GithubSummaryReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        markdown = render_github_summary(record)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{record.team}-summary.md"
        path.write_text(markdown, encoding="utf-8")
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as handle:
                handle.write(markdown + "\n")
        return path


def outcome(record: RunRecord) -> dict:
    """The facts a reader needs first, used by the team summary and the overview table."""
    from aiquality.review import build_review_queue          # the queue reads the reporting package
    rows = check_rows(record)
    blocking = [r for r in rows if r["blocking"]]
    judge_row = next((r for r in rows if record.judge and r["check"] == record.judge["check"]), None)
    result = verdict(record)
    open_problems = len(build_review_queue(record))
    judge_fails = judge_row["failed"] + judge_row["errors"] if judge_row else 0
    if record.expected_result:
        icon = "✅" if result == record.expected_result else "❌"
        headline = (f"{result}, as expected" if result == record.expected_result
                    else f"{result}, but this self-test expects {record.expected_result}: the gate itself may be broken")
    elif result == "PASS" and (open_problems or judge_fails):
        icon, headline = "⚠️", "PASS on the blocking checks, with open problems"
    else:
        icon, headline = {"PASS": ("✅", "PASS"), "FAIL": ("❌", "FAIL")}.get(result, ("📋", result))
    return {"result": result, "icon": icon, "headline": headline, "blocking": blocking,
            "blocking_met": sum(1 for r in blocking if r["gate_meets"]), "judge_row": judge_row,
            "open_problems": open_problems, "accepted": len(accepted_pairs(record))}


def render_github_summary(record: RunRecord) -> str:
    facts = outcome(record)
    gate = record.gate_decision or {}
    lines = [f"## {facts['icon']} {record.team}: {facts['headline']}", ""]
    if record.description:
        lines += [f"> {record.description}", ""]
    if gate.get("failures"):
        lines += ["**Why it failed**", ""] + [f"- {f}" for f in gate["failures"]] + [""]
    lines += _key_numbers(record, facts) + [""]
    warnings = [w for w in gate.get("warnings", []) if not w.startswith("answer_judge is advisory")]  # in the table
    if warnings:
        lines += ["**Warnings**", ""] + [f"- {w}" for w in warnings] + [""]
    lines += _details("Checks", _check_table(record))
    counted = _blocking_findings(record)
    note = (["The gate still passes: every check's pass rate is within its bar, and no high-priority case failed.", ""]
            if counted and facts["result"] == "PASS" else [])
    if counted:
        lines += _details(f"Failures the gate counted ({len(counted)})", note + _finding_lines(counted))
    if facts["judge_row"]:
        judge_findings = _judge_findings(record)
        lines += _details(f"Judge findings ({len(judge_findings)}), advisory unless the judge has qualified",
                          _finding_lines(judge_findings))
    if gate.get("accepted_findings"):
        lines += _details(f"Accepted findings ({len(gate['accepted_findings'])}), passes until they expire",
                          [f"- {a['case']} / {a['check']}: {a['reason']} ({a['approved_by']}, expires {a['expires']})"
                           for a in gate["accepted_findings"]])
    if record.attacks:
        lines += _details(f"Attacks: {record.attacks['resisted']} of {record.attacks['total']} resisted",
                          ["| Family | Resisted | Broken | Errors |", "|---|---|---|---|"]
                          + [f"| {f['family']} | {f['resisted']} / {f['total']} | {f['broken']} | {f['errors']} |"
                             for f in record.attacks["families"]])
    lines += _details("Run details", _run_details(record))
    return "\n".join(lines).rstrip() + "\n"


def _key_numbers(record: RunRecord, facts: dict) -> list[str]:
    accepted = f" ({facts['accepted']} findings accepted by a person)" if facts["accepted"] else ""
    rows = [("Blocking checks", f"{facts['blocking_met']} of {len(facts['blocking'])} meet their bar{accepted}")]
    if record.attacks:
        rows.append(("Attacks", f"{record.attacks['resisted']} of {record.attacks['total']} resisted"))
    judge_row = facts["judge_row"]
    if judge_row:
        judged = judge_row["passed"] + judge_row["failed"] + judge_row["errors"]
        role = "can block" if record.judge["blocking"] else f"advisory, {record.judge['status'].replace('_', ' ')}"
        rows.append((f"AI judge ({role})", f"{judge_row['passed']} of {judged} answers pass"))
    if facts["open_problems"]:
        rows.append(("Needs a person", f"{facts['open_problems']} items where the checks and the judge disagree, or a "
                                        f"check doubts itself · `aiquality review --team {record.team}`"))
    return ["| | |", "|---|---|"] + [f"| {name} | {value} |" for name, value in rows]


def _check_table(record: RunRecord) -> list[str]:
    lines = ["| Check | Pass rate | Bar | Result | Pass | Fail | N/A | Error |", "|---|---|---|---|---|---|---|---|"]
    for row in check_rows(record):
        lines.append(f"| {row['label']} | {rate_text(row)} | {percent(row['threshold'])} | {result_text(row)} | "
                     f"{row['passed']} | {row['failed']} | {row['not_applicable']} | {row['errors']} |")
    return lines


def _blocking_findings(record: RunRecord) -> list:
    """Failures of blocking checks that no person has accepted: the ones the gate counts."""
    blocking = {s["check"] for s in record.summaries if s.get("blocking", True)}
    accepted = accepted_pairs(record)
    return [(o, r) for o, r in findings(record)
            if r["check"] in blocking and (o["case_id"], r["check"]) not in accepted]


def _judge_findings(record: RunRecord) -> list:
    return [(o, r) for o, r in findings(record) if r["check"] == record.judge["check"]]


def _finding_lines(found: list) -> list[str]:
    if not found:
        return ["None."]
    lines = [f"- **{o['case_id']}** {r['check']}: {r['reason']}" for o, r in found[:MAX_FINDINGS]]
    if len(found) > MAX_FINDINGS:
        lines.append(f"- … {len(found) - MAX_FINDINGS} more in the run record")
    return lines


def _run_details(record: RunRecord) -> list[str]:
    lines = [f"- Agent: `{record.agent_version}` ({record.run_mode} answers)",
             f"- Golden set: {record.golden_set_name} ({version_text(record.golden_set_version)})"]
    if record.judge:
        lines.append(f"- Judge: `{record.judge['version']}` ({record.judge['mode']} verdicts)")
    when = record.created_at.replace("T", " ")[:16] + " UTC" if record.created_at.endswith("+00:00") else record.created_at
    lines.append(f"- Run: `{record.run_id}` · {when}" + (f" · commit `{record.git_commit}`" if record.git_commit else ""))
    return lines


def _details(title: str, body: list[str]) -> list[str]:
    return ["<details><summary>" + title + "</summary>", ""] + body + ["", "</details>", ""]
