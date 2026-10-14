"""
Judge validation — check the examiner before trusting its marks
===============================================================
An AI judge decides whether answers are good, and the release gate trusts it.
So before the judge is allowed to gate, we measure it against human labels.

Two numbers, because one is not enough:
  catches real failures      of the answers a person FAILED, how many the judge also failed
  leaves good answers alone  of the answers a person PASSED, how many the judge also passed
A judge that fails everything scores 100% on the first and 0% on the second — so both
must clear their bar. Results are also broken down by category, because an average can
hide one category the judge gets wrong.

Works with ANY judge that has .version and .verdict(case, answer) — see answer_judge.py.
Works with ANY label file in the judge_labels.json format — teams bring their own labels.

Rules that keep the numbers honest:
  - tune the judge's instructions on the TUNING half only
  - measure the HELD-BACK half once the judge is final; never tune on it
  - re-run whenever the judge's version changes (new model, new rubric)

Run:
  python judge_validation.py --judge llm  --split tune      # improve the judge here
  python judge_validation.py --judge llm  --split holdout   # the real measurement
  python judge_validation.py --judge mock --split all       # key-free plumbing check

Exit code: on the held-back half, 0 = judge qualified to gate, 1 = not qualified.
Every run is appended to judge_validation_results.jsonl with the judge's version.

What "not qualified" means downstream: eval_harness.py reads judge_status() and runs an
unqualified judge in ADVISORY mode — it reports, and the answers it fails go to human
review, but it cannot block a release.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from answer_judge import make_answer_judge

LABELS_PATH = "judge_labels.json"
RESULTS_PATH = "judge_validation_results.jsonl"

# The judge's own exam: it may gate releases only if it clears BOTH bars on held-back data.
MIN_CATCH_RATE = 0.85        # of human FAILs, the judge must also fail at least this share
MIN_LEAVE_ALONE_RATE = 0.80  # of human PASSes, the judge must also pass at least this share


# ======================================================================
# SECTION A — Load the labelled cases
# ======================================================================
def load_labelled(path, split):
    with open(path) as f:
        cases = json.load(f)["cases"]
    if split != "all":
        cases = [c for c in cases if c.get("split") == split]
    labelled = [c for c in cases if c.get("human_label") in ("PASS", "FAIL")]
    skipped = len(cases) - len(labelled)
    if skipped:
        print(f"  ⚠️  {skipped} case(s) have no human label yet — skipped.")
    return labelled


# ======================================================================
# SECTION B — Run the judge (a failed call is infrastructure, not a verdict)
# ======================================================================
def run_judge(judge, cases, retries=2):
    """Returns {case_id: Verdict}; cases whose judge call kept failing are left out
    and reported, so a network glitch never counts as a right or wrong verdict."""
    verdicts, errored = {}, []
    for c in cases:
        for attempt in range(retries + 1):
            try:
                verdicts[c["id"]] = judge.verdict(c, c["answer"])
                break
            except Exception as e:  # noqa: BLE001
                if attempt == retries:
                    errored.append((c["id"], str(e)[:120]))
                else:
                    time.sleep(1)
    return verdicts, errored


# ======================================================================
# SECTION C — The two numbers (overall and per category)
# ======================================================================
def rate(numerator, denominator):
    return round(numerator / denominator, 3) if denominator else None


def score(cases, verdicts):
    scored = [c for c in cases if c["id"] in verdicts]
    human_fail = [c for c in scored if c["human_label"] == "FAIL"]
    human_pass = [c for c in scored if c["human_label"] == "PASS"]
    caught = sum(1 for c in human_fail if not verdicts[c["id"]].passed)
    left_alone = sum(1 for c in human_pass if verdicts[c["id"]].passed)
    return {
        "n": len(scored),
        "human_fail": len(human_fail),
        "human_pass": len(human_pass),
        "catch_rate": rate(caught, len(human_fail)),
        "leave_alone_rate": rate(left_alone, len(human_pass)),
        "agreement": rate(caught + left_alone, len(scored)),
    }


def by_category(cases, verdicts):
    groups = defaultdict(list)
    for c in cases:
        groups[c["category"]].append(c)
    return {cat: score(group, verdicts) for cat, group in sorted(groups.items())}


def disagreements(cases, verdicts):
    out = []
    for c in cases:
        v = verdicts.get(c["id"])
        if v is None:
            continue
        judge_label = "PASS" if v.passed else "FAIL"
        if judge_label != c["human_label"]:
            out.append({
                "id": c["id"], "category": c["category"],
                "human": c["human_label"], "judge": judge_label,
                "human_reason": c.get("label_reason"), "judge_reason": v.reason,
                "failure_type": c.get("failure_type"),
            })
    return out


# ======================================================================
# SECTION D — Report, save, and decide whether the judge may gate
# ======================================================================
def pct(x):
    return "  n/a" if x is None else f"{x:5.0%}"


def report(judge, split, overall, per_cat, misses, errored):
    print(f"\nJudge: {judge.version}   ·   split: {split}")
    print(f"\n{'':14} {'n':>3} {'fails':>6} {'catches':>8} {'leaves good':>12}")
    print("-" * 47)
    for cat, s in per_cat.items():
        print(f"{cat:14} {s['n']:>3} {s['human_fail']:>6} {pct(s['catch_rate']):>8} {pct(s['leave_alone_rate']):>12}")
    print("-" * 47)
    print(f"{'ALL':14} {overall['n']:>3} {overall['human_fail']:>6} "
          f"{pct(overall['catch_rate']):>8} {pct(overall['leave_alone_rate']):>12}")
    if overall["human_fail"]:
        print(f"\n  Small-sample note: {overall['human_fail']} human FAILs here, so one case moves "
              f"the catch rate by about {1 / overall['human_fail']:.0%}. A direction, not a verdict.")
    if errored:
        print(f"\n  ⚠️  {len(errored)} judge call(s) errored (infrastructure, not quality) — left out.")
    if misses:
        print(f"\nDisagreements ({len(misses)}):")
        for m in misses:
            print(f"  {m['id']} [{m['category']}] human {m['human']} vs judge {m['judge']}")
            print(f"      human: {m['human_reason']}")
            print(f"      judge: {m['judge_reason']}")


def save(judge, split, overall, per_cat, misses, errored, qualified):
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge_version": judge.version,
        "split": split,
        "overall": overall,
        "by_category": per_cat,
        "disagreement_ids": [m["id"] for m in misses],
        "errored_ids": [e[0] for e in errored],
        "bars": {"min_catch_rate": MIN_CATCH_RATE, "min_leave_alone_rate": MIN_LEAVE_ALONE_RATE},
        "qualified": qualified,
    }
    with open(RESULTS_PATH, "a") as f:
        f.write(json.dumps(row) + "\n")


def judge_status(version, path=None):
    """'qualified' / 'not_qualified' / 'unvalidated' for this exact judge version, from its
    most recent held-back run. A new model or rubric = a new version = unvalidated again."""
    try:
        with open(path or RESULTS_PATH) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return "unvalidated"
    runs = [r for r in rows if r.get("judge_version") == version and r.get("split") in ("holdout", "all")]
    if not runs:
        return "unvalidated"
    return "qualified" if runs[-1].get("qualified") else "not_qualified"


def qualifies(overall):
    c, g = overall["catch_rate"], overall["leave_alone_rate"]
    return c is not None and g is not None and c >= MIN_CATCH_RATE and g >= MIN_LEAVE_ALONE_RATE


def main():
    ap = argparse.ArgumentParser(description="Validate an answer judge against human labels.")
    ap.add_argument("--judge", default="mock", choices=["mock", "llm"])
    ap.add_argument("--split", default="tune", choices=["tune", "holdout", "all"])
    ap.add_argument("--labels", default=LABELS_PATH)
    args = ap.parse_args()

    judge = make_answer_judge(args.judge)
    cases = load_labelled(args.labels, args.split)
    if not cases:
        print("No labelled cases to validate against — label judge_labels.json first.")
        return 1

    verdicts, errored = run_judge(judge, cases)
    overall = score(cases, verdicts)
    per_cat = by_category(cases, verdicts)
    misses = disagreements(cases, verdicts)
    report(judge, args.split, overall, per_cat, misses, errored)

    gating_run = args.split in ("holdout", "all")
    qualified = qualifies(overall) if gating_run else None
    save(judge, args.split, overall, per_cat, misses, errored, qualified)

    print()
    if not gating_run:
        print("Tuning run — use the disagreements above to improve the judge. "
              "Not a qualification; run --split holdout once the judge is final.")
        return 0
    bars = f"(bars: catches ≥ {MIN_CATCH_RATE:.0%}, leaves good alone ≥ {MIN_LEAVE_ALONE_RATE:.0%})"
    if qualified:
        print(f"JUDGE: ✅ QUALIFIED to gate {bars}")
        return 0
    print(f"JUDGE: ❌ NOT QUALIFIED to gate {bars}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
