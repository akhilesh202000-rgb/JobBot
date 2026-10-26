# util/jobs.py
#
# Reine Filter-/Scoring-Logik ohne Netzwerk. Damit testbar.
#
# Reihenfolge:
#   1. Titel-Ausschlüsse (Senior, Praktikum, Angular, Java, ...)
#   2. Entwickler-Rolle?
#   3. React-Bezug?
#   4. Liegt der Job in Wien?
#   5. Fit-Score (Mid-Level, React/RN, TypeScript, ...)
#   6. Sortierung: nähester Pendelweg zuerst

import re

from config.constants import (
    BACKEND_EXCLUDE,
    BASE_SCORE,
    DEV_ROLE,
    FRAMEWORK_EXCLUDE,
    FULLSTACK,
    MAX_JOBS_PER_RUN,
    MIN_FIT_SCORE,
    REACT_IN_TEXT,
    REACT_NATIVE,
    SECONDARY_TECH,
    TYPESCRIPT,
    ALWAYS_EXCLUDE,
    FRONTEND_TITLE,
)
from util.geo import best_vienna_location

_YEARS_RE = re.compile(r"(\d{1,2})\s*(?:\+)?\s*(?:jahre|years|j\.)", re.I)
_YEARS_RANGE_RE = re.compile(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*(?:jahre|years)", re.I)


def is_title_excluded(title):
    """
    True, wenn der Job schon anhand des Titels rausfliegt.

    Wichtig: "Java" wird mit \\bjava\\b geprüft, damit "JavaScript"
    NICHT ausgeschlossen wird. Backend-Sprachen führen nur dann zum
    Ausschluss, wenn der Titel nicht React-/Frontend-orientiert ist.
    """
    title = title or ""
    if not title:
        return True

    if any(pattern.search(title) for pattern in ALWAYS_EXCLUDE):
        return True

    react_in_title = bool(REACT_IN_TEXT.search(title))

    if not react_in_title and any(pattern.search(title) for pattern in FRAMEWORK_EXCLUDE):
        return True

    if (
        not react_in_title
        and not FRONTEND_TITLE.search(title)
        and any(pattern.search(title) for pattern in BACKEND_EXCLUDE)
    ):
        return True

    return False


def is_dev_role(title):
    return bool(DEV_ROLE.search(title or ""))


def is_react_relevant(title, description, matched_terms=None):
    """Es muss irgendwo React vorkommen – im Titel, in der Beschreibung
    oder in den Suchbegriffen, über die der Job gefunden wurde."""
    text = f"{title or ''} {description or ''}"

    if REACT_IN_TEXT.search(text):
        if REACT_IN_TEXT.search(title or ""):
            return True
        # React steht nur in der Beschreibung. Dann muss der Titel trotzdem
        # eine Frontend-/Entwickler-Rolle sein (und nicht z. B. ein Tester).
        return bool(FRONTEND_TITLE.search(title or "") or DEV_ROLE.search(title or ""))

    # karriere.at liefert oft einen leeren Summary. Wenn der Job aber über
    # "react" gefunden wurde, steckt React im Volltext der Anzeige.
    return any("react" in (term or "").lower() for term in (matched_terms or []))


def years_required(text):
    """Größte genannte Erfahrungsdauer in Jahren oder None."""
    text = text or ""
    values = [int(match.group(1)) for match in _YEARS_RE.finditer(text)]
    values += [int(match.group(2)) for match in _YEARS_RANGE_RE.finditer(text)]
    return max(values) if values else None


def score_job(title, description, matched_terms=None):
    """Fit-Score 0–10. Höher = besser für React/RN, Mid-Level, Wien."""
    title = title or ""
    description = description or ""
    text = f"{title} {description}"
    terms = [str(term).lower() for term in (matched_terms or [])]

    score = BASE_SCORE

    if REACT_IN_TEXT.search(title):
        score += 2
    elif any("react" in term for term in terms):
        # React ist im Volltext bestätigt, aber der Summary ist leer.
        score += 1
    if "react native" in terms:
        score += 1
    if REACT_NATIVE.search(text):
        score += 2
    if TYPESCRIPT.search(text):
        score += 1

    if FULLSTACK.search(title):
        score -= 1

    if REACT_IN_TEXT.search(title) and any(
        pattern.search(title) for pattern in BACKEND_EXCLUDE
    ):
        score -= 1

    if SECONDARY_TECH.search(text):
        score -= 1

    years = years_required(text)
    if years is not None:
        if years >= 5:
            score -= 2
        elif 2 <= years <= 4:
            score += 1
        elif years <= 1:
            score -= 1

    return max(0.0, min(10.0, score))


def enrich_job(job):
    """
    Ergänzt Fit, Distanz, Bezirk und Roh-Standort – ohne zu filtern.

    Wird auch zum Nachtragen von Metadaten in bestehenden Airtable-Zeilen
    genutzt, wo ein Job inzwischen z. B. durch neue Ausschlüsse aus der
    Shortlist fallen würde, die Standortdaten aber weiterhin brauchbar sind.
    """
    location = best_vienna_location(job.get("locations"))
    if not location:
        return None

    fit = score_job(
        job.get("title", ""),
        job.get("description", ""),
        job.get("matched_terms"),
    )
    return {
        **job,
        "fit": fit,
        "distance_km": round(location["km"], 1),
        "district": location["name"],
        "district_number": location.get("district"),
        "location": location["raw"],
        "location_approx": location["approx"],
    }


def evaluate(job, min_fit=None):
    """
    Prüft einen normalisierten Job. Gibt den Job mit Zusatzfeldern
    (fit, distance_km, district, location) zurück oder None.
    """
    min_fit = MIN_FIT_SCORE if min_fit is None else min_fit
    title = job.get("title", "")
    description = job.get("description", "")

    if not title or not job.get("url"):
        return None
    if is_title_excluded(title):
        return None
    if not is_dev_role(title):
        return None
    if not is_react_relevant(title, description, job.get("matched_terms")):
        return None

    enriched = enrich_job(job)
    if not enriched:
        return None
    if enriched["fit"] < min_fit:
        return None

    return enriched


def build_shortlist(jobs, limit=None, min_fit=None):
    """
    Filtert, bewertet, sortiert (nähester Pendelweg zuerst)
    und kappt auf `limit`.
    """
    limit = MAX_JOBS_PER_RUN if limit is None else limit

    evaluated = [
        job for job in (evaluate(job, min_fit=min_fit) for job in jobs) if job
    ]
    # 1-km-Bänder: Bezirks-Zentroide sind nur grob, deshalb soll ein
    # Unterschied von 100 Metern nicht 2 Fit-Punkte überstimmen.
    evaluated.sort(key=lambda job: (int(job["distance_km"]), -job["fit"]))
    return evaluated[:limit]


def dedupe_by_url(jobs):
    """Entfernt doppelte URLs (z. B. gleicher Job über mehrere Suchbegriffe)."""
    seen = set()
    unique = []
    for job in jobs:
        url = job.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(job)
    return unique
