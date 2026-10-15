"""AeroAssist's live agent, in the shape the platform expects: answer(question) -> dict.

It wraps the policy-retrieval agent (AeroAssistRAG in rag_eval.py) with the same settings
used to build the judge-validation answers: the agent model from llm.py, top 2 policies.
Needs:  pip install "aiquality[aeroassist]"  and ANTHROPIC_API_KEY (Colab secret or environment).
Importing this file costs nothing; the platform calls prepare() once before the first
question, so loading the embedding model isn't counted in the first answer's time.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm import AGENT_MODEL  # noqa: E402  (light import: model name only)

AGENT_VERSION = f"aeroassist-rag:{AGENT_MODEL}:top2"
POLICIES_PATH = REPO_ROOT / "policies.md"

_agent = None


def prepare() -> None:
    """Build the agent (model client + embeddings) before timing starts."""
    _get_agent()


def answer(question: str) -> dict:
    """Answer one passenger question; also return the policies the agent retrieved."""
    answer_text, retrieved_policies = _get_agent().answer(question)
    return {"answer_text": answer_text, "retrieved_documents": retrieved_policies}


def _get_agent():
    global _agent
    if _agent is None:
        from anthropic import Anthropic
        from llm import get_api_key
        from rag_eval import AeroAssistRAG, make_embedder

        client = Anthropic(api_key=get_api_key())
        _agent = AeroAssistRAG(POLICIES_PATH, make_embedder(), client, model=AGENT_MODEL, top_n=2)
    return _agent
