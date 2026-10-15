"""The company-wide floor every team config is checked against."""

import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

import yaml

from aiquality.errors import ConfigError

ENVIRONMENT_VARIABLE = "AIQUALITY_COMPANY_MINIMUMS"


@dataclass
class CompanyMinimums:
    mandatory_checks: list[str] = field(default_factory=list)
    minimum_thresholds: dict[str, float] = field(default_factory=dict)
    minimum_attack_resistance: Optional[float] = None
    source: str = "built-in"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CompanyMinimums":
        """Read the floor from `path`, else $AIQUALITY_COMPANY_MINIMUMS, else the built-in file."""
        path = path or os.environ.get(ENVIRONMENT_VARIABLE)
        if path:
            path = Path(path)
            if not path.is_file():
                raise ConfigError(str(path), ["company minimums file not found"])
            text, source = path.read_text(encoding="utf-8"), str(path)
        else:
            text = resources.files("aiquality.config").joinpath("company_minimums.yaml").read_text(encoding="utf-8")
            source = "built-in"
        data = yaml.safe_load(text) or {}
        return cls(mandatory_checks=list(data.get("mandatory_checks", [])),
                   minimum_thresholds={k: float(v) for k, v in (data.get("minimum_thresholds") or {}).items()},
                   minimum_attack_resistance=_optional_float(data.get("minimum_attack_resistance")),
                   source=source)

    def problems_with(self, team_checks: dict) -> list[str]:
        """Return readable problems where a team's checks go below the floor."""
        problems = []
        for name in self.mandatory_checks:
            if name not in team_checks:
                problems.append(f"check '{name}' is mandatory company-wide and cannot be left out")
        for name, settings in team_checks.items():
            floor = self.minimum_thresholds.get(name)
            if floor is not None and settings.threshold < floor:
                problems.append(f"check '{name}': threshold {settings.threshold} is below the "
                                f"company minimum {floor}; a team may only be stricter")
        return problems


def _optional_float(value):
    return None if value is None else float(value)
