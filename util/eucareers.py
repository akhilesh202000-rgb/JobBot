# util/eucareers.py
#
# EU Careers (EPSO) hat eine öffentliche Jobsuche:
#     https://eu-careers.europa.eu/jobs_en?page=1
#
# Jede Seite enthält 20 Karten (`eujmp-vacancy-result`) mit:
#   - Institution + Datum in `eujmp-vacancy-result__top-meta`
#   - Titel + Link in `eujmp-vacancy-result__title`
#   - Vertragsart, Grad und Ort in `eujmp-vacancy-result__bottom-meta`
#
# Die meisten Stellen sind in Brüssel/Luxemburg. Wir behalten nur
# Wien/Österreich (oder Remote) und lassen den normalen React-Filter
# entscheiden.

import html
import re
import time

import requests

from config.constants import (
    EUCAREERS_JOBS_URL,
    EUCAREERS_MAX_PAGES,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_SPLIT = '<div class="eujmp-vacancy-result">'
_TOP_RE = re.compile(
    r'<ul class="eujmp-vacancy-result__top-meta">\s*<li>(.*?)</li>', re.S
)
_DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
_TITLE_RE = re.compile(
    r'<a href="(/jobs/[^"]+)"[^>]*class="[^"]*'
    r'eujmp-vacancy-result__title[^"]*">(.*?)</a>',
    re.S,
)
_BOTTOM_RE = re.compile(
    r'<ul class="eujmp-vacancy-result__bottom-meta">(.*?)</ul>', re.S
)
_LI_RE = re.compile(r"<li>(.*?)</li>", re.S)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def normalize_card(block):
    """EU-Careers-Karte -> normalisiertes Job-Dict oder None."""
    title_match = _TITLE_RE.search(block)
    if not title_match:
        return None

    path, title_raw = title_match.groups()
    title = _clean(title_raw)
    if not title:
        return None

    top_match = _TOP_RE.search(block)
    institution = _clean(top_match.group(1)) if top_match else ""

    bottom_match = _BOTTOM_RE.search(block)
    meta = [
        _clean(value)
        for value in _LI_RE.findall(bottom_match.group(1) if bottom_match else "")
        if _clean(value)
    ]
    location = meta[-1] if meta else ""
    contract = " / ".join(meta[:-1]) if len(meta) > 1 else ""

    lower = location.lower()
    if "wien" in lower or "vienna" in lower or "austria" in lower:
        locations = [location]
        home_office = False
    elif "remote" in lower or "home-based" in lower:
        locations = ["Wien (Remote)"]
        home_office = True
    else:
        return None

    date_match = _DATE_RE.search(block)
    posted = date_match.group(1)[:10] if date_match else ""

    description = " · ".join(
        part
        for part in (title, institution, location, contract)
        if part
    )

    return {
        "id": path.rstrip("/").rsplit("/", 1)[-1],
        "title": title,
        "url": f"https://eu-careers.europa.eu{path}",
        "company": institution,
        "description": description,
        "locations": locations,
        "home_office": home_office,
        "employment_type": contract,
        "posted": posted,
        "source": "eu-careers.europa.eu",
        "matched_terms": [],
    }


def parse_page(page_html):
    """EU-Careers-Seite -> normalisierte Jobs."""
    chunks = (page_html or "").split(_CARD_SPLIT)
    jobs = []
    for chunk in chunks[1:]:
        job = normalize_card(chunk)
        if job:
            jobs.append(job)
    return jobs


def fetch_eucareers_jobs():
    """Liest mehrere EU-Careers-Seiten und filtert Wien/Österreich."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese EU Careers (Wien/Österreich) ...")

    for page in range(1, EUCAREERS_MAX_PAGES + 1):
        try:
            response = session.get(
                EUCAREERS_JOBS_URL,
                params={"page": page},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"⚠️ EU Careers Seite {page}: {exc}")
            break

        if response.status_code != 200:
            print(f"⚠️ EU Careers Seite {page}: HTTP {response.status_code}")
            break

        page_jobs = parse_page(response.text)
        if not page_jobs:
            break

        new_count = 0
        for job in page_jobs:
            if job["url"] in jobs:
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"   Seite {page:>2}: {new_count:>3} Wien-Treffer (gesamt {len(jobs)})")
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"📊 {len(jobs)} Wien-/Österreich-Jobs von EU Careers\n")
    return list(jobs.values())
