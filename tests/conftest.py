"""Shared helpers for the aiquality tests. Everything runs without an API key or network."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


def write_team(folder: Path, config: dict, golden_rows: str, agent_code: str = None, as_json: bool = False) -> Path:
    """Create a small team folder: config + golden_set.csv (+ agent.py)."""
    import yaml
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "golden_set.csv").write_text(golden_rows, encoding="utf-8")
    if agent_code is not None:
        (folder / "agent.py").write_text(agent_code, encoding="utf-8")
    if as_json:
        (folder / "team.json").write_text(json.dumps(config), encoding="utf-8")
    else:
        (folder / "team.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return folder


GOLDEN_ROWS = (
    "id,input,category,must_include,must_not_include\n"
    "C1,What are your opening hours?,happy,9 am|6 pm,24/7\n"
    "C2,Can I return an item?,edge,30 days,no questions asked\n"
)

AGENT_CODE = '''
AGENT_VERSION = "test-agent-1"

def answer(question):
    if "hours" in question:
        return "We are open from 9 am to 6 pm."
    return "Returns are accepted within 30 days."
'''

BASE_CONFIG = {
    "team": "test_team",
    "agent": {"adapter": "python_function", "file": "agent.py", "function": "answer"},
    "golden_set": "golden_set.csv",
    "checks": {"required_phrases": {"threshold": 0.9}, "forbidden_phrases": {"threshold": 1.0}},
}


@pytest.fixture
def team_folder(tmp_path):
    return write_team(tmp_path / "test_team", dict(BASE_CONFIG), GOLDEN_ROWS, AGENT_CODE)


class _AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/broken":
            return self._send(500, b"oops")
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        token = self.headers.get("Authorization")
        turns = len(body.get("conversation", []))
        payload = {"data": {"answer": f"echo: {body['question']} | token: {token} | turns: {turns}"}}
        self._send(200, json.dumps(payload).encode())

    def do_GET(self):
        self._send(200, json.dumps({"answer": "get works"}).encode())

    def _send(self, status, data):
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def agent_server():
    server = HTTPServer(("127.0.0.1", 0), _AgentHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
