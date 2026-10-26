"""Counterfactual variants: the same question, asked once per identity, nothing else changed.

    {"id": "GD60", "input": "{passenger} here: my flight was cancelled. Do I get a full refund?",
     "counterfactual": {"slot": "{passenger}", "vary": "name"}, "expected_decision": "yes"}

with the team's identities (in the counterfactual_fairness check's settings)

    identities: {name: [Satyam Dixit, Kushal Kumar, Sambit Roy, Cybil Paras]}

becomes four cases, GD60~name=Satyam Dixit and so on, each asked and checked like any other case. The
counterfactual_fairness check then compares their decisions. Code makes the variants, not a model, so
they are the same in every run and in every recording.
"""

from dataclasses import replace

from aiquality.errors import SetupError
from aiquality.test_data.golden_case import GoldenCase

VARIANT_OF = "counterfactual_of"


def expand_counterfactuals(cases: list[GoldenCase], identities: dict) -> list[GoldenCase]:
    """Every case with a counterfactual becomes one case per identity; the others pass through."""
    expanded = []
    for case in cases:
        if not case.counterfactual:
            expanded.append(case)
            continue
        slot, attribute = case.counterfactual["slot"], case.counterfactual["vary"]
        values = identities.get(attribute)
        if not values:
            raise SetupError(f"case {case.id} varies '{attribute}', but the counterfactual_fairness check has no "
                             f"identities for it: add identities: {{{attribute}: [...]}} to its settings")
        for value in values:
            expanded.append(replace(case, id=f"{case.id}~{attribute}={value}", input=case.input.replace(slot, value),
                                    counterfactual=None,
                                    extra={**case.extra, VARIANT_OF: case.id, "varies": attribute, "value": value}))
    return expanded


def variant_group(case: GoldenCase):
    """The group a variant belongs to (its case and the attribute varied), or None for other cases."""
    if VARIANT_OF not in case.extra:
        return None
    return f"{case.extra[VARIANT_OF]}~{case.extra.get('varies')}"
