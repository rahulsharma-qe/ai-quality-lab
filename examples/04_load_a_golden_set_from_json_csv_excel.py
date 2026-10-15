"""Example 04: load the same golden set from JSON, CSV and Excel.

The file extension picks the reader. In CSV and Excel, a cell that holds a list uses
"|" between items, e.g.  must_include = "9 am|6 pm".  Excel needs:  pip install "aiquality[excel]"
Run:  python examples/04_load_a_golden_set_from_json_csv_excel.py
"""

import tempfile
from pathlib import Path

from aiquality import GoldenSetError, load_golden_set

DATA = Path(__file__).parent / "data"

for file_name in ("sample_golden_set.json", "sample_golden_set.csv", "sample_golden_set.xlsx"):
    golden_set = load_golden_set(DATA / file_name)
    first = golden_set.cases[0]
    print(f"{file_name:<26} {len(golden_set)} cases · first: {first.id} must_include={first.must_include}")

# All three hold the same cases.
loaded = [load_golden_set(DATA / name).cases for name in
          ("sample_golden_set.json", "sample_golden_set.csv", "sample_golden_set.xlsx")]
print("same cases in all three formats:",
      all([c.to_dict() for c in cases] == [c.to_dict() for c in loaded[0]] for cases in loaded))

# A broken file lists every problem at once, so it can be fixed in one go.
broken = Path(tempfile.mkdtemp()) / "broken_golden_set.csv"
broken.write_text("id,input\nB1,\nB1,What is the baggage allowance?\n", encoding="utf-8")
try:
    load_golden_set(broken)
except GoldenSetError as error:
    print(error)
