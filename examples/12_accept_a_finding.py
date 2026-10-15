"""Example 12: accept a reviewed finding, for a limited time.

Phrase checks can't understand "not": "your refund is not approved yet" matches the forbidden
phrase "approved". A person who has read the answer can accept that one finding, with a reason,
an approver and an expiry within 90 days. Until it expires it counts as a pass and is listed in
every report; after it expires it counts again.
Run:  python examples/12_accept_a_finding.py
"""

import tempfile
from datetime import date
from pathlib import Path

from aiquality import TeamConfig
from aiquality.commands import gate_team

EXAMPLES = Path(__file__).parent
SETTINGS = {
    "team": "acceptance_demo",
    "agent": {"adapter": "python_function", "file": "sample_store_agent.py", "function": "answer"},
    "golden_set": "quickstart_team/golden_set.csv",
    "checks": {"forbidden_phrases": {"threshold": 1.0}},
}
ACCEPTANCE = {"case": "Q04", "check": "forbidden_phrases",
              "reason": "Negation false alarm: the answer says the refund is NOT approved",
              "approved_by": "qa-lead", "expires": "2026-11-15"}


def run_gate(settings, today):
    config = TeamConfig.from_dict(settings, folder=EXAMPLES, today=today)
    _, decision = gate_team(config, output_dir=Path(tempfile.mkdtemp()), print_reports=False, today=today)
    return decision


before = run_gate(SETTINGS, date(2026, 10, 15))
print("without acceptance:", "PASS" if before.passed else "FAIL", before.failures)

accepted = run_gate({**SETTINGS, "accepted_findings": [ACCEPTANCE]}, date(2026, 10, 15))
print("with acceptance:   ", "PASS" if accepted.passed else "FAIL", "| accepted:",
      [f"{a['case']} until {a['expires']}" for a in accepted.accepted_findings])

expired = run_gate({**SETTINGS, "accepted_findings": [ACCEPTANCE]}, date(2026, 11, 20))
print("after it expires:  ", "PASS" if expired.passed else "FAIL", "| warnings:", expired.warnings)
