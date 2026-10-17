"""Golden-set lint: find mistakes in the test data before they turn into false alarms.

It checks the golden set, not the agent, and only warns: a run still goes ahead.

Rule 1, echoed forbidden phrase: a must_not_include phrase that already appears in the customer's
question (or an earlier turn of theirs). A good answer often repeats the request ("I understand
you'd like 100 kg free..."), so the phrase matches a correct refusal. Write it as the completed
action instead: '100 kg is approved', not '100'. Numbers glued to units ("100kg") are read as
"100 kg", the way an answer usually writes them.

Rule 2, model answer fails its own checks: the case's reference answer, the answer a person wrote
as the right one, misses a must_include phrase or contains a must_not_include phrase. Then a
correct agent answer can fail too: the phrase is wrong, or the reference is.
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
        warnings += _reference_answer_problems(case)
    return warnings


def _reference_answer_problems(case) -> list[str]:
    if not case.reference_answer:
        return []
    problems = [f"required phrase '{p}' is missing" for p in case.must_include
                if find_any(case.reference_answer, p) is None]
    problems += [f"forbidden phrase '{p}' is in it" for p in case.must_not_include
                 if find_any(case.reference_answer, p) is not None]
    return [f"{case.id}: the reference answer fails its own phrase checks ({problem}), so a correct answer "
            "can fail too; fix the phrase or the reference" for problem in problems]


def _spaced(text: str) -> str:
    """'100kg' -> '100 kg', so a number glued to its unit reads like an answer would write it."""
    return re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
