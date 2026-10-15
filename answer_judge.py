"""
Answer judge — is this support answer correct and grounded in Meridian policy?
==============================================================================
One question, one answer, one verdict: PASS or FAIL, with a one-line reason.
This is the judge the release gate relies on, so it is also the judge we validate
against human labels (see judge_validation.py) before trusting it to gate.

Two implementations, one interface:
  LLMAnswerJudge   live: a language model grades against the full policy text
  MockAnswerJudge  key-free: checks the golden case's must_include / must_not_include
                   phrases. Cheap and deterministic, so the per-change gate needs no key.
                   It checks plumbing, not meaning.

Interface every judge follows (so any judge can be validated the same way):
  judge.version                -> a string that changes whenever the judge changes
  judge.verdict(case, answer)  -> Verdict(passed: bool, reason: str)

Design choices that keep the judge honest:
  - PASS / FAIL, not a 1-5 score (clearer, easier to check against people)
  - reason first, verdict second (the judge explains before it decides)
  - temperature 0 where the client library accepts it (same answer in, same verdict out);
    consistency is also checked by re-running the tuning half
  - a different, stronger model than the agent (nothing grades its own work)
  - style and length are explicitly NOT grounds to fail (guards against length bias)
"""

from pathlib import Path

from aiquality.judges import JudgeVerdict, PhraseJudge, PolicyAnswerJudge
from aiquality.test_data import GoldenCase
from llm import JUDGE_MODEL

# The implementation lives in the aiquality package (aiquality/judges). This file keeps the old
# names and accepts plain dict cases, for the scripts that use them (eval_harness.py,
# judge_validation.py). The rubric is AeroAssist's own file, word for word, so the judge's
# version (and every validation result recorded for it) stays the same.
RUBRIC_FILE = Path(__file__).resolve().parent / "teams" / "aeroassist" / "judge_rubric.md"
RUBRIC = RUBRIC_FILE.read_text(encoding="utf-8").strip()
PROMPT_VERSION = "v2"  # v2: added rule 7 (exception hint) after the first tuning run

Verdict = JudgeVerdict


def as_case(case) -> GoldenCase:
    """Accept a GoldenCase or a plain dict with 'input' (and optional phrase lists)."""
    if isinstance(case, GoldenCase):
        return case
    return GoldenCase(id=str(case.get("id", "")), input=str(case.get("input", "")),
                      must_include=list(case.get("must_include") or []),
                      must_not_include=list(case.get("must_not_include") or []))


class LLMAnswerJudge(PolicyAnswerJudge):
    """Live judge: a language model grades the answer against the whole policy document."""

    def __init__(self, policy_text, model=JUDGE_MODEL, chat=None):
        super().__init__(policy_text, rubric=RUBRIC, rubric_version=PROMPT_VERSION, model=model, chat=chat)

    def verdict(self, case, answer):
        return super().verdict(as_case(case), answer)


class MockAnswerJudge(PhraseJudge):
    """Key-free judge: PASS if every must_include phrase is present and no must_not_include
    phrase is. It checks plumbing, not meaning."""

    def verdict(self, case, answer):
        return super().verdict(as_case(case), answer)


def make_answer_judge(kind=None, policy_path="policies.md"):
    """'llm' for the live judge, 'mock' for the key-free one."""
    kind = (kind or "mock").lower()
    if kind == "mock":
        return MockAnswerJudge()
    if kind == "llm":
        with open(policy_path) as f:
            return LLMAnswerJudge(f.read())
    raise ValueError(f"unknown judge kind '{kind}' (use 'llm' or 'mock')")
