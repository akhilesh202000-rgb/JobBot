# tests/test_devjobs.py
#
# Ausführen (aus dem Projekt-Root):
#   env/bin/python -m unittest discover -s tests -t . -v

import unittest

from util.devjobs import parse_cards

CARD = (
    '<a data-cy="jobSearchResultLink" class="x" href="/job/abc123">'
    '<div><h2 class="order-2 text-lg font-medium">React Developer</h2>'
    '<div class="bg-dj-tertiary font-medium uppercase">Neu</div></div>'
    '<div><picture><img alt="Logo ACME"/></picture>'
    '<div class="ml-2 mr-auto flex shrink flex-col truncate">'
    '<p class="dark:text-dj-mono-dark-200 font-semibold">ACME GmbH</p>'
    '<div class="flex place-items-center space-x-1"><div class="flex truncate">'
    '<span class="text-dj-mono-600 font-medium">Wien</span></div></div></div></div>'
    '<div><p class="text-dj-mono-500 line-clamp-2 px-4 font-normal">'
    'Wir bauen mit React und TypeScript.</p></div>'
    '<div><ul><li class="transition-all text-sm">Hybrid</li>'
    '<li class="transition-all text-sm">Vollzeit</li>'
    '<li class="transition-all text-sm">m/w/x</li></ul></div>'
    '<div><ul><li class="transition-all bg-dj-pill-secondary">React</li>'
    '<li class="transition-all bg-dj-pill-secondary">TypeScript</li></ul></div>'
    '</a>'
)

SECOND_CARD = (
    '<a data-cy="jobSearchResultLink" href="/job/def456">'
    '<h2>Frontend Engineer</h2>'
    '<p class="font-semibold">Beta OG</p>'
    '<span class="font-medium">Wien 2. Bezirk</span>'
    '<p class="line-clamp-2">Frontend mit React Native.</p>'
    '<ul><li class="transition-all">Remote</li></ul>'
    '</a>'
)


class ParseCardsTests(unittest.TestCase):
    def test_single_card_fields(self):
        jobs = parse_cards(CARD, source_slug="react")

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["title"], "React Developer")
        self.assertEqual(job["url"], "https://devjobs.at/job/abc123")
        self.assertEqual(job["company"], "ACME GmbH")
        self.assertEqual(job["locations"], ["Wien"])
        self.assertEqual(job["employment_type"], "Vollzeit")
        self.assertTrue(job["home_office"])
        self.assertEqual(job["source"], "devjobs.at")
        self.assertEqual(job["matched_terms"], ["react"])
        self.assertIn("React", job["description"])
        self.assertIn("Tech: React, TypeScript", job["description"])

    def test_two_cards_are_separated(self):
        jobs = parse_cards(CARD + SECOND_CARD, source_slug="react-native")

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[1]["title"], "Frontend Engineer")
        self.assertEqual(jobs[1]["company"], "Beta OG")
        self.assertEqual(jobs[1]["locations"], ["Wien 2. Bezirk"])
        self.assertTrue(jobs[1]["home_office"])
        self.assertEqual(jobs[1]["matched_terms"], ["react native"])

    def test_missing_title_is_skipped(self):
        broken = '<a data-cy="jobSearchResultLink" href="/job/x"></a>'
        self.assertEqual(parse_cards(broken), [])


if __name__ == "__main__":
    unittest.main()
