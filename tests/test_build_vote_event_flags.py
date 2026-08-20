import io
import json
import unittest

from build_vote_event_flags import (
    build_payload,
    is_amendment_name,
    parse_csv,
    serialize_payload,
)


CSV_HEADER = (
    "date_agenda,id_question,date_question,type_event,date_event,name_event,id_event\n"
)


class AmendmentClassifierTests(unittest.TestCase):
    def test_recognises_common_numbered_amendment_phrasings(self):
        names = [
            "Поіменне голосування за поправку №1",
            "Поіменне голосування по поправці № 27",
            "Підтвердження поправки №1045 у редакції комітету",
            "Голосування щодо поправок № 8 та № 9",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(is_amendment_name(name))

    def test_does_not_match_legal_title_with_word_amendment(self):
        self.assertFalse(
            is_amendment_name(
                "Проект Закону про Поправку до Монреальського протоколу"
            )
        )


class PayloadTests(unittest.TestCase):
    def test_classifies_named_votes_and_excludes_registration(self):
        csv_text = CSV_HEADER + """\
2026-08-20,1,2026-08-20T10:00:00,0,2026-08-20T10:01:00,Поіменне голосування за основу,101
2026-08-20,2,2026-08-20T10:02:00,0,2026-08-20T10:03:00,Поіменне голосування за поправку № 42,102
2026-08-20,3,2026-08-20T10:04:00,1,2026-08-20T10:05:00,Електронна реєстрація,103
2026-08-20,4,2026-08-20T10:06:00,0,2026-08-20T10:07:00,Проект Закону про Поправку до Монреальського протоколу,104
2026-08-20,5,2026-08-20T10:08:00,0,2026-08-20T10:09:00,Сигнальне голосування,105
2026-08-20,6,2026-08-20T10:10:00,8,2026-08-20T10:11:00,Виступ депутата,
"""
        payload = parse_csv(
            io.StringIO(csv_text),
            retrieved_at="2026-08-20T12:00:00Z",
            source_last_modified="Thu, 20 Aug 2026 10:56:09 GMT",
        )

        self.assertEqual(payload["named_vote_ids"], [101, 102, 104, 105])
        self.assertEqual(payload["amendment_ids"], [102])
        self.assertEqual(payload["meta"]["min_date"], "2026-08-20")
        self.assertEqual(payload["meta"]["max_date"], "2026-08-20")
        self.assertEqual(
            payload["meta"]["counts"],
            {"rows": 6, "named_votes": 4, "amendments": 1, "registrations": 1},
        )

    def test_output_is_deterministic_and_ids_are_sorted_and_deduplicated(self):
        rows = [
            {
                "date_agenda": "2020-02-02",
                "type_event": "0",
                "name_event": "Поправка № 3",
                "id_event": "9",
            },
            {
                "date_agenda": "2019-08-29",
                "type_event": "0",
                "name_event": "Звичайне голосування",
                "id_event": "2",
            },
            {
                "date_agenda": "2020-02-02",
                "type_event": "0",
                "name_event": "Поправка № 3",
                "id_event": "9",
            },
        ]
        kwargs = {
            "retrieved_at": "2026-08-20T12:00:00Z",
            "source_last_modified": "Thu, 20 Aug 2026 10:56:09 GMT",
        }
        forward = build_payload(rows, **kwargs)
        reverse = build_payload(reversed(rows), **kwargs)

        self.assertEqual(forward["named_vote_ids"], [2, 9])
        self.assertEqual(forward["amendment_ids"], [9])
        self.assertEqual(serialize_payload(forward), serialize_payload(reverse))
        json.loads(serialize_payload(forward))


if __name__ == "__main__":
    unittest.main()
