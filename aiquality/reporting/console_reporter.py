"""Plain-text report for the terminal and CI logs."""

from pathlib import Path

from aiquality.reporting.report_data import version_text
from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord

MAX_FINDINGS_SHOWN = 25


@register_reporter("console")
class ConsoleReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        print(render_console_report(record))
        return None


def render_console_report(record: RunRecord) -> str:
    golden_count = sum(1 for o in record.outcomes if o.get("category") != "attack")
    lines = [
        f"aiquality {record.command} · team {record.team}" + (f" · client {record.client}" if record.client else ""),
        f"agent {record.agent_name} ({record.agent_version}) · mode {record.run_mode} · run {record.run_id}",
        f"golden set {record.golden_set_name} ({version_text(record.golden_set_version)})",
    ]
    if golden_count:
        lines += [
            "",
            f"golden cases: {golden_count}",
            f"{'check':<22}{'pass rate':>10}{'threshold':>11}  {'result':<8}{'pass':>6}{'fail':>6}{'n/a':>6}{'error':>7}",
            "-" * 78,
        ]
        for s in record.summaries:
            rate = "-" if s["pass_rate"] is None else f"{s['pass_rate']:.0%}"
            verdict = {True: "MEETS", False: "BELOW", None: "NO DATA"}[s["meets_threshold"]]
            lines.append(f"{s['check']:<22}{rate:>10}{s['threshold']:>11.0%}  {verdict:<8}"
                         f"{s['passed']:>6}{s['failed']:>6}{s['not_applicable']:>6}{s['errors']:>7}")

    if record.attacks:
        lines += _attack_lines(record.attacks)

    accepted = {(a["case"], a["check"]): a for a in (record.gate_decision or {}).get("accepted_findings", [])}
    findings = [(o["case_id"], r) for o in record.outcomes for r in o["results"] if r["status"] in ("FAIL", "ERROR")]
    id_width = min(max([len(case_id) for case_id, _ in findings] + [6]) + 2, 40)
    lines += ["", f"findings: {len(findings)}"]
    for case_id, r in findings[:MAX_FINDINGS_SHOWN]:
        note = ""
        if (case_id, r["check"]) in accepted:
            note = f"  [ACCEPTED until {accepted[(case_id, r['check'])]['expires']}]"
        lines.append(f"  {r['status']:<6}{case_id:<{id_width}}{r['check']:<20}{r['reason']}{note}")
        if r.get("evidence"):
            lines.append(f"{'':<{8 + id_width + 20}}in: \"{r['evidence']}\"")
    if len(findings) > MAX_FINDINGS_SHOWN:
        lines.append(f"  ... {len(findings) - MAX_FINDINGS_SHOWN} more in the run record")
    if record.gate_decision:
        lines += _gate_lines(record.gate_decision)
    return "\n".join(lines)


def _gate_lines(gate: dict) -> list[str]:
    lines = ["", "=" * 78, f"RELEASE GATE: {gate['decision']}"]
    lines += [f"  why: {failure}" for failure in gate["failures"]]
    if gate["accepted_findings"]:
        lines.append(f"  accepted findings ({len(gate['accepted_findings'])}), counted as passes until they expire:")
        lines += [f"    {a['case']} / {a['check']}: {a['reason']} (approved by {a['approved_by']}, "
                  f"expires {a['expires']})" for a in gate["accepted_findings"]]
    lines += [f"  warning: {warning}" for warning in gate["warnings"]]
    lines.append("=" * 78)
    return lines


def _attack_lines(attacks: dict) -> list[str]:
    rate = "-" if attacks["resistance_rate"] is None else f"{attacks['resistance_rate']:.0%}"
    lines = ["", f"attacks: {attacks['resisted']} of {attacks['total']} resisted ({rate})",
             f"  {'family':<24}{'resisted':>9}{'broken':>8}{'errors':>8}"]
    for f in attacks["families"]:
        lines.append(f"  {f['family']:<24}{f['resisted']:>5} / {f['total']:<2}{f['broken']:>6}{f['errors']:>8}")
    return lines
