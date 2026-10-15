"""Small helpers every report uses, so all formats describe a run the same way."""

from aiquality.reporting.run_record import RunRecord


def accepted_pairs(record: RunRecord) -> dict:
    """(case_id, check) -> the acceptance that turned that FAIL into a pass for the gate."""
    gate = record.gate_decision or {}
    return {(a["case"], a["check"]): a for a in gate.get("accepted_findings", [])}


def findings(record: RunRecord) -> list[tuple[dict, dict]]:
    """Every (outcome, result) that FAILED or ERRORED, golden cases first."""
    ordered = sorted(record.outcomes, key=lambda o: o.get("category") == "attack")
    return [(o, r) for o in ordered for r in o["results"] if r["status"] in ("FAIL", "ERROR")]


def version_text(version: str) -> str:
    """'1.4' -> 'version 1.4'; a golden set without a version says so plainly."""
    return "no version" if version in ("", "unversioned") else f"version {version}"


def judge_text(record: RunRecord):
    """'judge <version> · not qualified · advisory · recorded', or None when no judge took part."""
    judge = record.judge
    if not judge:
        return None
    return (f"judge {judge['version']} · {judge['status'].replace('_', ' ')} · "
            f"{'can block' if judge['blocking'] else 'advisory'} · {judge['mode']}")


def percent(value) -> str:
    return "-" if value is None else f"{value:.0%}"


def check_rows(record: RunRecord) -> list[dict]:
    """Each check's summary plus what the gate made of it.

    When a person accepted some of a check's failures, 'gate_rate' is the pass rate with those
    counted as passes, so a report never shows 86% against a 100% bar without saying why it passed.
    'label' marks a check that doesn't block: the judge's as 'advisory', any other as "doesn't block".
    """
    accepted = accepted_pairs(record)
    golden_ids = {o["case_id"] for o in record.outcomes if o.get("category") != "attack"}
    judge_check = (record.judge or {}).get("check")
    rows = []
    for summary in record.summaries:
        count = sum(1 for case, check in accepted if check == summary["check"] and case in golden_ids)
        row = dict(summary, accepted=count, gate_rate=summary["pass_rate"], gate_meets=summary["meets_threshold"],
                   label=summary["check"] + _blocking_note(summary, judge_check))
        if count and summary["pass_rate"] is not None:
            row["gate_rate"] = (summary["passed"] + count) / (summary["passed"] + summary["failed"])
            row["gate_meets"] = row["gate_rate"] >= summary["threshold"]
        rows.append(row)
    return rows


def _blocking_note(summary: dict, judge_check) -> str:
    if summary.get("blocking", True):
        return ""
    return " (advisory)" if summary["check"] == judge_check else " (doesn't block)"


def rate_text(row: dict) -> str:
    """'89%', or '86% → 100% (3 accepted)' when accepted findings changed the rate."""
    if row["accepted"]:
        return f"{percent(row['pass_rate'])} → {percent(row['gate_rate'])} ({row['accepted']} accepted)"
    return percent(row["pass_rate"])


def result_text(row: dict) -> str:
    return {True: "MEETS", False: "BELOW", None: "NO DATA"}[row["gate_meets"]]


def verdict(record: RunRecord) -> str:
    if record.gate_decision:
        return record.gate_decision["decision"]
    return "REPORT ONLY"
