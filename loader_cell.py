# ============================================================
# GOLDEN DATASET — loader + validator (Colab cell)
# Load the JSON, check schema, and print a health summary.
# Re-run this every time you add cases to catch gaps early.
# ============================================================
import json
from collections import Counter

# If running in Colab, upload golden_dataset.json first (Files pane) or mount Drive.
PATH = "golden_dataset.json"

CORE = ["id","input","category","priority","retrieved_policy","reference_answer",
        "expected_behaviour","dimensions","source","version","notes"]
CATS = {"happy","edge","adversarial","out_of_scope"}
DIMS = {"correctness","relevance","completeness","consistency",
        "groundedness","faithfulness","safety"}

data = json.load(open(PATH))
cases = data["cases"]

problems = []
for c in cases:
    cid = c.get("id","?")
    # every core field present + non-empty
    for f in CORE:
        if f not in c or c[f] in ("", [], None):
            problems.append(f"[{cid}] missing/empty core field: {f}")
    # category + dimensions from the allowed vocab
    if c.get("category") not in CATS:
        problems.append(f"[{cid}] bad category: {c.get('category')}")
    for d in c.get("dimensions", []):
        if d not in DIMS:
            problems.append(f"[{cid}] unknown dimension: {d}")
    # unique id check happens below

# duplicate ids
id_counts = Counter(c.get("id") for c in cases)
for cid, n in id_counts.items():
    if n > 1:
        problems.append(f"duplicate id: {cid} (x{n})")

print(f"📋 Golden dataset: {data['meta']['name']} v{data['meta']['version']}")
print(f"   total cases: {len(cases)}")
print(f"   category spread: {dict(Counter(c['category'] for c in cases))}")
print(f"   priority spread: {dict(Counter(c.get('priority') for c in cases))}")
print()
if problems:
    print(f"⚠️  {len(problems)} schema issue(s) — fix before using:")
    for p in problems:
        print("   •", p)
else:
    print("✅ all cases pass schema checks")

# quick coverage nudge: warn if any category is missing entirely
missing_cats = CATS - set(c["category"] for c in cases)
if missing_cats:
    print(f"\n🔎 coverage gap — no cases yet for: {', '.join(sorted(missing_cats))}")
