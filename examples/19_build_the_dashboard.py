"""Example 19: one page for every team, built from the run records already saved.

The per-run report covers one team and one run, and the CI run page one change. The dashboard
shows each team's latest gate, its accepted findings with their expiry, and its saved runs from
oldest to newest, so a reader sees where every team stands and how it got there. It is a static
HTML file (tables only): build it again after new runs.

Here it gates the second team (post_order_support) into a fresh folder, then builds the page from
that run and from AeroAssist's history folders (teams/aeroassist/history/*).

Command-line equivalent:
    aiquality gate --team post_order_support
    aiquality dashboard --output aiquality-runs/dashboard.html
Run:  python examples/19_build_the_dashboard.py
"""

import tempfile
from pathlib import Path

from aiquality import TeamConfig
from aiquality.commands import gate_team
from aiquality.reporting.dashboard import collect_team_runs, write_dashboard

TEAMS = Path(__file__).resolve().parents[1] / "teams"
runs = Path(tempfile.mkdtemp())

gate_team(TeamConfig.load(TEAMS / "post_order_support"), output_dir=runs, print_reports=False)
page = write_dashboard(runs / "dashboard.html", runs_dir=runs, teams_dir=TEAMS)

for team in collect_team_runs(runs, TEAMS):
    gate = team.latest_gate
    result = ("PASS" if gate.gate_decision["passed"] else "FAIL") if gate else "no gate run"
    print(f"{team.team:20} latest gate {result:12} saved runs {len(team.runs):2}  "
          f"accepted findings {len(team.accepted_findings)}")
print(f"\nopen {page} in a browser")
