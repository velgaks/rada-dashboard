import io
import json
import tempfile
import unittest
from pathlib import Path

from build_faction_diagnostics import (
    EVENT_FLAGS_SCHEMA_VERSION,
    SCHEMA_VERSION,
    aggregate_vote_rows,
    build_membership_index,
    faction_at,
    is_signal_name,
    is_unnumbered_amendment_name,
    law_stage,
    output_is_current,
    parse_member_votes,
    read_event_questions,
    read_faction_transitions,
    read_roster,
    serialize_payload,
)


def member_records(faction_id, vote_code, count, start):
    return [f"{start + offset}:{faction_id}:{vote_code}" for offset in range(count)]


def vote_row(date, event_id, records):
    return {"date_agenda": date, "id_event": str(event_id), "results": "|".join(records)}


def synthetic_memberships(rows):
    memberships = {}
    for row in rows:
        for entry in row["results"].split("|"):
            if not entry:
                continue
            deputy_id, faction_id, _ = entry.split(":")
            memberships[int(deputy_id)] = [
                ("2019-08-29T00:00:00", None, str(int(faction_id)))
            ]
    return memberships


def aggregation_context(rows, event_names):
    return {
        "event_names": event_names,
        "event_times": {
            event_id: "2026-01-10T12:00:00" for event_id in event_names
        },
        "memberships": synthetic_memberships(rows),
    }


META = {
    "retrieved_at": "2026-08-20T19:00:00Z",
    "vote_results_last_modified": "Wed, 19 Aug 2026 12:56:00 GMT",
    "event_questions_last_modified": "Thu, 20 Aug 2026 10:56:09 GMT",
    "roster_last_modified": "Tue, 18 Aug 2026 14:56:18 GMT",
    "faction_transitions_last_modified": "Wed, 19 Aug 2026 01:58:44 GMT",
}


class NameClassifierTests(unittest.TestCase):
    def test_signal_classifier_is_case_insensitive_and_normalized(self):
        self.assertTrue(is_signal_name("  СИГНАЛЬНЕ   голосування "))
        self.assertTrue(is_signal_name("Повторне сигнальне голосування"))
        self.assertFalse(is_signal_name("Поіменне голосування за основу"))

    def test_law_stage_accepts_substantive_law_and_code_stages(self):
        accepted = {
            "Поіменне голосування про проєкт Закону про бюджет (№1) - за основу": "first",
            "Поіменне голосування про проект Кодексу України (№2) - у першому читанні": "first",
            "Поіменне голосування про проєкт Закону про освіту (№3) - у другому читанні та в цілому": "second",
            "Поіменне голосування про проєкт Закону про освіту (№31) - в другому читанні": "second",
            "Поіменне голосування про проєкт Закону про освіту (№32) - у повторному другому читанні": "second",
            "Поіменне голосування про проєкт Закону про освіту (№33) - в повторному другому читанні": "second",
            "Поіменне голосування про проект Закону про службу (№4) - в цілому": "final",
            "Поіменне голосування про проєкт Закону про оборону (№5) - за основу з урахуванням пропозицій комітету": "first",
        }
        for name, expected in accepted.items():
            with self.subTest(name=name):
                self.assertEqual(law_stage(name), expected)

    def test_law_stage_rejects_procedures_resolutions_and_amendments(self):
        rejected = [
            "Поіменне голосування про включення до порядку денного проєкту Закону про бюджет (№1)",
            "Поіменне голосування про проєкт Постанови про звіт (№2) - в цілому",
            "Поіменне голосування про поправку №2 до проєкту Закону про освіту",
            "Поіменне голосування про проєкт Закону про службу (№4) - направлення на повторне перше читання",
        ]
        for name in rejected:
            with self.subTest(name=name):
                self.assertIsNone(law_stage(name))

    def test_unnumbered_amendment_rule_is_specific_to_amendment_action(self):
        self.assertTrue(
            is_unnumbered_amendment_name(
                "Поіменне голосування про поправку до проекту Закону про бюджет"
            )
        )
        self.assertFalse(
            is_unnumbered_amendment_name(
                "Поіменне голосування про проект Закону про ратифікацію "
                "Поправки до Монреальського протоколу - за основу"
            )
        )

    def test_event_csv_fallback_excludes_registration_and_finds_amendment(self):
        source = io.StringIO(
            "date_agenda,type_event,date_event,name_event,id_event\n"
            "2026-01-01,0,2026-01-01T10:00:00,Поіменне голосування за основу,10\n"
            "2026-01-01,0,2026-01-01T10:01:00,Поіменне голосування за поправку № 7,11\n"
            "2026-01-01,1,2026-01-01T10:02:00,Електронна реєстрація,12\n"
        )
        names, times, named, amendments = read_event_questions(source)
        self.assertEqual(set(names), {10, 11})
        self.assertEqual(times[10], "2026-01-01T10:00:00")
        self.assertEqual(named, {10, 11})
        self.assertEqual(amendments, {11})


class HistoricalMembershipTests(unittest.TestCase):
    def setUp(self):
        roster_source = io.StringIO(
            "id_mp,name\n"
            "1,Старе Ім'я\n"
            "9,Нове Ім'я\n"
        )
        transition_source = io.StringIO(
            "num,convocation,full_name,fra_name,date_in,date_out\n"
            "1,9,Старе Ім'я,Позафракційні,2019-08-29T12:00:00,2019-08-29T13:00:00\n"
            "2,9,Старе Ім'я,\"Фракція політичної партії \"\"ОПОЗИЦІЙНА ПЛАТФОРМА-ЗА ЖИТТЯ\"\"\",2019-08-29T13:00:00,2022-04-14T12:00:00\n"
            "3,9,Нове Ім'я,\"Депутатська група \"\"Платформа за життя та мир\"\" у Верховній Раді України\",2022-04-14T12:00:00,\n"
        )
        roster = read_roster(roster_source)
        histories, _ = read_faction_transitions(transition_source)
        self.memberships = build_membership_index(roster, histories)

    def test_old_and_new_voting_ids_share_event_time_history(self):
        self.assertEqual(
            faction_at(self.memberships, 1, "2020-01-01T10:00:00"), "2"
        )
        self.assertEqual(
            faction_at(self.memberships, 9, "2023-01-01T10:00:00"), "9"
        )

    def test_tsv_faction_is_ignored_in_favour_of_event_time_history(self):
        parsed = parse_member_votes(
            "1:10:1",
            event_time="2020-01-01T10:00:00",
            memberships=self.memberships,
        )
        self.assertEqual(parsed, {"2": {1: 1}})


class FactionAggregationTests(unittest.TestCase):
    def test_member_parser_rejects_malformed_and_unknown_codes(self):
        memberships = {
            1: [("2019-01-01T00:00:00", None, "1")],
            2: [("2019-01-01T00:00:00", None, "1")],
        }
        parsed = parse_member_votes(
            "1:01:1|2:1:4|bad|3:x:1|4:1:9",
            event_time="2026-01-01T10:00:00",
            memberships=memberships,
        )
        self.assertEqual(parsed, {"1": {1: 1, 4: 1}})

    def test_daily_participation_and_discipline_exclusions(self):
        event_names = {
            10: "Поіменне голосування про процедурне питання",
            11: "Поіменне голосування про поправку №1",
            12: "Сигнальне голосування",
            13: "Поіменне голосування про поправку до проекту Закону про бюджет",
        }
        rows = [
            vote_row(
                "2026-01-10",
                10,
                member_records(1, 1, 2, 1)
                + member_records(1, 2, 1, 3)
                + member_records(1, 4, 1, 4)
                + member_records(1, 0, 1, 5)
                + member_records(2, 1, 1, 6)
                + member_records(2, 2, 1, 7)
                + member_records(2, 4, 1, 8)
                + member_records(3, 3, 1, 9)
                + member_records(3, 4, 1, 10)
                + member_records(3, 0, 1, 11),
            ),
            vote_row("2026-01-10", 11, member_records(1, 1, 3, 20)),
            vote_row("2026-01-10", 12, member_records(1, 1, 3, 30)),
            vote_row("2026-01-10", 13, member_records(1, 1, 3, 40)),
        ]
        payload = aggregate_vote_rows(
            rows,
            **aggregation_context(rows, event_names),
            named_vote_ids={10, 11, 12, 13},
            amendment_ids={11},
            **META,
        )
        factions = payload["daily"]["2026-01-10"]["factions"]

        self.assertEqual(
            factions["1"],
            {
                "active": 3,
                "present": 4,
                "total": 5,
                "votes": 1,
                "discipline_agree": 2,
                "discipline_total": 3,
                "discipline_ties": 0,
                "discipline_low_activity": 0,
            },
        )
        self.assertEqual(factions["2"]["discipline_ties"], 1)
        self.assertEqual(factions["2"]["discipline_total"], 0)
        self.assertEqual(factions["3"]["discipline_low_activity"], 1)
        self.assertEqual(payload["meta"]["counts"]["source_rows"], 4)
        self.assertEqual(payload["meta"]["counts"]["relevant_votes"], 1)

    def test_law_stage_coalition_and_partner_dependence(self):
        names = {
            20: "Поіменне голосування про проєкт Закону про А (№1) - за основу",
            21: "Поіменне голосування про проект Закону про Б (№2) - у другому читанні та в цілому",
            22: "Поіменне голосування про проєкт Закону про В (№3) - в цілому",
        }
        rows = [
            vote_row(
                "2026-02-01",
                20,
                member_records(1, 1, 226, 1) + member_records(3, 4, 3, 300),
            ),
            vote_row(
                "2026-02-01",
                21,
                member_records(1, 1, 200, 1000)
                + member_records(3, 1, 20, 1300)
                + member_records(4, 1, 6, 1400)
                + member_records(0, 0, 1, 1500),
            ),
            vote_row(
                "2026-02-01",
                22,
                member_records(1, 1, 200, 2000)
                + member_records(3, 1, 25, 2300),
            ),
        ]
        payload = aggregate_vote_rows(
            rows,
            **aggregation_context(rows, names),
            named_vote_ids={20, 21, 22},
            amendment_ids=set(),
            **META,
        )
        coalition = payload["daily"]["2026-02-01"]["coalition"]

        self.assertEqual(
            {key: coalition[key] for key in ("passed", "sn_alone", "sn_dependent")},
            {"passed": 2, "sn_alone": 1, "sn_dependent": 1},
        )
        self.assertEqual(
            coalition["partners"]["3"],
            {"for_votes": 20, "opportunities": 20, "strictly_necessary_votes": 1},
        )
        self.assertEqual(
            coalition["partners"]["4"],
            {"for_votes": 6, "opportunities": 6, "strictly_necessary_votes": 1},
        )
        self.assertEqual(
            coalition["partners"]["0"],
            {"for_votes": 0, "opportunities": 1, "strictly_necessary_votes": 0},
        )
        self.assertEqual(
            payload["meta"]["counts"],
            {
                "source_rows": 3,
                "relevant_votes": 3,
                "law_stage_votes": 3,
                "passed_law_stage_votes": 2,
            },
        )

    def test_serialization_is_deterministic_across_row_order(self):
        names = {
            30: "Поіменне голосування про питання",
            31: "Поіменне голосування про інше питання",
        }
        rows = [
            vote_row("2020-01-02", 30, member_records(3, 1, 2, 1)),
            vote_row("2019-08-29", 31, member_records(1, 3, 2, 10)),
        ]
        kwargs = {
            **aggregation_context(rows, names),
            "named_vote_ids": {30, 31},
            "amendment_ids": set(),
            **META,
        }
        forward = aggregate_vote_rows(rows, **kwargs)
        reverse = aggregate_vote_rows(reversed(rows), **kwargs)
        self.assertEqual(serialize_payload(forward), serialize_payload(reverse))
        json.loads(serialize_payload(forward))

    def test_skip_requires_matching_schema_and_all_last_modified_values(self):
        payload = {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "vote_event_flags_schema_version": EVENT_FLAGS_SCHEMA_VERSION,
                **{key: value for key, value in META.items() if key.endswith("last_modified")},
            },
            "daily": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostics.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(
                output_is_current(
                    path,
                    META["vote_results_last_modified"],
                    META["event_questions_last_modified"],
                    META["roster_last_modified"],
                    META["faction_transitions_last_modified"],
                )
            )
            self.assertFalse(
                output_is_current(
                    path,
                    "new vote Last-Modified",
                    META["event_questions_last_modified"],
                    META["roster_last_modified"],
                    META["faction_transitions_last_modified"],
                )
            )
            payload["meta"]["schema_version"] = SCHEMA_VERSION - 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(
                output_is_current(
                    path,
                    META["vote_results_last_modified"],
                    META["event_questions_last_modified"],
                    META["roster_last_modified"],
                    META["faction_transitions_last_modified"],
                )
            )


if __name__ == "__main__":
    unittest.main()
