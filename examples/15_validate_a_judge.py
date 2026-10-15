"""Example 15: measure a judge against people's labels before trusting it.

A judge (usually an AI) grades meaning, but it can be wrong too, so it earns trust per version:
two numbers on answers a person has labelled PASS or FAIL.
  catches real failures      of the answers a person FAILED, the share the judge also failed
  leaves good answers alone  of the answers a person PASSED, the share the judge also passed
Both must clear their bar on the held-back half, or the judge stays advisory.

Here the phrase judge (key-free, words only) is measured. It catches every real failure, but it
also fails a good answer that says the right thing in other words, so it doesn't qualify.
For a team: put labels in a file, point 'judge.labels' at it, then run
    aiquality validate-judge --team <team> --split holdout
Run:  python examples/15_validate_a_judge.py
"""

from aiquality import GoldenCaseBuilder
from aiquality.judges import PhraseJudge
from aiquality.judges.validation import LabelledAnswer, render_validation, validate_judge

QUESTION = "I booked 3 days ago. Can I get a full refund?"


def labelled(case_id: str, answer: str, person_says: str, why: str) -> LabelledAnswer:
    case = GoldenCaseBuilder(case_id, QUESTION).category("edge").must_include("24 hours").build()
    return LabelledAnswer(case, answer, person_says, category="edge", label_reason=why)


labelled_answers = [
    labelled("L1", "Full refunds are only within 24 hours of booking, so not now.", "PASS", "correct"),
    labelled("L2", "A full refund is only possible within a day of booking.", "PASS", "correct, other words"),
    labelled("L3", "Yes, you'll get a full refund.", "FAIL", "promises a refund that isn't due"),
    labelled("L4", "Refunds are available for 30 days.", "FAIL", "wrong window"),
]

run = validate_judge(PhraseJudge(), labelled_answers, split="holdout")
print(render_validation(run))
