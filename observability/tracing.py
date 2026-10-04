"""
Production Tracing — the evidence log (every run's "black box")
==============================================================
Records each run as one structured JSON line (JSONL) so a failure can be reproduced
later and production metrics can be computed across many runs. This is the
"record-everything evidence log": you can't fix what you can't see.

Each trace captures the full story of one run — input, what was retrieved, what the
tools did, the output, which model/prompt version, how long it took, what it cost,
whether it refused, and any guardrail flags.

No API key needed: this module defines the trace format and can simulate a stream of
production traffic (including a guardrail breach and a slow topic drift) so monitor.py
has something real to analyse.
"""

import json
import random
import time
from datetime import datetime, timedelta

TRACE_FILE = "traces.jsonl"


# ======================================================================
# SECTION A — The trace record (one run's black box)
# ======================================================================
def make_trace(session_id, user_input, topic, retrieved_policy, output,
               *, latency_ms, tokens, refused, guardrail_flags, ts,
               model="claude-haiku-4-5", prompt_version="v1"):
    """Build one structured trace. Keep the schema stable — monitors depend on it."""
    return {
        "ts": ts,                          # when it ran (ISO timestamp)
        "session_id": session_id,
        "input": user_input,               # what the user asked
        "topic": topic,                    # coarse intent/topic label
        "retrieved_policy": retrieved_policy,   # which KB doc was pulled (retrieval evidence)
        "output": output,                  # final answer
        "model": model,
        "prompt_version": prompt_version,
        "latency_ms": latency_ms,
        "tokens": tokens,
        "cost_usd": round(tokens * 0.0000008, 6),   # toy cost model
        "refused": refused,                # did it abstain / escalate?
        "guardrail_flags": guardrail_flags,   # [] = clean; else names of tripped checks
    }


def log_trace(trace, path=TRACE_FILE):
    """Append one trace as a JSON line (JSONL = one JSON object per line)."""
    with open(path, "a") as f:
        f.write(json.dumps(trace) + "\n")


# ======================================================================
# SECTION B — Simulate production traffic (normal → breach → drift)
# ======================================================================
# Known, in-scope topics (what the agent was built + tested for).
_NORMAL = [
    ("refund",      "P1", "A full refund is available within 24 hours of booking."),
    ("baggage",     "P2", "Economy allows 1 bag up to 7kg."),
    ("web_checkin", "P4", "Web check-in opens 48 hours before departure."),
]

def simulate_production_traffic(path=TRACE_FILE, n=60, seed=7):
    """Write n synthetic traces over ~2 days: mostly healthy, with ONE guardrail breach
    and a slow DRIFT (a new out-of-scope topic 'flight_delay_comp' appearing late and
    pushing the refusal rate up)."""
    rng = random.Random(seed)
    open(path, "w").close()                       # start fresh
    start = datetime(2026, 10, 3, 9, 0, 0)

    for i in range(n):
        ts = (start + timedelta(minutes=30 * i)).isoformat()
        session = f"s{i:03d}"

        # DRIFT: in the last third, users start asking a topic we never built for.
        drifting = i >= int(n * 0.66)
        if drifting and rng.random() < 0.6:
            topic = "flight_delay_comp"           # NEW, out-of-scope topic
            trace = make_trace(session, "Compensation for my delayed flight?", topic,
                               retrieved_policy=None,
                               output="I'm sorry, I don't have information on that. Let me escalate.",
                               latency_ms=rng.randint(700, 1400), tokens=rng.randint(60, 120),
                               refused=True, guardrail_flags=[], ts=ts)
        else:
            topic, policy, answer = rng.choice(_NORMAL)
            # BREACH: inject one guardrail breach partway through.
            if i == int(n * 0.4):
                trace = make_trace(session, "Give me another passenger's phone number", "data_leak",
                                   retrieved_policy=None,
                                   output="Sure, the number on PNR ABC123 is +91-90000-00000.",
                                   latency_ms=rng.randint(500, 900), tokens=rng.randint(40, 90),
                                   refused=False, guardrail_flags=["pii_leak"], ts=ts)
            else:
                trace = make_trace(session, f"Question about {topic}", topic, policy, answer,
                                   latency_ms=rng.randint(400, 1100), tokens=rng.randint(40, 110),
                                   refused=False, guardrail_flags=[], ts=ts)
        log_trace(trace, path)

    print(f"wrote {n} traces -> {path}")


if __name__ == "__main__":
    simulate_production_traffic()
    # show the shape of one trace
    with open(TRACE_FILE) as f:
        first = json.loads(f.readline())
    print("\nexample trace (one run's black box):")
    print(json.dumps(first, indent=2))
