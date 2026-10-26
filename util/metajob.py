# util/metajob.py
#
# metajob.at ist eine österreichische Meta-Suchmaschine mit eigenem JSON-RPC:
#
#   POST https://www.metajob.at/_irpc/joyservice/se
#   {"h": "<op-hash>", "a0": <UiSearch>, "a1": 1, "a2": 1}
#
# Der Server verlangt:
#   - ein Cookie, das der Browser-Client setzt (Anti-Bot)
#   - einen Such-Token `a0.s` ("teint"), den die SPA pro Suche erzeugt
#
# Deshalb läuft die Suche über Playwright:
#   1. Startseite laden (setzt Cookie)
#   2. eine UI-Suche auslösen und den Token aus dem RPC-Request abgreifen
#   3. alle Begriffe/Seiten direkt per fetch im Browser-Kontext abfragen
#
# Ohne Playwright fällt das Modul auf reine requests zurück. Die bekommen
# aktuell "Unser System benötigt Cookies" und liefern [] – der Lauf bricht
# dadurch nicht ab.
#
# Installation:
#   env/bin/python -m pip install playwright
#   env/bin/python -m playwright install chromium

import html
import json
import re
import time

import requests

from config.constants import (
    METAJOB_BROWSER_TIMEOUT_MS,
    METAJOB_LOCATION,
    METAJOB_MAX_PAGES,
    METAJOB_PAGE_SIZE,
    METAJOB_RPC_URL,
    METAJOB_SEARCH_HASH,
    METAJOB_SEARCH_TERMS,
    METAJOB_USE_BROWSER,
    POLITE_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
)

_TAG_RE = re.compile(r"<[^>]+>")
_COOKIE_ERROR = "benötigt Cookies"

_BROWSER_SEARCH_JS = """
async (payload) => {
    const response = await fetch("/_irpc/joyservice/se", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
        credentials: "same-origin",
    });
    if (!response.ok) {
        return {_http: response.status};
    }
    return await response.json();
}
"""


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _payload(term, offset=0, token=None):
    """Request-Body für die RPC-Operation `se` (search).

    Entspricht dem echten Client-Request:
        {"a": {"c": term, "e": "Wien"}, "e": 20, "k": 1, "m": 1, "o": 1,
         "q": 8, "s": "<token>", "c": <offset>}
    """
    query = {
        "a": {"c": term, "e": METAJOB_LOCATION},
        "e": METAJOB_PAGE_SIZE,
        "k": 1,   # retRelRegions
        "m": 1,   # retRelConcepts
        "o": 1,   # ynRadiusExpansion
        "q": 8,   # clientSearchSource
    }
    if offset:
        query["c"] = offset
    if token:
        query["s"] = token

    return {"h": METAJOB_SEARCH_HASH, "a0": query, "a1": 1, "a2": 1}


def _normalize_row(row):
    """UiSearchResultRow -> normalisiertes Job-Dict.

    Kurzschlüssel laut Client-Bundle:
      a=jid, c=title, e=url, g=snippets, i=locs, r=ageDays, u=company
    """
    jid = str(row.get("a") or "")
    url = row.get("e") or ""

    # metajob hat keine eigenen Detailseiten; ohne Ziel-URL führt der
    # Click-Through über /dres/jc?p=<jid>.
    if not url and jid:
        url = f"https://www.metajob.at/dres/jc?p={jid}"

    locations = [_clean(loc) for loc in (row.get("i") or []) if _clean(loc)]

    age_days = row.get("r")
    posted = (
        f"vor {age_days} Tagen"
        if isinstance(age_days, int) and age_days >= 0
        else ""
    )

    return {
        "id": jid,
        "title": _clean(row.get("c")),
        "url": url,
        "company": _clean(row.get("u")),
        "description": _clean(row.get("g")),
        "locations": locations,
        "home_office": False,
        "employment_type": "",
        "posted": posted,
        "source": "metajob.at",
        "matched_terms": [],
    }


def _capture_token(page, term):
    """Löst eine UI-Suche aus und liest den `a0.s`-Token aus dem RPC-Request."""
    try:
        with page.expect_response(
            lambda response: "/_irpc/joyservice/se" in response.url,
            timeout=METAJOB_BROWSER_TIMEOUT_MS,
        ) as response_info:
            search_input = page.locator("input:visible").first
            search_input.fill(term)
            search_input.press("Enter")

        post_data = response_info.value.request.post_data or ""
        return json.loads(post_data)["a0"]["s"]
    except Exception as exc:
        print(f"   ⚠️ metajob.at: Such-Token nicht ermittelbar ({exc})")
        return None


def _browser_search(page, term, offset, token):
    """Direkter RPC-Aufruf im Browser-Kontext (Cookie + Token sind gültig)."""
    try:
        return page.evaluate(
            _BROWSER_SEARCH_JS, _payload(term, offset=offset, token=token)
        )
    except Exception as exc:
        print(f"   ⚠️ metajob.at: Suche fehlgeschlagen ({exc})")
        return None


def _fetch_with_browser(terms):
    """Playwright-Fallback: echte Browser-Session + Token, dann RPC."""
    from playwright.sync_api import sync_playwright

    jobs = {}
    print("   🌐 metajob.at: Browser-Fallback (Playwright) ...")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="de-AT")
        page = context.new_page()

        try:
            page.goto(
                "https://www.metajob.at/",
                wait_until="networkidle",
                timeout=METAJOB_BROWSER_TIMEOUT_MS,
            )
            token = _capture_token(page, terms[0])
            if not token:
                return []

            for term in terms:
                new_count = 0

                for page_index in range(METAJOB_MAX_PAGES):
                    offset = page_index * METAJOB_PAGE_SIZE
                    data = _browser_search(page, term, offset, token)

                    if not data or data.get("_http"):
                        print(
                            f"   ⚠️ metajob.at: HTTP "
                            f"{(data or {}).get('_http', '?')} bei '{term}'"
                        )
                        break
                    if data.get("_err"):
                        print(f"   ⚠️ metajob.at: {data['_err']}")
                        break

                    result = data.get("r") or {}
                    rows = result.get("b") or []
                    total = result.get("e")

                    for row in rows:
                        job = _normalize_row(row)
                        if not job["title"] or not job["url"] or job["url"] in jobs:
                            continue
                        job["matched_terms"] = [term]
                        jobs[job["url"]] = job
                        new_count += 1

                    fetched = offset + len(rows)
                    if len(rows) < METAJOB_PAGE_SIZE or (
                        isinstance(total, int) and fetched >= total
                    ):
                        break

                    time.sleep(POLITE_DELAY_SECONDS)

                print(f"   {term:<18} +{new_count}")
                time.sleep(POLITE_DELAY_SECONDS)
        finally:
            browser.close()

    return list(jobs.values())


def _fetch_with_requests(terms):
    """Reiner requests-Versuch. Aktuell vom Anti-Bot-Cookie blockiert."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.metajob.at",
            "Referer": "https://www.metajob.at/",
        }
    )

    jobs = {}
    for term in terms:
        try:
            response = session.post(
                METAJOB_RPC_URL, json=_payload(term), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            print(f"   ⚠️ metajob.at nicht erreichbar ({exc})")
            break

        if response.status_code != 200:
            print(f"   ⚠️ metajob.at: HTTP {response.status_code}")
            break

        try:
            data = response.json()
        except ValueError:
            print("   ⚠️ metajob.at: Antwort ist kein JSON")
            break

        if data.get("_err"):
            message = str(data["_err"])
            if _COOKIE_ERROR in message:
                print("   ⚠️ metajob.at blockt requests (Cookie-/Anti-Bot-Schutz).")
                print("      Playwright installieren oder Quelle überspringen.")
            else:
                print(f"   ⚠️ metajob.at: {message}")
            break

        result = data.get("r") or {}
        for row in result.get("b") or []:
            job = _normalize_row(row)
            if not job["title"] or not job["url"] or job["url"] in jobs:
                continue
            job["matched_terms"] = [term]
            jobs[job["url"]] = job

    return list(jobs.values())


def fetch_metajob_jobs(terms=None):
    """Holt Wien-Treffer über metajob. Browser zuerst, requests als Fallback."""
    terms = terms or METAJOB_SEARCH_TERMS
    print("📡 Lese metajob.at (Wien) ...")

    jobs = []
    browser_ok = False

    if METAJOB_USE_BROWSER:
        try:
            jobs = _fetch_with_browser(terms)
            browser_ok = True
        except ImportError:
            print(
                "   ⚠️ playwright fehlt – Quelle wird mit requests versucht.\n"
                "      Installation: env/bin/python -m pip install playwright\n"
                "                    env/bin/python -m playwright install chromium"
            )
        except Exception as exc:
            print(f"   ⚠️ metajob.at Browser-Fallback fehlgeschlagen: {exc}")

    if not browser_ok:
        jobs = _fetch_with_requests(terms)

    print(f"📊 {len(jobs)} eindeutige Jobs von metajob.at\n")
    return jobs
