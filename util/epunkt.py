# util/epunkt.py
#
# epunkt ist ein österreichischer Recruiter mit eigener Job-Liste:
#     https://job.epunkt.com/jobs/wien
#
# Die Seite ist eine Laravel/Inertia-App. Die komplette Jobliste steht als
# JSON im `data-page`-Attribut des #app-Containers – kein API-Call nötig.
# Pro Seite 30 Jobs, die Wien-Liste hat aktuell 4 Seiten.
#
# epunkt nennt in den Daten keinen Auftraggebernamen (nur eine
# Organisationsbeschreibung), deshalb wird "epunkt" als Firma gespeichert.

import html
import json
import re
import time

import requests

from config.constants import (
    EPUNKT_BASE,
    EPUNKT_LOCATION_SLUG,
    EPUNKT_MAX_PAGES,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_DATA_PAGE_RE = re.compile(r'data-page="([^"]+)"', re.S)


def _clean(text):
    """HTML entfernen, Entities auflösen, Whitespace normalisieren."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _load_page(page_html):
    """Liest das Inertia-JSON aus dem data-page-Attribut."""
    match = _DATA_PAGE_RE.search(page_html)
    if not match:
        return {}
    try:
        return json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return {}


def _names(items):
    return [
        item.get("name", "")
        for item in (items or [])
        if isinstance(item, dict) and item.get("name")
    ]


def normalize_job(row):
    """epunkt-Jobobjekt -> normalisiertes Job-Dict."""
    job_id = str(row.get("id") or "")
    route = row.get("route_uri") or job_id
    title = _clean(row.get("title") or row.get("client_title") or "")

    description_parts = [
        _clean(row.get("sub_title")),
        _clean(row.get("future_role")),
        _clean(row.get("requirements")),
        _clean(row.get("usp")),
    ]
    description = " ".join(part for part in description_parts if part)

    locations = []
    if row.get("location"):
        locations.append(_clean(row["location"]))
    locations.extend(_names(row.get("working_regions")))
    locations = list(dict.fromkeys(loc for loc in locations if loc))

    employment_types = _names(row.get("employment_types"))
    created = row.get("created_at") or ""

    return {
        "id": job_id,
        "title": title,
        "url": f"{EPUNKT_BASE}/jobs/{route}" if route else "",
        "company": "epunkt",
        "description": description,
        "locations": locations,
        "home_office": bool(row.get("home_office")),
        "employment_type": ", ".join(employment_types),
        "posted": created[:10],
        "source": "epunkt",
        # epunkt wird ohne Suchbegriff gelesen; React muss im Text stehen.
        "matched_terms": [],
    }


def parse_jobs(page_html):
    """Zerlegt eine epunkt-Listenseite in normalisierte Jobs."""
    data = _load_page(page_html)
    rows = (
        data.get("props", {})
        .get("jobPostings", {})
        .get("data", [])
    )
    jobs = []
    for row in rows:
        job = normalize_job(row)
        if job["title"] and job["url"]:
            jobs.append(job)
    return jobs


def fetch_epunkt_jobs():
    """Holt alle Wien-Jobs von epunkt (ohne Suchbegriff, Filter passiert später)."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese epunkt (Wien) ...")

    for page in range(1, EPUNKT_MAX_PAGES + 1):
        url = (
            f"{EPUNKT_BASE}/jobs/{EPUNKT_LOCATION_SLUG}"
            f"?query=&page={page}"
        )
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"   ⚠️ epunkt Seite {page}: {exc}")
            break

        if response.status_code != 200:
            print(f"   ⚠️ epunkt Seite {page}: HTTP {response.status_code}")
            break

        page_jobs = parse_jobs(response.text)
        if not page_jobs:
            break

        new_count = 0
        for job in page_jobs:
            if job["url"] not in jobs:
                jobs[job["url"]] = job
                new_count += 1
        print(f"   Seite {page:<2} | {new_count:>3} neu | {len(jobs):>3} gesamt")

        # Letzte Seite erreicht?
        data = _load_page(response.text)
        meta = data.get("props", {}).get("jobPostings", {}).get("meta", {})
        if page >= int(meta.get("last_page") or page):
            break
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"📊 {len(jobs)} eindeutige Jobs von epunkt\n")
    return list(jobs.values())
