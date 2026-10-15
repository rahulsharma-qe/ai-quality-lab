"""One place that knows what personal contact data looks like.

Used to redact run records before they are written, and by the no_personal_data check.
Deterministic and simple on purpose: phone-like numbers and email addresses (the same
detectors as the monitoring guardrail, observability/pii_guardrail.py). Widen the
patterns for your own data (card numbers, national IDs) before using real traffic.
"""

import re

PERSONAL_DATA_PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"\+?\d[\d\-\s]{8,}\d"),
}


def find_personal_data(text: str) -> dict[str, list[str]]:
    """Every match per kind, e.g. {"EMAIL": ["a@b.com"]}; kinds with no match are left out."""
    if not isinstance(text, str):
        return {}
    found = {}
    for kind, pattern in PERSONAL_DATA_PATTERNS.items():
        matches = [m.group(0).strip() for m in pattern.finditer(text)]
        if matches:
            found[kind] = matches
    return found


def redact_personal_data(text):
    """Replace personal contact data with [REDACTED-EMAIL] / [REDACTED-PHONE]."""
    if not isinstance(text, str):
        return text
    for kind, pattern in PERSONAL_DATA_PATTERNS.items():
        text = pattern.sub(f"[REDACTED-{kind}]", text)
    return text
