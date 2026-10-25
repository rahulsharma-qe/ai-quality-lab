"""compliance: in team.yaml: the team's risk level and the frameworks its evidence report holds it to.

    compliance:
      risk_level: limited          # minimal | limited | high, the EU AI Act's levels (high: Annex III)
      frameworks: [eu-ai-act, nist-ai-rmf, dpdp, owasp-llm]

A framework is a file in aiquality/compliance/frameworks/, or the team's own in <team>/frameworks/.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ComplianceSettings:
    risk_level: str
    frameworks: list


def parse_compliance_settings(raw, folder: Path) -> tuple:
    """(ComplianceSettings or None, problems)."""
    from aiquality.compliance.frameworks import RISK_LEVELS, available_frameworks   # here: avoids an import cycle
    if raw is None:
        return None, []
    if not isinstance(raw, dict):
        return None, ["'compliance' must be a mapping: risk_level and frameworks"]
    problems = [f"'compliance.{key}' is not a setting (use risk_level, frameworks)" for key in raw
                if key not in ("risk_level", "frameworks")]
    level = raw.get("risk_level")
    if level not in RISK_LEVELS:
        problems.append(f"'compliance.risk_level' must be one of {', '.join(RISK_LEVELS)}")
    frameworks = raw.get("frameworks")
    known = available_frameworks(folder)
    if not isinstance(frameworks, list) or not frameworks:
        problems.append("'compliance.frameworks' must list at least one framework, e.g. [eu-ai-act, nist-ai-rmf]")
    else:
        problems += [f"unknown framework '{name}'. Available: {', '.join(sorted(known))}"
                     for name in frameworks if name not in known]
    if problems:
        return None, problems
    return ComplianceSettings(level, [str(name) for name in frameworks]), []
