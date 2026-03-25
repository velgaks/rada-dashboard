"""
build_faction_summary.py
Downloads plenary_vote_results-skl9.tsv incrementally and produces faction_summary.json.

Supports three modes:
  1. Skip       — server file unchanged (Last-Modified matches) → nothing to do
  2. Incremental — server file grew → download only new bytes, parse new rows, merge
  3. Full        — no prior meta or server returned full file → download + parse everything

Metadata (byte offset, last-modified) stored in faction_summary.meta.json.

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
import sys
import urllib.request
from collections import defaultdict

TSV_URL   = "https://data.rada.gov.ua/ogd/zal/ppz/skl9/plenary_vote_results-skl9.tsv"
TSV_PATH  = "plenary_vote_results-skl9.tsv"
OUT_PATH  = "faction_summary.json"
META_PATH = "faction_summary.meta.json"

VOTE_CODE = {"1": "for", "2": "against", "3": "abstain", "4": "not_voting", "0": "absent"}

# Known TSV column order (so we don't need a header row for incremental chunks)
TSV_COLUMNS = ["id_question", "date_agenda", "id_event", "id_session", "results"]


def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(byte_offset, last_modified):
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({"byte_offset": byte_offset, "last_modified": last_modified}, f)


def load_existing_summary():
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_rows(text):
    """Parse TSV text into faction vote counts. Returns a defaultdict summary."""
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


def merge_summaries(existing, new_data):
    """Merge new_data counts into existing summary dict."""
    for date, factions in new_data.items():
        if date not in existing:
            existing[date] = {}
        for fid, votes in factions.items():
            if fid not in existing[date]:
                existing[date][fid] = {"for": 0, "against": 0, "abstain": 0, "not_voting": 0, "absent": 0}
            for key, count in votes.items():
                existing[date][fid][key] += count
    return existing


def save_summary(summary):
    output = {date: factions for date, factions in sorted(summary.items())}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    return len(output)


def main():
    meta = load_meta()
    old_offset = meta.get("byte_offset", 0)
    old_modified = meta.get("last_modified", "")

    # Step 1: HEAD request to check if file changed
    head_req = urllib.request.Request(TSV_URL, method="HEAD")
    head_resp = urllib.request.urlopen(head_req)
    server_modified = head_resp.headers.get("Last-Modified", "")
    server_size = int(head_resp.headers.get("Content-Length", 0))

    if old_modified and server_modified == old_modified and old_offset == server_size:
        print(f"Skip — file unchanged ({server_modified})")
        return

    # Step 2: Try incremental download
    if old_offset > 0 and old_modified and server_size > old_offset:
        print(f"Incremental — downloading bytes {old_offset}–{server_size} ({(server_size - old_offset) / 1024:.0f} KB)...")
        range_req = urllib.request.Request(TSV_URL)
        range_req.add_header("Range", f"bytes={old_offset}-")
        try:
            range_resp = urllib.request.urlopen(range_req)
            if range_resp.status == 206:
                chunk = range_resp.read().decode("utf-8")
                # First line is likely partial — skip it
                newline_pos = chunk.find("\n")
                if newline_pos >= 0:
                    chunk = chunk[newline_pos + 1:]
                new_data = parse_rows(chunk)
                if new_data:
                    existing = load_existing_summary()
                    old_dates = len(existing)
                    merged = merge_summaries(existing, new_data)
                    total = save_summary(merged)
                    save_meta(server_size, server_modified)
                    new_dates = total - old_dates
                    print(f"Done — {total} dates total, {new_dates} new dates added")
                    return
                else:
                    print("No new rows in chunk, saving meta only")
                    save_meta(server_size, server_modified)
                    return
        except urllib.error.HTTPError:
            print("Range request failed, falling back to full download")

    # Step 3: Full download
    print(f"Full download — {server_size / 1024 / 1024:.1f} MB...")
    urllib.request.urlretrieve(TSV_URL, TSV_PATH)
    with open(TSV_PATH, encoding="utf-8") as f:
        text = f.read()
    summary = parse_rows(text)
    # Convert defaultdicts to plain dicts
    plain = {date: {fid: dict(votes) for fid, votes in factions.items()} for date, factions in summary.items()}
    total = save_summary(plain)
    save_meta(server_size, server_modified)
    print(f"Done — {total} dates written (full rebuild)")


if __name__ == "__main__":
    main()
