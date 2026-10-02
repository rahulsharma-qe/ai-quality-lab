"""
Consistency Check — test a probabilistic agent across N runs, not once
=====================================================================
A single pass can't certify a non-deterministic agent: the same messy multi-intent
message may get every intent answered on one run and silently drop one on the next
(context-sensitivity). So we run the SAME scenario N times and report a per-intent
completeness RATE — turning "it worked once" into a measurable reliability number.

Requires: ANTHROPIC_API_KEY, aeroassist_agent.py, trajectory_eval.py (same folder).
"""

import os
from collections import defaultdict
from aeroassist_agent import run_agent
from trajectory_eval import judge_completeness

N_RUNS = 6


# ======================================================================
# SECTION A — A harder, messier multi-intent scenario (4 in-scope asks)
# ======================================================================
# Chit-chat + interleaving makes intents easier to drop than a clean numbered list.
HARD_SCENARIO = {
    "message": ("Hey, long day! Quick one — can I get a refund on ABC123? "
                "Oh and what's the cabin baggage allowance in economy? "
                "Also roughly what's the fee to change my flight date? "
                "And one more — when does web check-in open? Thanks so much!"),
    "intents": [
        "refund eligibility for booking ABC123",
        "economy cabin baggage allowance",
        "fee to change the flight date",
        "when web check-in opens",
    ],
}


# ======================================================================
# SECTION B — Run N times and tally how often each intent is answered
# ======================================================================
def run_consistency(scenario, client, n=N_RUNS):
    answered_count = defaultdict(int)      # intent -> times answered
    all_complete_runs = 0                  # runs where EVERY intent was answered

    for run_i in range(1, n + 1):
        final, _trajectory = run_agent(scenario["message"], client)
        completeness = judge_completeness(client, scenario["intents"], final)
        dropped = [i for i, ok in completeness if not ok]
        for intent, ok in completeness:
            if ok:
                answered_count[intent] += 1
        if not dropped:
            all_complete_runs += 1
        mark = "✅ all" if not dropped else f"❌ dropped {len(dropped)}"
        print(f"  run {run_i}/{n}: {mark}")

    return answered_count, all_complete_runs


# ======================================================================
# SECTION C — Report the rates (the reliability numbers)
# ======================================================================
def report(scenario, answered_count, all_complete_runs, n=N_RUNS):
    print(f"\n{'='*64}")
    print(f"COMPLETENESS RATE over {n} runs (per intent):")
    for intent in scenario["intents"]:
        c = answered_count[intent]
        flag = "" if c == n else "   <-- context-sensitive / unreliable"
        print(f"  {c}/{n}  {intent}{flag}")
    print(f"\nFULLY-COMPLETE runs: {all_complete_runs}/{n} "
          f"({all_complete_runs/n:.0%}) — this is the number you'd gate on, not a single pass.")
    print("=" * 64)


def main():
    from anthropic import Anthropic
    try:
        from google.colab import userdata
        api_key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)

    print(f"Consistency check — same messy multi-intent message, {N_RUNS} runs\n")
    answered_count, all_complete_runs = run_consistency(HARD_SCENARIO, client)
    report(HARD_SCENARIO, answered_count, all_complete_runs)


if __name__ == "__main__":
    main()
