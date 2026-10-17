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
    assert default.VERSION == "v3"                                     # the default since Run 5
    assert default.AGENT_VERSION.endswith(f":v3-top3:policies-{default.POLICIES_VERSION}")
    assert default.POLICIES_VERSION == "1.3"                           # read from policies.md
    assert default.VERSIONS["v3"]["system_prompt"] == default.PROMPT_V3
    v1 = load_agent_module(monkeypatch, "v1")
    assert ":v1-top2:policies-" in v1.AGENT_VERSION and v1.VERSIONS["v1"]["system_prompt"] is None
    v2 = load_agent_module(monkeypatch, "v2")
    assert ":v2-top3:policies-" in v2.AGENT_VERSION and v2.VERSIONS["v2"]["system_prompt"] == v2.PROMPT_V2
    v4 = load_agent_module(monkeypatch, "v4")
    assert ":v4-top3:policies-" in v4.AGENT_VERSION and v4.VERSIONS["v4"]["policy_limits_tool"] is True
    with pytest.raises(ValueError, match="must be one of: v1, v2, v3, v4"):
        load_agent_module(monkeypatch, "v9")


# Words from golden cases, including the held-out ones (GD37-GD45): a rule that names them was
# written for those cases, and passing them would prove nothing about other passengers.
CASE_SPECIFIC = ["vip", "influencer", "instagram", "social media", "attendant", "mrd1a1", "pnr",
                 "uber", "accident", "politician", "ceo", "parrot", "connecting", "another airline",
                 "hotel", "suitcase", "frequent flyer", "delayed", "wheelchair", "tomorrow", "cabin bag",
                 "check-in", "web check", "no-show", "refund", "kg"]


@pytest.mark.parametrize("prompt_name", ["PROMPT_V2", "PROMPT_V3", "PROMPT_V4"])
def test_prompt_rules_are_general_not_written_for_golden_cases(monkeypatch, prompt_name):
    """A fix tuned to the golden cases would pass them and fail real passengers."""
    module = load_agent_module(monkeypatch, "v3")
    prompt = getattr(module, prompt_name).lower()
    assert [word for word in CASE_SPECIFIC if word in prompt] == []
    assert re.search(r"\bgd\d+", prompt) is None                   # no golden case ids


@pytest.mark.parametrize("rules_name", ["RULES_V3", "RULES_V4"])
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


def test_the_v4_tool_is_the_policy_limits_tool(monkeypatch):
    import policy_limits
    assert policy_limits.TOOL_NAME == "check_policy_limits"         # the name the v4 rules use
