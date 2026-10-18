"""The decision check: does the answer decide what the case expects?

Phrase checks look for words, so a correct answer in other words fails and a wrong answer with the
right words passes. This check reads what the answer decided, from its opening, and compares it
with the case's expected_decision ("yes", "no", "depends", "hand_over", an amount, or alternatives).

The reader is rules, not a model: it is free, repeatable and readable, and when it can't tell what
an answer decided it says so (NOT_APPLICABLE) instead of guessing. Like a judge, it should be
measured against a person's reading before it is trusted to block a release. A team that needs a
different reader registers its own check with @register_check.
"""

import re
from dataclasses import dataclass
from typing import Optional

from aiquality.checks.base import Check
from aiquality.checks.registry import register_check
from aiquality.test_data.expected_decision import parse_expected_decision

UNREADABLE = "unreadable_decision"

_MARKDOWN = re.compile(r"[*_`#>]+")
_SENTENCES = re.compile(r"(?<=[.!?:])\s+|\n+")
_DEPENDS = re.compile(r"\b(it depends|that depends|depends on|depending on)\b|^whether\b", re.I)
_CONDITION = re.compile(r"\b(if|unless)\b(?! so\b)", re.I)
_OTHER_CASE = re.compile(r"^(if|otherwise|after that|else|unless)\b", re.I)
_OTHER_CASE_INSIDE = re.compile(r"[;,]\s*(otherwise|after that|if not)\b", re.I)   # "...; after that, ..."
_YES_OPENING = re.compile(
    r"^(yes\b|yeah\b|yep\b|sure\b|absolutely\b|of course\b|good news\b|no problem\b|no issues?\b|"
    r"that'?s (fine|okay|ok|allowed)\b|that is (fine|okay|ok|allowed)\b|"
    r"you can\b|you may\b|you('re| are) (allowed|eligible|entitled|within|fine)\b|you (do )?qualify\b)", re.I)
_NO_OPENING = re.compile(
    r"^(no\b(?! (problem|issues?)\b)|not\b|unfortunately\b|sadly\b|i can'?t\b|i cannot\b|i can not\b|i('m| am) (not able|unable)\b|"
    r"you can'?t\b|you cannot\b|you can not\b|you won'?t\b|you('re| are) not\b|"
    r"that'?s not\b|that is not\b|it'?s not\b|it is not\b)", re.I)
_NEGATIVE = re.compile(r"\b(can'?t|cannot|can not|not allowed|not possible|isn'?t|is not|aren'?t|not eligible|"
                       r"not open|not yet|no longer|won'?t|unable|not available|not guaranteed|no refund|"
                       r"forfeit(ed)?|doesn'?t qualify|does not qualify|(is|'s|are|'re) closed|has closed|exceeds?|"
                       r"over the (allowance|limit))\b", re.I)
_POSITIVE = re.compile(r"\b(you can|is open|are open|is allowed|are allowed|eligible|qualif(y|ies)|"
                       r"is fine|no extra charge|free of charge)\b", re.I)
_HAND_OVER = re.compile(r"\b(human agent|connect you|transfer you|escalate|take over)\b", re.I)
_NOT_COVERED = re.compile(r"\b(no policy|don'?t have (a |any )?(policy|information)|do not have (a |any )?(policy|"
                          r"information)|not covered|isn'?t covered|aren'?t covered|outside (what|the scope|my)|"
                          r"beyond (our|my|the))\b", re.I)
_AMOUNTS = re.compile(r"(?:₹|\brs\.?\s?|\binr\s?)([\d,]+)", re.I)
_SENTENCES_READ = 4         # the decision is read from the first sentences that state one


@dataclass(frozen=True)
class ReadDecision:
    """What an answer decided, as far as the rules can tell. decision None: couldn't tell."""

    decision: Optional[str]
    amounts: tuple
    evidence: str


def read_decision(answer_text: str) -> ReadDecision:
    """The first of the opening sentences that states a decision decides. Sentences that state none
    ("I understand.", "I can help with that.", "Here's why:") are passed over."""
    text = _MARKDOWN.sub("", answer_text or "")
    sentences = [s.strip() for s in _SENTENCES.split(text) if s.strip()]
    amounts = tuple(int(a.replace(",", "")) for a in _AMOUNTS.findall(text) if a.replace(",", "").isdigit())
    opening = sentences[:_SENTENCES_READ]
    first = opening[0] if opening else ""
    if any(_NOT_COVERED.search(s) for s in opening[:2]) and _HAND_OVER.search(text):
        return ReadDecision("hand_over", amounts, first)
    for number, sentence in enumerate(opening):
        following = sentences[number + 1] if number + 1 < len(sentences) else ""
        decision = _sentence_decision(sentence, following)
        if decision:
            return ReadDecision(decision, amounts, sentence)
    if any(_HAND_OVER.search(s) for s in opening):
        return ReadDecision("hand_over", amounts, first)
    return ReadDecision(None, amounts, first)


def _sentence_decision(sentence: str, following: str = "") -> Optional[str]:
    """yes, no or depends, as this sentence states it; None if it states no decision. A condition counts
    as 'depends' only when the other case follows, in the next sentence ("If ... you can. If not, ...") or
    after a semicolon or comma ("If ... you can; after that, ..."), so
    "If you miss your flight, the ticket is forfeited" still reads as a decision."""
    other_case = _OTHER_CASE.match(following) or _OTHER_CASE_INSIDE.search(sentence)
    if _DEPENDS.search(sentence) or (_CONDITION.search(sentence) and other_case):
        return "depends"
    if sentence.endswith(":"):          # an introduction ("Here's why:", "If it's more than 2 hours away:")
        return None
    if _YES_OPENING.match(sentence):
        return "yes"
    if _NO_OPENING.match(sentence):
        return "no"
    negative, positive = _NEGATIVE.search(sentence), _POSITIVE.search(sentence)
    if negative and not positive:
        return "no"
    if positive and not negative:
        return "yes"
    return None


@register_check("decision")
class DecisionCheck(Check):
    description = ("The answer reaches the case's expected_decision (yes, no, depends, hand_over, an amount like "
                   "₹1500, or alternatives with OR), read from its opening by rules. When the rules can't tell "
                   "what was decided, the case doesn't count. Usually blocking: false until the reader has been "
                   "measured against a person's reading.")

    def evaluate(self, case, response):
        if not case.expected_decision:
            return self.not_applicable(case, "case has no expected_decision")
        alternatives = parse_expected_decision(case.expected_decision)
        read = read_decision(response.answer_text)
        if any(_matches(alternative, read) for alternative in alternatives):
            return self.passed(case, f"reads as {_describe(read)}", evidence=read.evidence)
        needs_decision = all(a.decision for a in alternatives)
        if read.decision is None and needs_decision:
            return _unreadable(self, case, read)
        expected = " or ".join(a.describe() for a in alternatives)
        return self.failed(case, f"expected {expected}; the answer reads as {_describe(read)}", evidence=read.evidence)


def _matches(alternative, read: ReadDecision) -> bool:
    if alternative.decision and alternative.decision != read.decision:
        return False
    if alternative.amount is not None and alternative.amount not in read.amounts:
        return False
    return True


def _describe(read: ReadDecision) -> str:
    parts = [read.decision] if read.decision else []
    if read.amounts:
        parts.append(", ".join(f"₹{a:,}" for a in read.amounts))
    return ", ".join(parts) or "no clear decision"


def _unreadable(check: Check, case, read: ReadDecision):
    result = check.not_applicable(case, "couldn't read a decision from the answer's opening")
    result.evidence = read.evidence
    result.flags.append(UNREADABLE)
    return result
