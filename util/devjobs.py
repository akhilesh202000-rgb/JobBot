# util/devjobs.py
#
# Liest devjobs.at über die öffentlichen SEO-Suchseiten:
#     https://devjobs.at/jobs/react-wien-109166
# Jede Seite liefert ~15 serverseitig gerenderte Job-Karten.
#
# Die Seite ist eine Remix-App hinter Cloudflare. Normale requests bekommen
# 403 ("Just a moment..."), deshalb cloudscraper. Fehlt cloudscraper, wird
# auf requests zurückgefallen und einmal gewarnt.
#
# Pagination: ?page=2 / ?p=2 werden serverseitig ignoriert. Abdeckung kommt
# daher über mehrere Tech-Slugs (react, typescript, ...), ähnlich wie bei
# karriere.at.

import html
import re
import time

from config.constants import (
    DEVJOBS_BASE,
    DEVJOBS_LOCATION_SLUG,
    DEVJOBS_TECH_SLUGS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")

_CARD_RE = re.compile(
    r'<a[^>]*data-cy="jobSearchResultLink"[^>]*href="(?P<href>/job/[^"]+)"',
    re.I,
)
_TITLE_RE = re.compile(r"<h2[^>]*>(?P<v>.*?)</h2>", re.S)
_COMPANY_RE = re.compile(r'<p[^>]*font-semibold[^>]*>(?P<v>.*?)</p>', re.S)
_LOCATION_RE = re.compile(r'<span[^>]*font-medium[^>]*>(?P<v>.*?)</span>', re.S)
_DESCRIPTION_RE = re.compile(r'<p[^>]*line-clamp-2[^>]*>(?P<v>.*?)</p>', re.S)
_PILL_RE = re.compile(r'<li[^>]*transition-all[^>]*>(?P<v>.*?)</li>', re.S)
_TECH_RE = re.compile(r'<li[^>]*bg-dj-pill-secondary[^>]*>(?P<v>.*?)</li>', re.S)

_GENDER_MARKERS = {"m/w/x", "m/w/d", "w/m/d", "m/w/d/x", "m/f/x", "m/f/d"}


def _clean(text):
    """HTML entfernen, Entities auflösen, Whitespace normalisieren."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _first(pattern, block):
    match = pattern.search(block)
    return _clean(match.group("v")) if match else ""


def _make_scraper():
    """cloudscraper bevorzugen; ohne Paket mit requests weitermachen."""
    try:
        import cloudscraper

        return cloudscraper.create_scraper()
    except ImportError:
        print(
            "   ⚠️ cloudscraper fehlt – devjobs.at blockt ohne Paket evtl. "
            "(env/bin/python -m pip install cloudscraper)"
        )
        import requests

        return requests.Session()


def parse_cards(page_html, source_slug=""):
    """Zerlegt eine devjobs-Suchseite in normalisierte Job-Dicts."""
    matches = list(_CARD_RE.finditer(page_html))
    jobs = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[start:end]

        href = match.group("href")
        title = _first(_TITLE_RE, block)
        if not title:
            continue

        company = _first(_COMPANY_RE, block)

        # Standort-Spans liegen zwischen Firmenname und Beschreibung.
        location_segment = block
        company_match = _COMPANY_RE.search(block)
        if company_match:
            location_segment = block[company_match.end():]
        description_match = _DESCRIPTION_RE.search(location_segment)
        if description_match:
            location_segment = location_segment[:description_match.start()]
        locations = [
            _clean(value) for value in _LOCATION_RE.findall(location_segment)
        ]
        locations = list(dict.fromkeys(loc for loc in locations if loc))

        summary = _first(_DESCRIPTION_RE, block)

        techs = [_clean(value) for value in _TECH_RE.findall(block)]
        techs = list(dict.fromkeys(tech for tech in techs if tech))

        pills = [_clean(value) for value in _PILL_RE.findall(block)]
        tags = [
            pill
            for pill in pills
            if pill
            and pill not in techs
            and pill.lower() not in _GENDER_MARKERS
        ]

        home_office = any(
            re.search(r"home[\s-]?office|remote|hybrid", tag, re.I) for tag in tags
        )
        employment_type = next(
            (
                tag
                for tag in tags
                if re.search(
                    r"vollzeit|teilzeit|freelance|praktik|befristet|geringfügig",
                    tag,
                    re.I,
                )
            ),
            "",
        )

        description = summary
        if techs:
            description = f"{description} Tech: {', '.join(techs)}".strip()

        job_id = href.rstrip("/").rsplit("/", 1)[-1]
        matched_term = source_slug.replace("-", " ") if source_slug else ""

        jobs.append(
            {
                "id": job_id,
                "title": title,
                "url": href if href.startswith("http") else DEVJOBS_BASE + href,
                "company": company,
                "description": description,
                "locations": locations,
                "home_office": home_office,
                "employment_type": employment_type,
                "posted": "",
                "source": "devjobs.at",
                # Wichtig: Auf einer react-Suche gefundene Jobs gelten als
                # React-relevant, auch wenn der Teaser keinen React-Text hat.
                "matched_terms": [matched_term] if matched_term else [],
            }
        )

    return jobs


def fetch_devjobs_jobs(slugs=None):
    """Holt Wien-Treffer für alle konfigurierten Tech-Slugs, dedupliziert nach URL."""
    slugs = slugs or DEVJOBS_TECH_SLUGS
    scraper = _make_scraper()
    jobs = {}

    print("📡 Lese devjobs.at (Wien) ...")
    print(f"{'Tech':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for slug in slugs:
        url = f"{DEVJOBS_BASE}/jobs/{slug}-{DEVJOBS_LOCATION_SLUG}"
        try:
            response = scraper.get(
                url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except Exception as exc:  # cloudscraper/requests werfen verschiedene Typen
            print(f"{slug:<20} | ⚠️  | {exc}")
            continue

        if response.status_code == 404:
            print(f"{slug:<20} | –   | keine Seite")
            continue
        if response.status_code != 200:
            print(f"{slug:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        new_count = 0
        for job in parse_cards(response.text, source_slug=slug):
            if job["url"] in jobs:
                if slug not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(slug)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{slug:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von devjobs.at\n")
    return list(jobs.values())
