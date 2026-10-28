"""
Production Monitor — turn thousands of traces into trends + alerts
=================================================================
One trace debugs one failure; thousands reveal the trend. This reads the evidence
log (traces.jsonl) and prints:
  - a production dashboard (quality + operational signals)
  - a drift check (first-half vs second-half of the window)
  - the specific runs to triage (guardrail breaches)

Everything here is deterministic and key-free — it just reads the JSONL.
"""

import json
import sys
from pathlib import Path

# Traces go to aiquality-runs/ (ignored by git), wherever the script is run from.
RUNS_FOLDER = Path(__file__).resolve().parents[2] / "aiquality-runs"
TRACE_FILE = RUNS_FOLDER / "traces.jsonl"
REFUSAL_JUMP_ALERT = 0.15      # alert if refusal rate rises by more than this across the window


# ======================================================================
# SECTION A — Load the evidence log
# ======================================================================
def load_traces(path=TRACE_FILE):
    if not Path(path).is_file():
        sys.exit(f"no traces at {path}: run python demos/observability/tracing.py first")
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def percentile(values, pct):
    """Simple percentile (e.g. p95 = typical worst-case). values need not be pre-sorted."""
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100) * (len(s) - 1))))
    return s[idx]


# ======================================================================
# SECTION B — The production dashboard (aggregate signals)
# ======================================================================
def dashboard(traces):
    n = len(traces)
    breaches = [t for t in traces if t["guardrail_flags"]]
    refusals = [t for t in traces if t["refused"]]
    latencies = [t["latency_ms"] for t in traces]
    cost = sum(t["cost_usd"] for t in traces)

    print("=" * 56)
    print(f"PRODUCTION DASHBOARD  ({n} runs)")
    print("=" * 56)
    print("Quality signals:")
    print(f"  guardrail-breach rate : {len(breaches)/n:.1%}  ({len(breaches)} run/s)")
    print(f"  refusal/escalation    : {len(refusals)/n:.1%}  ({len(refusals)} run/s)")
    print("Operational signals:")
    print(f"  latency p50 / p95     : {percentile(latencies,50)} ms / {percentile(latencies,95)} ms")
    print(f"  avg cost per run      : ${cost/n:.6f}   (total ${cost:.4f})")
    return breaches


# ======================================================================
# SECTION C — Drift check (did production shift across the window?)
# ======================================================================
def drift_check(traces):
    """Split the window in half (by time order) and compare: refusal-rate jump + new topics."""
    half = len(traces) // 2
    first, second = traces[:half], traces[half:]

    def refusal_rate(ts):
        return sum(t["refused"] for t in ts) / len(ts) if ts else 0

    r1, r2 = refusal_rate(first), refusal_rate(second)
    topics_first = {t["topic"] for t in first}
    topics_second = {t["topic"] for t in second}
    new_topics = topics_second - topics_first

    print("\n" + "=" * 56)
    print("DRIFT CHECK  (first half vs second half)")
    print("=" * 56)
    print(f"  refusal rate: {r1:.1%}  ->  {r2:.1%}")
    alerts = []
    if r2 - r1 > REFUSAL_JUMP_ALERT:
        alerts.append(f"refusal rate jumped {r2-r1:+.0%} — users asking things we can't answer")
    if new_topics:
        alerts.append(f"new topic(s) appeared: {sorted(new_topics)} — semantic drift")
    for a in alerts:
        print(f"  ⚠️  DRIFT ALERT: {a}")
    if not alerts:
        print("  ✅ no significant drift")
    return alerts


# ======================================================================
# SECTION D — Triage list (what a human must look at) + the loop
# ======================================================================
def triage(breaches):
    print("\n" + "=" * 56)
    print("TRIAGE — runs a human must review now")
    print("=" * 56)
    if not breaches:
        print("  none")
        return
    for b in breaches:
        print(f"  ❌ [{b['session_id']}] {b['guardrail_flags']} | input: {b['input']!r}")
        print(f"       output: {b['output']!r}")
    print("\n  -> feed each into the loop: add to red-team/golden set (CI gate) + add a runtime guardrail.")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else TRACE_FILE
    print(f"(reading {path})")
    traces = load_traces(path)
    breaches = dashboard(traces)
    drift_check(traces)
    triage(breaches)


if __name__ == "__main__":
    main()
