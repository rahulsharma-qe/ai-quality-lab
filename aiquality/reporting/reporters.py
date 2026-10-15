"""Reports plug in here. Adding a format = one class with @register_reporter; no core edit.

Every reporter reads the same RunRecord, so all formats always agree.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from aiquality.reporting.run_record import RunRecord

_REPORTERS: dict[str, type] = {}


class Reporter(ABC):
    name: str = "unnamed-reporter"

    @abstractmethod
    def write(self, record: RunRecord, output_dir: Path) -> Optional[Path]:
        """Produce the report. Return the file written, or None if it only printed."""


def register_reporter(name: str):
    def decorator(reporter_class: type) -> type:
        if not issubclass(reporter_class, Reporter):
            raise TypeError(f"{reporter_class.__name__} must inherit from Reporter")
        reporter_class.name = name
        _REPORTERS[name] = reporter_class
        return reporter_class
    return decorator


def create_reporter(name: str) -> Reporter:
    if name not in _REPORTERS:
        raise KeyError(f"unknown report '{name}'. Available: {', '.join(available_reporters())}")
    return _REPORTERS[name]()


def available_reporters() -> list[str]:
    return sorted(_REPORTERS)
