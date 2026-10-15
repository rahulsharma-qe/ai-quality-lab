"""Errors that mean "the setup is broken", never "the agent's quality is bad".

The command line turns any SetupError into exit code 2, so a broken config or an
unreachable agent is never reported as a quality regression (exit code 1).
"""


class SetupError(Exception):
    """Base class: something about the setup stops a fair measurement."""


class ConfigError(SetupError):
    """A team config file is missing, unreadable or invalid. Lists every problem found."""

    def __init__(self, source: str, problems: list[str]):
        self.source = source
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"Invalid config {source}:\n{lines}")


class GoldenSetError(SetupError):
    """A golden set file is missing, unreadable or has invalid cases."""

    def __init__(self, source: str, problems: list[str]):
        self.source = source
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"Invalid golden set {source}:\n{lines}")


class AgentConnectionError(SetupError):
    """The agent could not be reached or returned something unreadable."""


class RecordingNotFoundError(SetupError):
    """A recorded-answers file has no answer for the question that was asked."""
