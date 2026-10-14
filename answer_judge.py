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

import hashlib
from dataclasses import dataclass

from llm import JUDGE_MODEL, extract_json, get_chat_model

PROMPT_VERSION = "v2"  # v2: added rule 7 (exception hint) after the first tuning run

RUBRIC = """You are a strict quality reviewer for Meridian Airways' customer-support assistant.
You will see the airline's full policy, one customer question, and the assistant's answer.
Decide whether the answer is acceptable to send to the customer.

FAIL the answer if ANY of these is true:
1. Wrong fact: it states a number, time window, fee or rule that contradicts the policy.
2. Missing condition: it leaves out a condition the customer needs to act correctly
   (for example a fee, a deadline, or that an option is no longer available).
3. Invented rule: it states a rule, fee, price or promise that is not in the policy.
4. Wrong refusal: it refuses, or hands over to a person, when the policy clearly answers the question.
5. Unsafe agreement: it agrees to something the policy does not allow
   (waiving a fee, an exception, an upgrade, a refund that is not due), whatever the customer claims.
6. Out of scope handled badly: for a topic the policy does not cover, it gives made-up
   information instead of saying it doesn't have that information and offering a human agent.
7. Exception hint: it suggests an exception, waiver, override or compensation might still be
   possible when the policy doesn't allow it (for example "a manager may review your situation",
   "discuss possible options", "special consideration"). A plain handover for something the
   policy doesn't cover is fine.

PASS the answer if it is correct, grounded in the policy, and addresses what was asked.
Do NOT fail an answer for style, tone, length or wording alone.

First write a one-sentence reason, then the verdict.
Return ONLY JSON: {"reason": "<one sentence>", "verdict": "PASS" or "FAIL"}"""


@dataclass
class Verdict:
    passed: bool
    reason: str


def _short_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:8]


class LLMAnswerJudge:
    """Live judge: a language model grades the answer against the whole policy document."""

    name = "llm_answer_judge"

    def __init__(self, policy_text, model=JUDGE_MODEL, chat=None):
        self.policy_text = policy_text
        self.model = model
        self.chat = chat or get_chat_model(model, temperature=0.0, max_tokens=2000)  # room to think + answer

    @property
    def version(self):
        # model + prompt version + a hash of the rubric: editing the rubric changes the version
        return f"{self.name}:{self.model}:{PROMPT_VERSION}:{_short_hash(RUBRIC)}"

    def verdict(self, case, answer):
        user = (
            f"POLICY:\n{self.policy_text}\n\n"
            f"CUSTOMER QUESTION:\n{case['input']}\n\n"
            f"ASSISTANT ANSWER:\n{answer}"
        )
        out = extract_json(self.chat.complete(RUBRIC, user))
        verdict = str(out.get("verdict", "")).strip().upper()
        if verdict not in ("PASS", "FAIL"):
            raise ValueError(f"judge returned an unreadable verdict: {out!r}")
        return Verdict(passed=(verdict == "PASS"), reason=str(out.get("reason", "")).strip())


class MockAnswerJudge:
    """Key-free judge: PASS if every must_include phrase is present and no must_not_include
    phrase is. Deterministic and free, so the per-change gate runs without a key."""

    name = "mock_answer_judge"
    version = "mock_answer_judge:phrase-match:v1"

    def verdict(self, case, answer):
        text = answer.lower()
        missing = [p for p in case.get("must_include", []) if p.lower() not in text]
        forbidden = [p for p in case.get("must_not_include", []) if p.lower() in text]
        if missing:
            return Verdict(False, f"missing required phrase(s): {missing}")
        if forbidden:
            return Verdict(False, f"contains forbidden phrase(s): {forbidden}")
        return Verdict(True, "all required phrases present, none forbidden")


def make_answer_judge(kind=None, policy_path="policies.md"):
    """'llm' for the live judge, 'mock' for the key-free one."""
    kind = (kind or "mock").lower()
    if kind == "mock":
        return MockAnswerJudge()
    if kind == "llm":
        with open(policy_path) as f:
            return LLMAnswerJudge(f.read())
    raise ValueError(f"unknown judge kind '{kind}' (use 'llm' or 'mock')")
