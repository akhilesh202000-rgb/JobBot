# tests/test_airtable.py
#
# Ausführen (aus dem Projekt-Root):
#   python -m unittest discover -s tests -t . -v

import datetime as dt
import unittest
from unittest import mock

from util.airtable import (
    _unknown_fields,
    build_fields,
    build_update_fields,
    delete_legacy_urls,
    district_number,
    fallback_job,
    is_legacy_url,
    normalize_posted,
    normalize_url,
)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class UnknownFieldTests(unittest.TestCase):
    def test_escaped_field_name(self):
        body = (
            '{"error":{"type":"UNKNOWN_FIELD_NAME",'
            '"message":"Unknown field name: \\"Location\\""}}'
        )
        self.assertEqual(_unknown_fields(FakeResponse(body)), ["Location"])

    def test_plain_field_name(self):
        self.assertEqual(
            _unknown_fields(FakeResponse('Unknown field name: "District"')),
            ["District"],
        )

    def test_multiple_field_names(self):
        body = 'Unknown field names: "Location", "District"'
        self.assertEqual(_unknown_fields(FakeResponse(body)), ["Location", "District"])

    def test_other_error_is_ignored(self):
        self.assertEqual(
            _unknown_fields(FakeResponse('{"error":{"type":"INVALID_VALUE"}}')),
            [],
        )


class BuildFieldsTests(unittest.TestCase):
    def test_required_and_optional_fields(self):
        job = {
            "title": "React Developer",
            "url": "https://example.com/1",
            "description": "React",
            "fit": 7,
            "distance_km": 3.4,
            "company": "ACME",
            "location": "Wien",
        }
        fields = build_fields(job)
        self.assertEqual(fields["Job Title"], "React Developer")
        self.assertEqual(fields["Match Score"], 7.0)
        self.assertEqual(fields["Distance (km)"], 3.4)
        self.assertEqual(fields["Company"], "ACME")

    def test_skip_fields(self):
        job = {
            "title": "React Developer",
            "url": "https://example.com/1",
            "fit": 7,
            "company": "ACME",
            "location": "Wien",
        }
        fields = build_fields(job, skip_fields={"Company", "Location"})
        self.assertNotIn("Company", fields)
        self.assertNotIn("Location", fields)
        self.assertIn("Job Title", fields)


class NormalizePostedTests(unittest.TestCase):
    def test_iso_and_german_dates(self):
        self.assertEqual(normalize_posted("2026-10-20"), "2026-10-20")
        self.assertEqual(normalize_posted("18.03.2026"), "2026-03-18")

    def test_relative_dates(self):
        today = dt.date.today()
        self.assertEqual(
            normalize_posted("vor 3 Tagen veröffentlicht"),
            (today - dt.timedelta(days=3)).isoformat(),
        )
        self.assertEqual(
            normalize_posted("Gestern veröffentlicht"),
            (today - dt.timedelta(days=1)).isoformat(),
        )
        self.assertEqual(normalize_posted("Heute"), today.isoformat())

    def test_unknown_is_dropped(self):
        self.assertEqual(normalize_posted("irgendwann"), "")
        self.assertEqual(normalize_posted(""), "")

    def test_build_fields_normalizes_posted(self):
        job = {
            "title": "React Developer",
            "url": "https://example.com/1",
            "fit": 7,
            "posted": "vor 2 Tagen",
        }
        fields = build_fields(job)
        self.assertEqual(
            fields["Posted"],
            (dt.date.today() - dt.timedelta(days=2)).isoformat(),
        )


class DistrictNumberTests(unittest.TestCase):
    def test_names_and_unknown(self):
        self.assertEqual(district_number("Leopoldstadt"), 2)
        self.assertEqual(district_number("Donaustadt"), 22)
        self.assertEqual(district_number("Favoriten (Süden, ca.)"), 10)
        self.assertIsNone(district_number("Wien (Bezirk unbekannt)"))
        self.assertIsNone(district_number(""))


class NormalizeUrlTests(unittest.TestCase):
    def test_host_www_slash_and_scheme(self):
        self.assertEqual(
            normalize_url("https://www.karriere.at/jobs/1/"),
            "https://karriere.at/jobs/1",
        )
        self.assertEqual(
            normalize_url("http://metajob.at/dres/jc?p=1"),
            "https://metajob.at/dres/jc?p=1",
        )


class BuildUpdateFieldsTests(unittest.TestCase):
    def test_fills_only_missing_optional_fields(self):
        record = {"URL": "https://www.karriere.at/jobs/1", "Company": "ACME"}
        job = {
            "company": "ACME",
            "description": "React und TypeScript",
            "location": "Wien 2. Bezirk (Leopoldstadt)",
            "district": "Leopoldstadt",
            "district_number": 2,
            "distance_km": 1.4,
            "home_office": True,
            "source": "karriere.at",
            "posted": "2026-10-20",
            "employment_type": "Vollzeit",
        }
        fields = build_update_fields(record, job)
        self.assertEqual(fields["Location"], "Wien 2. Bezirk (Leopoldstadt)")
        self.assertEqual(fields["District"], 2)
        self.assertEqual(fields["Distance (km)"], 1.4)
        self.assertTrue(fields["Home Office"])
        self.assertEqual(fields["Source"], "karriere.at")
        self.assertEqual(fields["Posted"], "2026-10-20")
        self.assertEqual(fields["Employment Type"], "Vollzeit")
        self.assertEqual(fields["Description"], "React und TypeScript")
        self.assertNotIn("Company", fields)

    def test_keeps_existing_values(self):
        record = {
            "URL": "https://www.karriere.at/jobs/1",
            "Company": "ACME",
            "Description": "alt",
            "Location": "Wien",
            "District": 2,
            "Distance (km)": 1.4,
            "Home Office": True,
            "Source": "karriere.at",
            "Posted": "2026-10-20",
            "Employment Type": "Vollzeit",
        }
        job = {
            "company": "ACME",
            "description": "neu",
            "location": "Wien 2. Bezirk (Leopoldstadt)",
            "district": "Leopoldstadt",
            "distance_km": 1.4,
            "home_office": True,
            "source": "karriere.at",
            "posted": "2026-10-21",
            "employment_type": "Teilzeit",
        }
        self.assertEqual(build_update_fields(record, job), {})


class FallbackJobTests(unittest.TestCase):
    def test_parses_cover_letter(self):
        record = {
            "URL": "https://www.metajob.at/dres/jc?p=1",
            "Job Title": "Frontend Developer",
            "Company": "ACME",
            "Description": "",
            "Cover Letter / Anschreiben": (
                "Fit 8.0/10 · ~1.4 km von Kaisermühlen U1 (1220 Wien) · "
                "Leopoldstadt · Home Office möglich · Vollzeit · vor 41 Tagen"
            ),
        }
        job = fallback_job(record)
        self.assertEqual(job["source"], "metajob.at")
        self.assertEqual(job["location"], "Wien (Leopoldstadt)")
        self.assertEqual(job["district"], "Leopoldstadt")
        self.assertEqual(job["district_number"], 2)
        self.assertEqual(job["distance_km"], 1.4)
        self.assertTrue(job["home_office"])
        self.assertEqual(job["employment_type"], "Vollzeit")
        self.assertEqual(job["posted"], "vor 41 Tagen")
        self.assertIn("Frontend Developer", job["description"])


class LegacyUrlTests(unittest.TestCase):
    def test_legacy_hosts(self):
        self.assertTrue(is_legacy_url("https://weworkremotely.com/jobs/123"))
        self.assertTrue(is_legacy_url("https://www.weworkremotely.com/jobs/123"))
        self.assertTrue(is_legacy_url("https://remoteOK.com/remote-jobs/1"))

    def test_current_and_unknown_hosts(self):
        self.assertFalse(is_legacy_url("https://www.karriere.at/jobs/1"))
        self.assertFalse(is_legacy_url("https://devjobs.at/job/abc"))
        self.assertFalse(is_legacy_url("https://www.metajob.at/dres/jc?p=1"))
        self.assertFalse(is_legacy_url(""))
        # Kein Prefix-Match: notweworkremotely.com ist eine andere Domain.
        self.assertFalse(is_legacy_url("https://notweworkremotely.com/job"))


class DeleteLegacyTests(unittest.TestCase):
    def test_rows_with_source_are_protected(self):
        records = [
            {
                "id": "rec1",
                "url": "https://remoteok.com/remote-jobs/1",
                "fields": {"URL": "https://remoteok.com/remote-jobs/1", "Source": "remoteok.com"},
            },
            {
                "id": "rec2",
                "url": "https://remoteok.com/remote-jobs/2",
                "fields": {"URL": "https://remoteok.com/remote-jobs/2"},
            },
            {
                "id": "rec3",
                "url": "https://example.com/job/3",
                "fields": {"URL": "https://example.com/job/3"},
            },
        ]

        with mock.patch(
            "util.airtable.get_records", return_value=records
        ), mock.patch(
            "util.airtable.delete_records", return_value=1
        ) as delete:
            deleted = delete_legacy_urls("base", "table", "pat")

        self.assertEqual(deleted, 1)
        delete.assert_called_once_with("base", "table", "pat", ["rec2"])


if __name__ == "__main__":
    unittest.main()
