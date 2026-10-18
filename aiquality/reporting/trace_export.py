"""Export a run as OpenTelemetry traces, so a team's own tracing tool can show the test results.

    aiquality export-traces aiquality-runs --output traces.json

Each case becomes one trace: a root span for the case (the question in, the answer out), a span
for each tool the agent called, and a span for each check (status ERROR when the check failed, with
its reason). Attribute names follow OpenInference (input.value, output.value, the span kind), which
tracing tools such as Phoenix read.

The file is OTLP in its JSON encoding, the format OpenTelemetry collectors accept, written with the
standard library: no new dependency. examples/20_export_traces.py also checks it with the official
OpenTelemetry definitions.

What it can't show: how long each step inside the agent took. The platform sees the agent from the
outside (the answer, its tool calls, the policies it retrieved), so every span carries the run's
time, not a measured duration. Timings per step come from instrumenting the agent itself.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from aiquality.reporting.run_record import RunRecord

SCOPE = "aiquality"
STATUS_OK, STATUS_ERROR = 1, 2
KIND_INTERNAL = 1
FAILED = ("FAIL", "ERROR")


def run_to_otlp(record: RunRecord) -> dict:
    """The run as an OTLP/JSON request: {"resourceSpans": [...]}, one trace per case."""
    start = _nanoseconds(record.created_at)
    spans = []
    for number, outcome in enumerate(record.outcomes):
        spans += _case_spans(record, outcome, start + number * 1_000_000)     # cases 1 ms apart, in order
    resource = _attributes({"service.name": record.agent_name, "aiquality.team": record.team,
                            "aiquality.run_id": record.run_id, "aiquality.run_mode": record.run_mode,
                            "aiquality.agent_version": record.agent_version,
                            "aiquality.golden_set_version": record.golden_set_version})
    return {"resourceSpans": [{"resource": {"attributes": resource},
                               "scopeSpans": [{"scope": {"name": SCOPE}, "spans": spans}]}]}


def write_traces(record: RunRecord, output) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run_to_otlp(record), ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def _case_spans(record: RunRecord, outcome: dict, at: int) -> list[dict]:
    trace_id = _hex_id(record.run_id, outcome["case_id"], length=32)
    root_id = _hex_id(trace_id, "case")
    failed = [r for r in outcome["results"] if r["status"] in FAILED]
    root = _span(trace_id, root_id, None, f"case {outcome['case_id']}", at, "CHAIN", {
        "input.value": outcome.get("question") or "", "output.value": outcome.get("answer_text") or "",
        "aiquality.case_id": outcome["case_id"], "aiquality.category": outcome.get("category") or "",
        "aiquality.priority": outcome.get("priority") or "",
        "aiquality.failed_checks": ", ".join(r["check"] for r in failed)},
        error=outcome.get("error") or (f"{len(failed)} check(s) failed" if failed else None))
    spans = [root]
    for number, call in enumerate(outcome.get("tool_calls") or []):
        spans.append(_span(trace_id, _hex_id(root_id, "tool", number), root_id, f"tool {call.get('name')}", at,
                           "TOOL", {"tool.name": call.get("name") or "",
                                    "input.value": json.dumps(call.get("arguments") or {}, ensure_ascii=False)}))
    for result in outcome["results"]:
        failed_check = result["status"] in FAILED
        spans.append(_span(trace_id, _hex_id(root_id, "check", result["check"]), root_id,
                           f"check {result['check']}", at, "EVALUATOR",
                           {"aiquality.check": result["check"], "aiquality.status": result["status"],
                            "output.value": result.get("reason") or "",
                            "aiquality.evidence": result.get("evidence") or "",
                            "aiquality.flags": ", ".join(result.get("flags") or [])},
                           error=result.get("reason") if failed_check else None))
    return spans


def _span(trace_id, span_id, parent_id, name, at, kind, attributes, error=None) -> dict:
    span = {"traceId": trace_id, "spanId": span_id, "name": name, "kind": KIND_INTERNAL,
            "startTimeUnixNano": str(at), "endTimeUnixNano": str(at),
            "attributes": _attributes({"openinference.span.kind": kind, **attributes}),
            "status": {"code": STATUS_ERROR, "message": str(error)} if error else {"code": STATUS_OK}}
    if parent_id:
        span["parentSpanId"] = parent_id
    return span


def _attributes(values: dict) -> list[dict]:
    return [{"key": key, "value": {"stringValue": str(value)}} for key, value in values.items()
            if value not in (None, "")]


def _hex_id(*parts, length: int = 16) -> str:
    """Stable ids (the same run exports the same ids): hex, as OTLP/JSON writes trace and span ids."""
    return hashlib.sha256("/".join(str(part) for part in parts).encode()).hexdigest()[:length]


def _nanoseconds(created_at: str) -> int:
    return int(datetime.fromisoformat(created_at).timestamp() * 1_000_000_000)
