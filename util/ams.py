# util/ams.py
#
# AMS eJob-Room ist eine Angular-SPA:
#     https://jobs.ams.at/public/emps/jobs?query=react&location=Wien
#
# Die interne API (/public/emps/api/search) antwortet auf direkte requests
# mit 401. Die SPA selbst darf sie aufrufen. Deshalb laden wir die
# Suchseite mit Playwright und lesen die gerenderten Karten:
#
#   <h2><a href="/public/emps/jobs/<uuid>">Titel</a></h2>
#   bei <Firma>
#   ...
#   Arbeitsort:
#   <PLZ>, <Ort>,<Bezirk>
#
# Playwright ist optional. Fehlt es, wird die Quelle übersprungen.

import re
import time
from urllib.parse import quote

from config.constants import (
    AMS_BASE,
    AMS_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
)

_CARD_JS = """
els => els.map(li => {
    const a = li.querySelector("h2 a[id^='ams-search-joboffer-']");
    if (!a) return null;
    return {
        title: a.innerText.trim(),
        url: a.href,
        text: li.innerText.trim(),
    };
}).filter(Boolean)
"""

_UUID_RE = re.compile(r"/jobs/([0-9a-f-]{20,})", re.I)
_COMPANY_RE = re.compile(r"\nbei\s+([^\n]+)")
_LOCATION_RE = re.compile(r"Arbeitsort:\s*\n?\s*([^\n]+)")


def normalize_cards(cards, term=""):
    """Vom Browser extrahierte AMS-Karten -> normalisierte Jobs."""
    jobs = []
    seen = set()
    for card in cards:
        title = (card.get("title") or "").strip()
        url = (card.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)

        text = (card.get("text") or "").strip()
        company_match = _COMPANY_RE.search(text)
        location_match = _LOCATION_RE.search(text)

        company = company_match.group(1).strip() if company_match else ""
        location = location_match.group(1).strip() if location_match else ""

        # "1070, Wien,Neubau" -> ["1070", "Wien", "Neubau"]
        locations = [
            part.strip()
            for part in re.split(r"[,;]", location)
            if part.strip()
        ]
        if not locations:
            locations = ["Wien"]

        match = _UUID_RE.search(url)

        jobs.append(
            {
                "id": match.group(1) if match else url,
                "title": title,
                "url": url,
                "company": company,
                "description": text,
                "locations": locations,
                "home_office": bool(
                    re.search(r"home[\s-]?office|remote|hybrid", text, re.I)
                ),
                "employment_type": "",
                "posted": "",
                "source": "ams.at",
                "matched_terms": [term] if term else [],
            }
        )
    return jobs


def fetch_ams_jobs(terms=None):
    """Holt Wien-Treffer über einen Headless-Browser."""
    terms = terms or AMS_SEARCH_TERMS

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "   ⚠️ Playwright fehlt – AMS wird übersprungen "
            "(env/bin/python -m pip install playwright)"
        )
        return []

    jobs = {}
    print("📡 Lese AMS eJob-Room (Wien) ...")
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
            url = (
                f"{AMS_BASE}/jobs?query={quote(term)}"
                f"&location=Wien"
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(7000)
                cards = page.eval_on_selector_all(
                    "#ams-search-result-list li", _CARD_JS
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
    print(f"📊 {len(jobs)} eindeutige Jobs vom AMS\n")
    return list(jobs.values())
