"""Test any agent that sits behind an HTTP endpoint. Standard library only."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from aiquality.contracts import AgentResponse, AgentUnderTest
from aiquality.errors import AgentConnectionError, ConfigError


class HttpEndpointAgent(AgentUnderTest):
    """Sends each question to a URL and reads the answer from the JSON reply.

    POST (default): body {"<question_field>": question, "conversation": [...]}
    GET:            ?<question_field>=question
    answer_field is a dotted path into the reply, e.g. "data.answer".
    The access token is read from an environment variable whose NAME is configured,
    so the secret itself never appears in a config file. By default it is sent as
    "Authorization: Bearer <token>"; auth_header and auth_prefix change that
    (for example auth_header "x-api-key" with auth_prefix "").
    """

    def __init__(self, url: str, method: str = "POST", question_field: str = "question",
                 answer_field: str = "answer", headers: Optional[dict] = None,
                 auth_token_env: Optional[str] = None, auth_header: str = "Authorization",
                 auth_prefix: str = "Bearer ", timeout_seconds: float = 30,
                 name: str = "http-agent", version: str = "unversioned"):
        method = method.upper()
        if method not in ("GET", "POST"):
            raise ConfigError("http_endpoint agent", [f"method must be GET or POST, got {method}"])
        self.url = url
        self.method = method
        self.question_field = question_field
        self.answer_field = answer_field
        self.headers = dict(headers or {})
        self.auth_token_env = auth_token_env
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix
        self.timeout_seconds = timeout_seconds
        self.name = name
        self.version = version

    def answer(self, question: str, conversation: Optional[list[dict]] = None) -> AgentResponse:
        request = self._build_request(question, conversation)
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as reply:
                body = reply.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise AgentConnectionError(f"{self.url} answered HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise AgentConnectionError(f"could not reach {self.url}: {error}") from error
        latency_ms = round((time.perf_counter() - started) * 1000, 1)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise AgentConnectionError(f"{self.url} did not return JSON") from error
        answer_text = _read_dotted_path(payload, self.answer_field)
        if not isinstance(answer_text, str):
            raise AgentConnectionError(f"no text at '{self.answer_field}' in the reply from {self.url}")
        return AgentResponse(answer_text=answer_text, latency_ms=latency_ms)

    def _build_request(self, question: str, conversation: Optional[list[dict]]) -> urllib.request.Request:
        headers = {"Accept": "application/json", **self.headers}
        if self.auth_token_env:
            token = os.environ.get(self.auth_token_env)
            if not token:
                raise AgentConnectionError(
                    f"environment variable {self.auth_token_env} is not set (needed for {self.url})")
            headers[self.auth_header] = f"{self.auth_prefix}{token}"

        if self.method == "GET":
            query = urllib.parse.urlencode({self.question_field: question})
            separator = "&" if "?" in self.url else "?"
            return urllib.request.Request(f"{self.url}{separator}{query}", headers=headers, method="GET")

        body = json.dumps({self.question_field: question, "conversation": conversation or []}).encode("utf-8")
        headers["Content-Type"] = "application/json"
        return urllib.request.Request(self.url, data=body, headers=headers, method="POST")


def _read_dotted_path(payload, dotted_path: str):
    value = payload
    for key in dotted_path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value
