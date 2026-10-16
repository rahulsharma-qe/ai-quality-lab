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
import json
import sys
import types

# AeroAssist's agent lives with its team; the evaluation below tests it.
import paths  # noqa: F401  (puts teams/aeroassist on the import path)
from paths import GOLDEN_SET, POLICIES
from aeroassist_rag import (DEFAULT_SYSTEM_PROMPT, EMBED_MODEL, MODEL, RETRIEVAL_TURNS,  # noqa: F401
                            AeroAssistRAG, make_embedder)


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
# SECTION B — The RAG under test: AeroAssistRAG, in teams/aeroassist/aeroassist_rag.py
# ======================================================================


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
    rag = AeroAssistRAG(POLICIES, embedder, gen_client, top_n=2)
    print(f"   {len(rag.chunks)} policy chunks loaded")

    print("C) building eval dataset from a golden subset ...")
    subset = ["GD01", "GD02", "GD05", "GD09", "GD04"]   # happy, edge, happy, happy, out-of-scope
    eval_dataset = build_eval_dataset(rag, GOLDEN_SET, subset)

    print("D) running RAGAS (this makes many judge calls; takes a minute) ...")
    df = run_evaluation(eval_dataset, metrics, judge, ragas_embedder)
    return df


if __name__ == "__main__":
    df = main()
    print("\n=== PER-CASE ===")
    print(df.to_string())
