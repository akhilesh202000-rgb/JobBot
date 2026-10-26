# util/remotive.py
#
# Remotive hat eine öffentliche Remote-Jobs-API:
#     https://remotive.com/api/remote-jobs?search=react
#
# Die API liefert JSON mit u. a.:
#   id, url, title, company_name, category, job_type,
#   publication_date, candidate_required_location, description
#
# Remotive ist ein Remote-Board. Für den Wien-Fokus behalten wir nur Jobs,
# die laut `candidate_required_location` für Wien/Österreich/Europa oder
# Worldwide offen sind. Der Standort wird als "Wien (Remote)" gemappt,
# damit die vorhandene Distanzlogik (Stadtzentrum) greift.

import html
import re
import time
from urllib.parse import quote

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    REMOTIVE_ALLOWED_LOCATIONS,
    REMOTIVE_API,
    REMOTIVE_SEARCH_TERMS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _is_open_to_vienna(location):
    location = (location or "").strip().lower()
    if not location:
        return True
    return any(token in location for token in REMOTIVE_ALLOWED_LOCATIONS)


def normalize_job(row, term=""):
    """Remotive-Job -> normalisiertes Job-Dict."""
    job_id = str(row.get("id") or "")
    title = _clean(row.get("title"))
    company = _clean(row.get("company_name"))
    location = _clean(row.get("candidate_required_location"))
    job_type = _clean(row.get("job_type"))
    posted = str(row.get("publication_date") or "")[:10]

    description = _clean(row.get("description"))
    if location:
        description = f"{description} Remote-Region: {location}".strip()

    return {
        "id": job_id,
        "title": title,
        "url": row.get("url") or "",
        "company": company,
        "description": description,
        "locations": ["Wien (Remote)"],
        "home_office": True,
        "employment_type": job_type,
        "posted": posted,
        "source": "remotive.com",
        # Remotive liefert den Volltext. Anders als bei den HTML-Karten
        # brauchen wir den Suchbegriff nicht als React-Beleg.
        "matched_terms": [],
        "remote_region": location,
    }


def parse_jobs(payload, term=""):
    """JSON-Antwort der Remotive-API -> normalisierte Jobs."""
    jobs = []
    for row in payload.get("jobs") or []:
        if not _is_open_to_vienna(row.get("candidate_required_location")):
            continue
        job = normalize_job(row, term=term)
        if job["title"] and job["url"]:
            jobs.append(job)
    return jobs


def fetch_remotive_jobs(terms=None):
    """Holt Remote-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or REMOTIVE_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    jobs = {}
    print("📡 Lese Remotive (Remote, Wien-tauglich) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        try:
            response = session.get(
                REMOTIVE_API,
                params={"search": term},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        try:
            payload = response.json()
        except ValueError:
            print(f"{term:<20} | ⚠️  | kein JSON")
            continue

        new_count = 0
        for job in parse_jobs(payload, term=term):
            if job["url"] in jobs:
                if term not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(term)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Remote-Jobs von Remotive\n")
    return list(jobs.values())
