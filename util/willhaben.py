# util/willhaben.py
#
# Willhaben hat eine öffentliche JSON-API für die Jobsuche:
#     https://publicapi.willhaben.at/jobs/v2/adverts?keyword=react
#
# Jeder Treffer hat `description` (Titel) und `attributes`:
#   ORGNAME, LOCATION, EMPLOYMENT_TYPE, PUBLISHED
#
# Die öffentliche Web-URL eines Jobs ist:
#     https://www.willhaben.at/jobs/job/<id>
#
# Die API filtert `location=Wien` sehr streng (nur exakte Treffer). Wir
# suchen deshalb nur nach dem Keyword und filtern die LOCATION-Attribute
# selbst auf "Wien".

import datetime as dt
import re
import time
from zoneinfo import ZoneInfo

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    WILLHABEN_API,
    WILLHABEN_JOB_URL,
    WILLHABEN_MAX_PAGES,
    WILLHABEN_SEARCH_TERMS,
)


def _attributes(advert):
    result = {}
    for item in advert.get("attributes") or []:
        name = item.get("name")
        values = item.get("values") or []
        if name:
            result[name] = values
    return result


def _first(attributes, name):
    values = attributes.get(name) or []
    return str(values[0]) if values else ""


def _posted(attributes):
    raw = _first(attributes, "PUBLISHED_String")
    if raw:
        return raw[:10]
    raw = _first(attributes, "PUBLISHED")
    if raw.isdigit():
        timestamp = int(raw) / 1000
        return dt.datetime.fromtimestamp(
            timestamp, ZoneInfo("Europe/Vienna")
        ).strftime("%Y-%m-%d")
    return ""


def normalize_advert(advert, term=""):
    """Willhaben-Advert -> normalisiertes Job-Dict."""
    attributes = _attributes(advert)
    locations = [
        str(value).strip()
        for value in attributes.get("LOCATION", [])
        if str(value).strip()
    ]
    title = str(advert.get("description") or "").strip()
    company = _first(attributes, "ORGNAME")
    employment_type = _first(attributes, "EMPLOYMENT_TYPE")
    job_id = str(advert.get("id") or "")

    description = " ".join(
        part for part in (title, company, ", ".join(locations), employment_type) if part
    )

    return {
        "id": job_id,
        "title": title,
        "url": f"{WILLHABEN_JOB_URL}/{job_id}" if job_id else "",
        "company": company,
        "description": description,
        "locations": locations,
        "home_office": bool(
            re.search(
                r"home[\s-]?office|remote|hybrid",
                f"{title} {' '.join(locations)}",
                re.I,
            )
        ),
        "employment_type": employment_type,
        "posted": _posted(attributes),
        "source": "willhaben.at",
        "matched_terms": [term] if term else [],
    }


def parse_adverts(payload, term=""):
    """JSON-Antwort der Willhaben-API -> Liste normalisierter Jobs."""
    jobs = []
    for advert in payload.get("advertSummaryList") or []:
        job = normalize_advert(advert, term=term)
        # Nur Wien-Treffer behalten; die API liefert auch andere Bundesländer.
        if not any("wien" in loc.lower() for loc in job["locations"]):
            continue
        if job["title"] and job["url"]:
            jobs.append(job)
    return jobs


def fetch_willhaben_jobs(terms=None):
    """Holt Wien-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or WILLHABEN_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    jobs = {}
    print("📡 Lese Willhaben Jobs (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        new_count = 0
        for page in range(1, WILLHABEN_MAX_PAGES + 1):
            try:
                response = session.get(
                    WILLHABEN_API,
                    params={
                        "keyword": term,
                        "rowsRequested": 30,
                        "page": page,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                print(f"{term:<20} | ⚠️  | {exc}")
                break

            if response.status_code != 200:
                print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
                break

            try:
                payload = response.json()
            except ValueError:
                print(f"{term:<20} | ⚠️  | kein JSON")
                break

            page_jobs = parse_adverts(payload, term=term)
            if not page_jobs:
                break

            for job in page_jobs:
                if job["url"] in jobs:
                    if term not in jobs[job["url"]]["matched_terms"]:
                        jobs[job["url"]]["matched_terms"].append(term)
                    continue
                jobs[job["url"]] = job
                new_count += 1

            if len(payload.get("advertSummaryList") or []) < 30:
                break
            time.sleep(POLITE_DELAY_SECONDS)

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von Willhaben\n")
    return list(jobs.values())
