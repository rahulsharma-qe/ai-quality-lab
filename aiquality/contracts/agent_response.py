"""What an agent gives back for one question."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """One tool the agent called, with the arguments it used."""

    name: str
    arguments: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCall":
        return cls(name=data["name"], arguments=data.get("arguments", {}))


@dataclass
class AgentResponse:
    """The agent's answer plus whatever evidence the adapter can see.

    Optional fields stay None when an adapter cannot observe them. None means
    "unknown", which is different from an empty list ("the agent called no tools").
    Checks that need a field the adapter can't provide report NOT_APPLICABLE.
    """

    answer_text: str
    tool_calls: Optional[list[ToolCall]] = None
    retrieved_documents: Optional[list[str]] = None
    latency_ms: Optional[float] = None
    cost: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "answer_text": self.answer_text,
            "tool_calls": None if self.tool_calls is None else [t.to_dict() for t in self.tool_calls],
            "retrieved_documents": self.retrieved_documents,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentResponse":
        tool_calls = data.get("tool_calls")
        return cls(
            answer_text=data.get("answer_text", ""),
            tool_calls=None if tool_calls is None else [ToolCall.from_dict(t) for t in tool_calls],
            retrieved_documents=data.get("retrieved_documents"),
            latency_ms=data.get("latency_ms"),
            cost=data.get("cost"),
        )

    @classmethod
    def from_any(cls, value: Any) -> "AgentResponse":
        """Accept what a plain function is likely to return: text, a dict or an AgentResponse."""
        if isinstance(value, AgentResponse):
            return value
        if isinstance(value, str):
            return cls(answer_text=value)
        if isinstance(value, dict):
            return cls.from_dict(value)
        raise TypeError(
            "An agent must return text, a dict with 'answer_text', or an AgentResponse; "
            f"got {type(value).__name__}."
        )
