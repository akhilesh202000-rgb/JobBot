# util/arbeitnow.py
#
# Arbeitnow hat eine öffentliche Job-Board-API:
#     https://www.arbeitnow.com/api/job-board-api?page=1
#
# Jede Seite liefert bis zu 300 Jobs; `links.next` zeigt die nächste Seite.
# Felder: slug, company_name, title, description, remote, url, tags,
#         job_types, location, created_at
#
# Arbeitnow ist europaweit. Wir behalten nur Jobs in Wien/Österreich oder
# echte Remote-Jobs (dann als "Wien (Remote)").

import datetime as dt
import html
import re
import time

import requests

from config.constants import (
    ARBEITNOW_API,
    ARBEITNOW_MAX_PAGES,
    POLITE_DELAY_SECONDS,
    REACT_IN_TEXT,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_VIENNA_RE = re.compile(r"\b(wien|vienna)\b", re.I)
_AUSTRIA_RE = re.compile(r"\baustria\b|\bösterreich\b|\boesterreich\b", re.I)


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


def _is_remote(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "remote"}


def normalize_job(row):
    """Arbeitnow-Job -> normalisiertes Job-Dict oder None."""
    title = _clean(row.get("title"))
    description = _clean(row.get("description"))
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(item) for item in tags]
    location = _clean(row.get("location"))
    remote = _is_remote(row.get("remote"))

    if not title or not REACT_IN_TEXT.search(
        " ".join([title, description, " ".join(tags)])
    ):
        return None

    if _VIENNA_RE.search(location):
        locations = [location]
        home_office = remote
    elif remote:
        locations = ["Wien (Remote)"]
        home_office = True
    elif _AUSTRIA_RE.search(location):
        # Österreich, aber nicht Wien (z. B. Graz/Linz) -> nicht pendelbar.
        return None
    else:
        return None

    slug = row.get("slug") or ""
    url = row.get("url") or (
        f"https://www.arbeitnow.com/view/{slug}" if slug else ""
    )
    if not url:
        return None

    job_types = row.get("job_types") or []
    if isinstance(job_types, str):
        job_types = [job_types]

    region = location or ("Remote" if remote else "")
    if region:
        description = f"{description} Standort: {region}".strip()

    return {
        "id": str(slug or row.get("url") or url),
        "title": title,
        "url": url,
        "company": _clean(row.get("company_name")),
        "description": description,
        "locations": locations,
        "home_office": home_office,
        "employment_type": " / ".join(
            _clean(item) for item in job_types if item
        ),
        "posted": _posted(row.get("created_at")),
        "source": "arbeitnow.com",
        "matched_terms": [],
        "remote_region": region,
    }


def parse_jobs(payload):
    """JSON-Antwort der Arbeitnow-API -> normalisierte Jobs."""
    jobs = []
    for row in payload.get("data") or []:
        job = normalize_job(row)
        if job:
            jobs.append(job)
    return jobs


def fetch_arbeitnow_jobs():
    """Liest mehrere Arbeitnow-Seiten und filtert Wien/Remote."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers["Accept"] = "application/json"

    jobs = {}
    print("📡 Lese Arbeitnow (Wien/Remote, React) ...")

    for page in range(1, ARBEITNOW_MAX_PAGES + 1):
        try:
            response = session.get(
                ARBEITNOW_API,
                params={"page": page},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"⚠️ Arbeitnow Seite {page}: {exc}")
            break

        if response.status_code != 200:
            print(f"⚠️ Arbeitnow Seite {page}: HTTP {response.status_code}")
            break

        try:
            payload = response.json()
        except ValueError:
            print(f"⚠️ Arbeitnow Seite {page}: kein JSON")
            break

        rows = payload.get("data") or []
        if not rows:
            break

        new_count = 0
        for job in parse_jobs(payload):
            if job["url"] in jobs:
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"   Seite {page:>2}: {new_count:>3} neue Treffer (gesamt {len(jobs)})")
        if not (payload.get("links") or {}).get("next"):
            break
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"📊 {len(jobs)} React-Jobs (Wien/Remote) von Arbeitnow\n")
    return list(jobs.values())
