# util/wellfound.py
#
# Wellfound (ehemals AngelList Talent) ist eine Next.js-Seite:
#     https://wellfound.com/jobs
#
# Die Jobdaten stehen im Apollo-State von `__NEXT_DATA__`:
#   JobListing:<id>  -> title, slug, locationNames, acceptedRemoteLocationNames,
#                       remote, liveStartAt, startup
#   Startup:<id>     -> name, slug
#
# Wellfound ist stark US-lastig. Wir behalten nur Jobs in Wien/Österreich
# oder Remote-Jobs, die laut `acceptedRemoteLocationNames` für Europa/
# Worldwide/Österreich offen sind.

import datetime as dt
import html
import json
import re

import requests

from config.constants import (
    REMOTE_ALLOWED_LOCATIONS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    WELLFOUND_JOBS_URL,
)

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
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


def _allowed_remote(names):
    if isinstance(names, str):
        names = [names]
    values = [str(item).lower() for item in (names or []) if item]
    return any(
        token in value
        for value in values
        for token in REMOTE_ALLOWED_LOCATIONS
    )


def _apollo_state(page_html):
    match = _NEXT_RE.search(page_html or "")
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return {}
    return (
        data.get("props", {})
        .get("pageProps", {})
        .get("apolloState", {})
        .get("data", {})
    )


def _startups(state):
    result = {}
    for key, value in (state or {}).items():
        if key.startswith("Startup:") and isinstance(value, dict):
            result[key] = value
    return result


def normalize_job(obj, startups):
    """JobListing -> normalisiertes Job-Dict oder None."""
    job_id = str(obj.get("id") or "")
    title = _clean(obj.get("title"))
    if not job_id or not title:
        return None

    location_names = obj.get("locationNames") or []
    if isinstance(location_names, str):
        location_names = [location_names]
    location_names = [_clean(item) for item in location_names if item]

    accepted_remote = obj.get("acceptedRemoteLocationNames") or []
    if isinstance(accepted_remote, str):
        accepted_remote = [accepted_remote]
    accepted_remote = [_clean(item) for item in accepted_remote if item]
    remote = bool(obj.get("remote"))

    local = [
        value for value in location_names
        if re.search(r"\b(wien|vienna|austria)\b", value, re.I)
    ]
    if local:
        locations = local
    elif remote and _allowed_remote(accepted_remote):
        locations = ["Wien (Remote)"]
    else:
        return None

    startup_ref = obj.get("startup")
    if isinstance(startup_ref, dict):
        startup_ref = startup_ref.get("__ref")
    startup = startups.get(startup_ref) or {}
    company = _clean(startup.get("name"))

    role = _clean((obj.get("primaryRole") or {}).get("slug"))
    description = " · ".join(
        part
        for part in (
            title,
            company,
            ", ".join(location_names),
            f"Rolle: {role}" if role else "",
            "Remote-Region: " + ", ".join(accepted_remote) if accepted_remote else "",
        )
        if part
    )

    slug = _clean(obj.get("slug"))
    url = f"https://wellfound.com/jobs/{job_id}"
    if slug:
        url = f"{url}-{slug}"

    return {
        "id": job_id,
        "title": title,
        "url": url,
        "company": company,
        "description": description,
        "locations": locations,
        "home_office": remote,
        "employment_type": "",
        "posted": _posted(obj.get("liveStartAt")),
        "source": "wellfound.com",
        "matched_terms": [],
        "remote_region": ", ".join(accepted_remote),
    }


def parse_page(page_html):
    """Wellfound-Seite -> normalisierte Jobs."""
    state = _apollo_state(page_html)
    if not state:
        return []

    startups = _startups(state)
    jobs = {}
    for key, value in state.items():
        if not key.startswith("JobListing:") or not isinstance(value, dict):
            continue
        job = normalize_job(value, startups)
        if job and job["id"] not in jobs:
            jobs[job["id"]] = job
    return list(jobs.values())


def fetch_wellfound_jobs():
    """Liest die Wellfound-Jobs aus dem Next.js-State."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    print("📡 Lese Wellfound (Wien/Remote) ...")
    try:
        response = session.get(
            WELLFOUND_JOBS_URL, timeout=REQUEST_TIMEOUT_SECONDS
        )
    except Exception as exc:
        print(f"⚠️ Wellfound: {exc}")
        return []

    if response.status_code != 200:
        print(f"⚠️ Wellfound: HTTP {response.status_code}")
        return []

    jobs = parse_page(response.text)
    print(f"📊 {len(jobs)} Wien-/Remote-Jobs von Wellfound\n")
    return jobs
