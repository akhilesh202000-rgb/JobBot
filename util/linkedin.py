# util/linkedin.py
#
# LinkedIn bietet eine öffentliche Guest-Jobsuche, die ohne Login
# HTML-Fragmente liefert:
#     https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
#         ?keywords=react&location=Vienna&start=0
#
# Pro Seite kommen 10 Karten. Wir lesen pro Suchbegriff eine Seite und
# deduplizieren über die Job-ID aus `data-entity-urn`.
#
# Die Karten enthalten keinen Volltext, deshalb nutzen wir den Suchbegriff
# als React-Beleg (`matched_terms`).

import html
import re
import time

import requests

from config.constants import (
    LINKEDIN_GUEST_API,
    LINKEDIN_LOCATION,
    LINKEDIN_MAX_PAGES,
    LINKEDIN_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(r"<li>(.*?)</li>", re.S)
_URN_RE = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_TITLE_RE = re.compile(
    r'base-search-card__title[^>]*>(.*?)</h3>', re.S
)
_COMPANY_RE = re.compile(
    r'base-search-card__subtitle[^>]*>(.*?)</h4>', re.S
)
_LOCATION_RE = re.compile(
    r'job-search-card__location[^>]*>(.*?)</span>', re.S
)
_DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
_LINK_RE = re.compile(
    r'base-card__full-link[^"]*"[^>]*href="([^"]+)"', re.S
)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _is_vienna(location):
    lower = (location or "").lower()
    return "vienna" in lower or "wien" in lower


def normalize_card(block, term=""):
    """LinkedIn-Karten-HTML -> normalisiertes Job-Dict oder None."""
    urn = _URN_RE.search(block)
    title_match = _TITLE_RE.search(block)
    location_match = _LOCATION_RE.search(block)
    if not title_match:
        return None

    title = _clean(title_match.group(1))
    company_match = _COMPANY_RE.search(block)
    company = _clean(company_match.group(1)) if company_match else ""
    location = _clean(location_match.group(1)) if location_match else ""

    if not title or not _is_vienna(location):
        return None

    job_id = urn.group(1) if urn else ""
    if job_id:
        url = f"https://www.linkedin.com/jobs/view/{job_id}"
    else:
        link_match = _LINK_RE.search(block)
        url = html.unescape(link_match.group(1)) if link_match else ""
    if not url:
        return None

    description = " · ".join(
        part for part in (title, company, location) if part
    )
    date_match = _DATE_RE.search(block)
    posted = date_match.group(1)[:10] if date_match else ""

    return {
        "id": job_id or url,
        "title": title,
        "url": url,
        "company": company,
        "description": description,
        "locations": [location],
        "home_office": bool(
            re.search(r"home[\s-]?office|remote", description, re.I)
        ),
        "employment_type": "",
        "posted": posted,
        "source": "linkedin.com",
        "matched_terms": [term] if term else [],
    }


def parse_cards(fragment, term=""):
    """HTML-Fragment der LinkedIn-Guest-Suche -> normalisierte Jobs."""
    jobs = []
    for match in _CARD_RE.finditer(fragment or ""):
        job = normalize_card(match.group(1), term=term)
        if job:
            jobs.append(job)
    return jobs


def fetch_linkedin_jobs(terms=None):
    """Holt Wien-Treffer aus der öffentlichen LinkedIn-Guest-Suche."""
    terms = terms or LINKEDIN_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese LinkedIn Jobs (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        new_count = 0
        for page in range(LINKEDIN_MAX_PAGES):
            params = {
                "keywords": term,
                "location": LINKEDIN_LOCATION,
                "start": page * 10,
            }
            try:
                response = session.get(
                    LINKEDIN_GUEST_API,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                print(f"{term:<20} | ⚠️  | {exc}")
                break

            if response.status_code == 429:
                print(f"{term:<20} | ⚠️  | Rate-Limit (429)")
                break
            if response.status_code != 200:
                print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
                break

            page_jobs = parse_cards(response.text, term=term)
            if not page_jobs:
                break

            for job in page_jobs:
                if job["url"] in jobs:
                    if term not in jobs[job["url"]]["matched_terms"]:
                        jobs[job["url"]]["matched_terms"].append(term)
                    continue
                jobs[job["url"]] = job
                new_count += 1

            time.sleep(POLITE_DELAY_SECONDS)

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von LinkedIn\n")
    return list(jobs.values())
