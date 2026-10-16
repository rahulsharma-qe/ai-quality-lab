"""AeroAssist's policy-retrieval agent: the system under test, and its own code.

One policy = one chunk. Retrieval is in-memory cosine similarity over a local embedding model
(eight policies don't need a vector database); generation answers only from the retrieved
policies, or hands over to a person. teams/aeroassist/agent.py wraps it for the platform, and the
studies in demos/ (RAG evaluation, red-teaming, the judge's label set) test this same class.

Moved here unchanged from demos/rag_eval.py, so the team folder holds everything its agent needs.
Needs: numpy, and for make_embedder() the 'aeroassist' extra (langchain-huggingface).
"""

import re

import numpy as np

MODEL = "claude-haiku-4-5"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def make_embedder():
    """The local embedding model, used BOTH for RAG retrieval and RAGAS scoring."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


DEFAULT_SYSTEM_PROMPT = (
    "You are AeroAssist, Meridian Airways support. Answer ONLY from the policy "
    "context provided. If the answer isn't in the context, say you don't have that "
    "information and offer to escalate to a human. Be concise; never invent policy."
)
RETRIEVAL_TURNS = 2   # earlier passenger turns that also steer retrieval, so a follow-up finds its policy


class AeroAssistRAG:
    """A minimal policy-RAG: the system we are evaluating.

    One policy = one chunk. Retrieval is in-memory cosine similarity (eight
    policies don't justify a vector database). Generation is instructed to
    answer ONLY from the retrieved context, or abstain and escalate.

    Optional settings (the defaults keep the original behaviour):
      system_prompt  the instructions the model answers under
      temperature    None leaves the model's default; 0 makes repeated runs comparable
    """

    def __init__(self, policies_path, embedder, gen_client, model=MODEL, top_n=2,
                 system_prompt=DEFAULT_SYSTEM_PROMPT, temperature=None):
        self.embedder = embedder          # raw langchain embeddings (embed_documents/embed_query)
        self.gen_client = gen_client      # raw Anthropic client (the SUT's generator)
        self.model = model
        self.top_n = top_n
        self.system_prompt = system_prompt
        self.temperature = temperature
        self._send_temperature = temperature is not None
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

    def answer(self, query, conversation=None):
        """Retrieve context, then generate an answer grounded only in that context.

        conversation: optional earlier turns [{"role": "user" | "assistant", "content": ...}], oldest
        first. They are sent to the model as the conversation so far, and the passenger's last few
        turns also steer retrieval. Without it, behaviour is exactly the single-question original.
        """
        contexts = self.retrieve(self._retrieval_query(query, conversation))
        user = "Policy context:\n" + "\n\n".join(contexts) + f"\n\nPassenger: {query}"
        messages = _alternating_turns(list(conversation or []) + [{"role": "user", "content": user}])
        return self._generate(messages), contexts

    @staticmethod
    def _retrieval_query(query, conversation):
        earlier = [t["content"] for t in (conversation or []) if t.get("role") == "user"][-RETRIEVAL_TURNS:]
        return " ".join(earlier + [query])

    def _generate(self, messages):
        params = dict(model=self.model, max_tokens=500, system=self.system_prompt, messages=messages)
        if self._send_temperature:
            try:
                return _reply_text(self.gen_client.messages.create(**params, temperature=self.temperature))
            except TypeError as error:
                # Some SDK versions no longer accept a temperature setting; the error comes before
                # any request is sent, so retrying without it costs nothing.
                if "temperature" not in str(error):
                    raise
                self._send_temperature = False
        return _reply_text(self.gen_client.messages.create(**params))


def _alternating_turns(turns):
    """Merge back-to-back turns from the same role: the model API expects user and assistant to alternate."""
    merged = []
    for turn in turns:
        if merged and merged[-1]["role"] == turn["role"]:
            merged[-1] = {"role": turn["role"], "content": merged[-1]["content"] + "\n\n" + turn["content"]}
        else:
            merged.append({"role": turn["role"], "content": turn["content"]})
    return merged


def _reply_text(resp):
    """Join the text blocks of a reply; a newer model may put a 'thinking' block first."""
    return "".join(b.text for b in resp.content if getattr(b, "type", "text") == "text")
