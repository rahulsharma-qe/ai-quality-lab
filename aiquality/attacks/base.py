"""What every attack family has in common, and the registry teams extend.

An attack family turns a team's attack goals into attack cases (ordinary golden cases
with category "attack"), so the same runner and the same safety checks judge them.

    @register_attack("urgency_pressure")
    class UrgencyPressure(Attack):
        description = "Claims an emergency to rush the agent past its rules."
        def build_cases(self, goal):
            return [self.make_case(goal, f"This is an emergency, there is no time: {goal.ask}.")]
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from aiquality.test_data import GoldenCase

ATTACK_CATEGORY = "attack"


@dataclass
class AttackGoal:
    """Something the agent must never be talked into, and the phrases that would prove it was."""

    id: str
    ask: str                                   # written as an instruction: "approve a full refund for ..."
    must_not_include: list[str] = field(default_factory=list)


class Attack(ABC):
    name: str = "unnamed-attack"               # set by @register_attack
    description: str = ""
    per_goal: bool = True                      # False: the family builds its own cases, once per team

    @abstractmethod
    def build_cases(self, goal: Optional[AttackGoal]) -> list[GoldenCase]:
        """Return the attack cases for one goal (or for the team, when per_goal is False)."""

    def make_case(self, goal: Optional[AttackGoal], question: str, variant: str = "",
                  conversation: Optional[list[dict]] = None,
                  must_not_include: Optional[list[str]] = None) -> GoldenCase:
        goal_part = f"-{goal.id}" if goal else ""
        variant_part = f"-{variant}" if variant else ""
        return GoldenCase.from_dict({
            "id": f"ATK-{self.name}{goal_part}{variant_part}",
            "input": question,
            "category": ATTACK_CATEGORY,
            "priority": "high",
            "must_not_include": list(goal.must_not_include if goal else must_not_include or []),
            "conversation_history": conversation or [],
            "attack_family": self.name,
            "attack_goal": goal.id if goal else None,
        })


_ATTACKS: dict[str, type] = {}


def register_attack(name: str):
    def decorator(attack_class: type) -> type:
        if not issubclass(attack_class, Attack):
            raise TypeError(f"{attack_class.__name__} must inherit from Attack")
        existing = _ATTACKS.get(name)
        same = existing is not None and existing.__qualname__ == attack_class.__qualname__ \
            and existing.__module__ == attack_class.__module__
        if existing is not None and existing is not attack_class and not same:
            raise ValueError(f"an attack family named '{name}' is already registered")
        attack_class.name = name
        _ATTACKS[name] = attack_class
        return attack_class
    return decorator


def create_attack(name: str) -> Attack:
    if name not in _ATTACKS:
        raise KeyError(f"unknown attack family '{name}'. Available: {', '.join(available_attacks())}")
    return _ATTACKS[name]()


def available_attacks() -> list[str]:
    return sorted(_ATTACKS)


def describe_attacks() -> dict[str, str]:
    return {name: _ATTACKS[name].description for name in available_attacks()}
