"""AeroAssistRAG's optional settings, tested with a fake embedding model and a fake model client.

No API key and no download: the fake embedder counts words, the fake client records each call.
"""

import re
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")
from aeroassist_rag import DEFAULT_SYSTEM_PROMPT, TOOL_LIMIT_REPLY, AeroAssistRAG  # noqa: E402

POLICIES = """# Policies
## P1 — Refund
- full refund within 24 hours of booking
## P2 — Baggage
- one cabin bag up to 7 kg
## P3 — Change
- date change allowed up to 4 hours before departure
"""
VOCABULARY = ["refund", "booking", "bag", "baggage", "kg", "change", "departure", "hours"]


class WordCountEmbedder:
    """One dimension per vocabulary word: enough for retrieval to pick the obvious policy."""

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        words = re.findall(r"[a-z]+", text.lower())
        return [float(words.count(word)) + 0.01 for word in VOCABULARY]


class RecordingClient:
    def __init__(self, reject_temperature=False):
        self.calls = []
        self.reject_temperature = reject_temperature
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **params):
        if self.reject_temperature and "temperature" in params:
            raise TypeError("create() got an unexpected keyword argument 'temperature'")
        self.calls.append(params)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", text="..."),
                                        SimpleNamespace(type="text", text="an answer")])


def make_rag(tmp_path, client, **options):
    policies = tmp_path / "policies.md"
    policies.write_text(POLICIES)
    return AeroAssistRAG(policies, WordCountEmbedder(), client, model="test-model", **options)


def test_defaults_keep_the_original_behaviour(tmp_path):
    client = RecordingClient()
    text, contexts = make_rag(tmp_path, client, top_n=1).answer("How many kg can my cabin bag weigh?")
    call = client.calls[0]
    assert text == "an answer"                                       # the thinking block is skipped
    assert contexts[0].startswith("## P2") and len(contexts) == 1
    assert call["system"] == DEFAULT_SYSTEM_PROMPT and "temperature" not in call
    assert len(call["messages"]) == 1 and call["messages"][0]["content"].endswith("Passenger: How many kg "
                                                                                  "can my cabin bag weigh?")


def test_prompt_temperature_and_top_n_are_settings(tmp_path):
    client = RecordingClient()
    _, contexts = make_rag(tmp_path, client, top_n=3, system_prompt="Rules.", temperature=0).answer("refund?")
    assert len(contexts) == 3
    assert client.calls[0]["system"] == "Rules." and client.calls[0]["temperature"] == 0


def test_an_sdk_without_temperature_still_answers(tmp_path):
    client = RecordingClient(reject_temperature=True)
    rag = make_rag(tmp_path, client, temperature=0)
    assert rag.answer("refund?")[0] == "an answer" and rag.answer("bag?")[0] == "an answer"
    assert len(client.calls) == 2 and "temperature" not in client.calls[1]


def test_earlier_turns_are_sent_and_steer_retrieval(tmp_path):
    client = RecordingClient()
    conversation = [{"role": "user", "content": "I need a refund for my booking."},
                    {"role": "assistant", "content": "Happy to help."}]
    _, contexts = make_rag(tmp_path, client, top_n=1).answer("And how long does it take?", conversation)
    assert contexts[0].startswith("## P1")                           # the follow-up alone names no policy
    roles = [m["role"] for m in client.calls[0]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_back_to_back_turns_from_one_role_are_merged(tmp_path):
    client = RecordingClient()
    make_rag(tmp_path, client).answer("Still there?", [{"role": "user", "content": "Hello?"}])
    messages = client.calls[0]["messages"]
    assert len(messages) == 1 and messages[0]["content"].startswith("Hello?")


# --- Optional tools: the model asks, code runs the tool, the model answers with the result ---------

class ScriptedToolClient:
    """Replies from a script: each item is either ("tool", name, arguments) or ("text", answer)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **params):
        self.calls.append({**params, "messages": list(params["messages"])})
        kind, *rest = self.script.pop(0)
        if kind == "tool":
            name, arguments = rest
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="Let me check."),
                                            SimpleNamespace(type="tool_use", id=f"call-{len(self.calls)}",
                                                            name=name, input=arguments)])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=rest[0])])


LIMITS_TOOL = {"name": "check_limits", "description": "test tool", "input_schema": {"type": "object"}}


def test_without_tools_no_tool_definitions_are_sent(tmp_path):
    client = RecordingClient()
    text, contexts, tool_calls = make_rag(tmp_path, client).answer_with_tool_calls("refund?")
    assert text == "an answer" and tool_calls == [] and "tools" not in client.calls[0]


def test_a_tool_call_is_run_and_its_result_goes_back_to_the_model(tmp_path):
    client = ScriptedToolClient([("tool", "check_limits", {"hours": 6}), ("text", "Yes, you can change it.")])
    ran = []
    rag = make_rag(tmp_path, client, tools=[LIMITS_TOOL],
                   run_tool=lambda name, arguments: ran.append((name, arguments)) or {"outcome": "allowed"})
    text, _, tool_calls = rag.answer_with_tool_calls("Can I change my flight in 6 hours?")
    assert text == "Yes, you can change it."
    assert tool_calls == [{"name": "check_limits", "arguments": {"hours": 6}}] and ran == [("check_limits", {"hours": 6})]
    second = client.calls[1]
    assert second["tools"] == [LIMITS_TOOL]
    assert [m["role"] for m in second["messages"]] == ["user", "assistant", "user"]
    result = second["messages"][2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "call-1" and '"allowed"' in result["content"]


def test_a_failing_tool_is_reported_to_the_model_not_raised(tmp_path):
    client = ScriptedToolClient([("tool", "check_limits", {}), ("text", "A human agent will take over.")])

    def broken(name, arguments):
        raise KeyError("hours")

    rag = make_rag(tmp_path, client, tools=[LIMITS_TOOL], run_tool=broken)
    assert rag.answer("Can I change it?")[0] == "A human agent will take over."
    assert "KeyError" in client.calls[1]["messages"][2]["content"][0]["content"]


def test_too_many_tool_rounds_end_in_a_plain_hand_over(tmp_path):
    client = ScriptedToolClient([("tool", "check_limits", {"round": n}) for n in range(3)])
    rag = make_rag(tmp_path, client, tools=[LIMITS_TOOL], run_tool=lambda name, arguments: {}, max_tool_rounds=2)
    text, _, tool_calls = rag.answer_with_tool_calls("Can I change it?")
    assert text == TOOL_LIMIT_REPLY and len(tool_calls) == 2 and len(client.calls) == 3


def test_tools_without_a_runner_are_refused(tmp_path):
    with pytest.raises(ValueError, match="run_tool"):
        make_rag(tmp_path, RecordingClient(), tools=[LIMITS_TOOL])
