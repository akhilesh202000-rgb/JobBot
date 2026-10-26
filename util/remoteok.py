# util/remoteok.py
#
# Remote OK hat eine öffentliche JSON-API:
#     https://remoteok.com/api
#
# Der erste Eintrag ist ein Metadaten-Objekt (Terms of Service), danach
# folgen ~100 Remote-Jobs. Es gibt keine brauchbare serverseitige Suche;
# deshalb lokal auf React in Titel/Beschreibung/Tags filtern.
#
# Felder: id, slug, position, company, location, description, url,
#         apply_url, date, tags, salary_min, salary_max
#
# Remote-Jobs werden als "Wien (Remote)" gemappt. Die API verlangt einen
# Browser-User-Agent (siehe REQUEST_HEADERS).

import html
import re

import requests

from config.constants import (
    REACT_IN_TEXT,
    REMOTEOK_API,
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


def normalize_job(row):
    """Remote-OK-Job -> normalisiertes Job-Dict oder None."""
    title = _clean(row.get("position"))
    description = _clean(row.get("description"))
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(item) for item in tags]
    text = " ".join([title, description, " ".join(tags)])

    if not title or not REACT_IN_TEXT.search(text):
        return None

    slug = row.get("slug") or ""
    url = row.get("url") or (
        f"https://remoteok.com/remote-jobs/{slug}" if slug else ""
    )
    if not url:
        return None

    employment_type = ""
    lower_tags = {tag.lower() for tag in tags}
    if "full time" in lower_tags:
        employment_type = "Full Time"
    elif "part time" in lower_tags:
        employment_type = "Part Time"
    elif "contract" in lower_tags:
        employment_type = "Contract"

    return {
        "id": str(row.get("id") or slug or url),
        "title": title,
        "url": url,
        "company": _clean(row.get("company")),
        "description": description,
        "locations": ["Wien (Remote)"],
        "home_office": True,
        "employment_type": employment_type,
        "posted": str(row.get("date") or "")[:10],
        "source": "remoteok.com",
        "matched_terms": [],
        "remote_region": _clean(row.get("location")) or "Worldwide",
    }


def parse_jobs(payload):
    """JSON-Antwort der Remote-OK-API -> normalisierte Jobs."""
    jobs = []
    for row in payload or []:
        if not isinstance(row, dict):
            continue
        # Erster Eintrag: {"last_updated": ..., "legal": ...}
        if "id" not in row and "position" not in row:
            continue
        job = normalize_job(row)
        if job:
            jobs.append(job)
    return jobs


def fetch_remoteok_jobs():
    """Liest den Remote-OK-Feed und filtert lokal auf React."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    print("📡 Lese Remote OK (Remote, React) ...")
    try:
        response = session.get(REMOTEOK_API, timeout=REQUEST_TIMEOUT_SECONDS)
    except Exception as exc:
        print(f"⚠️ Remote OK: {exc}")
        return []

    if response.status_code != 200:
        print(f"⚠️ Remote OK: HTTP {response.status_code}")
        return []

    try:
        payload = response.json()
    except ValueError:
        print("⚠️ Remote OK: kein JSON")
        return []

    jobs = parse_jobs(payload)
    print(f"📊 {len(jobs)} React-Remote-Jobs von Remote OK\n")
    return jobs
