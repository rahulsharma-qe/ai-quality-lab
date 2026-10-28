"""The 'accepted_findings:' block: findings a person has reviewed and accepted, for a limited time.

    accepted_findings:
      - case: GD25
        check: forbidden_phrases
        reason: "Negation false alarm: the answer says you don't need to pay extra"
        approved_by: rahulsharma-qe
        expires: 15-11-2026          # DD-MM-YYYY (2026-11-15 is read too)

Every acceptance names one case and one check, says why and who approved it, and expires
within 90 days. Expired ones count again. Each one is listed in every report.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from aiquality.dates import parse_day

MAX_DAYS_AHEAD = 90
REQUIRED_FIELDS = ("case", "check", "reason", "approved_by", "expires")


@dataclass(frozen=True)
class AcceptedFinding:
    case: str
    check: str
    reason: str
    approved_by: str
    expires: date

    def is_active(self, today: date) -> bool:
        return today <= self.expires

    def to_dict(self) -> dict:
        return {"case": self.case, "check": self.check, "reason": self.reason,
                "approved_by": self.approved_by, "expires": self.expires.isoformat()}


def parse_accepted_findings(raw, check_names: list[str], today: Optional[date] = None):
    """Return (list of AcceptedFinding, problems)."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["'accepted_findings' must be a list of {case, check, reason, approved_by, expires}"]
    today = today or date.today()
    findings, problems, seen = [], [], set()
    for number, item in enumerate(raw, start=1):
        label = f"accepted_findings[{number}]"
        if not isinstance(item, dict):
            problems.append(f"'{label}' must have {', '.join(REQUIRED_FIELDS)}")
            continue
        missing = [name for name in REQUIRED_FIELDS if not str(item.get(name, "")).strip()]
        if missing:
            problems.append(f"'{label}' is missing {', '.join(missing)}: an acceptance needs a reason, "
                            "an approver and an expiry date")
            continue
        unknown = set(item) - set(REQUIRED_FIELDS)
        if unknown:
            problems.append(f"'{label}' has unknown setting(s): {', '.join(sorted(unknown))}")
        if item["check"] not in check_names:
            problems.append(f"'{label}.check' '{item['check']}' is not one of this team's checks")
        expires = _to_date(item["expires"])
        if expires is None:
            problems.append(f"'{label}.expires' must be a date like 2026-11-15")
            continue
        if expires > today + timedelta(days=MAX_DAYS_AHEAD):
            problems.append(f"'{label}.expires' is more than {MAX_DAYS_AHEAD} days away; accept findings for "
                            "a limited time and review them again")
        key = (str(item["case"]), item["check"])
        if key in seen:
            problems.append(f"'{label}' accepts {key[0]} / {key[1]} a second time")
        seen.add(key)
        findings.append(AcceptedFinding(case=str(item["case"]), check=item["check"], reason=str(item["reason"]),
                                        approved_by=str(item["approved_by"]), expires=expires))
    return (findings, problems) if not problems else ([], problems)


def _to_date(value) -> Optional[date]:
    return parse_day(value)
