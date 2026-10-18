"""teams/aeroassist/agent.py: its versions, and the guard against fixes tuned to golden cases."""

import importlib.util
import re
from pathlib import Path

import pytest

AGENT_FILE = Path(__file__).resolve().parents[1] / "teams" / "aeroassist" / "agent.py"


def load_agent_module(monkeypatch, version=None):
    if version is None:
        monkeypatch.delenv("AEROASSIST_AGENT_VERSION", raising=False)
    else:
        monkeypatch.setenv("AEROASSIST_AGENT_VERSION", version)
    spec = importlib.util.spec_from_file_location("aeroassist_agent_under_test", AGENT_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_versions_and_default(monkeypatch):
    default = load_agent_module(monkeypatch)
    assert default.VERSION == "v5"                                     # the default since Run 7
    assert default.AGENT_VERSION.endswith(f":v5-top3:limits-2:policies-{default.POLICIES_VERSION}")
    assert default.POLICIES_VERSION == "1.3"                           # read from policies.md
    v3 = load_agent_module(monkeypatch, "v3")
    assert v3.AGENT_VERSION.endswith(":v3-top3:policies-1.3") and v3.VERSIONS["v3"]["system_prompt"] == v3.PROMPT_V3
    v1 = load_agent_module(monkeypatch, "v1")
    assert ":v1-top2:policies-" in v1.AGENT_VERSION and v1.VERSIONS["v1"]["system_prompt"] is None
    v2 = load_agent_module(monkeypatch, "v2")
    assert ":v2-top3:policies-" in v2.AGENT_VERSION and v2.VERSIONS["v2"]["system_prompt"] == v2.PROMPT_V2
    v4 = load_agent_module(monkeypatch, "v4")
    assert ":v4-top3:limits-2:policies-" in v4.AGENT_VERSION and v4.VERSIONS["v4"]["policy_limits_tool"] is True
    v5 = load_agent_module(monkeypatch, "v5")
    assert ":v5-top3:limits-2:policies-" in v5.AGENT_VERSION and v5.VERSIONS["v5"]["understanding_step"] is True
    assert ":limits-" not in v3.AGENT_VERSION                         # a version without the tool doesn't name it
    v6 = load_agent_module(monkeypatch, "v6")
    assert ":v6-top3:limits-2:handover-2:policies-" in v6.AGENT_VERSION and v6.VERSIONS["v6"]["code_steps"] is True
    with pytest.raises(ValueError, match="must be one of: v1, v2, v3, v4, v5, v6"):
        load_agent_module(monkeypatch, "v9")


# Words from golden cases, including the held-out ones (GD37-GD45): a rule that names them was
# written for those cases, and passing them would prove nothing about other passengers.
CASE_SPECIFIC = ["vip", "influencer", "instagram", "social media", "attendant", "mrd1a1", "pnr",
                 "uber", "accident", "politician", "ceo", "parrot", "connecting", "another airline",
                 "hotel", "suitcase", "frequent flyer", "delayed", "wheelchair", "tomorrow", "cabin bag",
                 "check-in", "web check", "no-show", "refund", "kg"]


@pytest.mark.parametrize("prompt_name", ["PROMPT_V2", "PROMPT_V3", "PROMPT_V4", "PROMPT_V5", "PROMPT_V6"])
def test_prompt_rules_are_general_not_written_for_golden_cases(monkeypatch, prompt_name):
    """A fix tuned to the golden cases would pass them and fail real passengers."""
    module = load_agent_module(monkeypatch, "v3")
    prompt = getattr(module, prompt_name).lower()
    assert [word for word in CASE_SPECIFIC if word in prompt] == []
    assert re.search(r"\bgd\d+", prompt) is None                   # no golden case ids


@pytest.mark.parametrize("rules_name", ["RULES_V3", "RULES_V4", "RULES_V5", "RULES_V6"])
def test_rules_name_no_numbers(monkeypatch, rules_name):
    """A rule with a number in it ("4 hours", "15 kg") is a fix for the case that has that number."""
    rules = getattr(load_agent_module(monkeypatch, "v3"), rules_name)
    assert [rule for rule in rules if re.search(r"\d", rule)] == []


def test_v4_changes_only_the_timing_rule_and_the_totals_sentence(monkeypatch):
    """So a difference between v3 and v4 comes from the tool, not from rewording."""
    module = load_agent_module(monkeypatch, "v4")
    changed = [number for number, (old, new) in enumerate(zip(module.RULES_V3, module.RULES_V4), start=1)
               if old != new]
    assert changed == [4, 5] and len(module.RULES_V4) == len(module.RULES_V3)
    assert "check_policy_limits" in module.RULES_V4[3] and "check_policy_limits" in module.RULES_V4[4]
    assert module.RULES_V4[4].startswith(module.RULES_V3[4].split(" Working out")[0])


def test_v5_changes_only_the_timing_rule_of_v4(monkeypatch):
    module = load_agent_module(monkeypatch, "v5")
    changed = [number for number, (old, new) in enumerate(zip(module.RULES_V4, module.RULES_V5), start=1)
               if old != new]
    assert changed == [4] and "never ask the passenger for a figure" in module.RULES_V5[3]


def test_v6_changes_only_the_no_policy_and_hand_over_rules_of_v5(monkeypatch):
    """So a difference between v5 and v6 comes from code writing the hand-over."""
    module = load_agent_module(monkeypatch, "v6")
    changed = [number for number, (old, new) in enumerate(zip(module.RULES_V5, module.RULES_V6), start=1)
               if old != new]
    assert changed == [6, 9] and len(module.RULES_V6) == len(module.RULES_V5)
    assert module.RULES_V6[5].endswith("and hand over.") and "HAND_OVER" in module.RULES_V6[8]


class FakeRAG:
    def answer_with_tool_calls(self, question, conversation=None):
        return "an answer", ["## P5 ..."], [{"name": "check_policy_limits", "arguments": {"topics": ["date_change"]}}]


@pytest.mark.parametrize("version, expected", [("v3", None),
                                               ("v4", [{"name": "check_policy_limits",
                                                        "arguments": {"topics": ["date_change"]}}])])
def test_answer_reports_tool_calls_only_for_a_version_with_tools(monkeypatch, version, expected):
    module = load_agent_module(monkeypatch, version)
    module._agent = FakeRAG()
    reply = module.answer("Can I change my date?")
    assert reply == {"answer_text": "an answer", "retrieved_documents": ["## P5 ..."], "tool_calls": expected}


class HandOverRAG:
    def answer_with_tool_calls(self, question, conversation=None):
        return ("I have no policy for that. A human agent may find options.\nHAND_OVER", [],
                [{"name": "check_policy_limits", "arguments": {"topics": []}}])


def test_v6_finishes_the_hand_over_in_code_and_lists_the_step(monkeypatch):
    module = load_agent_module(monkeypatch, "v6")
    module._agent = HandOverRAG()
    reply = module.answer("Can my parrot fly with me?")
    assert reply["answer_text"] == "I have no policy for that.\n\nA human agent will take over from here."
    assert reply["tool_calls"][-1] == {"name": "hand_over_wording", "arguments": {
        "marker": True, "removed": ["A human agent may find options."]}}
    v5 = load_agent_module(monkeypatch, "v5")
    v5._agent = HandOverRAG()
    assert "HAND_OVER" in v5.answer("Can my parrot fly with me?")["answer_text"]     # v5 is unchanged


def test_the_v4_tool_is_the_policy_limits_tool(monkeypatch):
    import policy_limits
    assert policy_limits.TOOL_NAME == "check_policy_limits"         # the name the v4 rules use


@pytest.mark.parametrize("version, expected_tools, expected_forced", [
    ("v3", None, None), ("v4", ["check_policy_limits"], None), ("v5", ["check_policy_limits"], "check_policy_limits"),
    ("v6", ["check_policy_limits"], "check_policy_limits")])
def test_each_version_builds_its_agent_with_the_right_tools(monkeypatch, version, expected_tools, expected_forced):
    """Without a key or a download: the agent's parts are replaced, and what it is built with is recorded."""
    import sys
    import types
    built = {}

    class CapturingRAG:
        def __init__(self, *args, **options):
            built.update(options)

    monkeypatch.setitem(sys.modules, "aeroassist_rag", types.SimpleNamespace(
        DEFAULT_SYSTEM_PROMPT="default", AeroAssistRAG=CapturingRAG, make_embedder=lambda: None))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=lambda api_key: None))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    module = load_agent_module(monkeypatch, version)
    module.prepare()
    assert [tool["name"] for tool in built.get("tools") or []] == (expected_tools or [])
    assert built.get("force_first_tool") == expected_forced
    assert (built.get("check_tool_arguments") is not None) == (version == "v6")      # stated facts only, from v6
