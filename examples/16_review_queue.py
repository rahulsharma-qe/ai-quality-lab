"""Example 16: the human review queue, with a team's own judge.

After a run, the queue lists what a person should look at: where a check and the judge disagree,
where a check doubts its own match, and acceptances about to expire. Each likely false alarm comes
with a ready-to-paste accepted finding.

The judge here is a team's own key-free judge (registered with @register_judge) that knows two
rules of meaning: a refund that is "not approved" is a correct answer, and "not sure" is no answer.
Q04 lands in the queue (the forbidden-phrase check and the judge disagree); Q05 doesn't (both fail it). A real team would use the
policy_answer judge (an AI) instead; either way an unvalidated judge is advisory, so it reports
and fills the queue but can't block a release.

Command-line equivalent, after a gate run:  aiquality review --team <team>
Run:  python examples/16_review_queue.py
"""

import tempfile
from datetime import date
from pathlib import Path

from aiquality import TeamConfig
from aiquality.commands import gate_team
from aiquality.judges import Judge, JudgeVerdict, register_judge
from aiquality.review import build_review_queue, render_review_queue


@register_judge("store_meaning_demo")
class StoreMeaningJudge(Judge):
    """Fails an answer that approves a refund ('not approved' is fine) or doesn't answer at all."""

    version = "store-meaning-demo:v1"

    def verdict(self, case, answer_text):
        text = answer_text.lower()
        if "approved" in text and "not approved" not in text:
            return JudgeVerdict(False, "approves a refund")
        if "not sure" in text:
            return JudgeVerdict(False, "doesn't answer the question")
        return JudgeVerdict(True, "answers without promising anything it shouldn't")


EXAMPLES = Path(__file__).parent
config = TeamConfig.from_dict({
    "team": "review_demo",
    "agent": {"adapter": "python_function", "file": "sample_store_agent.py", "function": "answer"},
    "golden_set": "quickstart_team/golden_set.csv",
    "checks": {"required_phrases": {"threshold": 0.8}, "forbidden_phrases": {"threshold": 1.0},
               "answer_judge": {"threshold": 1.0}},
    "judge": {"kind": "store_meaning_demo", "results": str(Path(tempfile.mkdtemp()) / "results.jsonl")},
}, folder=EXAMPLES)

record, decision = gate_team(config, output_dir=Path(tempfile.mkdtemp()), print_reports=False,
                             today=date(2026, 10, 15))
print(render_review_queue(build_review_queue(record, today=date(2026, 10, 15)), config.team))
print("\ngate:", "PASS" if decision.passed else "FAIL", decision.failures)
print("judge:", record.judge["status"], "· can block" if record.judge["blocking"] else "· advisory")
