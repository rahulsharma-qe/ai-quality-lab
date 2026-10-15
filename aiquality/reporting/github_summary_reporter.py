"""A Markdown summary for the GitHub Actions run page.

Inside GitHub Actions it is appended to $GITHUB_STEP_SUMMARY, so it shows on the run page.
It is always also written to <output_dir>/<team>-summary.md.
"""

import os
from pathlib import Path

from aiquality.reporting.report_data import (accepted_pairs, check_rows, findings, judge_text, percent,
                                             rate_text, result_text, verdict, version_text)
from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord

MAX_FINDINGS = 20


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


def render_github_summary(record: RunRecord) -> str:
    gate = record.gate_decision or {}
    icon = {"PASS": "✅", "FAIL": "❌"}.get(verdict(record), "📋")
    lines = [f"## {icon} aiquality · {record.team}: {verdict(record)}", "",
             f"Agent `{record.agent_version}` · mode `{record.run_mode}` · golden set "
             f"{record.golden_set_name} ({version_text(record.golden_set_version)}) · run `{record.run_id}`", ""]
    if record.judge:
        lines[-1:-1] = [f"Judge: {judge_text(record).removeprefix('judge ')}"]
    if gate.get("failures"):
        lines += ["**Why it failed**", ""] + [f"- {f}" for f in gate["failures"]] + [""]
    lines += ["| Check | Pass rate | Bar | Result | Pass | Fail | N/A | Error |", "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {row['label']} | {rate_text(row)} | {percent(row['threshold'])} | {result_text(row)} | "
              f"{row['passed']} | {row['failed']} | {row['not_applicable']} | {row['errors']} |"
              for row in check_rows(record)]
    if record.attacks:
        lines += ["", f"**Attacks:** {record.attacks['resisted']} of {record.attacks['total']} resisted "
                      f"({percent(record.attacks['resistance_rate'])})", "",
                  "| Family | Resisted | Broken | Errors |", "|---|---|---|---|"]
        lines += [f"| {f['family']} | {f['resisted']} / {f['total']} | {f['broken']} | {f['errors']} |"
                  for f in record.attacks["families"]]
    if gate.get("accepted_findings"):
        lines += ["", "**Accepted findings** (count as passes until they expire)", ""]
        lines += [f"- {a['case']} / {a['check']}: {a['reason']} — {a['approved_by']}, expires {a['expires']}"
                  for a in gate["accepted_findings"]]
    if gate.get("warnings"):
        lines += ["", "**Warnings**", ""] + [f"- {w}" for w in gate["warnings"]]
    accepted = accepted_pairs(record)
    found = findings(record)
    lines += ["", f"<details><summary>Findings ({len(found)})</summary>", ""]
    for outcome, result in found[:MAX_FINDINGS]:
        tag = " (accepted)" if (outcome["case_id"], result["check"]) in accepted else ""
        lines.append(f"- **{result['status']}{tag}** `{outcome['case_id']}` {result['check']}: {result['reason']}")
    if len(found) > MAX_FINDINGS:
        lines.append(f"- … {len(found) - MAX_FINDINGS} more in the run record")
    lines += ["", "</details>"]
    return "\n".join(lines)
