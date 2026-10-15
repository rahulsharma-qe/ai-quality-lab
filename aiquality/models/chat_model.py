"""Model layer: one place to get a language-model client, whatever the provider.

Every live model call (an agent under test, a judge) comes through here, so switching the
provider or the model is one setting, not an edit in every file.

Settings (environment variables, all optional):
  LLM_PROVIDER   which provider to call for live models   (default: "anthropic")
  AGENT_MODEL    the model an agent under test answers with
  JUDGE_MODEL    the model that grades answers: deliberately a different, stronger model
                 than the agent, so nothing grades its own work

API keys are read from a Colab secret first, then from the environment. They are never
printed or logged. Provider libraries are imported only when a client is created, so the
package itself needs no provider library and no key.

Adding a provider = one ChatModel subclass and one branch in get_chat_model().
"""

import json
import os
import re

AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-4-5")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-5-5")


def get_api_key(name="ANTHROPIC_API_KEY"):
    """Colab secret first, then environment variable. Raises a clear error if missing."""
    try:
        from google.colab import userdata
        key = userdata.get(name)
        if key:
            return key
    except Exception:
        pass
    key = os.environ.get(name)
    if not key:
        raise RuntimeError(f"{name} is not set — add it as a Colab secret or an environment variable.")
    return key


class ChatModel:
    """The one interface every provider implements: complete(system, user) -> text."""

    provider = "base"

    def __init__(self, model, temperature=0.0, max_tokens=400):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system, user):
        raise NotImplementedError("each provider must implement complete()")


class AnthropicChat(ChatModel):
    provider = "anthropic"

    def __init__(self, model, **kwargs):
        super().__init__(model, **kwargs)
        from anthropic import Anthropic
        self._client = Anthropic(api_key=get_api_key("ANTHROPIC_API_KEY"))
        self._send_temperature = True

    def complete(self, system, user):
        params = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if self._send_temperature and self.temperature is not None:
            try:
                return self._text(self._client.messages.create(**params, temperature=self.temperature))
            except TypeError as e:
                # Some SDK versions no longer accept a temperature setting. The error is raised
                # before any request is sent, so retrying without it costs nothing extra.
                if "temperature" not in str(e):
                    raise
                self._send_temperature = False
        return self._text(self._client.messages.create(**params))

    def _text(self, resp):
        """Join the text blocks of a reply. Newer models may put a 'thinking' block first,
        so we never assume the first block is the answer."""
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if not text:
            raise RuntimeError(f"{self.model} returned no text — it may have used all "
                               f"{self.max_tokens} tokens thinking; raise max_tokens.")
        return text


def get_chat_model(model, provider=None, **kwargs):
    """Return a ChatModel for the configured provider."""
    provider = (provider or os.environ.get("LLM_PROVIDER", "anthropic")).lower()
    if provider == "anthropic":
        return AnthropicChat(model, **kwargs)
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Add a ChatModel subclass for it in aiquality/models/chat_model.py.")


def extract_json(text):
    """Pull the first JSON object out of a model reply (handles code fences and extra prose)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        return json.JSONDecoder().raw_decode(text, start)[0]
