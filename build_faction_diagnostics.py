"""Build daily faction-health and governing-majority diagnostics.

The dashboard must not fetch the large per-deputy TSV in the browser. This
builder joins it to official event names, removes amendments, registrations and
signal votes, then writes a compact deterministic daily aggregate.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping, TextIO

from build_vote_event_flags import (
    SCHEMA_VERSION as EVENT_FLAGS_SCHEMA_VERSION,
    curl_download,
    curl_head,
    is_amendment_name,
    is_unnumbered_amendment_name,
    utc_now,
)


VOTE_RESULTS_URL = (
    "https://data.rada.gov.ua/ogd/zal/ppz/skl9/"
    "plenary_vote_results-skl9.tsv"
)
EVENT_QUESTIONS_URL = (
    "https://data.rada.gov.ua/ogd/zal/ppz/skl9/"
    "plenary_event_question-skl9.csv"
)
ROSTER_URL = (
    "https://data.rada.gov.ua/ogd/zal/ppz/skl9/"
    "plenary_deputies-skl9.csv"
)
FACTION_TRANSITIONS_URL = (
    "https://data.rada.gov.ua/ogd/zal/mps/mps-trans_fr.csv"
)
VOTE_RESULTS_PATH = Path("plenary_vote_results-skl9.tsv")
EVENT_QUESTIONS_PATH = Path("plenary_event_question-skl9.csv")
ROSTER_PATH = Path("plenary_deputies-skl9.csv")
FACTION_TRANSITIONS_PATH = Path("mps-trans_fr.csv")
EVENT_FLAGS_PATH = Path("vote_event_flags.json")
OUTPUT_PATH = Path("faction_diagnostics.json")
SCHEMA_VERSION = 2
SN_FACTION_ID = "1"
VALID_VOTE_CODES = {0, 1, 2, 3, 4}
ACTIVE_VOTE_CODES = (1, 2, 3)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
LAW_STAGE_PATTERN = re.compile(
    r"^поіменне голосування про про[єе]кт (?:закону|кодексу)\b"
    r".*\s[-–—]\s*(за основу|у першому читанні|[ув] (?:повторному )?другому читанні|в цілому)\b"
)
# Canonical IDs from the official IX-convocation faction dictionary. Quotes
# are removed before lookup because two group names contain nested quotes.
FACTION_NAME_TO_ID = {
    "позафракційні": "0",
    "фракція політичної партії слуга народу": "1",
    "фракція політичної партії опозиційна платформа-за життя": "2",
    "фракція політичної партії всеукраїнське об'єднання батьківщина": "3",
    "фракція політичної партії європейська солідарність": "4",
    "фракція політичної партії голос": "5",
    "депутатська група за майбутнє": "6",
    "депутатська група довіра": "7",
    "депутатська група партія за майбутнє": "8",
    "депутатська група платформа за життя та мир у верховній раді україни": "9",
    "депутатська група відновлення україни у верховній раді україни": "10",
}

MembershipInterval = tuple[str, str | None, str]

FACTION_FIELDS = (
    "active",
    "present",
    "total",
    "votes",
    "discipline_agree",
    "discipline_total",
    "discipline_ties",
    "discipline_low_activity",
)


def normalize_name(name: str) -> str:
    """Case-fold and collapse whitespace without altering Ukrainian letters."""
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def normalize_person_name(name: str) -> str:
    normalized = normalize_name(name).replace("’", "'").replace("`", "'")
    return normalized.replace("ʼ", "'")


def normalize_faction_name(name: str) -> str:
    return normalize_person_name(name).replace('"', "")


def is_signal_name(name: str) -> bool:
    return "сигнальн" in normalize_name(name)


def law_stage(name: str) -> str | None:
    """Return the substantive legislative stage or None for procedural votes."""
    match = LAW_STAGE_PATTERN.search(normalize_name(name))
    if not match:
        return None
    stage = match.group(1)
    if stage in {"за основу", "у першому читанні"}:
        return "first"
    if "другому читанні" in stage:
        return "second"
    return "final"


def _event_id(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def read_event_questions(
    stream: TextIO,
) -> tuple[dict[int, str], dict[int, str], set[int], set[int]]:
    """Return type-0 names/timestamps plus fallback classification ID sets."""
    reader = csv.DictReader(stream)
    required = {"type_event", "date_event", "name_event", "id_event"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(
            f"event CSV is missing required columns: {', '.join(missing)}"
        )

    event_names: dict[int, str] = {}
    event_times: dict[int, str] = {}
    named_vote_ids: set[int] = set()
    amendment_ids: set[int] = set()
    for row in reader:
        if str(row.get("type_event", "")).strip() != "0":
            continue
        event_id = _event_id(row.get("id_event"))
        if event_id is None:
            continue
        name = str(row.get("name_event", ""))
        event_time = str(row.get("date_event", "")).strip()
        if not DATETIME_PATTERN.fullmatch(event_time):
            raise ValueError(f"invalid or missing date_event for event {event_id}")
        event_names[event_id] = name
        event_times[event_id] = event_time
        named_vote_ids.add(event_id)
        if is_amendment_name(name):
            amendment_ids.add(event_id)
    return event_names, event_times, named_vote_ids, amendment_ids


def read_roster(stream: TextIO) -> dict[int, set[str]]:
    """Map each chronology voting ID to its event-era official full name."""
    reader = csv.DictReader(stream)
    required = {"id_mp", "name"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"roster CSV is missing required columns: {', '.join(missing)}")

    roster: dict[int, set[str]] = defaultdict(set)
    for row in reader:
        raw_id = str(row.get("id_mp", "")).strip()
        if not raw_id.isdigit():
            continue
        person_name = normalize_person_name(str(row.get("name", "")))
        if not person_name:
            continue
        roster[int(raw_id)].add(person_name)
    return dict(roster)


def read_faction_transitions(
    stream: TextIO,
) -> tuple[dict[str, list[MembershipInterval]], int]:
    """Parse official faction membership intervals for the IX convocation."""
    reader = csv.DictReader(stream)
    required = {"convocation", "full_name", "fra_name", "date_in", "date_out"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(
            f"faction transitions CSV is missing required columns: {', '.join(missing)}"
        )

    histories: dict[str, list[MembershipInterval]] = defaultdict(list)
    transition_rows = 0
    for row in reader:
        if str(row.get("convocation", "")).strip() != "9":
            continue
        person_name = normalize_person_name(str(row.get("full_name", "")))
        faction_name = normalize_faction_name(str(row.get("fra_name", "")))
        faction_id = FACTION_NAME_TO_ID.get(faction_name)
        if not person_name or faction_id is None:
            raise ValueError(
                f"unknown person/faction in transition row: "
                f"{row.get('full_name', '')!r} / {row.get('fra_name', '')!r}"
            )
        date_in = str(row.get("date_in", "")).strip()
        date_out = str(row.get("date_out", "")).strip() or None
        if not DATETIME_PATTERN.fullmatch(date_in):
            raise ValueError(f"invalid date_in for {row.get('full_name', '')!r}")
        if date_out is not None and not DATETIME_PATTERN.fullmatch(date_out):
            raise ValueError(f"invalid date_out for {row.get('full_name', '')!r}")
        if date_out is not None and date_out <= date_in:
            raise ValueError(f"non-positive membership interval for {row.get('full_name', '')!r}")
        histories[person_name].append((date_in, date_out, faction_id))
        transition_rows += 1

    for person_name in histories:
        histories[person_name].sort(key=lambda interval: interval[0])
    return dict(histories), transition_rows


def build_membership_index(
    roster: Mapping[int, set[str]],
    histories: Mapping[str, list[MembershipInterval]],
) -> dict[int, list[MembershipInterval]]:
    """Join voting IDs to histories, merging old/new surname aliases."""
    roster_aliases = set().union(*roster.values()) if roster else set()
    unmatched_names = set(histories) - roster_aliases
    if unmatched_names:
        sample = ", ".join(sorted(unmatched_names)[:5])
        raise ValueError(f"transition names missing from roster aliases: {sample}")

    memberships: dict[int, list[MembershipInterval]] = {}
    for deputy_id, aliases in roster.items():
        intervals = {
            interval
            for alias in aliases
            for interval in histories.get(alias, [])
        }
        if not intervals:
            raise ValueError(f"no faction history for deputy voting ID {deputy_id}")
        memberships[deputy_id] = sorted(intervals, key=lambda interval: interval[0])
    return memberships


def faction_at(
    memberships: Mapping[int, list[MembershipInterval]],
    deputy_id: int,
    event_time: str,
) -> str | None:
    """Resolve event-time affiliation; date_out is an exclusive boundary."""
    candidates = [
        interval
        for interval in memberships.get(deputy_id, [])
        if interval[0] <= event_time
        and (interval[1] is None or event_time < interval[1])
    ]
    if not candidates:
        return None
    latest_start = max(interval[0] for interval in candidates)
    faction_ids = {
        interval[2] for interval in candidates if interval[0] == latest_start
    }
    if len(faction_ids) != 1:
        raise ValueError(
            f"ambiguous faction history for deputy {deputy_id} at {event_time}"
        )
    return next(iter(faction_ids))


def load_vote_event_flags(
    path: Path, expected_last_modified: str
) -> tuple[set[int], set[int]] | None:
    """Load the compact classifier only when its schema and source match."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        if meta.get("schema_version") != EVENT_FLAGS_SCHEMA_VERSION:
            return None
        if (
            expected_last_modified
            and meta.get("source_last_modified") != expected_last_modified
        ):
            return None
        named = {_event_id(value) for value in payload.get("named_vote_ids", [])}
        amendments = {_event_id(value) for value in payload.get("amendment_ids", [])}
        if None in named or None in amendments:
            return None
        named_ids = {value for value in named if value is not None}
        amendment_ids = {value for value in amendments if value is not None}
        if not amendment_ids <= named_ids:
            return None
        return named_ids, amendment_ids
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def parse_member_votes(
    results: object,
    *,
    event_time: str,
    memberships: Mapping[int, list[MembershipInterval]],
) -> dict[str, Counter[int]]:
    """Count valid vote codes by reconstructed event-time faction."""
    factions: dict[str, Counter[int]] = defaultdict(Counter)
    for entry in str(results or "").split("|"):
        fields = entry.split(":")
        if len(fields) != 3:
            continue
        deputy_id, faction_id, vote_code = (field.strip() for field in fields)
        if not deputy_id.isdigit() or not faction_id.isdigit() or not vote_code.isdigit():
            continue
        code = int(vote_code)
        if code not in VALID_VOTE_CODES:
            continue
        deputy = int(deputy_id)
        event_faction_id = faction_at(memberships, deputy, event_time)
        if event_faction_id is None:
            raise ValueError(
                f"no event-time faction for deputy {deputy} at {event_time}"
            )
        # The TSV's faction_id is deliberately ignored: the source rewrites
        # historical rows when a deputy later changes faction.
        factions[event_faction_id][code] += 1
    return dict(factions)


def _empty_faction() -> dict[str, int]:
    return {field: 0 for field in FACTION_FIELDS}


def _empty_coalition() -> dict[str, object]:
    return {"passed": 0, "sn_alone": 0, "sn_dependent": 0, "partners": {}}


def _empty_day() -> dict[str, object]:
    return {"factions": {}, "coalition": _empty_coalition()}


def _update_faction_diagnostics(
    target: dict[str, int], vote_counts: Counter[int]
) -> None:
    active_counts = [vote_counts[code] for code in ACTIVE_VOTE_CODES]
    active = sum(active_counts)
    target["active"] += active
    target["present"] += active + vote_counts[4]
    target["total"] += sum(vote_counts[code] for code in VALID_VOTE_CODES)
    target["votes"] += 1

    if active < 2:
        target["discipline_low_activity"] += 1
        return
    modal = max(active_counts)
    if sum(count == modal for count in active_counts) >= 2:
        target["discipline_ties"] += 1
        return
    target["discipline_agree"] += modal
    target["discipline_total"] += active


def aggregate_vote_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    event_names: Mapping[int, str],
    event_times: Mapping[int, str],
    memberships: Mapping[int, list[MembershipInterval]],
    named_vote_ids: set[int],
    amendment_ids: set[int],
    retrieved_at: str,
    vote_results_last_modified: str,
    event_questions_last_modified: str,
    roster_last_modified: str,
    faction_transitions_last_modified: str,
) -> dict[str, object]:
    """Aggregate all approved metrics from official per-event member votes."""
    if not amendment_ids <= named_vote_ids:
        raise ValueError("amendment IDs must be a subset of named-vote IDs")
    relevant_ids = named_vote_ids - amendment_ids
    missing_names = relevant_ids - set(event_names)
    if missing_names:
        sample = ", ".join(str(value) for value in sorted(missing_names)[:5])
        raise ValueError(f"event names missing for relevant IDs: {sample}")
    missing_times = relevant_ids - set(event_times)
    if missing_times:
        sample = ", ".join(str(value) for value in sorted(missing_times)[:5])
        raise ValueError(f"event timestamps missing for relevant IDs: {sample}")

    daily: dict[str, dict[str, object]] = {}
    source_rows = 0
    relevant_votes = 0
    law_stage_votes = 0
    passed_law_stage_votes = 0
    relevant_dates: set[str] = set()

    for row in rows:
        source_rows += 1
        event_id = _event_id(row.get("id_event"))
        if event_id is None or event_id not in relevant_ids:
            continue
        name = event_names[event_id]
        if is_signal_name(name) or is_unnumbered_amendment_name(name):
            continue

        date = str(row.get("date_agenda", "")).strip()
        if not DATE_PATTERN.fullmatch(date):
            continue
        relevant_votes += 1
        relevant_dates.add(date)
        day = daily.setdefault(date, _empty_day())
        faction_votes = parse_member_votes(
            row.get("results"),
            event_time=event_times[event_id],
            memberships=memberships,
        )

        day_factions = day["factions"]
        for faction_id, vote_counts in faction_votes.items():
            faction_target = day_factions.setdefault(faction_id, _empty_faction())
            _update_faction_diagnostics(faction_target, vote_counts)

        if law_stage(name) is None:
            continue
        law_stage_votes += 1
        total_for = sum(counts[1] for counts in faction_votes.values())
        if total_for < 226:
            continue

        passed_law_stage_votes += 1
        coalition = day["coalition"]
        coalition["passed"] += 1
        sn_for = faction_votes.get(SN_FACTION_ID, Counter())[1]
        if sn_for >= 226:
            coalition["sn_alone"] += 1
            continue

        coalition["sn_dependent"] += 1
        partners = coalition["partners"]
        for faction_id, vote_counts in faction_votes.items():
            if faction_id == SN_FACTION_ID:
                continue
            partner = partners.setdefault(
                faction_id,
                {"for_votes": 0, "opportunities": 0, "strictly_necessary_votes": 0},
            )
            partner_for = vote_counts[1]
            partner["for_votes"] += partner_for
            partner["opportunities"] += sum(
                vote_counts[code] for code in VALID_VOTE_CODES
            )
            if total_for - partner_for < 226:
                partner["strictly_necessary_votes"] += 1

    ordered_daily: dict[str, object] = {}
    for date in sorted(daily):
        day = daily[date]
        ordered_factions = {
            faction_id: dict(day["factions"][faction_id])
            for faction_id in sorted(day["factions"], key=int)
        }
        coalition = day["coalition"]
        ordered_partners = {
            faction_id: dict(coalition["partners"][faction_id])
            for faction_id in sorted(coalition["partners"], key=int)
        }
        ordered_daily[date] = {
            "factions": ordered_factions,
            "coalition": {
                "passed": coalition["passed"],
                "sn_alone": coalition["sn_alone"],
                "sn_dependent": coalition["sn_dependent"],
                "partners": ordered_partners,
            },
        }

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "vote_event_flags_schema_version": EVENT_FLAGS_SCHEMA_VERSION,
            "retrieved_at": retrieved_at,
            "vote_results_last_modified": vote_results_last_modified,
            "event_questions_last_modified": event_questions_last_modified,
            "roster_last_modified": roster_last_modified,
            "faction_transitions_last_modified": faction_transitions_last_modified,
            "min_date": min(relevant_dates) if relevant_dates else None,
            "max_date": max(relevant_dates) if relevant_dates else None,
            "counts": {
                "source_rows": source_rows,
                "relevant_votes": relevant_votes,
                "law_stage_votes": law_stage_votes,
                "passed_law_stage_votes": passed_law_stage_votes,
            },
        },
        "daily": ordered_daily,
    }


def parse_vote_results(
    stream: TextIO,
    *,
    event_names: Mapping[int, str],
    event_times: Mapping[int, str],
    memberships: Mapping[int, list[MembershipInterval]],
    named_vote_ids: set[int],
    amendment_ids: set[int],
    retrieved_at: str,
    vote_results_last_modified: str,
    event_questions_last_modified: str,
    roster_last_modified: str,
    faction_transitions_last_modified: str,
) -> dict[str, object]:
    reader = csv.DictReader(stream, delimiter="\t")
    required = {"date_agenda", "id_event", "results"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"vote TSV is missing required columns: {', '.join(missing)}")
    return aggregate_vote_rows(
        reader,
        event_names=event_names,
        event_times=event_times,
        memberships=memberships,
        named_vote_ids=named_vote_ids,
        amendment_ids=amendment_ids,
        retrieved_at=retrieved_at,
        vote_results_last_modified=vote_results_last_modified,
        event_questions_last_modified=event_questions_last_modified,
        roster_last_modified=roster_last_modified,
        faction_transitions_last_modified=faction_transitions_last_modified,
    )


def serialize_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"


def write_payload(payload: Mapping[str, object], destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(serialize_payload(payload), encoding="utf-8", newline="\n")
    os.replace(temporary, destination)


def output_is_current(
    destination: Path,
    vote_results_last_modified: str,
    event_questions_last_modified: str,
    roster_last_modified: str,
    faction_transitions_last_modified: str,
) -> bool:
    if not all(
        (
            vote_results_last_modified,
            event_questions_last_modified,
            roster_last_modified,
            faction_transitions_last_modified,
        )
    ):
        return False
    try:
        payload = json.loads(destination.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        return (
            meta.get("schema_version") == SCHEMA_VERSION
            and meta.get("vote_event_flags_schema_version")
            == EVENT_FLAGS_SCHEMA_VERSION
            and meta.get("vote_results_last_modified")
            == vote_results_last_modified
            and meta.get("event_questions_last_modified")
            == event_questions_last_modified
            and meta.get("roster_last_modified") == roster_last_modified
            and meta.get("faction_transitions_last_modified")
            == faction_transitions_last_modified
            and isinstance(payload.get("daily"), dict)
        )
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def _content_length(headers: Mapping[str, str]) -> int:
    try:
        return int(headers.get("content-length", "0") or 0)
    except ValueError:
        return 0


def main() -> int:
    print(f"HEAD {VOTE_RESULTS_URL}", flush=True)
    vote_headers = curl_head(VOTE_RESULTS_URL)
    print(f"HEAD {EVENT_QUESTIONS_URL}", flush=True)
    event_headers = curl_head(EVENT_QUESTIONS_URL)
    print(f"HEAD {ROSTER_URL}", flush=True)
    roster_headers = curl_head(ROSTER_URL)
    print(f"HEAD {FACTION_TRANSITIONS_URL}", flush=True)
    transition_headers = curl_head(FACTION_TRANSITIONS_URL)
    vote_last_modified = vote_headers.get("last-modified", "")
    event_last_modified = event_headers.get("last-modified", "")
    roster_last_modified = roster_headers.get("last-modified", "")
    transition_last_modified = transition_headers.get("last-modified", "")
    print(
        f"  Vote TSV: {vote_last_modified or '[missing]'} "
        f"({_content_length(vote_headers) / 1024 / 1024:.1f} MB)",
        flush=True,
    )
    print(
        f"  Event CSV: {event_last_modified or '[missing]'} "
        f"({_content_length(event_headers) / 1024 / 1024:.1f} MB)",
        flush=True,
    )
    print(
        f"  MP roster: {roster_last_modified or '[missing]'} "
        f"({_content_length(roster_headers) / 1024 / 1024:.1f} MB)",
        flush=True,
    )
    print(
        f"  Faction transitions: {transition_last_modified or '[missing]'} "
        f"({_content_length(transition_headers) / 1024 / 1024:.1f} MB)",
        flush=True,
    )

    if output_is_current(
        OUTPUT_PATH,
        vote_last_modified,
        event_last_modified,
        roster_last_modified,
        transition_last_modified,
    ):
        print("Skip — source Last-Modified values and schema are unchanged")
        return 0

    # All ignored files are downloaded on every rebuild. This makes a clean
    # GitHub Actions checkout independent of whether either earlier builder
    # skipped after consulting its committed metadata.
    print("Downloading current vote TSV...", flush=True)
    curl_download(VOTE_RESULTS_URL, VOTE_RESULTS_PATH)
    print("Downloading current event CSV...", flush=True)
    curl_download(EVENT_QUESTIONS_URL, EVENT_QUESTIONS_PATH)
    print("Downloading current MP roster...", flush=True)
    curl_download(ROSTER_URL, ROSTER_PATH)
    print("Downloading current faction transitions...", flush=True)
    curl_download(FACTION_TRANSITIONS_URL, FACTION_TRANSITIONS_PATH)

    with EVENT_QUESTIONS_PATH.open(encoding="utf-8-sig", newline="") as stream:
        (
            event_names,
            event_times,
            derived_named_ids,
            derived_amendment_ids,
        ) = read_event_questions(stream)
    with ROSTER_PATH.open(encoding="utf-8-sig", newline="") as stream:
        roster = read_roster(stream)
    with FACTION_TRANSITIONS_PATH.open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        histories, transition_rows = read_faction_transitions(stream)
    memberships = build_membership_index(roster, histories)
    print(
        f"  Reconstructed {len(memberships)} voting IDs from "
        f"{transition_rows} faction intervals",
        flush=True,
    )
    loaded_flags = load_vote_event_flags(EVENT_FLAGS_PATH, event_last_modified)
    if loaded_flags is None:
        print("  vote_event_flags.json unavailable/stale — using event CSV classifier")
        named_vote_ids, amendment_ids = derived_named_ids, derived_amendment_ids
    else:
        named_vote_ids, amendment_ids = loaded_flags
        print("  Using vote_event_flags.json classifications")

    with VOTE_RESULTS_PATH.open(encoding="utf-8-sig", newline="") as stream:
        payload = parse_vote_results(
            stream,
            event_names=event_names,
            event_times=event_times,
            memberships=memberships,
            named_vote_ids=named_vote_ids,
            amendment_ids=amendment_ids,
            retrieved_at=utc_now(),
            vote_results_last_modified=vote_last_modified,
            event_questions_last_modified=event_last_modified,
            roster_last_modified=roster_last_modified,
            faction_transitions_last_modified=transition_last_modified,
        )
    write_payload(payload, OUTPUT_PATH)

    counts = payload["meta"]["counts"]
    print(
        "Done — "
        f"{counts['relevant_votes']} relevant votes, "
        f"{counts['law_stage_votes']} law-stage votes, "
        f"{counts['passed_law_stage_votes']} passed",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
