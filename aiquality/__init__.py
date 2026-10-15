"""aiquality: a self-serve quality platform for AI agents.

A team connects its agent and brings a config file and a golden set; the platform
asks the agent every case, scores the answers with pluggable checks, and writes a
RunRecord that every report reads. See docs/onboarding.md.
"""

from aiquality.adapters import HttpEndpointAgent, PythonFunctionAgent, RecordedResponsesAgent, build_agent
from aiquality.checks import Check, CheckResult, CheckStatus, register_check
from aiquality.config import CompanyMinimums, TeamConfig
from aiquality.contracts import AgentResponse, AgentUnderTest, SupportsDocumentInjection, ToolCall
from aiquality.errors import ConfigError, GoldenSetError, SetupError
from aiquality.reporting import Reporter, RunRecord, register_reporter
from aiquality.runner import Runner
from aiquality.test_data import GoldenCase, GoldenCaseBuilder, GoldenSet, load_golden_set

__version__ = "0.1.0"

__all__ = [
    "AgentResponse", "AgentUnderTest", "Check", "CheckResult", "CheckStatus", "CompanyMinimums",
    "ConfigError", "GoldenCase", "GoldenCaseBuilder", "GoldenSet", "GoldenSetError", "HttpEndpointAgent",
    "PythonFunctionAgent", "RecordedResponsesAgent", "Reporter", "RunRecord", "Runner", "SetupError",
    "SupportsDocumentInjection", "TeamConfig", "ToolCall", "build_agent", "load_golden_set",
    "register_check", "register_reporter",
]
