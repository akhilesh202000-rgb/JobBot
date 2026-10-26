# util/himalayas.py
#
# Himalayas hat eine öffentliche JSON-API:
#     https://himalayas.app/jobs/api
#
# Die API liefert die neuesten 20 Remote-Jobs. `limit`, `search` und `q`
# werden ignoriert; paginiert wird über `nextCursor`. Deshalb lesen wir
# mehrere Seiten und filtern lokal auf React + passende Remote-Region.
#
# Jeder Job hat u. a.:
#   title, companyName, locationRestrictions, description, guid,
#   applicationLink, pubDate, employmentType, categories
#
# `guid` ist die saubere Himalayas-URL (ohne utm-Parameter). Remote-Jobs
# werden als "Wien (Remote)" gemappt, damit die Distanzlogik greift.

import datetime as dt
import html
import re
import time
from urllib.parse import urlparse

import requests

from config.constants import (
    HIMALAYAS_API,
    HIMALAYAS_MAX_PAGES,
    POLITE_DELAY_SECONDS,
    REACT_IN_TEXT,
    REMOTE_ALLOWED_LOCATIONS,
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


def _posted(value):
    try:
        return dt.datetime.fromtimestamp(
            int(value), dt.timezone.utc
        ).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def _allowed_location(restrictions):
    """True, wenn der Job für Wien/Österreich/Europa/Worldwide offen ist."""
    if isinstance(restrictions, str):
        restrictions = [restrictions]
    values = [str(item).strip().lower() for item in (restrictions or []) if item]
    if not values:
        return True
    return any(
        token in value
        for value in values
        for token in REMOTE_ALLOWED_LOCATIONS
    )


def normalize_job(row):
    """Himalayas-Job -> normalisiertes Job-Dict oder None."""
    title = _clean(row.get("title"))
    description = _clean(row.get("description"))
    restrictions = row.get("locationRestrictions") or []
    categories = row.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    categories = [str(item) for item in categories]
    text = " ".join([title, description, " ".join(categories)])

    if isinstance(restrictions, str):
        restrictions = [restrictions]
    if not title or not REACT_IN_TEXT.search(text):
        return None
    if not _allowed_location(restrictions):
        return None

    url = row.get("guid") or row.get("applicationLink") or ""
    if not url:
        return None

    region = ", ".join(str(item) for item in restrictions if item)
    if region:
        description = f"{description} Remote-Region: {region}".strip()

    return {
        "id": str(row.get("id") or urlparse(url).path or url),
        "title": title,
        "url": url,
        "company": _clean(row.get("companyName")),
        "description": description,
        "locations": ["Wien (Remote)"],
        "home_office": True,
        "employment_type": _clean(row.get("employmentType")),
        "posted": _posted(row.get("pubDate")),
        "source": "himalayas.app",
        # Der Volltext ist vorhanden; der Suchbegriff ist nicht nötig.
        "matched_terms": [],
        "remote_region": region,
    }


def parse_jobs(payload):
    """JSON-Antwort der Himalayas-API -> normalisierte Jobs."""
    jobs = []
    for row in payload.get("jobs") or []:
        job = normalize_job(row)
        if job:
            jobs.append(job)
    return jobs


def fetch_himalayas_jobs():
    """Liest mehrere Seiten der Himalayas-API und filtert lokal."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    jobs = {}
    cursor = None
    print("📡 Lese Himalayas (Remote, React) ...")

    for page in range(1, HIMALAYAS_MAX_PAGES + 1):
        params = {"cursor": cursor} if cursor else None
        try:
            response = session.get(
                HIMALAYAS_API,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"⚠️ Himalayas Seite {page}: {exc}")
            break

        if response.status_code != 200:
            print(f"⚠️ Himalayas Seite {page}: HTTP {response.status_code}")
            break

        try:
            payload = response.json()
        except ValueError:
            print(f"⚠️ Himalayas Seite {page}: kein JSON")
            break

        new_count = 0
        for job in parse_jobs(payload):
            if job["url"] in jobs:
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"   Seite {page:>2}: {new_count:>3} neue Treffer (gesamt {len(jobs)})")
        cursor = payload.get("nextCursor")
        if not cursor:
            break
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"📊 {len(jobs)} React-Remote-Jobs von Himalayas\n")
    return list(jobs.values())
