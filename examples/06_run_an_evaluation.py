"""Example 06: evaluate a whole team from its config, the same way the command line does.

The quickstart team (examples/quickstart_team/team.json) has five cases, and two of
them fail on purpose so you can read real findings:
  Q04  the answer says "not approved" and the forbidden phrase is "approved". Phrase
       matching can't understand "not", so it fails and is flagged as a possible false alarm.
  Q05  the agent never says "Sunday delivery": a genuine miss.

Command-line equivalent:  aiquality evaluate --team examples/quickstart_team
Run:  python examples/06_run_an_evaluation.py
"""

import tempfile
from pathlib import Path

from aiquality import TeamConfig, evaluate_team

TEAM_FOLDER = Path(__file__).parent / "quickstart_team"

config = TeamConfig.load(TEAM_FOLDER)
record = evaluate_team(config, output_dir=Path(tempfile.mkdtemp()))

# The run record is plain data: use it in your own scripts or dashboards.
below_bar = [s["check"] for s in record.summaries if s["meets_threshold"] is False]
print("\nchecks below their threshold:", below_bar or "none")
