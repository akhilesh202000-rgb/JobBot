# util/thehub.py
#
# The Hub ist ein Nordeuropa-/UK-fokussiertes Job-Board auf Nuxt:
#     https://thehub.io/jobs?search=react
#
# Die Treffer sind serverseitig gerenderte Karten:
#   <div class="card card-job-find-list">
#     <span class="card-job-find-list__position">Titel</span>
#     <div class="bullet-inline-list ...">
#       <span>Firma</span><span>Ort</span><span>Vollzeit</span>
#     </div>
#     <a href="/jobs/<id>" class="card-job-find-list__link"></a>
#   </div>
#
# Wien-Treffer sind selten; Remote-Jobs werden als "Wien (Remote)" gemappt.

import html
import re
import time

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    THEHUB_JOBS_URL,
    THEHUB_SEARCH_TERMS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(r'<div class="card card-job-find-list"')
_TITLE_RE = re.compile(
    r'card-job-find-list__position">(.*?)</span>', re.S
)
_META_RE = re.compile(
    r'<div class="bullet-inline-list[^"]*"[^>]*>(.*?)</div>', re.S
)
_SPAN_RE = re.compile(r"<span>(.*?)</span>", re.S)
_LINK_RE = re.compile(r'href="(/jobs/[^"]+)"')


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def parse_cards(page_html, term=""):
    """The-Hub-Suchseite -> normalisierte Jobs."""
    matches = list(_CARD_RE.finditer(page_html or ""))
    jobs = []

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
        block = page_html[match.start():end]

        title_match = _TITLE_RE.search(block)
        link_match = _LINK_RE.search(block)
        if not title_match or not link_match:
            continue

        title = _clean(title_match.group(1))
        meta_match = _META_RE.search(block)
        meta = [
            _clean(value)
            for value in _SPAN_RE.findall(meta_match.group(1) if meta_match else "")
            if _clean(value)
        ]
        company = meta[0] if len(meta) > 0 else ""
        location = meta[1] if len(meta) > 1 else ""
        employment = meta[2] if len(meta) > 2 else ""

        lower = f"{location} {employment}".lower()
        if "wien" in lower or "vienna" in lower:
            locations = [location or "Wien"]
            home_office = False
        elif "remote" in lower:
            locations = ["Wien (Remote)"]
            home_office = True
        else:
            continue

        url = f"https://thehub.io{link_match.group(1)}"
        description = " · ".join(
            part for part in (title, company, location, employment) if part
        )

        jobs.append(
            {
                "id": url.rstrip("/").rsplit("/", 1)[-1],
                "title": title,
                "url": url,
                "company": company,
                "description": description,
                "locations": locations,
                "home_office": home_office,
                "employment_type": employment,
                "posted": "",
                "source": "thehub.io",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_thehub_jobs(terms=None):
    """Holt The-Hub-Treffer für alle konfigurierten Suchbegriffe."""
    terms = terms or THEHUB_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese The Hub (Wien/Remote) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        try:
            response = session.get(
                THEHUB_JOBS_URL,
                params={"search": term},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        new_count = 0
        for job in parse_cards(response.text, term=term):
            if job["url"] in jobs:
                if term not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(term)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von The Hub\n")
    return list(jobs.values())
