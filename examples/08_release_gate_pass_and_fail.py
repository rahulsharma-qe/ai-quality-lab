"""Example 08: the release gate, once passing and once failing.

examples/gate_demo/ holds two versions of the same agent with the same golden set and attacks:
  good_team       the current agent              -> PASS, exit code 0
  regressed_team  a new version with regressions -> FAIL, exit code 1, with every reason listed
Command-line equivalent:  aiquality gate --team examples/gate_demo/good_team
In CI, exit code 1 blocks the merge (with branch protection switched on).
Run:  python examples/08_release_gate_pass_and_fail.py
"""

import tempfile
from pathlib import Path

from aiquality import TeamConfig
from aiquality.cli import EXIT_OK, EXIT_QUALITY_FAILURE
from aiquality.commands import gate_team

DEMO = Path(__file__).parent / "gate_demo"
results = {}
for team_folder in ("good_team", "regressed_team"):
    config = TeamConfig.load(DEMO / team_folder)
    _, decision = gate_team(config, output_dir=Path(tempfile.mkdtemp()), print_reports=False)
    results[team_folder] = decision

for team_folder, decision in results.items():
    exit_code = EXIT_OK if decision.passed else EXIT_QUALITY_FAILURE
    print(f"{team_folder:<16} {'PASS' if decision.passed else 'FAIL'}  (exit code {exit_code})")
    for reason in decision.failures:
        print(f"{'':<17} why: {reason}")
