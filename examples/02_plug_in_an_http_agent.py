"""Example 02: plug in an agent that sits behind an HTTP endpoint (POST and GET).

This example starts a tiny local agent server (standard library only), then tests it
through HttpEndpointAgent. In a team config the same thing is:

    agent:
      adapter: http_endpoint
      url: https://your-agent.example.com/chat
      answer_field: data.answer
      auth_token_env: YOUR_AGENT_TOKEN     # the NAME of an environment variable, never the token

Run:  python examples/02_plug_in_an_http_agent.py
"""

import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiquality import HttpEndpointAgent
from sample_store_agent import answer as sample_store_answer


class DemoAgentServer(BaseHTTPRequestHandler):
    """POST /chat {"question": ...} and GET /chat?question=... both reply {"data": {"answer": ...}}."""

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer demo-token":
            return self._reply(401, {"error": "missing or wrong token"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._reply(200, {"data": {"answer": sample_store_answer(body["question"])}})

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self._reply(200, {"data": {"answer": sample_store_answer(query["question"][0])}})

    def _reply(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the example output clean
        pass


server = HTTPServer(("127.0.0.1", 0), DemoAgentServer)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/chat"

# The token lives in an environment variable; the config only names the variable.
os.environ["DEMO_AGENT_TOKEN"] = "demo-token"

post_agent = HttpEndpointAgent(url, method="POST", answer_field="data.answer", auth_token_env="DEMO_AGENT_TOKEN")
response = post_agent.answer("Can I return an item after 30 days?")
print("POST ->", response.answer_text, f"({response.latency_ms} ms)")

get_agent = HttpEndpointAgent(url, method="GET", answer_field="data.answer")
print("GET  ->", get_agent.answer("What are your opening hours?").answer_text)

server.shutdown()
