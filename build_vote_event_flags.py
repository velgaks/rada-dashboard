"""Build compact vote-event classification metadata for the dashboard.

The official plenary event CSV contains speeches, registrations and named votes.
Only type_event=0 rows with an id_event are named votes.  Amendment votes are a
subset whose event name contains an adjacent Ukrainian "поправ… №<digits>"
construction.  This intentionally does not classify legislation whose title
merely contains a phrase such as "Поправка до Монреальського протоколу".

The generated JSON is compact and stable: event IDs are de-duplicated and
sorted, object keys are sorted during serialization, and an unchanged upstream
Last-Modified value leaves the existing artifact untouched.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, TextIO


SOURCE_URL = (
    "https://data.rada.gov.ua/ogd/zal/ppz/skl9/"
    "plenary_event_question-skl9.csv"
)
SOURCE_PATH = Path("plenary_event_question-skl9.csv")
OUTPUT_PATH = Path("vote_event_flags.json")
SCHEMA_VERSION = 1

_UKRAINIAN_LETTERS = "А-Яа-яІіЇїЄєҐґ"
AMENDMENT_PATTERN = re.compile(
    rf"(?<![{_UKRAINIAN_LETTERS}])поправ[{_UKRAINIAN_LETTERS}'’\-]*\s*№\s*\d+",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def find_curl() -> str:
    """Return a curl executable available on Linux CI or the local Windows host."""
    executable = shutil.which("curl")
    if executable:
        return executable
    windows_curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    if windows_curl.exists():
        return str(windows_curl)
    raise RuntimeError("curl is required but was not found")


def curl_head(url: str) -> dict[str, str]:
    """Fetch response headers using curl with retries and strict failures."""
    command = [
        find_curl(),
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--head",
        "--connect-timeout",
        "15",
        "--max-time",
        "30",
        "--retry",
        "3",
        "--retry-delay",
        "10",
        "--retry-max-time",
        "90",
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(
            f"curl HEAD failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    # Redirects and proxies can yield more than one header block. Later values
    # describe the final response and intentionally overwrite earlier values.
    headers: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def curl_download(url: str, destination: Path) -> None:
    """Download via curl to a temporary file and atomically replace destination."""
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    command = [
        find_curl(),
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--output",
        str(temporary),
        "--connect-timeout",
        "30",
        "--max-time",
        "600",
        "--retry",
        "5",
        "--retry-delay",
        "10",
        "--retry-max-time",
        "300",
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=660)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"curl download failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    if not temporary.exists() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("curl download produced an empty file")
    os.replace(temporary, destination)


def is_amendment_name(name: str) -> bool:
    """Return whether a vote name contains an adjacent amendment-number phrase."""
    return bool(AMENDMENT_PATTERN.search(name or ""))


def _event_id(value: object) -> int | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    return int(text)


def build_payload(
    rows: Iterable[Mapping[str, object]],
    *,
    retrieved_at: str,
    source_last_modified: str,
) -> dict[str, object]:
    """Classify CSV rows and construct a compact, deterministic payload."""
    named_vote_ids: set[int] = set()
    amendment_ids: set[int] = set()
    named_dates: set[str] = set()
    source_rows = 0
    registrations = 0

    for row in rows:
        source_rows += 1
        event_type = str(row.get("type_event", "")).strip()
        event_id = _event_id(row.get("id_event"))

        if event_type == "1":
            registrations += 1
            continue
        if event_type != "0" or event_id is None:
            continue

        named_vote_ids.add(event_id)
        date = str(row.get("date_agenda", "")).strip()
        if DATE_PATTERN.fullmatch(date):
            named_dates.add(date)

        if is_amendment_name(str(row.get("name_event", ""))):
            amendment_ids.add(event_id)

    named_sorted = sorted(named_vote_ids)
    amendment_sorted = sorted(amendment_ids)
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "retrieved_at": retrieved_at,
            "source_last_modified": source_last_modified,
            "min_date": min(named_dates) if named_dates else None,
            "max_date": max(named_dates) if named_dates else None,
            "counts": {
                "rows": source_rows,
                "named_votes": len(named_sorted),
                "amendments": len(amendment_sorted),
                "registrations": registrations,
            },
        },
        "named_vote_ids": named_sorted,
        "amendment_ids": amendment_sorted,
    }


def parse_csv(
    stream: TextIO, *, retrieved_at: str, source_last_modified: str
) -> dict[str, object]:
    reader = csv.DictReader(stream)
    required = {"date_agenda", "type_event", "name_event", "id_event"}
    fields = set(reader.fieldnames or [])
    missing = sorted(required - fields)
    if missing:
        raise ValueError(f"source CSV is missing required columns: {', '.join(missing)}")
    return build_payload(
        reader,
        retrieved_at=retrieved_at,
        source_last_modified=source_last_modified,
    )


def serialize_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def write_payload(payload: Mapping[str, object], destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(serialize_payload(payload), encoding="utf-8", newline="\n")
    os.replace(temporary, destination)


def existing_source_last_modified(destination: Path) -> str:
    try:
        payload = json.loads(destination.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        if meta.get("schema_version") != SCHEMA_VERSION:
            return ""
        if not isinstance(payload.get("named_vote_ids"), list):
            return ""
        if not isinstance(payload.get("amendment_ids"), list):
            return ""
        return str(meta.get("source_last_modified", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    print(f"HEAD {SOURCE_URL}", flush=True)
    headers = curl_head(SOURCE_URL)
    source_last_modified = headers.get("last-modified", "")
    content_length = int(headers.get("content-length", "0") or 0)
    print(
        f"  Last-Modified: {source_last_modified or '[missing]'}  "
        f"Size: {content_length / 1024 / 1024:.1f} MB",
        flush=True,
    )

    previous_last_modified = existing_source_last_modified(OUTPUT_PATH)
    if source_last_modified and previous_last_modified == source_last_modified:
        print(f"Skip — source unchanged ({source_last_modified})")
        return 0

    print("Downloading official plenary event CSV...", flush=True)
    curl_download(SOURCE_URL, SOURCE_PATH)
    print(f"Downloaded {SOURCE_PATH.stat().st_size / 1024 / 1024:.1f} MB", flush=True)

    retrieved_at = utc_now()
    with SOURCE_PATH.open(encoding="utf-8-sig", newline="") as stream:
        payload = parse_csv(
            stream,
            retrieved_at=retrieved_at,
            source_last_modified=source_last_modified,
        )
    write_payload(payload, OUTPUT_PATH)

    counts = payload["meta"]["counts"]
    print(
        "Done — "
        f"{counts['named_votes']} named votes, "
        f"{counts['amendments']} amendments, "
        f"{counts['registrations']} registrations excluded",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
