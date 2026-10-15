"""Plain-text report for the terminal and CI logs."""

from pathlib import Path

from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord

MAX_FINDINGS_SHOWN = 25


@register_reporter("console")
class ConsoleReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        print(render_console_report(record))
        return None


def render_console_report(record: RunRecord) -> str:
    lines = [
        f"aiquality {record.command} · team {record.team}" + (f" · client {record.client}" if record.client else ""),
        f"agent {record.agent_name} ({record.agent_version}) · mode {record.run_mode}",
        f"golden set {record.golden_set_name} (version {record.golden_set_version}) · {record.case_count} cases · run {record.run_id}",
        "",
        f"{'check':<22}{'pass rate':>10}{'threshold':>11}  {'result':<8}{'pass':>6}{'fail':>6}{'n/a':>6}{'error':>7}",
        "-" * 78,
    ]
    for s in record.summaries:
        rate = "-" if s["pass_rate"] is None else f"{s['pass_rate']:.0%}"
        verdict = {True: "MEETS", False: "BELOW", None: "NO DATA"}[s["meets_threshold"]]
        lines.append(f"{s['check']:<22}{rate:>10}{s['threshold']:>11.0%}  {verdict:<8}"
                     f"{s['passed']:>6}{s['failed']:>6}{s['not_applicable']:>6}{s['errors']:>7}")

    findings = [(o["case_id"], r) for o in record.outcomes for r in o["results"] if r["status"] in ("FAIL", "ERROR")]
    lines += ["", f"findings: {len(findings)}"]
    for case_id, r in findings[:MAX_FINDINGS_SHOWN]:
        lines.append(f"  {r['status']:<6}{case_id:<8}{r['check']:<20}{r['reason']}")
        if r.get("evidence"):
            lines.append(f"{'':<34}in: \"{r['evidence']}\"")
    if len(findings) > MAX_FINDINGS_SHOWN:
        lines.append(f"  ... {len(findings) - MAX_FINDINGS_SHOWN} more in the run record")
    return "\n".join(lines)
