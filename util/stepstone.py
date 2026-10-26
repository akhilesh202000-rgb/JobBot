# util/stepstone.py
#
# StepStone Österreich ist serverseitig gerendert, blockt aber einfache
# requests mit Timeouts. Mit Playwright/Chromium funktioniert die Suche:
#     https://www.stepstone.at/jobs/react/in-wien
#
# Jede Trefferkarte ist ein <article data-at="job-item"> mit:
#   [data-at="job-item-title"]         Titel + Link
#   [data-at="job-item-company-name"]  Firma
#   [data-at="job-item-location"]      Standort
#
# Playwright ist optional. Fehlt es, wird die Quelle übersprungen.

import re
import time
from urllib.parse import quote

from config.constants import (
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    STEPSTONE_BASE,
    STEPSTONE_SEARCH_TERMS,
)

_CARD_JS = """
els => els.map(el => {
    const titleEl = el.querySelector("[data-at='job-item-title']");
    const companyEl = el.querySelector("[data-at='job-item-company-name']");
    const locationEl = el.querySelector("[data-at='job-item-location']");
    return {
        title: titleEl ? titleEl.innerText.trim() : "",
        url: titleEl ? titleEl.href : "",
        company: companyEl ? companyEl.innerText.trim() : "",
        location: locationEl ? locationEl.innerText.trim() : "",
        text: el.innerText.trim(),
    };
})
"""

_ID_RE = re.compile(r"--(\d+)-inline\.html")


def _job_id(url):
    match = _ID_RE.search(url or "")
    return match.group(1) if match else (url or "")


def normalize_cards(cards, term=""):
    """Vom Browser extrahierte StepStone-Karten -> normalisierte Jobs."""
    jobs = []
    seen = set()
    for card in cards:
        title = (card.get("title") or "").strip()
        url = (card.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)

        location = (card.get("location") or "").strip()
        # StepStone mischt englische Ortsnamen ("Vienna") ein.
        location = re.sub(r"\bVienna\b", "Wien", location)
        locations = [location] if location else []

        jobs.append(
            {
                "id": _job_id(url),
                "title": title,
                "url": url,
                "company": (card.get("company") or "").strip(),
                "description": (card.get("text") or "").strip(),
                "locations": locations,
                "home_office": bool(
                    re.search(
                        r"home[\s-]?office|remote|hybrid",
                        f"{location} {card.get('text') or ''}",
                        re.I,
                    )
                ),
                "employment_type": "",
                "posted": "",
                "source": "stepstone.at",
                "matched_terms": [term] if term else [],
            }
        )
    return jobs


def fetch_stepstone_jobs(terms=None):
    """Holt Wien-Treffer über einen Headless-Browser."""
    terms = terms or STEPSTONE_SEARCH_TERMS

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "   ⚠️ Playwright fehlt – StepStone wird übersprungen "
            "(env/bin/python -m pip install playwright)"
        )
        return []

    jobs = {}
    print("📡 Lese StepStone Österreich (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="de-AT",
            user_agent=REQUEST_HEADERS["User-Agent"],
        )
        page = context.new_page()

        for term in terms:
            slug = quote(term.replace(" ", "-"))
            url = f"{STEPSTONE_BASE}/jobs/{slug}/in-wien"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                cards = page.eval_on_selector_all(
                    "article[data-at='job-item']", _CARD_JS
                )
            except Exception as exc:
                print(f"{term:<20} | ⚠️  | {exc}")
                continue

            new_count = 0
            for job in normalize_cards(cards, term=term):
                if job["url"] in jobs:
                    if term not in jobs[job["url"]]["matched_terms"]:
                        jobs[job["url"]]["matched_terms"].append(term)
                    continue
                jobs[job["url"]] = job
                new_count += 1

            print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
            time.sleep(POLITE_DELAY_SECONDS)

        browser.close()

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von StepStone\n")
    return list(jobs.values())
