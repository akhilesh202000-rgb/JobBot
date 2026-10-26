# tests/test_metajob.py
#
# Ausführen (aus dem Projekt-Root):
#   env/bin/python -m unittest discover -s tests -t . -v

import unittest

from util.metajob import _normalize_row, _payload


class PayloadTests(unittest.TestCase):
    def test_search_payload_shape(self):
        payload = _payload("react", offset=20, token="z16m55")

        self.assertEqual(payload["h"], "1Dbc9D")
        self.assertEqual(payload["a0"]["a"]["c"], "react")
        self.assertEqual(payload["a0"]["a"]["e"], "Wien")
        self.assertEqual(payload["a0"]["e"], 20)
        self.assertEqual(payload["a0"]["c"], 20)
        self.assertEqual(payload["a0"]["q"], 8)
        self.assertEqual(payload["a0"]["s"], "z16m55")
        self.assertEqual(payload["a1"], 1)
        self.assertEqual(payload["a2"], 1)

    def test_first_page_has_no_offset(self):
        payload = _payload("react")
        self.assertNotIn("c", payload["a0"])
        self.assertNotIn("s", payload["a0"])


class NormalizeRowTests(unittest.TestCase):
    def test_row_fields(self):
        row = {
            "a": "jid-1",
            "c": "React Developer",
            "u": "ACME",
            "i": ["Wien", "Wien 2. Bezirk"],
            "g": "React &amp; TypeScript",
            "r": 3,
        }

        job = _normalize_row(row)

        self.assertEqual(job["id"], "jid-1")
        self.assertEqual(job["title"], "React Developer")
        self.assertEqual(job["company"], "ACME")
        self.assertEqual(job["locations"], ["Wien", "Wien 2. Bezirk"])
        self.assertEqual(job["description"], "React & TypeScript")
        self.assertEqual(job["posted"], "vor 3 Tagen")
        self.assertEqual(job["source"], "metajob.at")
        self.assertEqual(job["url"], "https://www.metajob.at/dres/jc?p=jid-1")

    def test_existing_url_wins(self):
        job = _normalize_row(
            {"a": "jid-1", "c": "Dev", "e": "https://example.com/job"}
        )
        self.assertEqual(job["url"], "https://example.com/job")

    def test_missing_id_has_no_url(self):
        job = _normalize_row({"c": "Dev"})
        self.assertEqual(job["url"], "")


if __name__ == "__main__":
    unittest.main()
