"""Attack tests: families registered by name turn a team's goals into attack cases."""

from typing import Optional

from aiquality.attacks.base import (ATTACK_CATEGORY, Attack, AttackGoal, available_attacks, create_attack,
                                    describe_attacks, register_attack)
from aiquality.attacks import families  # noqa: F401  (registers the built-in families)
from aiquality.attacks.summary import AttackSummary, FamilyResult, summarise_attacks


def build_attack_cases(family_names: list[str], goals: list[AttackGoal]) -> list:
    """Every family x every goal (or once per team for families that don't use goals)."""
    cases = []
    for name in family_names:
        attack = create_attack(name)
        targets: list[Optional[AttackGoal]] = list(goals) if attack.per_goal else [None]
        for goal in targets:
            cases.extend(attack.build_cases(goal))
    return cases


__all__ = ["ATTACK_CATEGORY", "Attack", "AttackGoal", "AttackSummary", "FamilyResult", "available_attacks",
           "build_attack_cases", "create_attack", "describe_attacks", "register_attack", "summarise_attacks"]
