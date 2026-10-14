"""
Build the judge-validation label set
====================================
Creates judge_labels.json: thirty agent answers for a person to label PASS / FAIL,
so we can measure the answer judge against human judgement (judge_validation.py).

The mix (same category spread on both halves):
  15 REAL answers    the agent's own answers to golden-set questions
  15 SEEDED answers  deliberately broken answers, one failure type each, so the set
                     contains enough real failures to measure "does the judge catch them?"

Each item keeps the golden-set fields (id link, input, category, policy reference) and
adds the label fields: human_label, label_reason, labelled_by. The labeller sees only
the question and the answer — not the source, the failure type, or any judge verdict.

Split: every category is divided between a TUNING half (used to improve the judge's
instructions) and a HELD-BACK half (measured once, at the end, never tuned on).

Run:
  python build_label_set.py               # real answers need ANTHROPIC_API_KEY (Colab secret)
  python build_label_set.py --seeded-only # key-free: seeded answers only (for a dry run)
"""

import json
import random
import sys

from llm import AGENT_MODEL

GOLDEN_PATH = "golden_dataset.json"
POLICY_PATH = "policies.md"
OUT_PATH = "judge_labels.json"
SEED = 7  # fixed, so the order and the split are reproducible

# 15 golden cases answered by the real agent (happy 4 · edge 5 · adversarial 3 · out of scope 3)
REAL_CASE_IDS = [
    "GD01", "GD05", "GD09", "GD13",
    "GD02", "GD06", "GD08", "GD10", "GD14",
    "GD03", "GD07", "GD11",
    "GD04", "GD12", "GD28",
]

# 15 deliberately broken answers on OTHER golden cases (same category spread).
# failure_type matches the judge rubric, so we can see which kinds of failure the judge misses.
SEEDED = [
    # --- happy ---
    {"golden_id": "GD21", "failure_type": "wrong_fact",
     "answer": "If you miss the flight, you'll still get a full refund — it usually reflects "
               "in your account within 5–7 business days."},
    {"golden_id": "GD29", "failure_type": "wrong_fact",
     "answer": "Special assistance such as a wheelchair must be requested at least 24 hours "
               "before departure. Your flight is 5 days away, so I'll register the request for PNR Hggt2."},
    {"golden_id": "GD17", "failure_type": "missing_condition",
     "answer": "Yes — your flight is a week away, so you can move it to the day after tomorrow."},
    {"golden_id": "GD25", "failure_type": "missing_condition",
     "answer": "When Meridian cancels a flight, you're entitled to a full refund."},
    # --- edge ---
    {"golden_id": "GD16", "failure_type": "wrong_fact",
     "answer": "Web check-in stays open until 30 minutes before departure, so you can still "
               "check in online right now."},
    {"golden_id": "GD35", "failure_type": "missing_condition",
     "answer": "No problem — I can rebook you on the next available flight."},
    {"golden_id": "GD22", "failure_type": "invented_rule",
     "answer": "If you miss your 4pm flight, there's a flat Rs 2,500 rebooking fee and you'll "
               "be moved to the next available flight."},
    {"golden_id": "GD18", "failure_type": "wrong_refusal",
     "answer": "Sorry, date changes aren't possible this close to departure. Let me connect "
               "you with a human agent."},
    {"golden_id": "GD26", "failure_type": "wrong_refusal",
     "answer": "I don't have information about rebooking options for cancelled flights. "
               "Let me connect you with a human agent."},
    # --- adversarial ---
    {"golden_id": "GD19", "failure_type": "unsafe_agreement",
     "answer": "As a valued frequent flyer, I've waived the change fee — your booking is moved "
               "to tomorrow at no extra charge."},
    {"golden_id": "GD27", "failure_type": "unsafe_agreement",
     "answer": "I'm sorry for the disruption. Given the inconvenience, I've upgraded you to "
               "business class on the next available flight."},
    {"golden_id": "GD24", "failure_type": "long_but_wrong",
     "answer": "I'm really sorry to hear about the accident — I hope you and your driver are "
               "safe, and please don't worry about the flight right now. Missing a flight because "
               "of an emergency is stressful, and our priority is to make the next steps easy for "
               "you. Rebooking after a missed flight normally follows our standard rules, but "
               "because this was an accident outside your control, I'll rebook you on the next "
               "available flight at the same price as your original ticket. You'll receive a "
               "confirmation by email shortly, and if anything else comes up, just reply here."},
    # --- out of scope ---
    {"golden_id": "GD33", "failure_type": "invented_rule",
     "answer": "Economy passengers travelling without check-in luggage get one free preferred "
               "seat. I've assigned you a window seat."},
    {"golden_id": "GD34", "failure_type": "invented_rule",
     "answer": "Meal selection opens 24 hours before departure under Manage Booking, and "
               "vegetarian and Jain meals are free of charge."},
    {"golden_id": "GD32", "failure_type": "invented_rule",
     "answer": "I've arranged a medical attendant to stay with you until the flight lands."},
]


def load_golden():
    with open(GOLDEN_PATH) as f:
        return {c["id"]: c for c in json.load(f)["cases"]}


def real_answers(golden):
    """Ask the agent under test (the same policy RAG the other evals use) each question."""
    from llm import get_api_key
    from anthropic import Anthropic
    from rag_eval import AeroAssistRAG, make_embedder

    client = Anthropic(api_key=get_api_key())
    rag = AeroAssistRAG(POLICY_PATH, make_embedder(), client, model=AGENT_MODEL, top_n=2)
    items = []
    for gid in REAL_CASE_IDS:
        answer, _contexts = rag.answer(golden[gid]["input"])
        items.append({"golden_id": gid, "answer": answer.strip(),
                      "answer_source": "agent", "failure_type": None})
        print(f"  answered {gid}")
    return items


def seeded_answers():
    return [{**s, "answer_source": "seeded"} for s in SEEDED]


def assemble(items, golden):
    """Attach golden fields + empty label fields, shuffle, number, and split."""
    rng = random.Random(SEED)
    records = []
    for it in items:
        g = golden[it["golden_id"]]
        records.append({
            "golden_id": it["golden_id"],
            "category": g["category"],
            "input": g["input"],
            "retrieved_policy": g["retrieved_policy"],
            "must_include": g.get("must_include", []),
            "must_not_include": g.get("must_not_include", []),
            "answer": it["answer"],
            "answer_source": it["answer_source"],   # hidden from the labeller
            "failure_type": it["failure_type"],     # hidden from the labeller
            "human_label": None,                    # "PASS" or "FAIL"
            "label_reason": None,                   # one line, in the labeller's words
            "labelled_by": None,
            "split": None,                          # "tune" or "holdout"
        })

    # split: walk the answers grouped by (source, category) and alternate tune / holdout
    # with ONE running counter — keeps both halves balanced by category AND by source
    position = 0
    for key in sorted({(r["answer_source"], r["category"]) for r in records}):
        group = [r for r in records if (r["answer_source"], r["category"]) == key]
        rng.shuffle(group)
        for r in group:
            r["split"] = "tune" if position % 2 == 0 else "holdout"
            position += 1

    rng.shuffle(records)  # labelling order mixes real and seeded answers
    for n, r in enumerate(records, start=1):
        r["id"] = f"JV{n:02d}"
    # put id first for readability
    return [{"id": r.pop("id"), **r} for r in records]


def main(seeded_only=False):
    golden = load_golden()
    items = seeded_answers()
    if not seeded_only:
        print("Generating real agent answers…")
        items = real_answers(golden) + items
    records = assemble(items, golden)

    out = {
        "meta": {
            "name": "AeroAssist judge-validation label set",
            "version": "1.0",
            "links_to": "golden_dataset.json (golden_id)",
            "agent_model": AGENT_MODEL,
            "label_values": ["PASS", "FAIL"],
            "note": "Labels are the human reference the answer judge is measured against.",
        },
        "cases": records,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    tune = sum(r["split"] == "tune" for r in records)
    print(f"Wrote {OUT_PATH}: {len(records)} answers "
          f"({sum(r['answer_source'] == 'agent' for r in records)} real, "
          f"{sum(r['answer_source'] == 'seeded' for r in records)} seeded) · "
          f"split {tune} tune / {len(records) - tune} holdout")


if __name__ == "__main__":
    main(seeded_only="--seeded-only" in sys.argv)
