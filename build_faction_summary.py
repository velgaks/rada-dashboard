"""
build_faction_summary.py
Reads plenary_vote_results-skl9.tsv and produces faction_summary.json.

Output format:
{
  "2026-03-12": {
    "1":  {"for": 140, "against": 0, "abstain": 1, "not_voting": 37, "absent": 50},
    "3":  {"for": 16,  ...},
    ...
  },
  ...
}

Vote codes in results column: 1=За, 2=Проти, 3=Утримався, 4=Не голосував, 0=Відсутній
results column format: deputy_id:faction_id:vote_code|...
"""

import csv
import json
from collections import defaultdict

TSV_PATH  = "plenary_vote_results-skl9.tsv"
OUT_PATH  = "faction_summary.json"

VOTE_CODE = {"1": "for", "2": "against", "3": "abstain", "4": "not_voting", "0": "absent"}

summary = defaultdict(lambda: defaultdict(lambda: {"for": 0, "against": 0, "abstain": 0, "not_voting": 0, "absent": 0}))

with open(TSV_PATH, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        date    = row["date_agenda"].strip()
        results = row["results"].strip()
        if not date or not results:
            continue
        for entry in results.split("|"):
            parts = entry.split(":")
            if len(parts) != 3:
                continue
            _, faction_id, vote_code = parts
            key = VOTE_CODE.get(vote_code)
            if key:
                summary[date][faction_id][key] += 1

# Convert defaultdicts to plain dicts for JSON serialisation
output = {date: {fid: dict(votes) for fid, votes in factions.items()}
          for date, factions in sorted(summary.items())}

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

print(f"Done — {len(output)} dates written to {OUT_PATH}")
