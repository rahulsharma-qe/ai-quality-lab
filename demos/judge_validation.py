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

Now a thin wrapper: the logic is in aiquality/judges/validation.py, and teams use
  aiquality validate-judge --team <team> --split holdout

Run:
  python demos/judge_validation.py --judge llm  --split tune      # improve the judge here
  python demos/judge_validation.py --judge llm  --split holdout   # the real measurement
  python demos/judge_validation.py --judge mock --split all       # key-free plumbing check

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
from types import SimpleNamespace

from aiquality.judges import validation
from aiquality.judges.validation import MIN_CATCH_RATE, MIN_LEAVE_ALONE_RATE, LabelledAnswer  # noqa: F401
from answer_judge import make_answer_judge
from paths import JUDGE_LABELS, JUDGE_RESULTS

# The implementation lives in the aiquality package (aiquality/judges/validation.py; command line:
# aiquality validate-judge). This file keeps the old command line and the old dict-based helpers.
LABELS_PATH = str(JUDGE_LABELS)
RESULTS_PATH = str(JUDGE_RESULTS)


def load_labelled(path, split):
    """Labelled cases as plain dicts (the old shape)."""
    with open(path) as f:
        cases = json.load(f)["cases"]
    if split != "all":
        cases = [c for c in cases if c.get("split") == split]
    return [c for c in cases if c.get("human_label") in ("PASS", "FAIL")]


def run_judge(judge, cases, retries=2):
    """{case_id: Verdict} for dict cases; calls that kept failing are left out and listed."""
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


def _view(cases):
    """Dict cases seen through the attributes the package's maths reads."""
    return [SimpleNamespace(id=c["id"], human_label=c["human_label"], category=c.get("category", "uncategorised"),
                            label_reason=c.get("label_reason"), failure_type=c.get("failure_type")) for c in cases]


def score(cases, verdicts):
    return validation.score(_view(cases), verdicts)


def by_category(cases, verdicts):
    return validation.by_category(_view(cases), verdicts)


def disagreements(cases, verdicts):
    return validation.disagreements(_view(cases), verdicts)


def qualifies(overall):
    return validation.qualifies(overall)


def judge_status(version, path=None):
    """'qualified' / 'not_qualified' / 'unvalidated' for this exact judge version."""
    return validation.judge_status(version, path or RESULTS_PATH)


def main():
    ap = argparse.ArgumentParser(description="Validate an answer judge against human labels.")
    ap.add_argument("--judge", default="mock", choices=["mock", "llm"])
    ap.add_argument("--split", default="tune", choices=["tune", "holdout", "all"])
    ap.add_argument("--labels", default=LABELS_PATH)
    args = ap.parse_args()

    judge = make_answer_judge(args.judge)
    items, skipped = validation.load_labels(args.labels, args.split)
    if not items:
        print("No labelled cases to validate against — label judge_labels.json first.")
        return 1
    run = validation.validate_judge(judge, items, args.split, skipped_unlabelled=skipped)
    print(validation.render_validation(run))
    validation.save_run(run, RESULTS_PATH)
    return 0 if run.qualified in (None, True) else 1


if __name__ == "__main__":
    sys.exit(main())
