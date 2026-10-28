"""One self-contained HTML file per team: opens in any browser, easy to keep as a CI artifact."""

from html import escape
from pathlib import Path

from aiquality.reporting.report_data import (accepted_pairs, check_rows, findings, judge_text, percent,
                                             rate_text, result_text, verdict, version_text)
from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord
from aiquality.dates import shown_day

STYLE = """
:root { --bg:#f7f8fa; --panel:#fff; --fg:#1d2430; --muted:#5b6577; --line:#d8dde6;
        --pass:#1f7a4d; --fail:#b42318; --warn:#9a6700; }
@media (prefers-color-scheme: dark) { :root { --bg:#12161d; --panel:#1a2029; --fg:#e3e8ef; --muted:#9aa5b5;
        --line:#2c3542; --pass:#4cc38a; --fail:#ff7b72; --warn:#e3b341; } }
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, -apple-system, Segoe UI, sans-serif;
       margin:0; padding:24px max(16px, 4vw); }
main { max-width:1000px; margin:0 auto; display:grid; gap:20px; }
h1 { font-size:24px; margin:0; } h2 { font-size:18px; margin:0 0 8px; }
.meta { color:var(--muted); font-size:13px; }
.banner { padding:14px 16px; border-radius:8px; border:1px solid var(--line); background:var(--panel);
          font-weight:600; border-left:6px solid var(--muted); }
.banner.PASS { border-left-color:var(--pass); } .banner.FAIL { border-left-color:var(--fail); }
section { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
.PASS, .MEETS { color:var(--pass); } .FAIL, .BELOW, .ERROR { color:var(--fail); } .ACCEPTED { color:var(--warn); }
details { margin-top:4px; } summary { cursor:pointer; color:var(--muted); font-size:13px; }
blockquote { margin:6px 0; padding:6px 10px; border-left:3px solid var(--line); white-space:pre-wrap; }
"""


@register_reporter("html")
class HtmlReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{record.team}-report.html"
        path.write_text(render_html_report(record), encoding="utf-8")
        return path


def render_html_report(record: RunRecord) -> str:
    gate = record.gate_decision or {}
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
             f"<title>aiquality · {escape(record.team)}</title><style>{STYLE}</style></head><body><main>",
             f"<header><h1>aiquality · {escape(record.team)}</h1><div class='meta'>"
             f"{escape(record.command)} · agent {escape(record.agent_name)} ({escape(record.agent_version)}) · "
             f"mode {escape(record.run_mode)} · golden set {escape(record.golden_set_name)} "
             f"({escape(version_text(record.golden_set_version))}) · run {escape(record.run_id)} · {escape(record.created_at)}"
             + (f"<br>{escape(judge_text(record))}" if record.judge else "") + "</div></header>"]

    decision = verdict(record)
    parts.append(f"<div class='banner {escape(decision)}'>Release gate: {escape(decision)}</div>")
    if gate.get("failures"):
        parts.append("<section><h2>Why it failed</h2><ul>"
                     + "".join(f"<li>{escape(f)}</li>" for f in gate["failures"]) + "</ul></section>")

    rows = "".join(
        f"<tr><td>{escape(row['label'])}</td><td>{escape(rate_text(row))}</td><td>{percent(row['threshold'])}</td>"
        f"<td class='{result_text(row)}'>{result_text(row)}</td><td>{row['passed']}</td><td>{row['failed']}</td>"
        f"<td>{row['not_applicable']}</td><td>{row['errors']}</td></tr>" for row in check_rows(record))
    parts.append("<section><h2>Golden cases</h2><table><tr><th>Check</th><th>Pass rate</th><th>Bar</th><th>Result</th>"
                 f"<th>Pass</th><th>Fail</th><th>N/A</th><th>Error</th></tr>{rows}</table></section>")

    if record.attacks:
        attack_rows = "".join(
            f"<tr><td>{escape(f['family'])}</td><td>{f['resisted']} / {f['total']}</td><td>{f['broken']}</td>"
            f"<td>{f['errors']}</td></tr>" for f in record.attacks["families"])
        parts.append(f"<section><h2>Attacks: {record.attacks['resisted']} of {record.attacks['total']} resisted "
                     f"({percent(record.attacks['resistance_rate'])})</h2><table><tr><th>Family</th>"
                     f"<th>Resisted</th><th>Broken</th><th>Errors</th></tr>{attack_rows}</table></section>")

    if gate.get("accepted_findings"):
        accepted_rows = "".join(
            f"<tr><td>{escape(a['case'])}</td><td>{escape(a['check'])}</td><td>{escape(a['reason'])}</td>"
            f"<td>{escape(a['approved_by'])}</td><td>{escape(shown_day(a['expires']))}</td></tr>" for a in gate["accepted_findings"])
        parts.append("<section><h2>Accepted findings</h2><p class='meta'>Reviewed and accepted by a person; they "
                     "count as passes until they expire.</p><table><tr><th>Case</th><th>Check</th><th>Reason</th>"
                     f"<th>Approved by</th><th>Expires</th></tr>{accepted_rows}</table></section>")
    if gate.get("warnings"):
        parts.append("<section><h2>Warnings</h2><ul>"
                     + "".join(f"<li class='ACCEPTED'>{escape(w)}</li>" for w in gate["warnings"]) + "</ul></section>")

    accepted = accepted_pairs(record)
    finding_rows = []
    for outcome, result in findings(record):
        status = "ACCEPTED" if (outcome["case_id"], result["check"]) in accepted else result["status"]
        evidence = f"<blockquote>{escape(result['evidence'])}</blockquote>" if result.get("evidence") else ""
        answer = (f"<details><summary>question and answer</summary><blockquote>{escape(outcome['question'])}"
                  f"</blockquote><blockquote>{escape(outcome.get('answer_text') or outcome.get('error') or '')}"
                  f"</blockquote></details>")
        finding_rows.append(f"<tr><td class='{status}'>{status}</td><td>{escape(outcome['case_id'])}</td>"
                            f"<td>{escape(result['check'])}</td><td>{escape(result['reason'])}{evidence}{answer}</td></tr>")
    parts.append(_review_section(record))
    parts.append(f"<section><h2>Findings ({len(finding_rows)})</h2><table><tr><th>Status</th><th>Case</th>"
                 f"<th>Check</th><th>Detail</th></tr>{''.join(finding_rows)}</table></section>")
    parts.append("</main></body></html>")
    return "".join(parts)


def _review_section(record: RunRecord) -> str:
    from aiquality.review import build_review_queue          # the queue reads the reporting package
    items = build_review_queue(record)
    if not items:
        return "<section><h2>Needs a person (0)</h2><p class='meta'>Nothing to review.</p></section>"
    rows = "".join(
        f"<tr><td>{escape(i.case_id)}</td><td>{escape(i.check)}</td><td>{escape(i.why)}"
        f"<blockquote>{escape(i.finding)}</blockquote>"
        + (f"<blockquote>judge {escape(i.judge)}</blockquote>" if i.judge else "")
        + (f"<details><summary>accept it (paste into the team config)</summary><blockquote>"
           f"{escape(i.accept_snippet)}</blockquote></details>" if i.accept_snippet else "")
        + "</td></tr>" for i in items)
    return (f"<section><h2>Needs a person ({len(items)})</h2><p class='meta'>Where a check and the judge disagree, "
            f"or a check doubts its own match. A person decides; an acceptance goes into the team config through "
            f"a reviewed pull request.</p><table><tr><th>Case</th><th>Check</th><th>Why</th></tr>{rows}</table></section>")

