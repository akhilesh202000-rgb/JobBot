# util/airtable.py
#
# Airtable als wachsende Shortlist:
#   - bestehende URLs werden gelesen und übersprungen (kein Duplikat)
#   - neue Jobs werden in 10er-Batches angelegt
#   - fehlen optionale Felder in der Tabelle, werden sie automatisch
#     weggelassen statt den ganzen Batch zu verlieren
#
# clear_airtable_table() bleibt als manuelles Reset-Werkzeug erhalten,
# wird von der Pipeline aber NICHT mehr aufgerufen.

import datetime as dt
import re
import time
from urllib.parse import urlparse, urlunparse

import requests

from config.constants import (
    AIRTABLE_BATCH_SIZE,
    AIRTABLE_PAGE_SIZE,
    DISTRICTS,
    HOME_LABEL,
    LEGACY_URL_HOSTS,
)
from util.geo import best_vienna_location
from util.jobs import enrich_job

_UNKNOWN_FIELD_NAMES_RE = re.compile(r'Unknown field names?:\s*(.+)')
_QUOTED_RE = re.compile(r'\\?"([^"\\]+)\\?"')

# Felder, die es in der Airtable-Tabelle geben sollte. Fehlen sie, wird
# ohne sie weiter geschrieben (die Pflichtfelder müssen existieren).
OPTIONAL_FIELDS = (
    "Company",
    "Location",
    "District",
    "Distance (km)",
    "Home Office",
    "Source",
    "Posted",
    "Employment Type",
)


def _unknown_fields(response):
    """
    Liest fehlende Feldnamen aus einer 422-Antwort von Airtable.

    Bewusst per Regex auf dem Rohtext statt über response.json(): die
    Feldnamen stehen dort als \\"Location\\" escaped, und so ist es egal,
    ob der Body (noch) als JSON geparst werden kann.
    """
    text = response.text or ""
    if "Unknown field name" not in text:
        return []
    match = _UNKNOWN_FIELD_NAMES_RE.search(text)
    if not match:
        return []
    return _QUOTED_RE.findall(match.group(1))


def table_url(base_id, table_name):
    return f"https://api.airtable.com/v0/{base_id}/{table_name}"


def _headers(pat):
    return {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }


def _notes(job):
    parts = [
        f"Fit {job.get('fit', 0)}/10",
        f"~{job.get('distance_km', '?')} km von {HOME_LABEL}",
    ]
    if job.get("district"):
        parts.append(job["district"])
    if job.get("home_office"):
        parts.append("Home Office möglich")
    if job.get("employment_type"):
        parts.append(job["employment_type"])
    if job.get("posted"):
        parts.append(job["posted"])
    return " · ".join(parts)


def normalize_posted(value):
    """
    `Posted` ist in Airtable ein Datumsfeld. Relative Angaben aus den Quellen
    ("vor 3 Tagen") müssen deshalb in ein ISO-Datum umgerechnet werden.
    Unbekannte Formate werden verworfen, damit kein Batch an einem
    ungültigen Datum scheitert.
    """
    if not value:
        return ""

    text = str(value).strip()
    today = dt.date.today()

    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)

    match = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    if match:
        month, day, year = match.groups()
        return f"{year}-{month}-{day}"

    if re.search(r"\bheute\b", text, re.I):
        return today.isoformat()
    if re.search(r"\bgestern\b", text, re.I):
        return (today - dt.timedelta(days=1)).isoformat()

    match = re.search(r"vor\s+(\d+)\+?\s*(?:tag|tagen|t)\b", text, re.I)
    if match:
        return (today - dt.timedelta(days=int(match.group(1)))).isoformat()
    if re.search(r"vor\s+einem\s+tag", text, re.I):
        return (today - dt.timedelta(days=1)).isoformat()

    match = re.search(r"(\d+)\s+days?\s+ago", text, re.I)
    if match:
        return (today - dt.timedelta(days=int(match.group(1)))).isoformat()

    return ""


def build_fields(job, skip_fields=()):
    """Airtable-Record für einen Job bauen."""
    fields = {
        "Job Title": job.get("title", ""),
        "URL": job.get("url", ""),
        "Description": (job.get("description") or "")[:5000],
        "Match Score": float(job.get("fit", 0)),
        "Cover Letter / Anschreiben": _notes(job),
        "Status": "To Review",
    }

    optional = {
        "Company": job.get("company") or "",
        "Location": job.get("location") or "",
        "District": (
            job.get("district_number")
            or district_number(job.get("district"))
            or ""
        ),
        "Distance (km)": round(float(job.get("distance_km") or 0), 1),
        "Home Office": bool(job.get("home_office")),
        "Source": job.get("source") or "",
        "Posted": normalize_posted(job.get("posted")),
        "Employment Type": job.get("employment_type") or "",
    }

    for name, value in optional.items():
        if name in skip_fields:
            continue
        if value in ("", None):
            continue
        fields[name] = value

    return fields


# Host -> Anzeigename der Quelle. Wird beim Nachtragen genutzt, wenn ein
# Job nicht mehr frisch von der Quelle geliefert wird.
_SOURCE_HOSTS = {
    "at.indeed.com": "indeed.at",
    "jobs.at": "jobs.at",
    "remotive.com": "remotive.com",
    "metajob.at": "metajob.at",
    "devjobs.at": "devjobs.at",
    "jobs.ams.at": "ams.at",
    "stepstone.at": "stepstone.at",
    "karriere.at": "karriere.at",
    "it-karriere.at": "it-karriere.at",
    "willhaben.at": "willhaben.at",
    "job.epunkt.com": "epunkt",
    "relocate.me": "relocate.me",
    "brutkasten.com": "brutkasten.com",
    "workinaustria.com": "workinaustria.com",
    "himalayas.app": "himalayas.app",
    "jobicy.com": "jobicy.com",
    "remoteok.com": "remoteok.com",
    "weworkremotely.com": "weworkremotely.com",
    "arbeitnow.com": "arbeitnow.com",
    "aiaustria.com": "aiaustria.com",
    "jobs.derstandard.at": "jobs.derstandard.at",
    "austrianstartups.com": "austrianstartups.com",
    "join.com": "join.com",
    "linkedin.com": "linkedin.com",
    "xing.com": "xing.com",
    "wellfound.com": "wellfound.com",
    "welcometothejungle.com": "welcometothejungle.com",
    "wearedevelopers.com": "wearedevelopers.com",
    "thehub.io": "thehub.io",
    "eu-careers.europa.eu": "eu-careers.europa.eu",
}

_EMPLOYMENT_TERMS = (
    "Vollzeit",
    "Teilzeit",
    "contract",
    "freelance",
    "Werkvertrag",
    "Geringfügig",
)

# Bezirksname -> Nummer. Airtables Feld "District" ist ein Zahlenfeld.
_DISTRICT_NUMBERS = {
    name: number for number, (name, _lat, _lng) in DISTRICTS.items()
}


def district_number(name):
    """Bezirksname ("Leopoldstadt") -> Bezirksnummer (2)."""
    if not name:
        return None
    if name in _DISTRICT_NUMBERS:
        return _DISTRICT_NUMBERS[name]
    for district_name, number in _DISTRICT_NUMBERS.items():
        if name.startswith(district_name):
            return number
    return None


def normalize_url(url):
    """URLs für den Abgleich vereinheitlichen (Host, www, Slash, https)."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunparse(
        ("https", host, parsed.path.rstrip("/"), parsed.params, parsed.query, "")
    )


def _source_from_url(url):
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for pattern, source in _SOURCE_HOSTS.items():
        if host == pattern or host.endswith("." + pattern):
            return source
    return host


def _parse_employment_type(*texts):
    found = []
    for text in texts:
        for term in _EMPLOYMENT_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", text or "", re.I):
                found.append(term)
    return " / ".join(dict.fromkeys(found))


def _parse_posted(cover):
    cover = cover or ""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", cover)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", cover)
    if match:
        return match.group(1)
    match = re.search(r"((?:vor|Gestern|Heute)[^·]*)", cover, re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def fallback_job(record_fields):
    """
    Metadaten aus einer bestehenden Airtable-Zeile ableiten.

    Wird genutzt, wenn die Original-URL nicht mehr in den frisch geladenen
    Quellen auftaucht (z. B. abgelaufene Anzeige). Distanz und Bezirk stehen
    bereits im generierten Anschreiben.
    """
    url = record_fields.get("URL", "")
    title = record_fields.get("Job Title", "")
    company = record_fields.get("Company", "")
    description = record_fields.get("Description", "")
    cover = record_fields.get("Cover Letter / Anschreiben", "")

    distance = None
    match = re.search(r"~([\d.]+)\s*km", cover)
    if match:
        try:
            distance = float(match.group(1))
        except ValueError:
            distance = None

    district = ""
    match = re.search(r"1220 Wien\)\s*·\s*([^·]+)", cover)
    if match:
        district = match.group(1).strip()

    location = "Wien"
    if district and district != "Wien (Bezirk unbekannt)":
        location = f"Wien ({district})"

    home_office = bool(
        re.search(r"home[\s-]?office|remote", f"{cover} {description}", re.I)
    )

    if not description:
        description = " · ".join(
            part for part in (title, company, location) if part
        )

    return {
        "url": url,
        "title": title,
        "company": company,
        "description": description,
        "location": location,
        "district": district,
        "district_number": district_number(district),
        "distance_km": distance,
        "home_office": home_office,
        "source": _source_from_url(url),
        "posted": _parse_posted(cover),
        "employment_type": _parse_employment_type(cover, description),
    }


def build_update_fields(record_fields, job):
    """Nur fehlende optionale Felder für einen bestehenden Record bauen."""
    updates = {}

    def missing(name):
        return record_fields.get(name) in (None, "", [])

    if missing("Company") and job.get("company"):
        updates["Company"] = job["company"]

    location = job.get("location")
    district = job.get("district")
    distance = job.get("distance_km")
    if (not location or not district or distance is None) and job.get("locations"):
        parsed = best_vienna_location(job.get("locations"))
        if parsed:
            location = location or parsed["raw"]
            district = district or parsed["name"]
            distance = distance if distance is not None else round(parsed["km"], 1)

    if missing("Location") and location:
        updates["Location"] = location
    district_number_value = job.get("district_number") or district_number(district)
    if missing("District") and district_number_value is not None:
        updates["District"] = int(district_number_value)
    if missing("Distance (km)") and distance is not None:
        updates["Distance (km)"] = round(float(distance), 1)
    if missing("Home Office") and job.get("home_office"):
        updates["Home Office"] = True
    if missing("Source") and job.get("source"):
        updates["Source"] = job["source"]
    posted = normalize_posted(job.get("posted"))
    if missing("Posted") and posted:
        updates["Posted"] = posted
    if missing("Employment Type") and job.get("employment_type"):
        updates["Employment Type"] = job["employment_type"]
    if missing("Description") and job.get("description"):
        updates["Description"] = job["description"][:5000]

    return updates


def update_records(base_id, table_name, pat, jobs_by_url):
    """
    Ergänzt fehlende optionale Felder bei bestehenden Records.

    `jobs_by_url` ist eine Map normalisierte URL -> frisch geladener Job.
    Nicht gefundene Jobs werden aus dem vorhandenen Anschreiben abgeleitet.
    Gibt (updated, unchanged, unmatched, failed) zurück.
    """
    records = get_records(
        base_id,
        table_name,
        pat,
        fields=["URL", "Company", "Description", *OPTIONAL_FIELDS],
    )
    updates = []
    unchanged = 0
    unmatched = 0

    for record in records:
        record_fields = record.get("fields", {})
        url = record.get("url") or record_fields.get("URL", "")
        job = jobs_by_url.get(normalize_url(url))
        if job:
            candidate = enrich_job(job) or job
        else:
            unmatched += 1
            candidate = fallback_job(record_fields)

        fields = build_update_fields(record_fields, candidate)
        if fields:
            updates.append({"id": record["id"], "fields": fields})
        else:
            unchanged += 1

    updated = 0
    failed = 0
    for start in range(0, len(updates), AIRTABLE_BATCH_SIZE):
        batch = [dict(record) for record in updates[start:start + AIRTABLE_BATCH_SIZE]]
        for _ in range(len(OPTIONAL_FIELDS) + 3):
            if not batch:
                break
            payload = {"records": batch, "typecast": True}
            try:
                response = requests.patch(
                    table_url(base_id, table_name),
                    headers=_headers(pat),
                    json=payload,
                    timeout=30,
                )
            except requests.RequestException as exc:
                print(f"❌ Airtable-Backfill fehlgeschlagen: {exc}")
                failed += len(batch)
                break

            if response.status_code == 200:
                updated += len(batch)
                break

            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", "1") or 1))
                continue

            if response.status_code == 422:
                unknown = _unknown_fields(response)
                if unknown:
                    print(
                        "⚠️ Airtable-Feld(er) fehlen und werden ignoriert: "
                        + ", ".join(sorted(unknown))
                    )
                    for record in batch:
                        for name in unknown:
                            record["fields"].pop(name, None)
                    batch = [record for record in batch if record["fields"]]
                    continue

            print(
                f"❌ Airtable-Backfill: "
                f"{response.status_code} {response.text[:300]}"
            )
            failed += len(batch)
            break
        else:
            failed += len(batch)

        time.sleep(0.3)

    return updated, unchanged, unmatched, failed


def get_existing_urls(base_id, table_name, pat):
    """Alle bereits gespeicherten URLs lesen (mit Pagination)."""
    urls = set()
    params = {"pageSize": AIRTABLE_PAGE_SIZE, "fields[]": "URL"}

    while True:
        try:
            response = requests.get(
                table_url(base_id, table_name),
                headers=_headers(pat),
                params=params,
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"⚠️ Airtable nicht erreichbar: {exc}")
            return urls

        if response.status_code != 200:
            print(f"❌ Airtable-Lesen fehlgeschlagen: {response.status_code} {response.text[:200]}")
            return urls

        data = response.json()
        for record in data.get("records", []):
            url = record.get("fields", {}).get("URL")
            if url:
                urls.add(url)

        offset = data.get("offset")
        if not offset:
            return urls
        params["offset"] = offset


def create_records(base_id, table_name, pat, jobs):
    """Legt neue Jobs an. Gibt (created, failed) zurück."""
    created = 0
    failed = 0
    skip_fields = set()
    # Genug Versuche, um unbekannte Felder nacheinander zu entdecken.
    max_attempts = len(OPTIONAL_FIELDS) + 3

    for start in range(0, len(jobs), AIRTABLE_BATCH_SIZE):
        batch = jobs[start:start + AIRTABLE_BATCH_SIZE]
        payload = {
            "records": [{"fields": build_fields(job, skip_fields)} for job in batch],
            "typecast": True,
        }

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    table_url(base_id, table_name),
                    headers=_headers(pat),
                    json=payload,
                    timeout=30,
                )
            except requests.RequestException as exc:
                print(f"❌ Airtable-Upload fehlgeschlagen: {exc}")
                failed += len(batch)
                break

            if response.status_code in (200, 201):
                created += len(batch)
                break

            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", "1") or 1)
                time.sleep(wait)
                continue

            if response.status_code == 422:
                unknown = _unknown_fields(response)
                new_fields = [name for name in unknown if name not in skip_fields]
                if new_fields:
                    skip_fields.update(new_fields)
                    print(
                        "⚠️ Airtable-Feld(er) fehlen und werden ignoriert: "
                        + ", ".join(sorted(new_fields))
                        + " – am besten in der Tabelle anlegen."
                    )
                    payload = {
                        "records": [
                            {"fields": build_fields(job, skip_fields)} for job in batch
                        ],
                        "typecast": True,
                    }
                    continue

            print(f"❌ Airtable-Upload: {response.status_code} {response.text[:300]}")
            failed += len(batch)
            break

        time.sleep(0.3)

    return created, failed


def is_legacy_url(url, hosts=LEGACY_URL_HOSTS):
    """True, wenn die URL zu einer alten, nicht mehr genutzten Quelle gehört."""
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == legacy or host.endswith("." + legacy) for legacy in hosts)


def get_records(base_id, table_name, pat, fields=None):
    """Alle Records als [{"id", "url", "fields"}] lesen (mit Pagination)."""
    records = []
    params = {"pageSize": AIRTABLE_PAGE_SIZE}
    params["fields[]"] = list(fields) if fields else "URL"

    while True:
        try:
            response = requests.get(
                table_url(base_id, table_name),
                headers=_headers(pat),
                params=params,
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"⚠️ Airtable nicht erreichbar: {exc}")
            return records

        if response.status_code != 200:
            print(
                f"❌ Airtable-Lesen fehlgeschlagen: "
                f"{response.status_code} {response.text[:200]}"
            )
            return records

        data = response.json()
        for record in data.get("records", []):
            record_fields = record.get("fields", {})
            records.append(
                {
                    "id": record["id"],
                    "url": record_fields.get("URL", ""),
                    "fields": record_fields,
                }
            )

        offset = data.get("offset")
        if not offset:
            return records
        params["offset"] = offset


def delete_records(base_id, table_name, pat, record_ids):
    """Löscht Records in 10er-Batches. Gibt die Anzahl gelöschter Zeilen zurück."""
    url = table_url(base_id, table_name)
    headers = _headers(pat)
    deleted = 0

    for start in range(0, len(record_ids), AIRTABLE_BATCH_SIZE):
        batch = record_ids[start:start + AIRTABLE_BATCH_SIZE]
        params = [("records[]", record_id) for record_id in batch]
        try:
            response = requests.delete(
                url, headers=headers, params=params, timeout=30
            )
        except requests.RequestException as exc:
            print(f"❌ Löschen fehlgeschlagen: {exc}")
            break

        if response.status_code != 200:
            print(
                f"❌ Löschen fehlgeschlagen: "
                f"{response.status_code} {response.text[:200]}"
            )
            break

        deleted += len(batch)
        time.sleep(0.3)

    return deleted


def delete_legacy_urls(base_id, table_name, pat, hosts=LEGACY_URL_HOSTS):
    """
    Löscht nur alte Records ohne `Source`-Feld.

    WeWorkRemotely und Remote OK sind inzwischen wieder aktive Quellen.
    Würde man pauschal nach Host löschen, wären auch die neuen Zeilen
    betroffen. Deshalb werden nur Zeilen gelöscht, die noch keine
    Quellenangabe haben (also aus der Zeit vor dem Backfill stammen).
    """
    records = get_records(
        base_id, table_name, pat, fields=["URL", "Source"]
    )
    legacy = [
        record
        for record in records
        if is_legacy_url(record["url"], hosts)
        and not record["fields"].get("Source")
    ]

    if not legacy:
        print("✨ Keine alten Airtable-Einträge gefunden.")
        return 0

    found_hosts = sorted(
        {urlparse(record["url"]).netloc.lower() for record in legacy}
    )
    print(
        f"🧹 Lösche {len(legacy)} alte Einträge "
        f"({', '.join(found_hosts)}) von {len(records)} gesamt ..."
    )

    return delete_records(base_id, table_name, pat, [record["id"] for record in legacy])


def clear_airtable_table(base_id, table_name, pat):
    """
    Manuelles Reset: löscht ALLE Zeilen (inkl. Pagination).
    Wird von der Pipeline nicht mehr aufgerufen.
    """
    url = table_url(base_id, table_name)
    headers = _headers(pat)
    deleted = 0

    print("🔄 Airtable wird geleert ...")

    while True:
        try:
            response = requests.get(url, headers=headers, params={"pageSize": 100}, timeout=30)
        except requests.RequestException as exc:
            print(f"❌ Airtable nicht erreichbar: {exc}")
            return

        if response.status_code != 200:
            print(f"❌ Lesen fehlgeschlagen: {response.text[:200]}")
            return

        records = response.json().get("records", [])
        if not records:
            break

        record_ids = [record["id"] for record in records]
        for i in range(0, len(record_ids), 10):
            batch = record_ids[i:i + 10]
            params = [("records[]", record_id) for record_id in batch]
            delete_response = requests.delete(url, headers=headers, params=params, timeout=30)
            if delete_response.status_code == 200:
                deleted += len(batch)
            else:
                print(f"❌ Löschen fehlgeschlagen: {delete_response.text[:200]}")
                return
            time.sleep(0.2)

    print(f"🎉 Airtable geleert ({deleted} Zeilen).\n")
