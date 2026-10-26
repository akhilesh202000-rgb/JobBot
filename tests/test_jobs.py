# tests/test_jobs.py
#
# Ausführen (aus dem Projekt-Root):
#   python -m unittest discover -s tests -t . -v

import unittest

from util.geo import best_vienna_location, parse_location
from util.jobs import (
    build_shortlist,
    is_react_relevant,
    is_title_excluded,
    score_job,
    years_required,
)


def make_job(**overrides):
    job = {
        "id": "1",
        "title": "React Frontend Developer",
        "url": "https://www.karriere.at/jobs/1",
        "company": "ACME",
        "description": "React und TypeScript, 3 Jahre Erfahrung.",
        "locations": ["Wien 2. Bezirk (Leopoldstadt)"],
        "home_office": True,
        "employment_type": "Vollzeit",
        "posted": "Heute veröffentlicht",
        "source": "karriere.at",
    }
    job.update(overrides)
    return job


class TitleExclusionTests(unittest.TestCase):
    def test_javascript_is_not_java(self):
        # Regression: "java" als Substring hat vorher ALLE JavaScript-Jobs gekillt.
        self.assertFalse(is_title_excluded("JavaScript Developer (React)"))
        self.assertFalse(is_title_excluded("Frontend Developer – JavaScript/TypeScript"))

    def test_java_role_is_excluded(self):
        self.assertTrue(is_title_excluded("Java Developer"))
        self.assertTrue(is_title_excluded("Junior Java Developer"))

    def test_senior_and_lead_are_excluded(self):
        self.assertTrue(is_title_excluded("Senior React Developer"))
        self.assertTrue(is_title_excluded("Lead Frontend Engineer"))
        self.assertTrue(is_title_excluded("(Senior) Frontend Developer"))

    def test_internship_is_excluded(self):
        self.assertTrue(is_title_excluded("Praktikum Frontend-Entwicklung"))
        self.assertTrue(is_title_excluded("Frontend Developer Internship"))

    def test_junior_is_excluded_for_mid_level_target(self):
        self.assertTrue(is_title_excluded("(Junior) Frontend Developer"))

    def test_angular_and_vue_are_excluded(self):
        self.assertTrue(is_title_excluded("Angular Frontend Developer"))
        self.assertTrue(is_title_excluded("Vue.js Developer"))

    def test_react_fullstack_with_backend_tech_is_kept(self):
        self.assertFalse(is_title_excluded("Full Stack Developer (.NET/React)"))

    def test_tester_and_backend_are_excluded(self):
        self.assertTrue(is_title_excluded("Test Automation Engineer"))
        self.assertTrue(is_title_excluded("Backend Engineer"))

    def test_designer_and_staff_are_excluded(self):
        self.assertTrue(is_title_excluded("Staff Product Designer - Mobile"))
        self.assertTrue(is_title_excluded("Senior Product Designer"))

    def test_project_engineer_is_excluded(self):
        self.assertTrue(
            is_title_excluded("Projekt-Ingenieur / IT-Solutions Engineer")
        )


class RelevanceTests(unittest.TestCase):
    def test_react_in_title(self):
        self.assertTrue(is_react_relevant("React Developer", ""))

    def test_react_only_in_description_with_dev_title(self):
        self.assertTrue(is_react_relevant("Software Developer", "Stack: React, TypeScript"))

    def test_no_react(self):
        self.assertFalse(is_react_relevant("Java Developer", "Spring Boot, Kafka"))


class YearsTests(unittest.TestCase):
    def test_range_uses_upper_bound(self):
        self.assertEqual(years_required("2-4 years of experience"), 4)

    def test_plus_years(self):
        self.assertEqual(years_required("5+ years of experience"), 5)

    def test_none(self):
        self.assertIsNone(years_required("Erfahrung mit React"))


class ScoreTests(unittest.TestCase):
    def test_react_native_typescript_scores_high(self):
        self.assertGreaterEqual(
            score_job("React Native Developer", "TypeScript, Expo, Redux Toolkit"),
            9,
        )

    def test_five_years_penalty(self):
        self.assertLessEqual(score_job("React Developer", "5+ years of experience"), 7)

    def test_fullstack_penalty(self):
        self.assertLess(
            score_job("Full Stack Developer", "React, TypeScript"),
            score_job("React Developer", "TypeScript"),
        )


class LocationTests(unittest.TestCase):
    def test_district(self):
        location = parse_location("Wien 22. Bezirk (Donaustadt)")
        self.assertIsNotNone(location)
        self.assertEqual(location["district"], 22)
        self.assertTrue(location["in_vienna"])

    def test_plz(self):
        location = parse_location("1220 Wien")
        self.assertIsNotNone(location)
        self.assertEqual(location["district"], 22)

    def test_short_district(self):
        location = parse_location("Wien 9")
        self.assertIsNotNone(location)
        self.assertEqual(location["district"], 9)

    def test_plz_is_not_parsed_as_short_district(self):
        location = parse_location("Wien 1220")
        self.assertIsNotNone(location)
        self.assertEqual(location["district"], 22)

    def test_plain_wien(self):
        location = parse_location("Wien")
        self.assertIsNotNone(location)
        self.assertIsNone(location["district"])
        self.assertTrue(location["in_vienna"])

    def test_non_vienna(self):
        self.assertIsNone(parse_location("Graz"))
        self.assertIsNone(parse_location("Berlin"))

    def test_best_location_picks_vienna(self):
        location = best_vienna_location(["Graz", "Wien 2. Bezirk (Leopoldstadt)"])
        self.assertIsNotNone(location)
        self.assertEqual(location["district"], 2)

    def test_distance_ordering(self):
        leopoldstadt = parse_location("Wien 2. Bezirk (Leopoldstadt)")["km"]
        favoriten = parse_location("Wien 10. Bezirk (Favoriten)")["km"]
        liesing = parse_location("Wien 23. Bezirk (Liesing)")["km"]
        self.assertLess(leopoldstadt, favoriten)
        self.assertLess(favoriten, liesing)


class ShortlistTests(unittest.TestCase):
    def test_sorted_by_distance(self):
        jobs = [
            make_job(id="far", url="https://x/1", locations=["Wien 23. Bezirk (Liesing)"]),
            make_job(id="near", url="https://x/2", locations=["Wien 2. Bezirk (Leopoldstadt)"]),
        ]
        shortlist = build_shortlist(jobs)
        self.assertEqual(shortlist[0]["id"], "near")
        self.assertEqual(shortlist[1]["id"], "far")

    def test_fit_breaks_ties_within_a_distance_band(self):
        # 1220 (~3.4 km) vs. "Wien" (~3.5 km): gleiche 1-km-Band, Fit gewinnt.
        low_fit = make_job(
            id="low",
            url="https://x/3",
            title="Fullstack Developer",
            description="React",
            locations=["Wien 22. Bezirk (Donaustadt)"],
        )
        high_fit = make_job(
            id="high",
            url="https://x/4",
            title="React Native Developer",
            description="React Native, TypeScript, Expo",
            locations=["Wien"],
        )
        shortlist = build_shortlist([low_fit, high_fit])
        self.assertEqual(shortlist[0]["id"], "high")

    def test_non_vienna_job_is_dropped(self):
        jobs = [make_job(locations=["Graz"])]
        self.assertEqual(build_shortlist(jobs), [])

    def test_excluded_job_is_dropped(self):
        jobs = [make_job(title="Senior React Developer")]
        self.assertEqual(build_shortlist(jobs), [])


if __name__ == "__main__":
    unittest.main()
