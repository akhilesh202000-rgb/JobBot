# util/relocate.py
#
# Relocate.me ist ein Relocation-Jobboard. Die Suche liefert serverseitig
# gerenderte Karten:
#     https://relocate.me/international-jobs?search=react&page=1
#
# Detail-URLs sehen so aus:
#     /<land>/<stadt>/<firma>/<slug>-<id>
#
# Für JobBot behalten wir nur Österreich-/Wien-Treffer. Relocate.me hat
# aktuell kaum Wien-Jobs; das Modul ist bewusst best effort und liefert
# dann eine leere Liste.

import html
import re
import time
from urllib.parse import quote

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    RELOCATE_BASE,
    RELOCATE_MAX_PAGES,
    RELOCATE_SEARCH_TERMS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(
    r'<div class="job__title">\s*<a href="(?P<href>[^"]+)">(?P<body>.*?)</a>',
    re.S | re.I,
)
_ID_RE = re.compile(r"-(\d+)/?$")


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _split_href(href):
    """'/austria/vienna/firma/slug-123' -> (country, city, company, id)."""
    parts = [part for part in href.strip("/").split("/") if part]
    if len(parts) < 4:
        return "", "", "", ""
    country, city, company = parts[0], parts[1], parts[2]
    match = _ID_RE.search(parts[-1])
    job_id = match.group(1) if match else parts[-1]
    return country, city, company.replace("-", " ").title(), job_id


def parse_cards(page_html, term=""):
    """Zerlegt eine Relocate.me-Listenseite in normalisierte Jobs."""
    matches = list(_CARD_RE.finditer(page_html))
    jobs = []
    seen = set()

    for index, match in enumerate(matches):
        href = match.group("href")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[match.start():end]
        text = _clean(block)

        country, city, company, job_id = _split_href(href)
        is_austria = country.lower() in ("austria", "at")
        mentions_vienna = bool(re.search(r"\b(wien|vienna)\b", text, re.I))
        if not (is_austria or mentions_vienna):
            continue
        if href in seen:
            continue
        seen.add(href)

        title = _clean(match.group("body"))
        if not title:
            continue

        if city.lower() in ("vienna", "wien"):
            locations = ["Wien"]
        elif city:
            locations = [city.title()]
        else:
            locations = ["Wien"]

        jobs.append(
            {
                "id": job_id,
                "title": title,
                "url": f"{RELOCATE_BASE}{href}",
                "company": company,
                "description": text,
                "locations": locations,
                "home_office": bool(
                    re.search(r"remote|home[\s-]?office", text, re.I)
                ),
                "employment_type": "",
                "posted": "",
                "source": "relocate.me",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_relocate_jobs(terms=None):
    """Holt Wien-/Österreich-Treffer für alle Suchbegriffe."""
    terms = terms or RELOCATE_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese Relocate.me (Wien/Österreich) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        new_count = 0
        for page in range(1, RELOCATE_MAX_PAGES + 1):
            url = (
                f"{RELOCATE_BASE}/international-jobs"
                f"?search={quote(term)}&page={page}"
            )
            try:
                response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            except Exception as exc:
                print(f"{term:<20} | ⚠️  | {exc}")
                break

            if response.status_code != 200:
                print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
                break

            page_jobs = parse_cards(response.text, term=term)
            if not page_jobs:
                break

            for job in page_jobs:
                if job["url"] in jobs:
                    if term not in jobs[job["url"]]["matched_terms"]:
                        jobs[job["url"]]["matched_terms"].append(term)
                    continue
                jobs[job["url"]] = job
                new_count += 1

            # Relocate.me liefert pro Seite ~20 Karten; leere Seiten beenden.
            if len(re.findall(r'class="job__title"', response.text)) < 20:
                break
            time.sleep(POLITE_DELAY_SECONDS)

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von Relocate.me\n")
    return list(jobs.values())
