"""
build_faction_summary.py
Downloads plenary_vote_results-skl9.tsv and produces faction_summary.json.

The TSV file is regenerated with newest sessions prepended (not appended),
so byte-range incremental downloads don't work. Instead we:
  1. Skip — server file unchanged (Last-Modified matches) → nothing to do
  2. Full — download entire file, parse, write summary

Metadata (last-modified) stored in faction_summary.meta.json.

Output format:
{
  "2026-03-12": {
    "1":  {"for": 140, "against": 0, "abstain": 1, "not_voting": 37, "absent": 50},
    ...
  },
  ...
}

Vote codes: 1=За, 2=Проти, 3=Утримався, 4=Не голосував, 0=Відсутній
Results column format: deputy_id:faction_id:vote_code|...
"""

import json
import os
import time
import urllib.request
from collections import defaultdict

TSV_URL   = "https://data.rada.gov.ua/ogd/zal/ppz/skl9/plenary_vote_results-skl9.tsv"
TSV_PATH  = "plenary_vote_results-skl9.tsv"
OUT_PATH  = "faction_summary.json"
META_PATH = "faction_summary.meta.json"

VOTE_CODE = {"1": "for", "2": "against", "3": "abstain", "4": "not_voting", "0": "absent"}


def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(last_modified):
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_modified": last_modified}, f)


def parse_rows(text):
    """Parse TSV text into faction vote counts."""
    # Columns: 0=date_agenda, 1=id_question, 2=id_event, 3=for, 4=against,
    #          5=abstain, 6=not_voting, 7=total, 8=presence, 9=absent, 10=results, 11=voting_result
    summary = defaultdict(lambda: defaultdict(lambda: {"for": 0, "against": 0, "abstain": 0, "not_voting": 0, "absent": 0}))
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 11:
            continue
        date = parts[0].strip()
        results = parts[10].strip()
        if not date or not results or date == "date_agenda":
            continue
        for entry in results.split("|"):
            fields = entry.split(":")
            if len(fields) != 3:
                continue
            _, faction_id, vote_code = fields
            key = VOTE_CODE.get(vote_code)
            if key:
                summary[date][faction_id][key] += 1
    return summary


def _urlopen_retry(req, retries=5, timeout=120):
    """urlopen with retry on timeout/connection errors."""
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"  Retry {attempt + 1}/{retries} after {wait}s — {e}")
                time.sleep(wait)
            else:
                raise


def main():
    meta = load_meta()
    old_modified = meta.get("last_modified", "")

    # Step 1: HEAD request to check if file changed
    head_req = urllib.request.Request(TSV_URL, method="HEAD")
    head_resp = _urlopen_retry(head_req)
    server_modified = head_resp.headers.get("Last-Modified", "")
    server_size = int(head_resp.headers.get("Content-Length", 0))

    if old_modified and server_modified == old_modified:
        print(f"Skip — file unchanged ({server_modified})")
        return

    # Step 2: Full download (TSV is regenerated, not appended — incremental won't work)
    print(f"Downloading {server_size / 1024 / 1024:.1f} MB...")
    full_req = urllib.request.Request(TSV_URL)
    full_resp = _urlopen_retry(full_req, timeout=300)
    # Stream in chunks to avoid timeout on slow connections
    with open(TSV_PATH, "wb") as f:
        while True:
            chunk = full_resp.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            f.write(chunk)
    print(f"Downloaded {os.path.getsize(TSV_PATH) / 1024 / 1024:.1f} MB")
    with open(TSV_PATH, encoding="utf-8") as f:
        text = f.read()

    summary = parse_rows(text)
    # Convert defaultdicts to plain dicts for JSON serialization
    plain = {date: {fid: dict(votes) for fid, votes in factions.items()} for date, factions in summary.items()}
    output = {date: factions for date, factions in sorted(plain.items())}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    save_meta(server_modified)
    print(f"Done — {len(output)} dates written")


if __name__ == "__main__":
    main()
