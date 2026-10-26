# util/itkarriere.py
#
# IT-Karriere.at ist ein klassisches österreichisches PHP-Jobboard:
#     https://www.it-karriere.at/search.php?search_company=react&search_city=124
#
# `search_city=124` ist Wien. Die Ergebnisse sind serverseitig gerendert:
#   <h1>Titel</h1>
#   <h3>Firma</h3>
#   <p class="job-info">Wien | Software Development</p>
#   <a href="https://www.it-karriere.at/<id>/0/<slug>">
#
# Das TLS-Zertifikat der Seite ist abgelaufen. Wir lesen nur öffentliche
# Stellenanzeigen und deaktivieren deshalb die Zertifikatsprüfung.

import html
import re
import time
from urllib.parse import quote

import requests
import urllib3

from config.constants import (
    ITKARRIERE_BASE,
    ITKARRIERE_CITY_ID,
    ITKARRIERE_SEARCH_TERMS,
    ITKARRIERE_SEARCH_URL,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_TAG_RE = re.compile(r"<[^>]+>")
_LINK_RE = re.compile(
    r'href="(https://www\.it-karriere\.at/(?P<id>\d+)/0/[^"]+)"',
    re.I,
)
_TITLE_RE = re.compile(r"<h1[^>]*>(?P<v>.*?)</h1>", re.S)
_COMPANY_RE = re.compile(r"<h3[^>]*>(?P<v>.*?)</h3>", re.S)
_INFO_RE = re.compile(r'<p[^>]*class="[^"]*job-info[^"]*"[^>]*>(?P<v>.*?)</p>', re.S)
_DATE_RE = re.compile(r"<!--\s*\|\s*([\d.]{6,10})\s*-->")


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _first(pattern, block):
    match = pattern.search(block)
    return _clean(match.group("v")) if match else ""


def parse_cards(page_html, term=""):
    """Zerlegt eine IT-Karriere-Suchseite in normalisierte Jobs."""
    matches = list(_LINK_RE.finditer(page_html))
    jobs = []
    seen = set()

    for index, match in enumerate(matches):
        job_id = match.group("id")
        if job_id in seen:
            continue

        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[match.start():end]

        title = _first(_TITLE_RE, block)
        if not title:
            # Zweiter Anchor derselben Karte (Favoriten-Button) – überspringen.
            continue

        seen.add(job_id)
        company = _first(_COMPANY_RE, block)
        info = _first(_INFO_RE, block)

        # "Wien | Software Development" -> Standortteil vor dem ersten "|".
        location_part = info.split("|", 1)[0].strip()
        locations = [
            part.strip()
            for part in location_part.split(",")
            if part.strip()
        ]
        if not locations:
            locations = ["Wien"]

        date_match = _DATE_RE.search(block)
        posted = date_match.group(1) if date_match else ""

        description = " ".join(part for part in (title, company, info) if part)

        jobs.append(
            {
                "id": job_id,
                "title": title,
                # Titel mit "C#" enthalten ein rohes "#", das sonst als
                # URL-Fragment interpretiert wird.
                "url": match.group(1).replace("#", "%23"),
                "company": company,
                "description": description,
                "locations": locations,
                "home_office": bool(
                    re.search(r"home[\s-]?office|remote|hybrid", info, re.I)
                ),
                "employment_type": "",
                "posted": posted,
                "source": "it-karriere.at",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_itkarriere_jobs(terms=None):
    """Holt Wien-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or ITKARRIERE_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese IT-Karriere.at (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        url = (
            f"{ITKARRIERE_SEARCH_URL}?search_company={quote(term)}"
            f"&search_city={ITKARRIERE_CITY_ID}"
        )
        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=False,
            )
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

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
    print(f"📊 {len(jobs)} eindeutige Jobs von IT-Karriere.at\n")
    return list(jobs.values())
