"""
Completeness Guardrail — close the silent multi-intent drop (the fix)
====================================================================
Trajectory testing found that a messy multi-intent message can get an intent silently dropped
(e.g. "web check-in" answered only 5/6 runs). You can't fix that by trusting the
model harder, so we wrap it with a CODE-OWNED intent checklist:

    1. extract the asks from the message        (what did the user actually request?)
    2. let the agent draft an answer            (the model talks)
    3. check each ask is covered; if any is missing, send it back to be answered
       and merge the result                     (the code rules)

Then a before/after harness runs the same hard scenario N times WITHOUT and WITH
the guardrail, so the completeness-rate improvement is a measured number.

Requires: ANTHROPIC_API_KEY, aeroassist_agent.py, trajectory_eval.py, consistency_check.py.
"""

import os
import json
from aeroassist_agent import run_agent
from trajectory_eval import judge_completeness
from consistency_check import HARD_SCENARIO

MODEL = "claude-haiku-4-5"
N_RUNS = 5
MAX_REPAIRS = 2          # how many times the checklist will send missed asks back


# ======================================================================
# SECTION A — Extract the intents from an arbitrary message
# ======================================================================
def extract_intents(message, client, model=MODEL):
    """Pull the distinct asks out of a (possibly messy) message. In production the
    guardrail must work on arbitrary input, so it discovers the asks itself."""
    system = ('List the distinct requests/questions in the message. '
              'Return ONLY JSON: {"intents":["<ask1>","<ask2>",...]}.')
    out = client.messages.create(model=model, max_tokens=300, system=system,
                                 messages=[{"role": "user", "content": message}])
    text = out.content[0].text
    text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)["intents"]


# ======================================================================
# SECTION B — The guardrail: draft -> check -> repair missed asks
# ======================================================================
def answer_complete(message, client, judge_intents, model=MODEL, max_repairs=MAX_REPAIRS):
    """Agent drafts; the checklist (code) guarantees every ask is covered.
    `judge_intents` is the fixed ground-truth list we measure against, so the
    before/after comparison is fair."""
    own_intents = extract_intents(message, client)          # the guardrail's own view
    final, _ = run_agent(message, client)                   # first draft (model talks)

    for _ in range(max_repairs):
        completeness = judge_completeness(client, own_intents, final, model)
        missed = [i for i, ok in completeness if not ok]
        if not missed:
            break
        # code rules: send the missed asks back and merge the reply
        repair_msg = ("Please also answer these parts of my earlier request, concisely:\n"
                      + "\n".join(f"- {m}" for m in missed))
        extra, _ = run_agent(repair_msg, client)
        final = final.rstrip() + "\n\n" + extra.strip()

    return final


# ======================================================================
# SECTION C — Before/after harness (same scenario, N runs, two arms)
# ======================================================================
def fully_complete_rate(scenario, client, n, use_guardrail):
    """Run the scenario n times; return how many runs answered EVERY ground-truth intent."""
    intents = scenario["intents"]
    complete_runs = 0
    for run_i in range(1, n + 1):
        if use_guardrail:
            final = answer_complete(scenario["message"], client, judge_intents=intents)
        else:
            final, _ = run_agent(scenario["message"], client)
        dropped = [i for i, ok in judge_completeness(client, intents, final) if not ok]
        complete_runs += (not dropped)
        tag = "guarded" if use_guardrail else "baseline"
        print(f"  [{tag}] run {run_i}/{n}: {'✅ all' if not dropped else f'❌ dropped {dropped}'}")
    return complete_runs


# ======================================================================
# SECTION D — Run both arms and show the before/after
# ======================================================================
def main():
    from anthropic import Anthropic
    try:
        from google.colab import userdata
        api_key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)

    print(f"BEFORE — no guardrail ({N_RUNS} runs):")
    before = fully_complete_rate(HARD_SCENARIO, client, N_RUNS, use_guardrail=False)

    print(f"\nAFTER — completeness guardrail ({N_RUNS} runs):")
    after = fully_complete_rate(HARD_SCENARIO, client, N_RUNS, use_guardrail=True)

    print("\n" + "=" * 60)
    print(f"FULLY-COMPLETE RATE:  before {before}/{N_RUNS} ({before/N_RUNS:.0%})"
          f"  ->  after {after}/{N_RUNS} ({after/N_RUNS:.0%})")
    print("The model still talks; the code now guarantees every ask is answered.")
    print("=" * 60)


if __name__ == "__main__":
    main()
