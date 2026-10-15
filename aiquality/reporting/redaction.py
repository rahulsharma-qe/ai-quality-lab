"""Remove personal contact data before anything is written to disk (see aiquality.personal_data)."""

from aiquality.personal_data import PERSONAL_DATA_PATTERNS, redact_personal_data

__all__ = ["PERSONAL_DATA_PATTERNS", "redact_personal_data"]
