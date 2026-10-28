"""aiquality: a self-serve quality platform for AI agents.

A team connects its agent and brings a config file and a golden set; the platform
asks the agent every case, scores the answers with pluggable checks, and writes a
RunRecord that every report reads. See docs/onboarding.md.
"""

__version__ = "0.2.0"     # the one place the version is written; pyproject.toml reads it

from aiquality.adapters import HttpEndpointAgent, PythonFunctionAgent, RecordedResponsesAgent, build_agent
from aiquality.checks import Check, CheckResult, CheckStatus, register_check
from aiquality.commands import evaluate_team, record_team
from aiquality.scaffold import create_team_scaffold
from aiquality.config import CompanyMinimums, TeamConfig
from aiquality.contracts import AgentResponse, AgentUnderTest, SupportsDocumentInjection, ToolCall
from aiquality.errors import ConfigError, GoldenSetError, SetupError
from aiquality.reporting import Reporter, RunRecord, compare_runs, pick_run, register_reporter
from aiquality.runner import Runner
from aiquality.test_data import GoldenCase, GoldenCaseBuilder, GoldenSet, load_golden_set


__all__ = [
    "AgentResponse", "AgentUnderTest", "Check", "CheckResult", "CheckStatus", "CompanyMinimums",
    "ConfigError", "GoldenCase", "GoldenCaseBuilder", "GoldenSet", "GoldenSetError", "HttpEndpointAgent",
    "PythonFunctionAgent", "RecordedResponsesAgent", "Reporter", "RunRecord", "Runner", "SetupError",
    "SupportsDocumentInjection", "TeamConfig", "ToolCall", "build_agent", "compare_runs", "create_team_scaffold",
    "evaluate_team", "load_golden_set", "pick_run", "record_team", "register_check", "register_reporter",
]
