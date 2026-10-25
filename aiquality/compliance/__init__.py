"""Responsible-AI evidence: a team's run held against the laws and standards it chose.

    aiquality evidence --team aeroassist [--as high]

frameworks/*.yaml   one file per law or standard: its controls and the evidence each can take
evidence.py         the evidence a run record gives, by name
assessment.py       the label of every control, at every risk level
report.py           index.html, evidence.md, evidence.json
"""

from aiquality.compliance.assessment import LABELS, Assessment, assess
from aiquality.compliance.frameworks import RISK_LEVELS, available_frameworks, load_framework
from aiquality.compliance.report import write_report

__all__ = ["LABELS", "RISK_LEVELS", "Assessment", "assess", "available_frameworks", "load_framework", "write_report"]
