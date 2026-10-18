"""Example 14: compare two runs case by case, to see what a change fixed and what it broke.

An average can go up while a case that used to pass breaks. Here the "before" agent is the
regressed store agent; the "after" agent fixes the receipt rule but now claims the shop is
open 24/7. Pass rates alone would call that progress; the comparison names the regression.
It also says, per check, how many cases got better and how many worse, and whether that split is
bigger than chance: on 9 cases it isn't, which is why one run of a few cases proves little.

Command-line equivalent (two saved run records, the last run in each by default):
    aiquality compare history/before.jsonl aiquality-runs --markdown comparison.md
    aiquality compare before.jsonl after.jsonl --fail-on-new-failures   # exit 1 on a regression
Run:  python examples/14_compare_two_runs.py
"""

import sys
import tempfile
from pathlib import Path

from aiquality import PythonFunctionAgent, TeamConfig, compare_runs, evaluate_team
from aiquality.reporting import render_comparison

DEMO = Path(__file__).parent / "gate_demo"
sys.path.insert(0, str(DEMO))
from agents import answer_good, answer_regressed  # noqa: E402


def answer_fixed_but_broke_hours(question: str, conversation=None) -> str:
    """Fixes the receipt rule, and breaks the opening-hours answer on the way."""
    if "hours" in question.lower():
        return "We are open 24/7."
    return answer_good(question, conversation)


config = TeamConfig.load(DEMO / "good_team")
runs = Path(tempfile.mkdtemp())


def run(answer_function, version):
    agent = PythonFunctionAgent(answer_function, name="store-agent", version=version)
    return evaluate_team(config, agent=agent, output_dir=runs, print_reports=False)


before = run(answer_regressed, "store-agent:v1")
after = run(answer_fixed_but_broke_hours, "store-agent:v2")
comparison = compare_runs(before, after)
print(render_comparison(comparison))
print("\nregressions:", [c.case_id for c in comparison.newly_failing])
