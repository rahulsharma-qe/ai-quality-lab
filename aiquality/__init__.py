"""aiquality: a self-serve quality platform for AI agents.

A team connects its agent and brings a config file and a golden set; the platform
asks the agent every case, scores the answers with pluggable checks, and writes a
RunRecord that every report reads. See docs/onboarding.md.
"""

from aiquality.contracts import AgentResponse, AgentUnderTest, SupportsDocumentInjection, ToolCall
from aiquality.errors import ConfigError, GoldenSetError, SetupError
from aiquality.test_data import GoldenCase, GoldenCaseBuilder, GoldenSet, load_golden_set

__version__ = "0.1.0"

__all__ = [
    "AgentResponse", "AgentUnderTest", "ConfigError", "GoldenCase", "GoldenCaseBuilder", "GoldenSet",
    "GoldenSetError", "SetupError", "SupportsDocumentInjection", "ToolCall", "load_golden_set",
]
