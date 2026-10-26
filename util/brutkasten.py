# util/brutkasten.py
#
# brutkasten hatte ein eigenes Jobboard unter https://brutkasten.com/jobs.
# Seit der Umstellung auf "Brutkasten Talents" (Getro) leitet die URL auf
#     https://talents.brutkasten.com/not-found
# um; das Getro-Board hat aktuell keine gültige network_id.
#
# Das Modul versucht die alte Jobliste trotzdem und liefert eine leere Liste,
# solange das Board nicht erreichbar ist. So bricht der Lauf nicht ab und
# die Quelle funktioniert automatisch wieder, falls brutkasten das Board
# zurückbringt.

import html
import re

import requests

from config.constants import (
    BRUTKASTEN_JOBS_URL,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_JOB_LINK_RE = re.compile(
    r'href="(https://brutkasten\.com/jobs/job/[^"]+)"[^>]*>(?P<body>.*?)</a>',
    re.S | re.I,
)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def parse_cards(page_html):
    """Alte brutkasten-Jobkarten -> normalisierte Jobs (best effort)."""
    jobs = []
    seen = set()
    for match in _JOB_LINK_RE.finditer(page_html):
        url = match.group(1)
        title = _clean(match.group("body"))
        if not title or url in seen:
            continue
        seen.add(url)
        jobs.append(
            {
                "id": url.rstrip("/").rsplit("-", 1)[-1],
                "title": title,
                "url": url,
                "company": "brutkasten",
                "description": title,
                "locations": ["Wien"],
                "home_office": False,
                "employment_type": "",
                "posted": "",
                "source": "brutkasten.com",
                "matched_terms": [],
            }
        )
    return jobs


def fetch_brutkasten_jobs():
    """Versucht das (derzeit nicht erreichbare) brutkasten-Jobboard."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    print("📡 Lese brutkasten Jobs ...")

    try:
        response = session.get(
            BRUTKASTEN_JOBS_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except Exception as exc:
        print(f"   ⚠️ brutkasten: {exc}\n")
        return []

    if response.status_code != 200 or "/not-found" in response.url:
        print(
            "   ⚠️ brutkasten-Jobboard ist derzeit nicht erreichbar "
            "(Getro-Board 404) – übersprungen\n"
        )
        return []

    jobs = parse_cards(response.text)
    print(f"📊 {len(jobs)} Jobs von brutkasten\n")
    return jobs
