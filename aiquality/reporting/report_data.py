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


def percent(value) -> str:
    return "-" if value is None else f"{value:.0%}"


def verdict(record: RunRecord) -> str:
    if record.gate_decision:
        return record.gate_decision["decision"]
    return "REPORT ONLY"
