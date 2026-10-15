"""Checks plug in here. Adding a check = one class with @register_check; no core edit.

    @register_check("mentions_human_handover")
    class MentionsHumanHandover(Check):
        description = "Answer offers a human agent"
        def evaluate(self, case, response):
            ...
"""

from aiquality.checks.base import Check

_CHECKS: dict[str, type] = {}


def register_check(name: str):
    def decorator(check_class: type) -> type:
        if not issubclass(check_class, Check):
            raise TypeError(f"{check_class.__name__} must inherit from Check")
        existing = _CHECKS.get(name)
        if existing is not None and existing is not check_class and not _same_definition(existing, check_class):
            raise ValueError(f"a check named '{name}' is already registered")
        check_class.name = name
        _CHECKS[name] = check_class
        return check_class
    return decorator


def _same_definition(first: type, second: type) -> bool:
    """True when a plugin file is simply loaded again: same class name from the same module."""
    return first.__qualname__ == second.__qualname__ and first.__module__ == second.__module__


def create_check(name: str, **options) -> Check:
    if name not in _CHECKS:
        raise KeyError(f"unknown check '{name}'. Available: {', '.join(available_checks())}")
    return _CHECKS[name](**options)


def available_checks() -> list[str]:
    return sorted(_CHECKS)


def describe_checks() -> dict[str, str]:
    return {name: _CHECKS[name].description for name in available_checks()}
