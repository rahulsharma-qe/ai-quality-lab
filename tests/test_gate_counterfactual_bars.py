"""A counterfactual case counts once in the priority and category bars: it passes only if every identity passes."""

from types import SimpleNamespace

from aiquality.gate.release_gate import count_cases_once


def outcome(case_id):
    return SimpleNamespace(case_id=case_id)


CASES = [outcome("GD01"), outcome("GD61~name=Satyam Dixit"), outcome("GD61~name=Kushal Kumar"),
         outcome("GD62~name=Satyam Dixit"), outcome("GD62~name=Kushal Kumar")]


def test_each_counterfactual_case_counts_once():
    total, failing = count_cases_once(CASES, failed=lambda o: False)
    assert total == 3 and failing == []


def test_a_counterfactual_case_fails_if_any_identity_fails_and_is_named_once_with_the_identity():
    total, failing = count_cases_once(CASES, failed=lambda o: o.case_id in ("GD61~name=Kushal Kumar", "GD01"))
    assert total == 3 and failing == ["GD01", "GD61 (name=Kushal Kumar)"]


def test_every_failing_identity_is_named():
    total, failing = count_cases_once(CASES, failed=lambda o: o.case_id.startswith("GD62"))
    assert failing == ["GD62 (name=Satyam Dixit, name=Kushal Kumar)"]
