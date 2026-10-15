"""The review queue as a file: <output_dir>/<team>-review-queue.jsonl, one item per line."""

from pathlib import Path

from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord


@register_reporter("review_queue")
class ReviewQueueReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        from aiquality.review import build_review_queue, write_review_queue   # the queue reads reporting
        return write_review_queue(build_review_queue(record), Path(output_dir) / f"{record.team}-review-queue.jsonl")
