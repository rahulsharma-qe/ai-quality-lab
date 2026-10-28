"""One page for every team: where each stands now, and how it changed run by run.

    aiquality dashboard --output aiquality-runs/dashboard.html

The per-run HTML report covers one team and one run; the CI run page covers one change. This page
reads what is already saved (the latest runs in the runs folder, and each team's history folders)
and shows, per team, its latest gate, its accepted findings with their expiry, and a table of its
saved runs from oldest to newest. Tables only: it opens offline and works as a CI artifact.

It is a static file, built from the run records at the moment the command runs: run the command
again after new runs (CI builds it after every gate).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Optional

from aiquality.config import TeamConfig
from aiquality.errors import SetupError
from aiquality.reporting.html_reporter import STYLE
from aiquality.reporting.report_data import percent
from aiquality.reporting.run_record import RUN_RECORDS_FILE, RunRecord, load_run_records
from aiquality.dates import shown_day

EXPIRES_SOON_DAYS = 14
HISTORY_FOLDER = "history"


@dataclass
class TeamRuns:
    """A team, the runs saved for it (oldest first, each with a label), and its accepted findings."""

    team: str
    description: str = ""
    runs: list = field(default_factory=list)          # [(label, RunRecord)]
    accepted_findings: list = field(default_factory=list)
    report_file: Optional[str] = None

    @property
    def latest_gate(self) -> Optional[RunRecord]:
        gated = [record for _, record in self.runs if record.gate_decision]
        return gated[-1] if gated else None


def collect_team_runs(runs_dir="aiquality-runs", teams_dir="teams") -> list[TeamRuns]:
    """Every team that has a saved run: from the runs folder (its last run per team) and from
    teams/<team>/history/<run>/run_records.jsonl (the last run in each history folder)."""
    teams: dict[str, TeamRuns] = {}
    runs_dir, teams_dir = Path(runs_dir), Path(teams_dir)
    for folder in sorted(teams_dir.glob(f"*/{HISTORY_FOLDER}/*")):
        records = _records(folder / RUN_RECORDS_FILE)
        if records:
            _team(teams, records[-1]).runs.append((folder.name, records[-1]))
    latest = {}
    for record in _records(runs_dir / RUN_RECORDS_FILE):
        latest[record.team] = record
    for record in latest.values():
        team = _team(teams, record)
        team.runs.append(("latest run", record))
        report = runs_dir / f"{record.team}-report.html"
        team.report_file = report.name if report.is_file() else None
    if not teams:
        raise SetupError(f"no run records in {runs_dir} or in {teams_dir}/*/{HISTORY_FOLDER}: run a gate first")
    for team in teams.values():
        team.runs.sort(key=lambda run: run[1].created_at)
        team.accepted_findings = _accepted_findings(teams_dir / team.team)
    return sorted(teams.values(), key=lambda team: (bool(team.latest_gate and team.latest_gate.expected_result),
                                                   team.team))


def render_dashboard(teams: list[TeamRuns], today: Optional[date] = None) -> str:
    today = today or date.today()
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             f"<title>Quality dashboard</title><style>{STYLE}{_EXTRA_STYLE}</style></head><body><main>",
             "<h1>Quality dashboard</h1>",
             f"<p class='meta'>Built {shown_day(today)} from the saved run records. A static page: build it "
             "again after new runs.</p>", _overview(teams, today)]
    parts += [_team_section(team, today) for team in teams]
    parts.append("</main></body></html>")
    return "\n".join(parts)


def write_dashboard(output, runs_dir="aiquality-runs", teams_dir="teams", today: Optional[date] = None) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(collect_team_runs(runs_dir, teams_dir), today), encoding="utf-8")
    return output


# ----------------------------------------------------------------------------------------

_EXTRA_STYLE = """
main { max-width:1280px; } table { font-size:13px; }
.soon { color:var(--warn); font-weight:600; } .num { text-align:right; } .nowrap { white-space:nowrap; }
td.num { white-space:nowrap; }
td.version { font-size:12px; color:var(--muted); white-space:nowrap; }
"""


def _overview(teams: list[TeamRuns], today: date) -> str:
    rows = []
    for team in teams:
        gate = team.latest_gate
        result = _gate_text(gate) if gate else "<span class='meta'>no gate run</span>"
        soon = [f for f in team.accepted_findings if f.is_active(today) and f.expires <= today + timedelta(EXPIRES_SOON_DAYS)]
        active = [f for f in team.accepted_findings if f.is_active(today)]
        accepted = f"{len(active)}" + (f" <span class='soon'>({len(soon)} expire within {EXPIRES_SOON_DAYS} days)</span>"
                                       if soon else "")
        rows.append(f"<tr><td><a href='#{escape(team.team)}'>{escape(team.team)}</a></td><td>{result}</td>"
                    f"<td>{escape(gate.golden_set_version) if gate else '-'}</td><td>{accepted}</td>"
                    f"<td>{len(team.runs)}</td><td>{escape(team.description)}</td></tr>")
    return ("<section><h2>Every team now</h2><table><tr><th>Team</th><th>Latest gate</th><th>Golden set</th>"
            "<th>Accepted findings</th><th>Saved runs</th><th>What it is</th></tr>" + "".join(rows) + "</table></section>")


def _team_section(team: TeamRuns, today: date) -> str:
    checks = list(dict.fromkeys(s["check"] for _, record in team.runs for s in record.summaries))
    head = "".join(f"<th class='num'>{escape(check.replace('_', ' '))}</th>" for check in checks)
    prefix = _common_prefix([record.agent_version for _, record in team.runs])
    rows = []
    for label, record in team.runs:
        rates = {s["check"]: s.get("pass_rate") for s in record.summaries}
        cells = "".join(f"<td class='num'>{percent(rates.get(check))}</td>" for check in checks)
        attacks = percent(record.attacks.get("resistance_rate")) if record.attacks else "-"
        rows.append(f"<tr><td class='nowrap'>{escape(label)}</td><td class='nowrap'>{escape(record.created_at[:10])}</td>"
                    f"<td class='version' title='{escape(record.agent_version)}'>"
                    f"{escape(record.agent_version[len(prefix):] or record.agent_version)}</td><td>{escape(record.golden_set_version)}</td>"
                    f"<td>{_gate_text(record) if record.gate_decision else '-'}</td>{cells}"
                    f"<td class='num'>{attacks}</td></tr>")
    versions = {record.golden_set_version for _, record in team.runs}
    note = (f"<p class='meta'>These runs used {len(versions)} golden set versions; pass rates from different "
            "versions are not directly comparable.</p>" if len(versions) > 1 else "")
    report = (f"<p><a href='{escape(team.report_file)}'>Latest run report</a></p>" if team.report_file else "")
    shared = (f"<p class='meta'>Agent versions all start with <code>{escape(prefix)}</code>; hover a version "
              "for the full name.</p>" if prefix else "")
    return (f"<section id='{escape(team.team)}'><h2>{escape(team.team)}</h2>{_findings(team, today)}{shared}"
            "<table><tr><th>Run</th><th>Date</th><th>Agent</th><th>Golden set</th><th>Gate</th>"
            f"{head}<th class='num'>attacks resisted</th></tr>" + "".join(rows) + f"</table>{note}{report}</section>")


def _findings(team: TeamRuns, today: date) -> str:
    active = [f for f in team.accepted_findings if f.is_active(today)]
    if not active:
        return ""
    items = "".join(
        f"<li>{escape(f.case)} / {escape(f.check)}: expires "
        f"<span class='{'soon' if f.expires <= today + timedelta(EXPIRES_SOON_DAYS) else ''}'>{shown_day(f.expires)}</span>"
        f" — {escape(f.reason)}</li>" for f in sorted(active, key=lambda f: f.expires))
    return f"<p class='meta'>Accepted findings (reviewed false alarms, each with an expiry):</p><ul>{items}</ul>"


def _gate_text(record: RunRecord) -> str:
    passed = record.gate_decision.get("passed")
    word = "PASS" if passed else "FAIL"
    expected = f" (expected {record.expected_result})" if record.expected_result else ""
    return f"<span class='{word}'>{word}</span>{escape(expected)}"


def _common_prefix(versions: list) -> str:
    """The part every version shares, up to a ':' boundary ('recorded:aeroassist-rag:model:'), or ''."""
    if len(set(versions)) < 2:
        return ""
    prefix = versions[0]
    for version in versions[1:]:
        while not version.startswith(prefix):
            prefix = prefix[:-1]
    return prefix[:prefix.rfind(":") + 1]


def _team(teams: dict, record: RunRecord) -> TeamRuns:
    if record.team not in teams:
        teams[record.team] = TeamRuns(record.team, record.description or "")
    elif record.description:
        teams[record.team].description = record.description
    return teams[record.team]


def _records(path: Path) -> list[RunRecord]:
    return load_run_records(path) if path.is_file() else []


def _accepted_findings(team_folder: Path) -> list:
    if not team_folder.is_dir():
        return []
    try:
        return TeamConfig.load(team_folder).accepted_findings
    except SetupError:
        return []
