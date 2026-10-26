# util/karriere.py
#
# Liest die Jobsuche von karriere.at.
#
# karriere.at rendert die Treffer serverseitig als JSON in
#     window.VUE_INITIAL_STATE = {...}
# Das ist stabiler als HTML-Selektoren und braucht keinen API-Key.
#
# Hinweis: Die "Mehr laden"-Pagination läuft clientseitig, d. h. ?page=2
# wird serverseitig ignoriert. Deshalb wird pro Suchbegriff die erste
# Ergebnisseite geholt und über mehrere Begriffe dedupliziert.

import html
import json
import re
import time
import urllib.parse

import requests

from config.constants import (
    KARRIERE_BASE,
    KARRIERE_LOCATION,
    KARRIERE_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
)

_STATE_MARKER = "window.VUE_INITIAL_STATE"
_TAG_RE = re.compile(r"<[^>]+>")


def _extract_state(page_html):
    """Schneidet das JSON-Objekt hinter window.VUE_INITIAL_STATE heraus."""
    marker_at = page_html.find(_STATE_MARKER)
    if marker_at == -1:
        raise ValueError("VUE_INITIAL_STATE nicht gefunden")

    start = page_html.find("{", marker_at)
    if start == -1:
        raise ValueError("JSON-Start nicht gefunden")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(page_html)):
        char = page_html[index]

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
                return json.loads(page_html[start:index + 1])

    raise ValueError("JSON-Ende nicht gefunden")


def _clean(text):
    """HTML entfernen, Entities auflösen, Whitespace normalisieren."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _fetch(url):
    """GET mit Retry/Backoff. Gibt HTML-Text oder None zurück."""
    last_error = None
    for attempt in range(REQUEST_RETRIES):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return response.text
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)

        if attempt < REQUEST_RETRIES - 1:
            time.sleep(1.5 * (attempt + 1))

    print(f"   ⚠️ karriere.at nicht erreichbar ({last_error})")
    return None


def _normalize(item):
    company = item.get("company") or {}
    locations = [
        _clean(loc.get("name"))
        for loc in (item.get("locations") or [])
        if loc.get("name")
    ]

    return {
        "id": str(item.get("id", "")),
        "title": _clean(item.get("title")),
        "url": item.get("link", ""),
        "company": _clean(company.get("name")),
        "description": _clean(item.get("summary")),
        "locations": locations,
        "home_office": bool(item.get("isHomeOffice")),
        "employment_type": _clean(item.get("employmentTypes")),
        "posted": _clean(item.get("date")),
        "source": "karriere.at",
        # Suchbegriffe, über die der Job gefunden wurde. Wichtig, weil der
        # Such-Summary oft leer ist und React dann nur hier auftaucht.
        "matched_terms": [],
    }


def fetch_karriere_jobs(terms=None):
    """Holt Wien-Treffer für alle Suchbegriffe und dedupliziert nach Job-ID."""
    terms = terms or KARRIERE_SEARCH_TERMS
    jobs = {}

    print("📡 Lese karriere.at (Wien) ...")
    print(f"{'Suchbegriff':<22} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    for term in terms:
        query = urllib.parse.quote_plus(term)
        url = f"{KARRIERE_BASE}?keywords={query}&locations={KARRIERE_LOCATION}"

        page = _fetch(url)
        if not page:
            continue

        try:
            state = _extract_state(page)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"{term:<22} | ⚠️  | {exc}")
            continue

        items = (
            state.get("jobsSearchList", {})
            .get("activeItems", {})
            .get("items", [])
        )

        new_count = 0
        for wrapper in items:
            item = wrapper.get("jobsItem")
            if not item or not item.get("id") or not item.get("link"):
                continue
            job_id = str(item["id"])
            if job_id in jobs:
                jobs[job_id]["matched_terms"].append(term)
                continue
            normalized = _normalize(item)
            normalized["matched_terms"] = [term]
            jobs[job_id] = normalized
            new_count += 1

        print(f"{term:<22} | {new_count:>4} | {len(jobs):>6}")
        time.sleep(POLITE_DELAY_SECONDS)

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von karriere.at\n")
    return list(jobs.values())
