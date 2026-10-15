"""Example 09: add your own check without touching the platform.

Write one class with @register_check. In a team folder, put it in a .py file and list that
file under 'plugins:' in the config; then use the check's name under 'checks:'.
Run:  python examples/09_add_your_own_check.py
"""

import tempfile
from pathlib import Path

from aiquality import Check, TeamConfig, evaluate_team, register_check


@register_check("offers_human_handover")
class OffersHumanHandover(Check):
    """Out-of-scope and adversarial questions must end with a hand-over to a person."""

    description = "Out-of-scope and adversarial answers offer a human agent."

    def evaluate(self, case, response):
        if case.category not in ("out_of_scope", "adversarial"):
            return self.not_applicable(case, "only judged for out-of-scope and adversarial cases")
        if "human" in response.answer_text.lower():
            return self.passed(case, "offers a human agent")
        return self.failed(case, "no hand-over to a person")


config = TeamConfig.from_dict({
    "team": "custom_check_demo",
    "agent": {"adapter": "python_function", "file": "sample_store_agent.py", "function": "answer"},
    "golden_set": "data/sample_golden_set.json",
    "checks": {"forbidden_phrases": {"threshold": 1.0}, "offers_human_handover": {"threshold": 1.0}},
}, folder=Path(__file__).parent)

evaluate_team(config, output_dir=Path(tempfile.mkdtemp()))
