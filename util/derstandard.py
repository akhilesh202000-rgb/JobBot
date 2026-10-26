# util/derstandard.py
#
# DER STANDARD Jobs ist eine Next.js-App:
#     https://jobs.derstandard.at/suche/wien/react
#
# Die Treffer stehen nicht als normales HTML, sondern als React-Server-
# Components-Flight-Daten in `self.__next_f.push([1,"..."])`. Nach dem
# Entpacken findet man Objekte der Form:
#     {"JobListingResponse:<uuid>": {...}}
#
# Relevante Felder:
#   id, title, hiringOrganization.name, jobLocationsRaw, displayDate,
#   tags, employmentTypes, jobSummary
#
# Die Tags enthalten oft "React" – das reicht als React-Beleg, auch wenn
# die Anzeige keinen Volltext im Suchergebnis hat.

import html
import json
import re
import time
from urllib.parse import quote

import requests

from config.constants import (
    DERSTANDARD_BASE,
    DERSTANDARD_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_FLIGHT_RE = re.compile(
    r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', re.S
)
_JOB_KEY = '"JobListingResponse:'

_EMPLOYMENT = {
    "FULL_TIME": "Vollzeit",
    "PART_TIME": "Teilzeit",
    "CONTRACTOR": "Freelance",
    "TEMPORARY": "Befristet",
    "INTERN": "Praktikum",
}


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def flight_text(page_html):
    """Alle `self.__next_f.push`-Strings zu einem Text zusammenfügen."""
    parts = []
    for match in _FLIGHT_RE.finditer(page_html or ""):
        try:
            parts.append(json.loads(match.group(1)))
        except ValueError:
            continue
    return "".join(parts)


def _extract_objects(flight):
    """Alle {..}-Objekte hinter `"JobListingResponse:<id>":` extrahieren."""
    objects = []
    position = 0

    while True:
        key = flight.find(_JOB_KEY, position)
        if key == -1:
            break

        start = flight.find("{", key + len(_JOB_KEY))
        if start == -1:
            break

        depth = 0
        in_string = False
        escaped = False
        end = None

        for index in range(start, len(flight)):
            char = flight[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break

        if end is None:
            break

        try:
            objects.append(json.loads(flight[start:end]))
        except ValueError:
            pass
        position = end

    return objects


def _posted(value):
    match = re.search(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return match.group(1) if match else ""


def _employment(values):
    return " / ".join(
        _EMPLOYMENT.get(str(value), str(value)) for value in (values or []) if value
    )


def normalize_job(obj, term=""):
    """JobListingResponse -> normalisiertes Job-Dict oder None."""
    job_id = str(obj.get("id") or "")
    title = _clean(obj.get("title"))
    if not job_id or not title:
        return None

    company = _clean((obj.get("hiringOrganization") or {}).get("name"))
    raw_locations = [
        _clean(value) for value in (obj.get("jobLocationsRaw") or []) if value
    ]
    benefits = obj.get("benefits") or []
    tags = [_clean(value) for value in (obj.get("tags") or []) if value]

    lowered = [value.lower() for value in raw_locations]
    vienna = [
        value for value, lower in zip(raw_locations, lowered)
        if "wien" in lower or "vienna" in lower
    ]
    remote = any(
        "home" in lower or "remote" in lower for lower in lowered
    ) or "home_office" in benefits

    if vienna:
        locations = vienna
    elif remote:
        locations = ["Wien (Remote)"]
    else:
        return None

    employment = _employment(obj.get("employmentTypes"))
    summary = _clean(obj.get("jobSummary"))
    description = " · ".join(
        part
        for part in (
            title,
            company,
            ", ".join(raw_locations),
            "Tags: " + ", ".join(tags) if tags else "",
            employment,
            summary,
        )
        if part
    )

    return {
        "id": job_id,
        "title": title,
        "url": f"{DERSTANDARD_BASE}/detail/{job_id}",
        "company": company,
        "description": description,
        "locations": locations,
        "home_office": remote,
        "employment_type": employment,
        "posted": _posted(obj.get("displayDate")),
        "source": "jobs.derstandard.at",
        "matched_terms": [term] if term else [],
    }


def parse_flight(flight, term=""):
    """Flight-Text -> normalisierte, deduplizierte Jobs."""
    jobs = {}
    for obj in _extract_objects(flight):
        job = normalize_job(obj, term=term)
        if job and job["id"] not in jobs:
            jobs[job["id"]] = job
    return list(jobs.values())


def parse_search_page(page_html, term=""):
    """HTML einer DER-STANDARD-Suchseite -> normalisierte Jobs."""
    return parse_flight(flight_text(page_html), term=term)


def fetch_derstandard_jobs(terms=None):
    """Holt Wien-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or DERSTANDARD_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese DER STANDARD Jobs (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        url = f"{DERSTANDARD_BASE}/suche/wien/{quote(term)}"
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        new_count = 0
        for job in parse_search_page(response.text, term=term):
            if job["url"] in jobs:
                if term not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(term)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von DER STANDARD\n")
    return list(jobs.values())
