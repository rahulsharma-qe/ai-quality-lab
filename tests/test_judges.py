"""Judges: the phrase judge, the policy judge with a fake model, versions and the registry."""

import pytest

from aiquality import GoldenCaseBuilder
from aiquality.judges import Judge, JudgeVerdict, PhraseJudge, PolicyAnswerJudge, create_judge, register_judge
from aiquality.models import ChatModel


class FakeChat(ChatModel):
    """Returns a fixed reply and remembers what it was asked."""

    def __init__(self, reply):
        super().__init__("fake-model")
        self.reply, self.calls = reply, []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.reply


CASE = GoldenCaseBuilder("R1", "Can I get a refund after 3 days?").must_include("24 hours").build()


def test_phrase_judge_grades_words_not_meaning():
    judge = PhraseJudge()
    assert judge.verdict(CASE, "Only within 24 hours of booking.").passed
    assert not judge.verdict(CASE, "Only within a day of booking.").passed      # same meaning, other words


def test_policy_judge_reads_the_verdict_and_sees_policy_question_and_answer():
    chat = FakeChat('```json\n{"reason": "Says 30 days; the policy says 24 hours.", "verdict": "FAIL"}\n```')
    judge = PolicyAnswerJudge("POLICY TEXT", rubric="Grade it.", rubric_version="r1", model="fake", chat=chat)
    verdict = judge.verdict(CASE, "Within 30 days.")
    assert verdict == JudgeVerdict(False, "Says 30 days; the policy says 24 hours.")
    system, user = chat.calls[0]
    assert system == "Grade it." and "POLICY TEXT" in user and CASE.input in user and "Within 30 days." in user


def test_policy_judge_refuses_an_unreadable_verdict():
    judge = PolicyAnswerJudge("P", rubric="r", chat=FakeChat('{"reason": "?", "verdict": "maybe"}'))
    with pytest.raises(ValueError, match="unreadable verdict"):
        judge.verdict(CASE, "a")


def test_editing_the_rubric_makes_a_new_version():
    first = PolicyAnswerJudge("P", rubric="Rule A.", rubric_version="r1", model="m", chat=FakeChat("{}"))
    edited = PolicyAnswerJudge("P", rubric="Rule A. Rule B.", rubric_version="r1", model="m", chat=FakeChat("{}"))
    assert first.version.startswith("llm_answer_judge:m:r1:") and first.version != edited.version


def test_the_default_rubric_names_no_company():
    rubric = PolicyAnswerJudge("P", chat=FakeChat("{}")).rubric
    assert "Return ONLY JSON" in rubric and "Meridian" not in rubric and "airline" not in rubric


def test_a_team_can_register_its_own_judge():
    @register_judge("always_pass_test")
    class AlwaysPass(Judge):
        version = "always-pass:v1"

        def verdict(self, case, answer_text):
            return JudgeVerdict(True, "fine")

    assert create_judge("always_pass_test").verdict(CASE, "x").passed
    with pytest.raises(KeyError, match="Available: .*always_pass_test"):
        create_judge("no_such_judge")
