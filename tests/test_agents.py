"""The agent contract and the three adapters."""

import pytest

from aiquality import AgentResponse, HttpEndpointAgent, PythonFunctionAgent, RecordedResponsesAgent
from aiquality.adapters import build_agent, record_responses
from aiquality.errors import AgentConnectionError, ConfigError, RecordingNotFoundError
from aiquality.test_data import GoldenCaseBuilder


def test_agent_response_accepts_text_dict_and_object():
    assert AgentResponse.from_any("hi").answer_text == "hi"
    from_dict = AgentResponse.from_any({"answer_text": "hi", "tool_calls": [{"name": "t", "arguments": {}}]})
    assert from_dict.tool_calls[0].name == "t"
    same = AgentResponse("hi")
    assert AgentResponse.from_any(same) is same
    with pytest.raises(TypeError):
        AgentResponse.from_any(42)


def test_unknown_evidence_stays_none_not_empty():
    response = AgentResponse.from_any("hi")
    assert response.tool_calls is None and response.retrieved_documents is None


def test_python_function_agent_with_one_or_two_parameters():
    one = PythonFunctionAgent(lambda q: q.upper())
    assert one.answer("hi").answer_text == "HI"
    assert one.answer("hi").latency_ms is not None
    two = PythonFunctionAgent(lambda q, conversation: f"{len(conversation or [])} turns")
    assert two.answer("hi", [{"role": "user", "content": "x"}]).answer_text == "1 turns"


def test_python_function_agent_from_file_reads_version(team_folder):
    agent = PythonFunctionAgent.from_file(team_folder / "agent.py", "answer")
    assert agent.version == "test-agent-1"
    with pytest.raises(ConfigError):
        PythonFunctionAgent.from_file(team_folder / "agent.py", "no_such_function")


def test_http_agent_post_with_token_from_environment(agent_server, monkeypatch):
    monkeypatch.setenv("TEST_AGENT_TOKEN", "secret-123")
    agent = HttpEndpointAgent(f"{agent_server}/chat", answer_field="data.answer", auth_token_env="TEST_AGENT_TOKEN")
    response = agent.answer("hello", [{"role": "user", "content": "earlier"}])
    assert response.answer_text == "echo: hello | token: Bearer secret-123 | turns: 1"
    assert response.latency_ms >= 0


def test_http_agent_get_and_errors(agent_server, monkeypatch):
    assert HttpEndpointAgent(f"{agent_server}/chat", method="GET").answer("x").answer_text == "get works"
    with pytest.raises(AgentConnectionError):
        HttpEndpointAgent(f"{agent_server}/broken").answer("x")
    with pytest.raises(AgentConnectionError):
        HttpEndpointAgent(f"{agent_server}/chat", answer_field="data.missing").answer("x")
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    with pytest.raises(AgentConnectionError, match="MISSING_TOKEN"):
        HttpEndpointAgent(f"{agent_server}/chat", auth_token_env="MISSING_TOKEN").answer("x")
    with pytest.raises(ConfigError):
        HttpEndpointAgent(f"{agent_server}/chat", method="DELETE")


def test_record_then_replay(tmp_path):
    cases = [GoldenCaseBuilder("A", "Question one?").build(), GoldenCaseBuilder("B", "Question two?").build()]

    def flaky_agent(question):
        if "two" in question:
            raise RuntimeError("model timeout")
        return {"answer_text": "answer one", "retrieved_documents": ["doc"]}

    path = tmp_path / "recorded.jsonl"
    summary = record_responses(PythonFunctionAgent(flaky_agent, version="v7"), cases, path)
    assert summary.written == 1 and "B" in summary.failed      # a failed call is never saved as an answer

    replay = RecordedResponsesAgent(path)
    assert replay.version == "recorded:v7"
    assert replay.answer("  question ONE? ").answer_text == "answer one"   # whitespace and case don't matter
    with pytest.raises(RecordingNotFoundError):
        replay.answer("Question two?")


def test_missing_recording_is_a_setup_error(tmp_path):
    with pytest.raises(ConfigError, match="aiquality record"):
        RecordedResponsesAgent(tmp_path / "nothing.jsonl")


def test_build_agent_rejects_unknown_adapter(tmp_path):
    with pytest.raises(ConfigError):
        build_agent({"adapter": "carrier_pigeon"}, tmp_path)


def test_custom_auth_header_for_apis_that_use_an_api_key_header(monkeypatch):
    monkeypatch.setenv("VENDOR_KEY", "k-1")
    agent = HttpEndpointAgent("http://127.0.0.1:9/chat", auth_token_env="VENDOR_KEY",
                              auth_header="x-api-key", auth_prefix="")
    request = agent._build_request("hi", None)
    assert request.get_header("X-api-key") == "k-1" and request.get_header("Authorization") is None


def test_replay_tells_apart_multi_turn_cases_with_the_same_last_question(tmp_path):
    first = GoldenCaseBuilder("M1", "Yes, please").after_turns(("user", "Change my seat?")).build()
    second = GoldenCaseBuilder("M2", "Yes, please").after_turns(("user", "Cancel my booking?")).build()

    def agent(question, conversation):
        return f"done: {conversation[0]['content']}"

    path = tmp_path / "recorded.jsonl"
    record_responses(PythonFunctionAgent(agent), [first, second], path)
    replay = RecordedResponsesAgent(path)
    assert replay.answer("Yes, please", first.conversation_history).answer_text == "done: Change my seat?"
    assert replay.answer("Yes, please", second.conversation_history).answer_text == "done: Cancel my booking?"


def test_prepare_runs_once_before_any_question(tmp_path):
    agent_file = tmp_path / "agent.py"
    agent_file.write_text("import time\nREADY = []\n"
                          "def prepare():\n    time.sleep(0.2)\n    READY.append(True)\n"
                          "def answer(q):\n    return 'ready' if READY else 'cold'\n")
    agent = PythonFunctionAgent.from_file(agent_file, "answer")
    response = agent.answer("hi")
    assert response.answer_text == "ready" and response.latency_ms < 150   # start-up not counted


def test_failed_prepare_is_a_setup_error(tmp_path):
    agent_file = tmp_path / "agent.py"
    agent_file.write_text("def prepare():\n    raise RuntimeError('ANTHROPIC_API_KEY is not set')\n"
                          "def answer(q):\n    return 'x'\n")
    with pytest.raises(AgentConnectionError, match="API_KEY is not set"):
        PythonFunctionAgent.from_file(agent_file, "answer")
