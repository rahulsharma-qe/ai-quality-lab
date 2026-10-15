"""Golden-set lint: find mistakes in the test data before they turn into false alarms.

It checks the golden set, not the agent, and only warns: a run still goes ahead.

Rule 1, echoed forbidden phrase: a must_not_include phrase that already appears in the customer's
question (or an earlier turn of theirs). A good answer often repeats the request ("I understand
you'd like 100 kg free..."), so the phrase matches a correct refusal. Write it as the completed
action instead: '100 kg is approved', not '100'. Numbers glued to units ("100kg") are read as
"100 kg", the way an answer usually writes them.
"""

import re

from aiquality.checks.phrase_matching import find_any
from aiquality.test_data.golden_case import GoldenSet


def lint_golden_set(golden_set: GoldenSet) -> list[str]:
    warnings = []
    for case in golden_set.cases:
        customer_text = _spaced(" ".join([case.input] + [t.get("content", "") for t in case.conversation_history
                                                         if t.get("role") == "user"]))
        for phrase in case.must_not_include:
            match = find_any(customer_text, phrase)
            if match is not None:
                warnings.append(f"{case.id}: forbidden phrase '{phrase}' is in the customer's own words, so an "
                                "answer that repeats the request matches it; write it as the completed action, "
                                "e.g. '<thing> is approved'")
    return warnings


def _spaced(text: str) -> str:
    """'100kg' -> '100 kg', so a number glued to its unit reads like an answer would write it."""
    return re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
