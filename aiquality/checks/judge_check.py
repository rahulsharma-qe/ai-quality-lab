"""The answer_judge check: a judge grades each golden answer's meaning.

The judge is built from the team's 'judge:' block and handed to this check by the platform.
Whether the check may block a release is decided by the judge's validation status, not by the
config: an unvalidated or unqualified judge is advisory (see aiquality/judging.py).
Attack cases are left to the safety checks, so the judge isn't paid to grade them.
"""

from aiquality.attacks import ATTACK_CATEGORY
from aiquality.checks.base import Check
from aiquality.checks.registry import register_check


@register_check("answer_judge")
class AnswerJudgeCheck(Check):
    description = ("A judge (an AI, validated against people's labels) grades whether the answer is correct "
                   "and grounded in the team's policy. Needs a 'judge:' block; advisory until the judge qualifies.")

    def evaluate(self, case, response):
        judge = self.options.get("judge")
        if judge is None:
            return self.errored(case, "no judge: add a 'judge:' block to the team config")
        if case.category == ATTACK_CATEGORY:
            return self.not_applicable(case, "attack cases are graded by the safety checks")
        verdict = judge.verdict(case, response.answer_text)
        if verdict.passed:
            return self.passed(case, verdict.reason)
        return self.failed(case, verdict.reason)
