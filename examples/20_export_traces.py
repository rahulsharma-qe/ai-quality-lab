"""Example 20: a run as OpenTelemetry traces, for a team's own tracing tool.

Teams already watch their agents in tracing tools (Phoenix, Langfuse, Jaeger) that read
OpenTelemetry. Exporting a run in that format puts the test results where the team already looks:
each case is one trace, with a span for every tool the agent called and every check, and a failed
check is an error span carrying its reason.

Here AeroAssist's recorded answers are replayed (no key) and the run is exported. The spans carry
the run's time, not measured durations: the platform sees the agent from the outside, so timings
per step would come from instrumenting the agent itself.

Command-line equivalent:
    aiquality gate --team aeroassist
    aiquality export-traces aiquality-runs --output traces.json
Run:  python examples/20_export_traces.py
"""

import json
import tempfile
from collections import Counter
from pathlib import Path

from aiquality import TeamConfig
from aiquality.commands import evaluate_team
from aiquality.reporting.trace_export import write_traces

TEAMS = Path(__file__).resolve().parents[1] / "teams"
runs = Path(tempfile.mkdtemp())

record = evaluate_team(TeamConfig.load(TEAMS / "aeroassist"), output_dir=runs, print_reports=False)
path = write_traces(record, runs / "traces.json")

spans = json.loads(path.read_text(encoding="utf-8"))["resourceSpans"][0]["scopeSpans"][0]["spans"]
kinds = Counter(span["name"].split()[0] for span in spans)
errors = [span for span in spans if span["name"].startswith("check") and span["status"]["code"] == 2]
print(f"{kinds['case']} traces (one per case), {kinds['tool']} tool spans, {kinds['check']} check spans")
print(f"{len(errors)} failed checks, each an error span with its reason; for example:")
for span in errors[:3]:
    case = next(s["name"] for s in spans if s["spanId"] == span["parentSpanId"])
    print(f"  {case:12} {span['name']:26} {span['status']['message'][:70]}")

try:   # pip install "aiquality[tracing]" to check the file against the official definitions
    from google.protobuf import json_format
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    json_format.Parse(path.read_text(encoding="utf-8"), ExportTraceServiceRequest())
    print("the file matches the official OpenTelemetry trace format")
except ImportError:
    print("(install the 'tracing' extra to check the file against the official OpenTelemetry definitions)")
print(f"written to {path}")
