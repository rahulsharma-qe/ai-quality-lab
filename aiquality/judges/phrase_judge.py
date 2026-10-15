"""A key-free judge that grades with the golden case's phrase lists.

Deterministic and free, so plumbing can be tested without a key. It checks words, not meaning:
it can't tell a correct answer in other words from a wrong one. Use it to test the pipeline, and
the policy judge to grade meaning.
"""

from aiquality.checks.phrase_matching import find_any
from aiquality.judges.base import Judge, JudgeVerdict
from aiquality.judges.registry import register_judge


@register_judge("phrase")
class PhraseJudge(Judge):
    name = "mock_answer_judge"

    @property
    def version(self) -> str:
        return "mock_answer_judge:phrase-match:v2"

    def verdict(self, case, answer_text):
        missing = [p for p in case.must_include if find_any(answer_text, p) is None]
        forbidden = [p for p in case.must_not_include if find_any(answer_text, p) is not None]
        if missing:
            return JudgeVerdict(False, f"missing required phrase(s): {missing}")
        if forbidden:
            return JudgeVerdict(False, f"contains forbidden phrase(s): {forbidden}")
        return JudgeVerdict(True, "all required phrases present, none forbidden")
