"""AeroAssist's policy-retrieval agent: the system under test, and its own code.

One policy = one chunk. Retrieval is in-memory cosine similarity over a local embedding model
(eight policies don't need a vector database); generation answers only from the retrieved
policies, or hands over to a person. teams/aeroassist/agent.py wraps it for the platform, and the
studies in demos/ (RAG evaluation, red-teaming, the judge's label set) test this same class.

Moved here from demos/rag_eval.py, so the team folder holds everything its agent needs. It can
also let the model call tools (off by default, so the studies in demos/ behave as before).
Needs: numpy, and for make_embedder() the 'aeroassist' extra (langchain-huggingface).
"""

import json
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
# Said when the model keeps calling tools past the limit: a plain hand-over, never a guess.
TOOL_LIMIT_REPLY = "I can't work this out reliably here. A human agent will take over."


class AeroAssistRAG:
    """A minimal policy-RAG: the system we are evaluating.

    One policy = one chunk. Retrieval is in-memory cosine similarity (eight
    policies don't justify a vector database). Generation is instructed to
    answer ONLY from the retrieved context, or abstain and escalate.

    Optional settings (the defaults keep the original behaviour):
      system_prompt  the instructions the model answers under
      temperature    None leaves the model's default; 0 makes repeated runs comparable
      tools          tool definitions the model may call (None: no tools, the original behaviour)
      run_tool       run_tool(name, arguments) -> result, called for each tool the model asks for
      max_tool_rounds  how many rounds of tool calls before a plain hand-over
      force_first_tool the name of a tool the model must call before it answers, on every message
                       (an understanding step: the code, not the model, decides that it runs)
    """

    def __init__(self, policies_path, embedder, gen_client, model=MODEL, top_n=2,
                 system_prompt=DEFAULT_SYSTEM_PROMPT, temperature=None, tools=None, run_tool=None,
                 max_tool_rounds=3, force_first_tool=None):
        self.embedder = embedder          # raw langchain embeddings (embed_documents/embed_query)
        self.gen_client = gen_client      # raw Anthropic client (the SUT's generator)
        self.model = model
        self.top_n = top_n
        self.system_prompt = system_prompt
        self.temperature = temperature
        self._send_temperature = temperature is not None
        if tools and run_tool is None:
            raise ValueError("tools need a run_tool function to run them")
        self.tools = tools
        self.run_tool = run_tool
        self.max_tool_rounds = max_tool_rounds
        if force_first_tool and force_first_tool not in [tool["name"] for tool in tools or []]:
            raise ValueError(f"force_first_tool {force_first_tool!r} is not one of the tools")
        self.force_first_tool = force_first_tool
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
        answer_text, contexts, _ = self.answer_with_tool_calls(query, conversation)
        return answer_text, contexts

    def answer_with_tool_calls(self, query, conversation=None):
        """answer(), plus the tools the model called: [{"name": ..., "arguments": {...}}] ([] if none)."""
        contexts = self.retrieve(self._retrieval_query(query, conversation))
        user = "Policy context:\n" + "\n\n".join(contexts) + f"\n\nPassenger: {query}"
        messages = _alternating_turns(list(conversation or []) + [{"role": "user", "content": user}])
        answer_text, tool_calls = self._generate(messages)
        return answer_text, contexts, tool_calls

    @staticmethod
    def _retrieval_query(query, conversation):
        earlier = [t["content"] for t in (conversation or []) if t.get("role") == "user"][-RETRIEVAL_TURNS:]
        return " ".join(earlier + [query])

    def _generate(self, messages):
        """The model's reply, and the tools it called on the way. Without tools: one call, as before."""
        if not self.tools:
            return _reply_text(self._create(messages)), []
        messages, tool_calls = list(messages), []
        for round_number in range(self.max_tool_rounds + 1):
            forced = self.force_first_tool if round_number == 0 else None
            reply = self._create(messages, forced_tool=forced)
            tool_uses = [block for block in reply.content if getattr(block, "type", None) == "tool_use"]
            if not tool_uses:
                return _reply_text(reply), tool_calls
            if round_number == self.max_tool_rounds:      # still asking for tools after the last round
                break
            messages.append({"role": "assistant", "content": reply.content})
            results = []
            for use in tool_uses:
                arguments = dict(use.input)
                tool_calls.append({"name": use.name, "arguments": arguments})
                results.append({"type": "tool_result", "tool_use_id": use.id,
                                "content": json.dumps(self._run_tool(use.name, arguments), ensure_ascii=False)})
            messages.append({"role": "user", "content": results})
        return TOOL_LIMIT_REPLY, tool_calls

    def _run_tool(self, name, arguments):
        try:
            return self.run_tool(name, arguments)
        except Exception as error:            # a broken tool must not crash the answer; the model sees why
            return {"error": f"{type(error).__name__}: {error}"}

    def _create(self, messages, forced_tool=None):
        params = dict(model=self.model, max_tokens=500, system=self.system_prompt, messages=messages)
        if self.tools:
            params["tools"] = self.tools
        if forced_tool:
            params["tool_choice"] = {"type": "tool", "name": forced_tool}
        if self._send_temperature:
            try:
                return self.gen_client.messages.create(**params, temperature=self.temperature)
            except TypeError as error:
                # Some SDK versions no longer accept a temperature setting; the error comes before
                # any request is sent, so retrying without it costs nothing.
                if "temperature" not in str(error):
                    raise
                self._send_temperature = False
        return self.gen_client.messages.create(**params)


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
