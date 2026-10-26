# util/wearedevelopers.py
#
# WeAreDevelopers bietet eine agentenfreundliche Markdown-Version:
#     https://www.wearedevelopers.com/jobs.md?country=AT&q=react
#
# Jeder Treffer sieht so aus:
#     ## Frontend Developer (React)
#     - **Company:** ACME
#     - **Location:** Wien, Austria
#     - **Contract:** Permanent contract
#     - **Published:** October 22, 2026
#     - [View job](https://www.wearedevelopers.com/jobs/ext/...)
#
# `q=<term>` funktioniert; `page` wird auf dem .md-Endpunkt nicht
# unterstützt. Deshalb mehrere Suchbegriffe abfragen und nach URL
# deduplizieren. Nur Wien und "Remote available" sind relevant.

import datetime as dt
import html
import re
import time

import requests

from config.constants import (
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    WEAREDEVELOPERS_COUNTRY,
    WEAREDEVELOPERS_JOBS_MD,
    WEAREDEVELOPERS_SEARCH_TERMS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_SECTION_RE = re.compile(r"^\s*## (.+)$", re.M)
_VIEW_RE = re.compile(r"- \[View job\]\((https?://[^)]+)\)")


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _field(block, name):
    match = re.search(
        rf"- \*\*{re.escape(name)}:\*\* (.*?)(?=\n\s*- |\n\s*## |\Z)",
        block,
        re.S,
    )
    return _clean(match.group(1)) if match else ""


def _posted(value):
    value = _clean(value)
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _location(raw):
    """Markdown-Standort -> (locations, home_office) oder (None, False)."""
    lower = (raw or "").lower()
    if "wien" in lower or "vienna" in lower:
        return [raw], False
    if "remote" in lower:
        return ["Wien (Remote)"], True
    return None, False


def parse_markdown(markdown, term=""):
    """Markdown-Antwort von WeAreDevelopers -> normalisierte Jobs."""
    matches = list(_SECTION_RE.finditer(markdown or ""))
    jobs = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        block = markdown[start:end]

        title = _clean(match.group(1))
        location_raw = _field(block, "Location")
        locations, home_office = _location(location_raw)
        if not title or not locations:
            continue

        view_match = _VIEW_RE.search(block)
        url = view_match.group(1) if view_match else ""
        if not url:
            continue

        company = _field(block, "Company")
        experience = _field(block, "Experience")
        salary = _field(block, "Salary")
        contract = _field(block, "Contract")
        published = _field(block, "Published")

        description = " · ".join(
            part
            for part in (
                title,
                company,
                location_raw,
                f"Erfahrung: {experience}" if experience else "",
                salary,
                contract,
            )
            if part
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
                "employment_type": contract,
                "posted": _posted(published),
                "source": "wearedevelopers.com",
                "matched_terms": [term] if term else [],
            }
        )

    return jobs


def fetch_wearedevelopers_jobs(terms=None):
    """Holt React-Treffer aus dem WeAreDevelopers-Markdown-Endpunkt."""
    terms = terms or WEAREDEVELOPERS_SEARCH_TERMS
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese WeAreDevelopers (Wien/Remote) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        try:
            response = session.get(
                WEAREDEVELOPERS_JOBS_MD,
                params={"country": WEAREDEVELOPERS_COUNTRY, "q": term},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"{term:<20} | ⚠️  | {exc}")
            continue

        if response.status_code != 200:
            print(f"{term:<20} | ⚠️  | HTTP {response.status_code}")
            continue

        new_count = 0
        for job in parse_markdown(response.text, term=term):
            if job["url"] in jobs:
                if term not in jobs[job["url"]]["matched_terms"]:
                    jobs[job["url"]]["matched_terms"].append(term)
                continue
            jobs[job["url"]] = job
            new_count += 1

        print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von WeAreDevelopers\n")
    return list(jobs.values())
