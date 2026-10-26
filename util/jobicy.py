# util/jobicy.py
#
# Jobicy hat eine öffentliche Remote-Jobs-API:
#     https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe
#
# `geo=europe` filtert grob nach Region. `tag=react` wird in den Filtern
# angezeigt, filtert aber nicht wirklich; deshalb lokal auf React prüfen.
#
# Felder: id, url, jobTitle, companyName, jobGeo, jobType, jobLevel,
#         jobDescription, jobExcerpt, pubDate, annualSalaryMin/Max
#
# Remote-Jobs werden als "Wien (Remote)" gemappt.

import html
import re
import time

import requests

from config.constants import (
    JOBICY_API,
    JOBICY_COUNT,
    JOBICY_GEO,
    JOBICY_MAX_PAGES,
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


def _allowed_location(geo):
    geo = (geo or "").strip().lower()
    if not geo:
        return True
    return any(token in geo for token in REMOTE_ALLOWED_LOCATIONS)


def normalize_job(row):
    """Jobicy-Job -> normalisiertes Job-Dict oder None."""
    title = _clean(row.get("jobTitle"))
    description = _clean(row.get("jobDescription"))
    excerpt = _clean(row.get("jobExcerpt"))
    text = " ".join([title, description, excerpt])
    geo = _clean(row.get("jobGeo"))

    if not title or not REACT_IN_TEXT.search(text):
        return None
    if not _allowed_location(geo):
        return None

    url = row.get("url") or ""
    if not url:
        return None

    job_types = row.get("jobType") or []
    if isinstance(job_types, str):
        job_types = [job_types]

    if geo:
        description = f"{description} Remote-Region: {geo}".strip()

    return {
        "id": str(row.get("id") or url),
        "title": title,
        "url": url,
        "company": _clean(row.get("companyName")),
        "description": description,
        "locations": ["Wien (Remote)"],
        "home_office": True,
        "employment_type": " / ".join(_clean(item) for item in job_types if item),
        "posted": str(row.get("pubDate") or "")[:10],
        "source": "jobicy.com",
        "matched_terms": [],
        "remote_region": geo,
    }


def parse_jobs(payload):
    """JSON-Antwort der Jobicy-API -> normalisierte Jobs."""
    jobs = []
    for row in payload.get("jobs") or []:
        job = normalize_job(row)
        if job:
            jobs.append(job)
    return jobs


def fetch_jobicy_jobs():
    """Liest Jobicy-Seiten und filtert lokal auf React + passende Region."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    jobs = {}
    cursor = None
    print("📡 Lese Jobicy (Remote, React) ...")

    for page in range(1, JOBICY_MAX_PAGES + 1):
        params = {"count": JOBICY_COUNT, "geo": JOBICY_GEO}
        if cursor:
            params["cursor"] = cursor
        try:
            response = session.get(
                JOBICY_API,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"⚠️ Jobicy Seite {page}: {exc}")
            break

        if response.status_code != 200:
            print(f"⚠️ Jobicy Seite {page}: HTTP {response.status_code}")
            break

        try:
            payload = response.json()
        except ValueError:
            print(f"⚠️ Jobicy Seite {page}: kein JSON")
            break

        new_count = 0
        for job in parse_jobs(payload):
            if job["url"] in jobs:
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"   Seite {page:>2}: {new_count:>3} neue Treffer (gesamt {len(jobs)})")
        cursor = payload.get("nextCursor")
        if not cursor or not payload.get("hasMore"):
            break
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"📊 {len(jobs)} React-Remote-Jobs von Jobicy\n")
    return list(jobs.values())
