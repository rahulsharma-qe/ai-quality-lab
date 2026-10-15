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
    assert v2.VERSION == "v2" and v2.AGENT_VERSION.endswith(":v2-top3")
    v1 = load_agent_module(monkeypatch, "v1")
    assert v1.AGENT_VERSION.endswith(":v1-top2") and v1.VERSIONS["v1"]["system_prompt"] is None
    with pytest.raises(ValueError, match="must be one of: v1, v2"):
        load_agent_module(monkeypatch, "v9")


def test_prompt_rules_are_general_not_written_for_golden_cases(monkeypatch):
    """A fix tuned to the golden cases would pass them and fail real passengers."""
    prompt = load_agent_module(monkeypatch).PROMPT_V2.lower()
    case_specific = ["vip", "influencer", "instagram", "social media", "attendant", "mrd1a1", "pnr"]
    assert [word for word in case_specific if word in prompt] == []
    assert re.search(r"\bgd\d+", prompt) is None                   # no golden case ids
