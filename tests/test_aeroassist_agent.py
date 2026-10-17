"""teams/aeroassist/agent.py: its two versions, and the guard against fixes tuned to golden cases."""

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
    v2 = load_agent_module(monkeypatch)
    assert v2.VERSION == "v2" and v2.AGENT_VERSION.endswith(f":v2-top3:policies-{v2.POLICIES_VERSION}")
    assert v2.POLICIES_VERSION == "1.3"                                # read from policies.md
    v1 = load_agent_module(monkeypatch, "v1")
    assert ":v1-top2:policies-" in v1.AGENT_VERSION and v1.VERSIONS["v1"]["system_prompt"] is None
    v3 = load_agent_module(monkeypatch, "v3")
    assert ":v3-top3:policies-" in v3.AGENT_VERSION and v3.VERSIONS["v3"]["system_prompt"] == v3.PROMPT_V3
    assert v3.PROMPT_V2 == load_agent_module(monkeypatch).PROMPT_V2          # v2 is unchanged
    with pytest.raises(ValueError, match="must be one of: v1, v2, v3"):
        load_agent_module(monkeypatch, "v9")


# Words from golden cases, including the held-out ones (GD37-GD45): a rule that names them was
# written for those cases, and passing them would prove nothing about other passengers.
CASE_SPECIFIC = ["vip", "influencer", "instagram", "social media", "attendant", "mrd1a1", "pnr",
                 "uber", "accident", "politician", "ceo", "parrot", "connecting", "another airline",
                 "hotel", "suitcase", "frequent flyer", "delayed", "wheelchair", "tomorrow", "cabin bag",
                 "check-in", "web check", "no-show", "refund", "kg"]


@pytest.mark.parametrize("prompt_name", ["PROMPT_V2", "PROMPT_V3"])
def test_prompt_rules_are_general_not_written_for_golden_cases(monkeypatch, prompt_name):
    """A fix tuned to the golden cases would pass them and fail real passengers."""
    module = load_agent_module(monkeypatch, "v3")
    prompt = getattr(module, prompt_name).lower()
    assert [word for word in CASE_SPECIFIC if word in prompt] == []
    assert re.search(r"\bgd\d+", prompt) is None                   # no golden case ids


def test_v3_rules_name_no_numbers(monkeypatch):
    """A rule with a number in it ("4 hours", "15 kg") is a fix for the case that has that number."""
    rules = load_agent_module(monkeypatch, "v3").RULES_V3
    assert [rule for rule in rules if re.search(r"\d", rule)] == []
