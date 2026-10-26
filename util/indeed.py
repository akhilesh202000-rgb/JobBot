# util/indeed.py
#
# Indeed Österreich blockt requests und RSS mit Cloudflare (403). Mit einem
# echten Chromium (Playwright) lädt die Suche:
#     https://at.indeed.com/jobs?q=react&l=Wien
#
# Jede Karte hat ein <a data-jk="<job-key>">. Die stabile Detail-URL ist
#     https://at.indeed.com/viewjob?jk=<job-key>
#
# Firma/Standort stehen in den Test-IDs company-name und text-location.
# Playwright ist optional. Fehlt es, wird die Quelle übersprungen.

import re
import time
from urllib.parse import quote

from config.constants import (
    INDEED_BASE,
    INDEED_LOCATION,
    INDEED_MAX_SCROLLS,
    INDEED_SEARCH_TERMS,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
)

_CARD_JS = """
els => els.map(el => {
    const card = el.closest("div.job_seen_beacon") || el.closest("li") || el.parentElement;
    const companyEl = card ? card.querySelector("[data-testid='company-name']") : null;
    const locationEl = card ? card.querySelector("[data-testid='text-location']") : null;
    const titleEl = el.querySelector("span[title]") || el;
    return {
        jk: el.getAttribute("data-jk") || "",
        title: titleEl ? titleEl.innerText.trim() : "",
        company: companyEl ? companyEl.innerText.trim() : "",
        location: locationEl ? locationEl.innerText.trim() : "",
        text: card ? card.innerText.trim() : "",
    };
})
"""


def normalize_cards(cards, term=""):
    """Vom Browser extrahierte Indeed-Karten -> normalisierte Jobs."""
    jobs = []
    seen = set()
    for card in cards:
        jk = (card.get("jk") or "").strip()
        title = (card.get("title") or "").strip()
        if not jk or not title or jk in seen:
            continue
        seen.add(jk)

        location = (card.get("location") or "").strip()
        # Indeed AT liefert gelegentlich englische Ortsnamen.
        location = re.sub(r"\bVienna\b", "Wien", location)
        locations = [location] if location else []

        jobs.append(
            {
                "id": jk,
                "title": title,
                "url": f"{INDEED_BASE}/viewjob?jk={jk}",
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
                "source": "indeed.at",
                "matched_terms": [term] if term else [],
            }
        )
    return jobs


def fetch_indeed_jobs(terms=None):
    """Holt Wien-Treffer über einen Headless-Browser."""
    terms = terms or INDEED_SEARCH_TERMS

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "   ⚠️ Playwright fehlt – Indeed wird übersprungen "
            "(env/bin/python -m pip install playwright)"
        )
        return []

    jobs = {}
    print("📡 Lese Indeed Österreich (Wien) ...")
    print(f"{'Suchbegriff':<20} | {'neu':>4} | {'gesamt':>6}")
    print("-" * 40)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        for term in terms:
            # Indeed zeigt nach mehreren Suchen schnell einen Security Check.
            # Ein frischer Context pro Begriff umgeht das zuverlässig.
            context = browser.new_context(
                locale="de-AT",
                user_agent=REQUEST_HEADERS["User-Agent"],
            )
            page = context.new_page()
            url = (
                f"{INDEED_BASE}/jobs?q={quote(term)}"
                f"&l={quote(INDEED_LOCATION)}"
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4000)
                for _ in range(INDEED_MAX_SCROLLS):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1200)
                cards = page.eval_on_selector_all("[data-jk]", _CARD_JS)
            except Exception as exc:
                print(f"{term:<20} | ⚠️  | {exc}")
                continue
            finally:
                context.close()

            new_count = 0
            for job in normalize_cards(cards, term=term):
                if job["url"] in jobs:
                    if term not in jobs[job["url"]]["matched_terms"]:
                        jobs[job["url"]]["matched_terms"].append(term)
                    continue
                jobs[job["url"]] = job
                new_count += 1

            print(f"{term:<20} | {new_count:>4} | {len(jobs):>6}")
            # Kurze Pausen reichen nicht: Indeed prüft die Frequenz.
            time.sleep(10)

        browser.close()

    print("-" * 40)
    print(f"📊 {len(jobs)} eindeutige Jobs von Indeed\n")
    return list(jobs.values())
