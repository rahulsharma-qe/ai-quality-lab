"""Judges register by kind, so a team config can name one: judge: {kind: policy_answer, ...}."""

_JUDGES: dict = {}


def register_judge(kind: str):
    """Class decorator: @register_judge("policy_answer")."""
    def decorate(cls):
        if kind in _JUDGES and _JUDGES[kind] is not cls:
            raise ValueError(f"a judge kind '{kind}' is already registered")
        _JUDGES[kind] = cls
        return cls
    return decorate


def create_judge(kind: str, **options):
    if kind not in _JUDGES:
        raise KeyError(f"unknown judge kind '{kind}'. Available: {', '.join(available_judges())}")
    return _JUDGES[kind](**options)


def available_judges() -> list[str]:
    return sorted(_JUDGES)
