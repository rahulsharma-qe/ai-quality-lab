"""Turn any Python function into an agent the platform can test."""

import importlib.util
import inspect
import time
from pathlib import Path
from typing import Callable, Optional

from aiquality.contracts import AgentResponse, AgentUnderTest
from aiquality.errors import AgentConnectionError, ConfigError


class PythonFunctionAgent(AgentUnderTest):
    """Wraps a function answer(question) or answer(question, conversation).

    The function may return plain text, a dict with "answer_text", or an AgentResponse.
    Response time is measured here if the function doesn't report it.
    """

    def __init__(self, answer_function: Callable, name: str = "python-function-agent",
                 version: str = "unversioned"):
        self.answer_function = answer_function
        self.name = name
        self.version = version
        self._accepts_conversation = _accepts_two_arguments(answer_function)

    def answer(self, question: str, conversation: Optional[list[dict]] = None) -> AgentResponse:
        started = time.perf_counter()
        if self._accepts_conversation:
            raw = self.answer_function(question, conversation)
        else:
            raw = self.answer_function(question)
        response = AgentResponse.from_any(raw)
        if response.latency_ms is None:
            response.latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return response

    @classmethod
    def from_file(cls, file_path: Path, function_name: str, name: Optional[str] = None,
                  version: str = "unversioned") -> "PythonFunctionAgent":
        """Load a function from a .py file, e.g. a team's agent.py.

        Optional in that file: AGENT_VERSION (recorded in every run), and prepare(),
        called once before any question so slow start-up (loading a model) is not
        counted in the first answer's response time.
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise ConfigError(str(file_path), [f"agent file not found: {file_path}"])
        spec = importlib.util.spec_from_file_location(f"team_agent_{file_path.stem}", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        function = getattr(module, function_name, None)
        if function is None or not callable(function):
            raise ConfigError(str(file_path), [f"no function named '{function_name}' in {file_path.name}"])
        prepare = getattr(module, "prepare", None)
        if callable(prepare):
            try:
                prepare()  # load models and clients now, so the first answer's time isn't inflated
            except Exception as error:  # e.g. a missing API key: a setup problem, not a quality result
                raise AgentConnectionError(f"prepare() in {file_path.name} failed: {type(error).__name__}: {error}")
        version = getattr(module, "AGENT_VERSION", version)
        return cls(function, name=name or file_path.parent.name, version=version)


def _accepts_two_arguments(function: Callable) -> bool:
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return False
    positional = [p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    has_var_args = any(p.kind == p.VAR_POSITIONAL for p in parameters)
    return has_var_args or len(positional) >= 2
