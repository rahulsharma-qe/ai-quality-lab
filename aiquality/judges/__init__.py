"""Judges: grade meaning where checks can only match words. Built-in judges register on import."""

from aiquality.judges.base import Judge, JudgeVerdict
from aiquality.judges.registry import available_judges, create_judge, register_judge
from aiquality.judges import phrase_judge, policy_judge  # noqa: F401  (register the built-in judges)
from aiquality.judges.phrase_judge import PhraseJudge
from aiquality.judges.policy_judge import PolicyAnswerJudge

__all__ = ["Judge", "JudgeVerdict", "PhraseJudge", "PolicyAnswerJudge", "available_judges", "create_judge",
           "register_judge"]
