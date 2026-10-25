"""Framework files: one YAML per law or standard, naming its controls and the evidence each can take.

The files that come with the platform are in compliance/frameworks/; a team can add its own, or
replace one of the same name, in teams/<team>/frameworks/.

    framework: eu-ai-act
    name: EU AI Act
    source: Regulation (EU) 2024/1689
    link: https://...
    controls:
      - id: Art. 15(5)
        title: Robust against attacks
        asks: The system resists attempts to change its outputs ...
        applies_when: [high]            # risk levels it applies at (default: every level)
        link: https://...
        evidence: [attack_resistance]   # names from compliance/evidence.py
        partial: what the evidence doesn't show   (optional)
      - id: Art. 9
        ...
        outside_the_tool: why a test run can't show it   (instead of evidence)

Every control has evidence or outside_the_tool, never both: a control the tool can't show is never
counted as covered.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from aiquality.compliance.evidence import known_evidence
from aiquality.errors import ConfigError

BUILT_IN = Path(__file__).parent / "frameworks"
RISK_LEVELS = ("minimal", "limited", "high")


@dataclass
class Control:
    id: str
    title: str
    asks: str
    applies_when: tuple = RISK_LEVELS
    evidence: tuple = ()
    outside_the_tool: str = ""
    partial: str = ""
    link: str = ""
    note: str = ""


@dataclass
class Framework:
    key: str
    name: str
    source: str
    link: str
    controls: list = field(default_factory=list)
    note: str = ""
    file: str = ""


def available_frameworks(team_folder: Optional[Path] = None) -> dict[str, Path]:
    """Framework key -> file. A team's own file replaces a built-in one with the same key."""
    found = {path.stem: path for path in sorted(BUILT_IN.glob("*.yaml"))}
    if team_folder is not None and (Path(team_folder) / "frameworks").is_dir():
        found.update({path.stem: path for path in sorted((Path(team_folder) / "frameworks").glob("*.yaml"))})
    return found


def load_framework(path: Path) -> Framework:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    problems = []
    for key in ("framework", "name", "source", "link", "controls"):
        if not data.get(key):
            problems.append(f"'{key}' is required")
    if data.get("framework") and data["framework"] != Path(path).stem:
        problems.append(f"'framework: {data['framework']}' must match the file name ({Path(path).stem})")
    controls = []
    for number, raw in enumerate(data.get("controls") or [], start=1):
        control, control_problems = _control(raw, number)
        problems += control_problems
        if control:
            controls.append(control)
    if problems:
        raise ConfigError(str(path), problems)
    return Framework(data["framework"], data["name"], data["source"], data["link"], controls,
                     str(data.get("note") or "").strip(), str(path))


def _control(raw, number: int) -> tuple[Optional[Control], list[str]]:
    where = f"control {number}"
    if not isinstance(raw, dict):
        return None, [f"{where}: must be a mapping with id, title, asks"]
    where = f"control {raw.get('id', number)}"
    problems = [f"{where}: '{key}' is required" for key in ("id", "title", "asks") if not raw.get(key)]
    evidence, outside = list(raw.get("evidence") or []), str(raw.get("outside_the_tool") or "")
    if bool(evidence) == bool(outside):
        problems.append(f"{where}: give either 'evidence' or 'outside_the_tool', not both and not neither")
    problems += [f"{where}: unknown evidence '{name}'" for name in evidence if not known_evidence(name)]
    levels = tuple(raw.get("applies_when") or RISK_LEVELS)
    problems += [f"{where}: unknown risk level '{level}' (use {', '.join(RISK_LEVELS)})"
                 for level in levels if level not in RISK_LEVELS]
    if problems:
        return None, problems
    return Control(str(raw["id"]), str(raw["title"]), " ".join(str(raw["asks"]).split()), levels, tuple(evidence),
                   outside, str(raw.get("partial") or ""), str(raw.get("link") or ""), str(raw.get("note") or "")), []
