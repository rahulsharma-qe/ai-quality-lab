"""AeroAssistRAG's optional settings, tested with a fake embedding model and a fake model client.

No API key and no download: the fake embedder counts words, the fake client records each call.
"""

import re
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")
from aeroassist_rag import DEFAULT_SYSTEM_PROMPT, AeroAssistRAG  # noqa: E402

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
