# config/constants.py
#
# Zentrale Tunables für JobBot. Alles, was man ohne Code-Änderung
# anpassen möchte (Suchbegriffe, Ausschlüsse, Bewertung, Standort),
# gehört hierher.

import os
import re

# ---------------------------------------------------------------------------
# 1. Quellen / Suche
# ---------------------------------------------------------------------------
# karriere.at liefert die Suchergebnisse als JSON in window.VUE_INITIAL_STATE.
# Kein API-Key nötig, aber pro Suchbegriff nur ~15 Treffer (Pagination ist
# clientseitig), deshalb mehrere Begriffe und anschließend deduplizieren.
KARRIERE_BASE = "https://www.karriere.at/jobs"
KARRIERE_LOCATION = "wien"

KARRIERE_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
    "javascript",
    "mobile developer",
    "web developer",
]

# devjobs.at: Remix-App hinter Cloudflare. Die SEO-Seiten
#     /jobs/<tech>-wien-<locationId>
# liefern serverseitig ~15 Karten. Pagination wird ignoriert, deshalb mehrere
# Tech-Slugs. 109166 ist die devjobs-Location-ID für Wien.
DEVJOBS_BASE = "https://devjobs.at"
DEVJOBS_LOCATION_SLUG = "wien-109166"
DEVJOBS_TECH_SLUGS = [
    "react",
    "react-native",
    "typescript",
    "javascript",
    "node-js",
    "next-js",
    "graphql",
]

# metajob.at: eigener JSON-RPC. Der Server verlangt ein Browser-Cookie und
# einen Such-Token (`a0.s`). Deshalb läuft die Suche über einen Headless-
# Browser (Playwright); der Token wird aus der ersten UI-Suche abgegriffen.
METAJOB_RPC_URL = "https://www.metajob.at/_irpc/joyservice/se"
METAJOB_SEARCH_HASH = "1Dbc9D"
METAJOB_LOCATION = "Wien"
METAJOB_PAGE_SIZE = 20        # Server-Obergrenze
METAJOB_MAX_PAGES = 2         # 2 × 20 Treffer pro Suchbegriff
METAJOB_USE_BROWSER = True    # False = nur requests (blockt aktuell)
METAJOB_BROWSER_TIMEOUT_MS = 30000
METAJOB_SEARCH_TERMS = ["react", "react native", "typescript", "frontend"]

# StepStone Österreich: serverseitig gerendert, aber langsam und mit
# Bot-Schutz. Ohne echten Browser oft Timeout -> Playwright.
STEPSTONE_BASE = "https://www.stepstone.at"
STEPSTONE_LOCATION_SLUG = "in-wien"
STEPSTONE_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
    "javascript",
    "mobile developer",
]

# Indeed Österreich: Cloudflare blockt requests/RSS mit 403. Playwright kommt
# durch, weil ein echter Chromium die Challenge löst.
INDEED_BASE = "https://at.indeed.com"
INDEED_LOCATION = "Wien"
INDEED_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
    "javascript",
]
INDEED_MAX_SCROLLS = 3

# epunkt: Laravel/Inertia-App. Die Jobdaten stehen als JSON im
# `data-page`-Attribut; die Wien-Liste hat ~94 Jobs auf 4 Seiten.
EPUNKT_BASE = "https://job.epunkt.com"
EPUNKT_LOCATION_SLUG = "wien"
EPUNKT_MAX_PAGES = 4

# IT-Karriere.at: klassisches PHP-Board. Das TLS-Zertifikat ist abgelaufen,
# deshalb verify=False (nur lesend, keine Login-Daten).
ITKARRIERE_BASE = "https://www.it-karriere.at"
ITKARRIERE_SEARCH_URL = f"{ITKARRIERE_BASE}/search.php"
ITKARRIERE_CITY_ID = "124"  # Wien
ITKARRIERE_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
    "javascript",
]

# jobs.at: Karten mit data-Attributen. Der Ziel-URL steckt base64-kodiert in
# `data-c-redirect`.
JOBSAT_BASE = "https://www.jobs.at"
JOBSAT_LOCATION = "Wien"
JOBSAT_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
    "javascript",
]

# Willhaben: öffentliche JSON-API der Jobsuche (kein Key nötig).
WILLHABEN_API = "https://publicapi.willhaben.at/jobs/v2/adverts"
WILLHABEN_JOB_URL = "https://www.willhaben.at/jobs/job"
WILLHABEN_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
    "javascript",
]
WILLHABEN_MAX_PAGES = 2

# Remotive: öffentliche Remote-Jobs-API. Wir behalten nur Stellen, die laut
# `candidate_required_location` für Wien/Österreich/Europa/Worldwide offen sind.
# Der Standort wird als "Wien (Remote)" gemappt, damit die Distanzlogik greift.
REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REMOTIVE_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
    "javascript",
]
REMOTIVE_ALLOWED_LOCATIONS = (
    "worldwide",
    "anywhere",
    "europe",
    "european",
    "emea",
    "austria",
    "österreich",
    "oesterreich",
)

# Relocate.me: Relocation-Board. Wir behalten nur Österreich/Wien-Treffer.
RELOCATE_BASE = "https://relocate.me"
RELOCATE_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "fullstack",
    "typescript",
]
RELOCATE_MAX_PAGES = 3

# AMS eJob-Room: Angular-SPA. Die API verlangt eine Browser-Session, deshalb
# wird die gerenderte Suchseite mit Playwright gelesen.
AMS_BASE = "https://jobs.ams.at/public/emps"
AMS_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
    "javascript",
]

# brutkasten und Work in Austria haben derzeit kein öffentlich scrapebares
# Job-Listing (Getro-Board 404 bzw. Login-Portal). Die Module versuchen es
# trotzdem und liefern bei fehlendem Board eine leere Liste.
BRUTKASTEN_JOBS_URL = "https://brutkasten.com/jobs"
WORKINAUSTRIA_JOBS_URL = "https://www.workinaustria.com/fachkraefte/jobs"

# ---------------------------------------------------------------------------
# 1b. Weitere Plattformen
# ---------------------------------------------------------------------------
# Gemeinsame Allowlist für Remote-Boards. Ein Job muss entweder weltweit,
# europaweit oder explizit für Österreich offen sein. Einzelne Länder (z. B.
# "USA" oder "Ukraine") reichen nicht, weil man von Wien aus nicht bewerben
# kann. Der Standort wird als "Wien (Remote)" gemappt.
REMOTE_ALLOWED_LOCATIONS = (
    "worldwide",
    "anywhere",
    "global",
    "europe",
    "european",
    "emea",
    "austria",
    "österreich",
    "oesterreich",
    "remote",
)

# Himalayas: öffentliche JSON-API mit Cursor-Pagination. Die API liefert
# immer die neuesten 20 Jobs; `search`/`limit` werden ignoriert. Deshalb
# mehrere Seiten lesen und lokal filtern.
HIMALAYAS_API = "https://himalayas.app/jobs/api"
HIMALAYAS_MAX_PAGES = 8

# Jobicy: öffentliche Remote-API. `geo=europe` filtert serverseitig grob;
# `tag=react` wird zwar angezeigt, filtert aber nicht. Lokal filtern.
JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"
JOBICY_COUNT = 50
JOBICY_GEO = "europe"
JOBICY_MAX_PAGES = 2

# Remote OK: öffentliche JSON-API. Erster Eintrag ist ein Metadaten-Objekt.
REMOTEOK_API = "https://remoteok.com/api"

# We Work Remotely: RSS-Feeds je Kategorie. Die Feeds enthalten den
# Volltext (HTML-escaped) und die Remote-Region.
WWR_RSS_FEEDS = (
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
)

# Arbeitnow: öffentliche Job-Board-API (300 Jobs pro Seite, `links.next`).
# Europa-/Österreich-Fokus, daher lokal auf Wien/Austria/Remote filtern.
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
ARBEITNOW_MAX_PAGES = 2

# AI Austria: statische Super.so/Notion-Seite mit Job-Karten. Es gibt keine
# Beschreibung, nur Titel + Standort-Pill.
AIAUSTRIA_JOBS_URL = "https://aiaustria.com/jobs"

# DER STANDARD Jobs: Next.js-App. Die Treffer stehen als Flight-Daten
# (`self.__next_f.push`) im HTML; darin liegen JobListingResponse-Objekte.
DERSTANDARD_BASE = "https://jobs.derstandard.at"
DERSTANDARD_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
]

# AustrianStartups: Opportunity-Board ist nur für eingeloggte Mitglieder
# sichtbar. Das Modul ist ein bewusster Stub.
AUSTRIANSTARTUPS_JOBS_URL = "https://austrianstartups.com/opportunities"

# JOIN: Die Jobsuche leitet auf auth.join.com um; ohne Login keine Liste.
JOIN_JOBS_URL = "https://join.com/jobs"

# LinkedIn: öffentliche Guest-Jobsuche (HTML-Fragmente, 10 Karten/Seite).
LINKEDIN_GUEST_API = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
LINKEDIN_LOCATION = "Vienna"
LINKEDIN_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
]
LINKEDIN_MAX_PAGES = 1

# XING Jobs: serverseitig gerenderte Suchseite mit Job-Karten.
XING_SEARCH_URL = "https://www.xing.com/jobs/search"
XING_SEARCH_TERMS = [
    "react",
    "react native",
    "frontend",
    "typescript",
]

# Wellfound: Next.js-Seite mit Apollo-State in `__NEXT_DATA__`. Meist
# US-Jobs; wir behalten nur Wien/Austria oder passende Remote-Regionen.
WELLFOUND_JOBS_URL = "https://wellfound.com/jobs"

# Welcome to the Jungle: Die öffentliche Jobsuche wurde auf "Matching"
# umgestellt und liefert ohne Login keine Stellen mehr. Bewusster Stub.
WELCOMETOTHEJUNGLE_JOBS_URL = "https://www.welcometothejungle.com/en/jobs"

# WeAreDevelopers: agentenfreundlicher Markdown-Endpunkt (`jobs.md`).
# `q=<term>&country=AT` funktioniert; `page` wird nicht unterstützt.
WEAREDEVELOPERS_JOBS_MD = "https://www.wearedevelopers.com/jobs.md"
WEAREDEVELOPERS_COUNTRY = "AT"
WEAREDEVELOPERS_SEARCH_TERMS = [
    "react",
    "react native",
    "typescript",
    "frontend",
]

# The Hub: Nuxt-Board mit serverseitig gerenderten Karten. `search=<term>`
# filtert; der Fokus liegt auf Nordeuropa/Großbritannien.
THEHUB_JOBS_URL = "https://thehub.io/jobs"
THEHUB_SEARCH_TERMS = ["react", "react native", "frontend"]

# EU Careers: Drupal-Jobsuche mit 20 Karten/Seite und `?page=N`.
# Die meisten Stellen sind in Brüssel/Luxemburg; Wien-Treffer sind selten.
EUCAREERS_JOBS_URL = "https://eu-careers.europa.eu/jobs_en"
EUCAREERS_MAX_PAGES = 5

POLITE_DELAY_SECONDS = 0.7
REQUEST_TIMEOUT_SECONDS = 25
REQUEST_RETRIES = 3

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
}

# ---------------------------------------------------------------------------
# 2. Standort / Pendeln
# ---------------------------------------------------------------------------
# Referenzpunkt für die Entfernungsrangliste (per Env überschreibbar).
HOME_LAT = float(os.getenv("HOME_LAT", "48.2227"))
HOME_LNG = float(os.getenv("HOME_LNG", "16.4159"))
HOME_LABEL = os.getenv("HOME_LABEL", "Kaisermühlen U1 (1220 Wien)")

# Näherung: Bezirks-Zentroide. Reicht, um Jobs nach Pendelweg zu sortieren,
# wenn die Quelle nur "Wien 22. Bezirk" statt einer Straße liefert.
DISTRICTS = {
    1: ("Innere Stadt", 48.2082, 16.3738),
    2: ("Leopoldstadt", 48.2167, 16.4000),
    3: ("Landstraße", 48.1960, 16.3900),
    4: ("Wieden", 48.1890, 16.3670),
    5: ("Margareten", 48.1870, 16.3560),
    6: ("Mariahilf", 48.1950, 16.3500),
    7: ("Neubau", 48.2010, 16.3480),
    8: ("Josefstadt", 48.2110, 16.3480),
    9: ("Alsergrund", 48.2230, 16.3560),
    10: ("Favoriten", 48.1600, 16.3800),
    11: ("Simmering", 48.1700, 16.4200),
    12: ("Meidling", 48.1700, 16.3300),
    13: ("Hietzing", 48.1800, 16.2600),
    14: ("Penzing", 48.2000, 16.2800),
    15: ("Rudolfsheim-Fünfhaus", 48.1950, 16.3200),
    16: ("Ottakring", 48.2100, 16.3000),
    17: ("Hernals", 48.2250, 16.2800),
    18: ("Währing", 48.2320, 16.3200),
    19: ("Döbling", 48.2500, 16.3500),
    20: ("Brigittenau", 48.2400, 16.3700),
    21: ("Floridsdorf", 48.2700, 16.4000),
    22: ("Donaustadt", 48.2300, 16.4600),
    23: ("Liesing", 48.1400, 16.2900),
}

# Wenn die Quelle nur "Wien" ohne Bezirk sagt: Stadtzentrum als Näherung.
VIENNA_CENTROID = (48.2082, 16.3738)

# Umliegende Gemeinden. Standardmäßig aus, weil der Nutzer "Wien" will.
# Auf True setzen, wenn Pendelorte wie Brunn am Gebirge mit rein sollen.
INCLUDE_SUBURBS = False
MAX_SUBURB_DISTANCE_KM = 20.0

SUBURB_COORDS = {
    "brunn am gebirge": (48.1070, 16.2842),
    "mödling": (48.0856, 16.2840),
    "moedling": (48.0856, 16.2840),
    "wiener neudorf": (48.0833, 16.3167),
    "perchtoldsdorf": (48.1167, 16.2667),
    "klosterneuburg": (48.3050, 16.3250),
    "schwechat": (48.1333, 16.4667),
    "vösendorf": (48.1167, 16.3333),
    "voesendorf": (48.1167, 16.3333),
    "gerasdorf": (48.2833, 16.4667),
    "langenzersdorf": (48.2833, 16.3500),
    "maria enzersdorf": (48.1000, 16.2833),
}

# ---------------------------------------------------------------------------
# 3. Relevanz: React / Frontend / Mobile
# ---------------------------------------------------------------------------
REACT_IN_TEXT = re.compile(r"\breact(?:[\s-]*native|\.?js)?\b", re.I)
REACT_NATIVE = re.compile(r"\breact[\s-]*native\b|\bexpo\b", re.I)
TYPESCRIPT = re.compile(r"\btypescript\b", re.I)
FULLSTACK = re.compile(r"\bfull[\s-]?stack\b", re.I)
SECONDARY_TECH = re.compile(r"\b(angular|vue(?:\.?js)?|flutter|xamarin)\b", re.I)
FRONTEND_TITLE = re.compile(r"\b(front[\s-]?end|react|mobile|full[\s-]?stack)\b", re.I)

# Muss in jedem Titel vorkommen, sonst ist es keine Entwickler-Rolle
# (z. B. "IT Projekttechniker" oder "Spiele-Software-Tester").
DEV_ROLE = re.compile(
    r"\b(developer|engineer|entwickler|programmer|softwaredeveloper|"
    r"frontend|front[\s-]end|fullstack|full[\s-]stack|mobile|react|web)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# 4. Ausschluss
# ---------------------------------------------------------------------------
# Immer raus, unabhängig vom Stack.
ALWAYS_EXCLUDE = [
    re.compile(p, re.I)
    for p in (
        r"\bsenior\b",
        r"\bsr\b",
        r"\blead\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\barchitect\b",
        r"\bhead\s+of\b",
        r"\bdirector\b",
        r"\bmanager\b",
        r"\bteam\s*lead(er)?\b",
        r"\bteamlead\b",
        r"\bintern(ship)?s?\b",
        r"\bjunior\b",
        r"\bpraktik(um|ant)?\b",
        r"\bwerkstudent",
        r"\bworking\s+student\b",
        r"\blehrling\b",
        r"\bausbildung\b",
        r"\btester\b",
        r"\btest\s*(engineer|automation|manager)\b",
        r"\bqa\b",
        r"\bquality\s+assurance\b",
        r"\bconsultant\b",
        r"\bdesigner\b",
        r"\bprojekt[\s-]?ingenieur\b",
        r"\bit[\s-]?solutions?\b",
        r"\bsupport\s+engineer\b",
        r"\bapplication\s+manager\b",
        r"\badmin(istrator)?\b",
        r"\bdevops\b",
        r"\bsre\b",
        r"\bdata\s+(scientist|engineer|analyst)\b",
        r"\bmachine\s+learning\b",
        r"\bai\s+engineer\b",
        r"\bbackend\b",
        r"\bback[\s-]?end\b",
        r"\bsap\b",
        r"\bservicenow\b",
        r"\bsalesforce\b",
        r"\bsharepoint\b",
        r"\bit\s+projekt",
    )
]

# Fremde Frameworks: raus, außer der Titel nennt zusätzlich React.
FRAMEWORK_EXCLUDE = [
    re.compile(p, re.I)
    for p in (
        r"\bangular\b",
        r"\bvue(?:\.?js)?\b",
        r"\bflutter\b",
        r"\bswift\b",
        r"\bkotlin\b",
        r"\bxamarin\b",
        r"\bobjective[\s-]?c\b",
    )
]

# Backend-Sprachen: raus, außer der Titel ist React-/Frontend-orientiert.
# \bjava\b matcht "JavaScript" bewusst NICHT.
BACKEND_EXCLUDE = [
    re.compile(p, re.I)
    for p in (
        r"\bjava\b",
        r"\.net\b",
        r"\bc#\b",
        r"\bc\+\+\b",
        r"\bphp\b",
        r"\blaravel\b",
        r"\bsymfony\b",
        r"\bpython\b",
        r"\bruby\b",
        r"\bgolang\b",
        r"\brust\b",
        r"\bscala\b",
        r"\bnestjs\b",
        r"\bwordpress\b",
        r"\btypo3\b",
        r"\bmagento\b",
        r"\bshopify\b",
        r"\bcontao\b",
    )
]

# ---------------------------------------------------------------------------
# 5. Bewertung / Upload
# ---------------------------------------------------------------------------
BASE_SCORE = 5.0
MIN_FIT_SCORE = 5.0      # darunter wird nicht nach Airtable geschrieben
MAX_JOBS_PER_RUN = 40    # Obergrenze neuer Zeilen pro Lauf

# Airtable: URL ist der Dedupe-Schlüssel.
AIRTABLE_PAGE_SIZE = 100
AIRTABLE_BATCH_SIZE = 10

# Alte Zeilen aus der Zeit vor dem Wien-Fokus. `--purge-legacy` löscht nur
# Records, deren URL-Host hier auftaucht – neue Quellen bleiben unangetastet.
LEGACY_URL_HOSTS = ("weworkremotely.com", "remoteok.com")
