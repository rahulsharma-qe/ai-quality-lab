"""Remove personal contact data before anything is written to disk.

Same detectors as the monitoring guardrail (observability/pii_guardrail.py): phone-like
numbers and email addresses. Deterministic and simple on purpose; widen the patterns
for your own data (card numbers, national IDs) before using real traffic.
"""

import re

PERSONAL_DATA_PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"\+?\d[\d\-\s]{8,}\d"),
}


def redact_personal_data(text):
    if not isinstance(text, str):
        return text
    for label, pattern in PERSONAL_DATA_PATTERNS.items():
        text = pattern.sub(f"[REDACTED-{label}]", text)
    return text
