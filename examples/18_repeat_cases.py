"""Example 18: ask the same cases several times, to see which results hold and which were luck.

A model doesn't give the same answer twice, so one run can make a change look like a fix when the
answer was only lucky that time. Here the store agent answers the opening-hours question right only
some of the time, like a model that hasn't really learned the rule. One run would say PASS or FAIL;
three repeats say "2 of 3", which is the honest result. Each check is counted on its own.

Command-line equivalent (asks the live agent, so a model agent needs its key):
    aiquality repeat --team aeroassist --cases GD13,GD18 --times 3
    aiquality repeat --team aeroassist --changed-between teams/aeroassist/history/v3-policies-1.3-run7 aiquality-runs
Run:  python examples/18_repeat_cases.py
"""

import itertools
import sys
import tempfile
from pathlib import Path

from aiquality import PythonFunctionAgent, TeamConfig
from aiquality.commands import repeat_team
from aiquality.reporting import load_repeat_rows, render_repeats

DEMO = Path(__file__).parent / "gate_demo"
sys.path.insert(0, str(DEMO))
from agents import answer_good  # noqa: E402

_hours_answers = itertools.cycle(["We are open from 9 am to 6 pm, Monday to Saturday.",
                                  "We are open 24/7.",
                                  "We are open from 9 am to 6 pm, Monday to Saturday."])


def answer_unsteady(question: str, conversation=None) -> str:
    """Right on most questions; on opening hours, right only some of the time."""
    if "hours" in question.lower():
        return next(_hours_answers)
    return answer_good(question, conversation)


config = TeamConfig.load(DEMO / "good_team")
agent = PythonFunctionAgent(answer_unsteady, name="store-agent", version="store-agent:unsteady")
output = Path(tempfile.mkdtemp()) / "repeat_check.jsonl"

path, summary = repeat_team(config, ["D01", "D02", "D03"], times=3, output_path=output, agent=agent)
print(render_repeats(summary))

rows = load_repeat_rows(path)
print(f"\n{len(rows)} rows saved, one per case per repeat. The answers behind D01's results:")
for row in rows:
    if row.case_id == "D01":
        statuses = {r["check"]: r["status"] for r in row.results}
        print(f"  repeat {row.repeat}: forbidden_phrases {statuses['forbidden_phrases']}  {row.answer_text}")
