"""Checks: one class per check, registered by name. Built-in checks register on import."""

from aiquality.checks.base import Check, CheckResult, CheckStatus, CheckSummary, summarise
from aiquality.checks.registry import available_checks, create_check, describe_checks, register_check
from aiquality.checks import personal_data_check, phrase_checks  # noqa: F401  (register the built-in checks)

__all__ = ["Check", "CheckResult", "CheckStatus", "CheckSummary", "summarise",
           "available_checks", "create_check", "describe_checks", "register_check"]
