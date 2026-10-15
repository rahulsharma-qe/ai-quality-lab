"""The one contract every agent plugs in through: a question in, an AgentResponse out."""

from abc import ABC, abstractmethod
from typing import Optional, Protocol, runtime_checkable

from aiquality.contracts.agent_response import AgentResponse


class AgentUnderTest(ABC):
    """Any agent the platform tests. Adapters turn real agents into this shape."""

    name: str = "agent"
    version: str = "unversioned"

    @abstractmethod
    def answer(self, question: str, conversation: Optional[list[dict]] = None) -> AgentResponse:
        """Answer one question.

        conversation: earlier turns as [{"role": "user" | "assistant", "content": "..."}],
        oldest first, for multi-turn cases. None for a single question.
        """


@runtime_checkable
class SupportsDocumentInjection(Protocol):
    """Optional capability: lets attack tests plant a document the agent will retrieve.

    Needed for indirect prompt-injection attacks. Agents without it simply get
    NOT_APPLICABLE for those attacks, never a pass.
    """

    def inject_document(self, text: str) -> None: ...

    def clear_injected_documents(self) -> None: ...
