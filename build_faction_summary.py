"""
build_faction_summary.py
Downloads plenary_vote_results-skl9.tsv and produces faction_summary.json.

The TSV file is regenerated with newest sessions prepended (not appended),
so byte-range incremental downloads don't work. Instead we:
  1. Skip — server file unchanged (Last-Modified matches) → nothing to do
  2. Full — download entire file via curl, parse, write summary

Uses curl for downloads (robust retries, timeouts, progress) and Python for parsing.
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
import subprocess
import sys
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


def curl_head(url):
    """HEAD request via curl. Returns dict of headers."""
    r = subprocess.run(
        ["curl", "-sS", "-I", "--connect-timeout", "15", "--max-time", "30",
         "--retry", "3", "--retry-delay", "10", "--retry-max-time", "90", url],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"curl HEAD failed (exit {r.returncode}): {r.stderr.strip()}", flush=True)
        sys.exit(1)
    headers = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return headers


def curl_download(url, dest):
    """Download file via curl with progress, retries, and resume."""
    r = subprocess.run(
        ["curl", "-sS", "-o", dest, "--connect-timeout", "30", "--max-time", "600",
         "--retry", "5", "--retry-delay", "10", "--retry-max-time", "300",
         "-C", "-", url],
        capture_output=True, text=True, timeout=660,
    )
    if r.returncode != 0:
        print(f"curl download failed (exit {r.returncode}): {r.stderr.strip()}", flush=True)
        sys.exit(1)


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


def main():
    meta = load_meta()
    old_modified = meta.get("last_modified", "")

    # Step 1: HEAD request to check if file changed
    print(f"HEAD {TSV_URL}", flush=True)
    headers = curl_head(TSV_URL)
    server_modified = headers.get("last-modified", "")
    server_size = int(headers.get("content-length", 0))
    print(f"  Last-Modified: {server_modified}  Size: {server_size / 1024 / 1024:.1f} MB", flush=True)

    if old_modified and server_modified == old_modified:
        print(f"Skip — file unchanged ({server_modified})")
        return

    # Step 2: Full download via curl (robust retries, resume support)
    print(f"Downloading {server_size / 1024 / 1024:.1f} MB...", flush=True)
    curl_download(TSV_URL, TSV_PATH)
    actual_size = os.path.getsize(TSV_PATH)
    print(f"Downloaded {actual_size / 1024 / 1024:.1f} MB", flush=True)

    with open(TSV_PATH, encoding="utf-8") as f:
        text = f.read()

    print("Parsing...", flush=True)
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
