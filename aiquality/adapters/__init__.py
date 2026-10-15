"""Adapters turn real agents into AgentUnderTest. build_agent() picks one from a config."""

from pathlib import Path

from aiquality.adapters.http_endpoint_agent import HttpEndpointAgent
from aiquality.adapters.python_function_agent import PythonFunctionAgent
from aiquality.adapters.recorded_responses_agent import (
    RecordedResponsesAgent,
    RecordingSummary,
    record_responses,
)
from aiquality.contracts import AgentUnderTest
from aiquality.errors import ConfigError

ADAPTER_NAMES = ("python_function", "http_endpoint", "recorded_responses")


def build_agent(settings: dict, team_folder: Path, team_name: str = "agent") -> AgentUnderTest:
    """Create an agent from an 'agent:' block of a team config.

    python_function:    {adapter, file, function}           file is relative to the team folder
    http_endpoint:      {adapter, url, method, question_field, answer_field, auth_token_env, ...}
    recorded_responses: {adapter, path}                      path is relative to the team folder
    """
    adapter = settings.get("adapter")
    team_folder = Path(team_folder)
    if adapter == "python_function":
        return PythonFunctionAgent.from_file(team_folder / settings["file"], settings["function"],
                                             name=team_name)
    if adapter == "http_endpoint":
        options = {k: v for k, v in settings.items() if k != "adapter"}
        return HttpEndpointAgent(name=team_name, **options)
    if adapter == "recorded_responses":
        return RecordedResponsesAgent(team_folder / settings["path"], name=team_name)
    raise ConfigError("agent", [f"unknown adapter '{adapter}'. Available: {', '.join(ADAPTER_NAMES)}"])


__all__ = [
    "ADAPTER_NAMES",
    "HttpEndpointAgent",
    "PythonFunctionAgent",
    "RecordedResponsesAgent",
    "RecordingSummary",
    "build_agent",
    "record_responses",
]
