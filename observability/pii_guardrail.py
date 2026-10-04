"""
PII Output Guardrail — block personal data before it reaches the user (the fix)
=============================================================================
The monitor flagged a PII leak. The fix doesn't live in the model — a deterministic
check scans every answer BEFORE it goes out and blocks anything that looks like
personal contact data (phone/email). The model drafts; the code decides what ships.

Demo flow (screen-share friendly — shows BOTH states):
    python tracing.py                       # raw traffic (the leak gets through)
    python monitor.py traces.jsonl          # BEFORE: breach-rate > 0
    python pii_guardrail.py                 # apply the guardrail -> traces_guarded.jsonl
    python monitor.py traces_guarded.jsonl  # AFTER: breach-rate 0

All PII in the data is fake/synthetic — safe to show on a screen-share.
"""

import json
import re

IN_FILE = "traces.jsonl"
OUT_FILE = "traces_guarded.jsonl"

# Deterministic PII detectors (phone-like and email-like).
PII_PATTERNS = [
    r"\+?\d[\d\-\s]{8,}\d",        # phone number
    r"[\w.+-]+@[\w-]+\.[\w.-]+",   # email address
]
SAFE_REPLY = "I'm sorry, I can't share personal contact details. Let me connect you to a human agent."


def contains_pii(text):
    return any(re.search(p, text) for p in PII_PATTERNS)


def apply_guardrail(in_path=IN_FILE, out_path=OUT_FILE):
    """Re-process every trace's output through the guardrail; block any PII, clear the leak."""
    blocked = 0
    with open(in_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            t = json.loads(line)
            if contains_pii(t["output"]):
                t["output"] = SAFE_REPLY          # redact/replace the unsafe answer
                t["refused"] = True
                t["guardrail_flags"] = []          # leak prevented -> no longer a breach
                blocked += 1
            fout.write(json.dumps(t) + "\n")
    print(f"guardrail applied: {blocked} answer(s) blocked -> {out_path}")


if __name__ == "__main__":
    apply_guardrail()
