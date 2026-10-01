"""
AeroAssist — RAG Evaluation with RAGAS
=================================================
Evaluates a small policy-RAG (the "system under test") against the human-verified
golden dataset, using RAGAS' four metrics with Claude as the judge and a local
embedding model (no OpenAI dependency).

Flow:  policies.md -> chunk & embed -> retrieve -> grounded answer
       -> run golden cases -> score with RAGAS -> read per-case metrics

Requires (in the environment / Colab):
  - ANTHROPIC_API_KEY   (Colab secret or env var)
  - policies.md         (the 8 Meridian policies, P1-P8)
  - golden_dataset.json (human-verified eval cases)

Metrics (RAGAS):
  retrieval  -> context_precision (relevant chunks ranked first?),
                context_recall    (did we fetch everything the reference needed?)
  generation -> faithfulness      (answer sticks to retrieved context?),
                answer_relevancy  (answer addresses the question?)
"""

import os
import re
import json
import sys
import types
import numpy as np

MODEL = "claude-haiku-4-5"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ======================================================================
# SECTION A — Setup: judge (Claude), embeddings (local), RAGAS wiring
# ======================================================================
def _apply_ragas_import_shim():
    """RAGAS imports a langchain module that newer versions removed; inject a
    harmless stub so the import succeeds. We never use Vertex — judge is Claude."""
    stub = types.ModuleType("langchain_community.chat_models.vertexai")
    stub.ChatVertexAI = type("ChatVertexAI", (), {})
    sys.modules["langchain_community.chat_models.vertexai"] = stub
    import langchain_community.llms as community_llms
    if not hasattr(community_llms, "VertexAI"):
        community_llms.VertexAI = type("VertexAI", (), {})


def make_embedder():
    """The local embedding model, used BOTH for RAG retrieval and RAGAS scoring."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def build_judge_and_metrics(embedder, model=MODEL):
    """Return the RAGAS judge LLM, the RAGAS-wrapped embedder, and the 4 metrics.
    Judge temperature is 0 so grading is consistent run-to-run."""
    _apply_ragas_import_shim()
    from langchain_anthropic import ChatAnthropic
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        faithfulness, answer_relevancy, context_precision, context_recall,
    )

    judge = LangchainLLMWrapper(ChatAnthropic(model=model, temperature=0))
    ragas_embedder = LangchainEmbeddingsWrapper(embedder)
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    return judge, ragas_embedder, metrics


# ======================================================================
# SECTION B — The RAG under test (chunk -> embed -> retrieve -> answer)
# ======================================================================
class AeroAssistRAG:
    """A minimal policy-RAG: the system we are evaluating.

    One policy = one chunk. Retrieval is in-memory cosine similarity (eight
    policies don't justify a vector database). Generation is instructed to
    answer ONLY from the retrieved context, or abstain and escalate.
    """

    def __init__(self, policies_path, embedder, gen_client, model=MODEL, top_n=2):
        self.embedder = embedder          # raw langchain embeddings (embed_documents/embed_query)
        self.gen_client = gen_client      # raw Anthropic client (the SUT's generator)
        self.model = model
        self.top_n = top_n
        self.chunks = self._load_and_chunk(policies_path)
        self.chunk_vectors = np.array(self.embedder.embed_documents(self.chunks))

    @staticmethod
    def _load_and_chunk(path):
        """Split policies.md into one chunk per policy section (## P1 .. ## P8)."""
        text = open(path).read()
        sections = re.split(r"\n(?=## )", text)
        return [s.strip() for s in sections if s.strip().startswith("## P")]

    def retrieve(self, query):
        """Return the top_n most semantically similar policy chunks."""
        q = np.array(self.embedder.embed_query(query))
        q = q / (np.linalg.norm(q) + 1e-9)
        mat = self.chunk_vectors / (np.linalg.norm(self.chunk_vectors, axis=1, keepdims=True) + 1e-9)
        scores = mat @ q
        top_idx = np.argsort(scores)[::-1][: self.top_n]
        return [self.chunks[i] for i in top_idx]

    def answer(self, query):
        """Retrieve context, then generate an answer grounded only in that context."""
        contexts = self.retrieve(query)
        system = (
            "You are AeroAssist, Meridian Airways support. Answer ONLY from the policy "
            "context provided. If the answer isn't in the context, say you don't have that "
            "information and offer to escalate to a human. Be concise; never invent policy."
        )
        user = "Policy context:\n" + "\n\n".join(contexts) + f"\n\nPassenger: {query}"
        resp = self.gen_client.messages.create(
            model=self.model, max_tokens=500, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text, contexts


# ======================================================================
# SECTION C — Build the eval dataset (run golden cases through the RAG)
# ======================================================================
def build_eval_dataset(rag, golden_path, case_ids):
    """For each selected golden case, run the RAG and collect the four fields
    RAGAS expects: user_input, retrieved_contexts, response, reference."""
    from ragas import EvaluationDataset

    cases = {c["id"]: c for c in json.load(open(golden_path))["cases"]}
    rows = []
    for cid in case_ids:
        case = cases[cid]
        response, contexts = rag.answer(case["input"])
        rows.append({
            "user_input": case["input"],
            "retrieved_contexts": contexts,
            "response": response,
            "reference": case["reference_answer"],   # human-verified ground truth
        })
        print(f"  [{cid}] {case['category']:12s} -> answered ({len(contexts)} chunks)")
    return EvaluationDataset.from_list(rows)


# ======================================================================
# SECTION D — Run RAGAS and show per-case + aggregate scores
# ======================================================================
def run_evaluation(eval_dataset, metrics, judge, ragas_embedder):
    """Score every case on every metric. Returns a pandas DataFrame."""
    from ragas import evaluate

    result = evaluate(dataset=eval_dataset, metrics=metrics, llm=judge, embeddings=ragas_embedder)
    print("\n=== AGGREGATE ===")
    print(result)
    return result.to_pandas()


# ======================================================================
# MAIN — wire it together (small subset first; scale in the full harness)
# ======================================================================
def main():
    from anthropic import Anthropic
    try:
        from google.colab import userdata
        api_key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ["ANTHROPIC_API_KEY"]

    # ChatAnthropic (the RAGAS judge) reads the key from the environment,
    # so set it here before building the judge.
    os.environ["ANTHROPIC_API_KEY"] = api_key

    print("A) setup: embedder + judge + metrics ...")
    embedder = make_embedder()                                   # one embedder, shared
    judge, ragas_embedder, metrics = build_judge_and_metrics(embedder)

    print("B) building the RAG under test ...")
    gen_client = Anthropic(api_key=api_key)
    rag = AeroAssistRAG("policies.md", embedder, gen_client, top_n=2)
    print(f"   {len(rag.chunks)} policy chunks loaded")

    print("C) building eval dataset from a golden subset ...")
    subset = ["GD01", "GD02", "GD05", "GD09", "GD04"]   # happy, edge, happy, happy, out-of-scope
    eval_dataset = build_eval_dataset(rag, "golden_dataset.json", subset)

    print("D) running RAGAS (this makes many judge calls; takes a minute) ...")
    df = run_evaluation(eval_dataset, metrics, judge, ragas_embedder)
    return df


if __name__ == "__main__":
    df = main()
    print("\n=== PER-CASE ===")
    print(df.to_string())
