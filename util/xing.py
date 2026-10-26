# util/xing.py
#
# XING Jobs liefert serverseitig gerenderte Suchseiten:
#     https://www.xing.com/jobs/search?keywords=react&location=Wien
#
# Jede Trefferkarte hat `data-testid="job-search-result"` und enthält:
#   - Link `/jobs/<slug>`
#   - Titel in `data-testid="job-teaser-list-title"`
#   - Firma in einer Klasse mit `job-teaser-list-item-styles__Company`
#   - Standort im `multi-location-display-styles__Container`
#
# Die Seite ist UTF-8; requests erkennt das nicht immer zuverlässig,
# deshalb setzen wir `response.encoding = "utf-8"`.

import html
import re
import time

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    XING_SEARCH_TERMS,
    XING_SEARCH_URL,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(r'data-testid="job-search-result"')
_LINK_RE = re.compile(r'href="(/jobs/[^"]+)"')
_TITLE_RE = re.compile(
    r'data-testid="job-teaser-list-title"[^>]*>(.*?)</h2>', re.S
)
_COMPANY_RE = re.compile(
    r'job-teaser-list-item-styles__Company[^"]*"[^>]*>(.*?)</p>', re.S
)
_LOCATION_RE = re.compile(
    r'multi-location-display-styles__Container[^"]*"[^>]*>.*?'
    r"<p[^>]*>(.*?)(?:<b|</p>)",
    re.S,
)
_DATE_RE = re.compile(
    r'job-teaser-list-item-styles__PublicationDate[^"]*"[^>]*>(.*?)</p>', re.S
)
_EMPLOYMENT_RE = re.compile(
    r"\b(Vollzeit|Teilzeit|Freelance|Contract|Befristet|Praktikum)\b", re.I
)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def parse_cards(page_html, term=""):
    """XING-Suchseite -> normalisierte Jobs."""
    matches = list(_CARD_RE.finditer(page_html or ""))
    jobs = []

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[match.start():end]

        link_match = _LINK_RE.search(block)
        title_match = _TITLE_RE.search(block)
        if not link_match or not title_match:
            continue

        title = _clean(title_match.group(1))
        url = f"https://www.xing.com{link_match.group(1)}"
        company_match = _COMPANY_RE.search(block)
        company = _clean(company_match.group(1)) if company_match else ""

        location_match = _LOCATION_RE.search(block)
        location = _clean(location_match.group(1)) if location_match else ""
        if "wien" not in location.lower():
            continue

        text = _clean(block)
        employment_match = _EMPLOYMENT_RE.search(text)
        employment = employment_match.group(1) if employment_match else ""
        date_match = _DATE_RE.search(block)
        posted = _clean(date_match.group(1)) if date_match else ""

        jobs.append(
            {
                "id": url.rstrip("/").rsplit("/", 1)[-1],
                "title": title,
                "url": url,
                "company": company,
                "description": text,
                "locations": [location],
                "home_office": bool(
                    re.search(r"home[\s-]?office|remote", text, re.I)
                ),
                "employment_type": employment,
                "posted": posted,
                "source": "xing.com",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_xing_jobs(terms=None):
    """Holt Wien-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or XING_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese XING Jobs (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        try:
            response = session.get(
                XING_SEARCH_URL,
                params={"keywords": term, "location": "Wien"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        response.encoding = "utf-8"
        new_count = 0
        for job in parse_cards(response.text, term=term):
            if job["url"] in jobs:
                if term not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(term)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von XING\n")
    return list(jobs.values())
