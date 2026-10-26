# util/workinaustria.py
#
# Work in Austria ist eine Informationsplattform für internationale
# Fachkräfte. Die Seite /fachkraefte/jobs verlinkt auf ein externes
# Bewerberportal (jobs.workinaustria.com), das ohne Login auf die
# Marketingseite zurückleitet. Ein öffentliches Job-Listing gibt es dort
# derzeit nicht.
#
# Das Modul prüft die Seite trotzdem auf Joblinks und liefert eine leere
# Liste, solange kein öffentliches Listing existiert.

import html
import re

import requests

from config.constants import (
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    WORKINAUSTRIA_JOBS_URL,
)

_TAG_RE = re.compile(r"<[^>]+>")
_JOB_LINK_RE = re.compile(
    r'href="(https?://[^"]*(?:job|stelle|inserat)[^"]*)"[^>]*>(?P<body>.*?)</a>',
    re.S | re.I,
)


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def parse_cards(page_html):
    """Joblinks auf der Work-in-Austria-Seite -> normalisierte Jobs."""
    jobs = []
    seen = set()
    for match in _JOB_LINK_RE.finditer(page_html):
        url = html.unescape(match.group(1))
        title = _clean(match.group("body"))
        if not title or url in seen:
            continue
        # Interne Navigations- und Login-Links sind keine Stellenanzeigen.
        if "/fachkraefte/jobs" in url or "/stellenausschreibungen" in url:
            continue
        if re.search(r"login|auth=|regist", f"{url} {title}", re.I):
            continue
        seen.add(url)
        jobs.append(
            {
                "id": url.rstrip("/").rsplit("/", 1)[-1],
                "title": title,
                "url": url,
                "company": "",
                "description": title,
                "locations": ["Wien"],
                "home_office": False,
                "employment_type": "",
                "posted": "",
                "source": "workinaustria.com",
                "matched_terms": [],
            }
        )
    return jobs


def fetch_workinaustria_jobs():
    """Prüft Work in Austria auf ein öffentliches Job-Listing."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    print("📡 Lese Work in Austria ...")

    try:
        response = session.get(
            WORKINAUSTRIA_JOBS_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except Exception as exc:
        print(f"   ⚠️ Work in Austria: {exc}\n")
        return []

    if response.status_code != 200:
        print(f"   ⚠️ Work in Austria: HTTP {response.status_code}\n")
        return []

    jobs = parse_cards(response.text)
    if not jobs:
        print(
            "   ⚠️ Work in Austria hat kein öffentliches Job-Listing "
            "(Bewerberportal nur mit Login) – übersprungen\n"
        )
        return []

    print(f"📊 {len(jobs)} Jobs von Work in Austria\n")
    return jobs
