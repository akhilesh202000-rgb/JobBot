# util/weworkremotely.py
#
# We Work Remotely bietet öffentliche RSS-Feeds je Kategorie:
#     https://weworkremotely.com/categories/remote-programming-jobs.rss
#
# Ein <item> enthält:
#   title       "Firma: Jobtitel"
#   region      z. B. "Anywhere in the World", "Europe", "USA Only"
#   category    z. B. "Full-Stack Programming"
#   description HTML-escaped Volltext
#   pubDate     RFC-822-Datum
#   link/guid   Job-URL
#
# Wir lesen mehrere Kategorien, filtern lokal auf React und behalten nur
# Regionen, die von Wien aus erreichbar sind (Worldwide/Europa/Österreich).

import datetime as dt
import email.utils
import html
import re

import requests
import xml.etree.ElementTree as ET

from config.constants import (
    REACT_IN_TEXT,
    REMOTE_ALLOWED_LOCATIONS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    WWR_RSS_FEEDS,
)

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", str(text))
    text = html.unescape(text)
    return " ".join(text.split())


def _posted(value):
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _allowed_region(region):
    region = (region or "").strip().lower()
    if not region:
        return True
    return any(token in region for token in REMOTE_ALLOWED_LOCATIONS)


def normalize_item(item):
    """RSS-<item> -> normalisiertes Job-Dict oder None."""
    raw_title = _clean(item.findtext("title"))
    region = _clean(item.findtext("region"))
    description = _clean(item.findtext("description"))
    category = _clean(item.findtext("category"))

    if not raw_title or not REACT_IN_TEXT.search(f"{raw_title} {description}"):
        return None
    if not _allowed_region(region):
        return None

    company, separator, title = raw_title.partition(":")
    if separator:
        company = company.strip()
        title = title.strip()
    else:
        company = ""
        title = raw_title

    url = (item.findtext("link") or item.findtext("guid") or "").strip()
    if not title or not url:
        return None

    if region:
        description = f"{description} Remote-Region: {region}".strip()

    return {
        "id": url.rstrip("/").rsplit("/", 1)[-1],
        "title": title,
        "url": url,
        "company": company,
        "description": description,
        "locations": ["Wien (Remote)"],
        "home_office": True,
        "employment_type": category,
        "posted": _posted(item.findtext("pubDate")),
        "source": "weworkremotely.com",
        "matched_terms": [],
        "remote_region": region,
    }


def parse_feed(xml_text):
    """RSS-XML -> normalisierte Jobs."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    jobs = []
    for item in root.findall("./channel/item"):
        job = normalize_item(item)
        if job:
            jobs.append(job)
    return jobs


def fetch_weworkremotely_jobs():
    """Liest alle konfigurierten WWR-Feeds und dedupliziert nach URL."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    jobs = {}
    print("📡 Lese We Work Remotely (RSS, React) ...")

    for feed in WWR_RSS_FEEDS:
        try:
            response = session.get(feed, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"⚠️ WWR-Feed: {exc}")
            continue

        if response.status_code != 200:
            print(f"⚠️ WWR-Feed: HTTP {response.status_code}")
            continue

        new_count = 0
        for job in parse_feed(response.text):
            if job["url"] in jobs:
                continue
            jobs[job["url"]] = job
            new_count += 1
        print(f"   {feed.rsplit('/', 1)[-1]:<48} {new_count:>3} neu")

    print(f"📊 {len(jobs)} React-Remote-Jobs von We Work Remotely\n")
    return list(jobs.values())
