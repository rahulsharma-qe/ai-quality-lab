"""Exporting a run as OpenTelemetry traces (OTLP JSON): one trace per case, a span per tool and per check."""

import json

import pytest

from aiquality import AgentResponse, PythonFunctionAgent, TeamConfig, ToolCall, evaluate_team
from aiquality.cli import EXIT_OK, main
from aiquality.reporting.trace_export import STATUS_ERROR, STATUS_OK, run_to_otlp

from conftest import BASE_CONFIG, GOLDEN_ROWS, write_team


@pytest.fixture
def record(tmp_path):
    def agent(question):
        if "hours" in question:
            return AgentResponse("We are open 24/7.", tool_calls=[ToolCall("opening_hours", {"day": "monday"})])
        return AgentResponse("Returns are accepted within 30 days.", tool_calls=[])

    folder = write_team(tmp_path / "team", dict(BASE_CONFIG), GOLDEN_ROWS)
    return evaluate_team(TeamConfig.load(folder), agent=PythonFunctionAgent(agent), output_dir=tmp_path / "runs",
                         print_reports=False)


def spans_by_trace(request):
    traces = {}
    for span in request["resourceSpans"][0]["scopeSpans"][0]["spans"]:
        traces.setdefault(span["traceId"], []).append(span)
    return traces


def attribute(span, key):
    return next(a["value"]["stringValue"] for a in span["attributes"] if a["key"] == key)


def test_each_case_is_a_trace_with_its_tools_and_checks(record):
    request = run_to_otlp(record)
    traces = spans_by_trace(request)
    assert len(traces) == 2
    first = traces[next(iter(traces))]
    root = first[0]
    assert root["name"] == "case C1" and "parentSpanId" not in root
    assert attribute(root, "input.value").startswith("What are your opening hours")
    assert attribute(root, "output.value") == "We are open 24/7."
    assert first[1]["name"] == "tool opening_hours"
    assert sorted(s["name"] for s in first[2:]) == ["check forbidden_phrases", "check required_phrases"]
    assert all(s["parentSpanId"] == root["spanId"] for s in first[1:])
    resource = {a["key"]: a["value"]["stringValue"] for a in request["resourceSpans"][0]["resource"]["attributes"]}
    assert resource["aiquality.run_id"] == record.run_id and resource["aiquality.team"] == "test_team"


def test_a_failed_check_is_an_error_span_with_its_reason(record):
    first = next(iter(spans_by_trace(run_to_otlp(record)).values()))
    root = first[0]
    forbidden = next(s for s in first if s["name"] == "check forbidden_phrases")
    assert forbidden["status"]["code"] == STATUS_ERROR and "24/7" in forbidden["status"]["message"]
    assert root["status"] == {"code": STATUS_ERROR, "message": "2 check(s) failed"}
    assert sorted(attribute(root, "aiquality.failed_checks").split(", ")) == ["forbidden_phrases", "required_phrases"]
    passing = list(spans_by_trace(run_to_otlp(record)).values())[1][0]
    assert passing["status"] == {"code": STATUS_OK}


def test_ids_are_stable_and_in_the_otlp_hex_form(record):
    first, second = run_to_otlp(record), run_to_otlp(record)
    assert first == second
    span = first["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert len(span["traceId"]) == 32 and len(span["spanId"]) == 16 and int(span["traceId"], 16) >= 0


def test_the_export_matches_the_official_opentelemetry_definitions(record):
    trace_service = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
    from google.protobuf import json_format
    parsed = json_format.Parse(json.dumps(run_to_otlp(record)), trace_service.ExportTraceServiceRequest())
    assert len(parsed.resource_spans[0].scope_spans[0].spans) == 7       # 2 cases: 2 roots, 1 tool, 4 checks


def test_cli_writes_the_last_run(record, tmp_path, capsys):
    output = tmp_path / "traces.json"
    assert main(["export-traces", str(tmp_path / "runs"), "--output", str(output)]) == EXIT_OK
    assert "2 cases of run" in capsys.readouterr().out and json.loads(output.read_text())["resourceSpans"]
