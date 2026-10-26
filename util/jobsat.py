# util/jobsat.py
#
# jobs.at (Österreich) liefert serverseitig gerenderte Suchseiten:
#     https://www.jobs.at/j/react?jobTitle=react&jobLocation=Wien
#
# Jede Trefferkarte ist ein <li data-job="<id>"> mit:
#   data-c-title       Titel
#   data-c-redirect    base64-kodierte Ziel-URL (https://www.jobs.at/i/<id>)
#   data-job-date      Unix-Zeitstempel (Sekunden)
#   sichtbarer Text    Firma + Standorte
#
# Die sichtbaren Standorte stehen zwischen "Standort" und "Job teilen",
# mehrere Orte sind mit Komma getrennt.

import base64
import datetime as dt
import html
import re
import time
from urllib.parse import quote

import requests

from config.constants import (
    JOBSAT_BASE,
    JOBSAT_LOCATION,
    JOBSAT_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(r'<li\b[^>]*\bdata-job="(?P<id>\d+)"', re.I)
_TITLE_ATTR_RE = re.compile(r'data-c-title="(?P<v>[^"]*)"', re.I)
_REDIRECT_RE = re.compile(r'data-c-redirect="(?P<v>[^"]*)"', re.I)
_DATE_RE = re.compile(r'data-job-date="(?P<v>\d+)"', re.I)
_COMPANY_RE = re.compile(r"\bFirma\s+(?P<v>.*?)\s+Standort\b", re.S)
_LOCATION_RE = re.compile(r"\bStandort\s+(?P<v>.*?)\s+Job teilen\b", re.S)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _decode_redirect(value):
    if not value:
        return ""
    try:
        decoded = base64.b64decode(value + "===").decode("utf-8", "ignore")
    except Exception:
        return ""
    return decoded if decoded.startswith("http") else ""


def _posted(value):
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%d")


def parse_cards(page_html, term=""):
    """Zerlegt eine jobs.at-Suchseite in normalisierte Jobs."""
    matches = list(_CARD_RE.finditer(page_html))
    jobs = []
    seen = set()

    for index, match in enumerate(matches):
        job_id = match.group("id")
        if job_id in seen:
            continue

        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[match.start():end]

        title_match = _TITLE_ATTR_RE.search(block)
        title = html.unescape(title_match.group("v")) if title_match else ""
        if not title:
            continue

        seen.add(job_id)
        text = _clean(block)

        company_match = _COMPANY_RE.search(text)
        company = company_match.group("v").strip() if company_match else ""

        location_match = _LOCATION_RE.search(text)
        locations = []
        if location_match:
            locations = [
                part.strip()
                for part in location_match.group("v").split(",")
                if part.strip()
            ]

        redirect_match = _REDIRECT_RE.search(block)
        url = _decode_redirect(
            html.unescape(redirect_match.group("v")) if redirect_match else ""
        )
        if not url:
            url = f"{JOBSAT_BASE}/i/{job_id}"

        date_match = _DATE_RE.search(block)

        jobs.append(
            {
                "id": job_id,
                "title": title,
                "url": url,
                "company": company,
                "description": text,
                "locations": locations,
                "home_office": bool(
                    re.search(r"home[\s-]?office|remote|hybrid", text, re.I)
                ),
                "employment_type": "",
                "posted": _posted(date_match.group("v")) if date_match else "",
                "source": "jobs.at",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_jobsat_jobs(terms=None):
    """Holt Wien-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or JOBSAT_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese jobs.at (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        slug = quote(term.replace(" ", "-"))
        url = (
            f"{JOBSAT_BASE}/j/{slug}"
            f"?jobTitle={quote(term)}&jobLocation={quote(JOBSAT_LOCATION)}"
        )
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
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
    print(f"📊 {len(jobs)} eindeutige Jobs von jobs.at\n")
    return list(jobs.values())
