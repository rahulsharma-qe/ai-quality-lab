"""The 'expected_decision' field of a golden case: what a good answer decides, in a form code can check.

    "yes"             the answer grants or confirms what the passenger asks
    "no"              the answer refuses or denies it
    "depends"         the answer depends on a fact the passenger didn't give, and says so
    "hand_over"       the question is outside the policies; the answer hands over to a person
    "₹1500"           the answer states this amount (any decision)
    "yes, ₹2000"      both: the decision and the amount
    "no OR hand_over" either alternative is a good answer

Phrase checks look for words; a decision check reads what was decided. 'no' and 'yes' are about the
passenger's own question: "Do I pay anything extra?" answered with "No" is a 'no'.
"""

import re
from dataclasses import dataclass
from typing import Optional

DECISIONS = ("yes", "no", "depends", "hand_over")
_AMOUNT = re.compile(r"^(?:₹|rs\.?\s*|inr\s*)([\d,]+)$", re.I)
_PARTS = re.compile(r",\s*(?=\D)")        # "yes, ₹2,000": the comma inside the amount doesn't split


@dataclass(frozen=True)
class ExpectedDecision:
    """One acceptable answer: a decision, an amount, or both (None means 'any')."""

    decision: Optional[str] = None
    amount: Optional[int] = None

    def describe(self) -> str:
        parts = [self.decision] if self.decision else []
        if self.amount is not None:
            parts.append(f"₹{self.amount:,}")
        return ", ".join(parts)


def parse_expected_decision(text: str) -> list[ExpectedDecision]:
    """'no OR hand_over' -> two alternatives. Raises ValueError with a readable message."""
    alternatives = []
    for alternative in str(text).split(" OR "):
        decision, amount = None, None
        for part in (p.strip() for p in _PARTS.split(alternative)):
            if part.lower() in DECISIONS:
                if decision:
                    raise ValueError(f"'{alternative.strip()}' names two decisions")
                decision = part.lower()
            elif _AMOUNT.match(part.replace(" ", "")):
                amount = int(_AMOUNT.match(part.replace(" ", "")).group(1).replace(",", ""))
            else:
                raise ValueError(f"'{part}' is not a decision ({', '.join(DECISIONS)}) or an amount like ₹1500")
        if decision is None and amount is None:
            raise ValueError(f"empty alternative in '{text}'")
        alternatives.append(ExpectedDecision(decision, amount))
    return alternatives
