# util/aiaustria.py
#
# AI Austria betreibt ein öffentliches Job-Board auf Super.so/Notion:
#     https://aiaustria.com/jobs
#
# Die Karten sind `notion-collection-list__item`-Blöcke. Jede Karte hat:
#   - einen Anchor mit `data-server-link="true"` (Bewerbungs-/Job-URL)
#   - den Titel in `notion-property__title`
#   - Standort-Pills in `notion-pill`
#
# Es gibt keine Beschreibung und keine Firma. Wir bauen eine kurze
# Beschreibung aus Titel + Standort. Nur Wien und Remote sind relevant.

import html
import re

import requests

from config.constants import (
    AIAUSTRIA_JOBS_URL,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_ITEM_RE = re.compile(
    r'<div class="notion-collection-list__item ">', re.I
)
_LINK_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*data-server-link="true"', re.I
)
_ANY_LINK_RE = re.compile(r'<a[^>]+href="([^"]+)"', re.I)
_TITLE_RE = re.compile(
    r'notion-property__title[^"]*"[^>]*>(.*?)</div>', re.S
)
_PILL_RE = re.compile(r'notion-pill[^"]*"[^>]*>(.*?)</span>', re.S)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _location(raw):
    """Standort-Pill -> locations-Liste oder None."""
    text = _clean(raw)
    lower = text.lower()
    if "wien" in lower:
        return [text], False
    if "vienna" in lower:
        # Englische Schreibweise für die Geo-Logik normalisieren.
        return ["Wien"], False
    if "remote" in lower:
        return ["Wien (Remote)"], True
    return None, False


def parse_cards(page_html):
    """AI-Austria-Seite -> normalisierte Jobs."""
    chunks = _ITEM_RE.split(page_html)
    jobs = []

    for chunk in chunks[1:]:
        link_match = _LINK_RE.search(chunk) or _ANY_LINK_RE.search(chunk)
        title_match = _TITLE_RE.search(chunk)
        if not link_match or not title_match:
            continue

        title = _clean(title_match.group(1))
        url = html.unescape(link_match.group(1))
        if not title or not url:
            continue

        pills = [_clean(value) for value in _PILL_RE.findall(chunk)]
        pills = [value for value in pills if value]
        location_raw = pills[0] if pills else ""
        locations, home_office = _location(location_raw)
        if not locations:
            continue

        description = " · ".join(
            part for part in (title, location_raw, "AI Austria Job Board") if part
        )

        jobs.append(
            {
                "id": url.rstrip("/").rsplit("/", 1)[-1] or url,
                "title": title,
                "url": url,
                "company": "",
                "description": description,
                "locations": locations,
                "home_office": home_office,
                "employment_type": "",
                "posted": "",
                "source": "aiaustria.com",
                "matched_terms": [],
            }
        )

    return jobs


def fetch_aiaustria_jobs():
    """Liest das AI-Austria-Job-Board."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    print("📡 Lese AI Austria Jobs ...")
    try:
        response = session.get(AIAUSTRIA_JOBS_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    except Exception as exc:
        print(f"⚠️ AI Austria: {exc}")
        return []

    if response.status_code != 200:
        print(f"⚠️ AI Austria: HTTP {response.status_code}")
        return []

    jobs = parse_cards(response.text)
    print(f"📊 {len(jobs)} Wien-/Remote-Jobs von AI Austria\n")
    return jobs
