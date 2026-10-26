# util/scraper.py
#
# Sammelstelle für Job-Quellen:
#   - karriere.at     (JSON in window.VUE_INITIAL_STATE)
#   - devjobs.at      (SEO-Seiten, serverseitig gerendert)
#   - metajob.at      (JSON-RPC; Playwright für Cookie + Token)
#   - epunkt          (Inertia-JSON in data-page)
#   - IT-Karriere.at  (PHP-Suchseite)
#   - jobs.at         (HTML-Karten mit data-Attributen)
#   - Willhaben       (öffentliche JSON-API)
#   - Remotive        (öffentliche Remote-JSON-API)
#   - Relocate.me     (HTML-Karten, nur Österreich/Wien)
#   - StepStone.at    (Playwright)
#   - Indeed.at       (Playwright)
#   - AMS eJob-Room   (Playwright, Angular-SPA)
#   - brutkasten      (best effort; Board derzeit 404)
#   - Work in Austria (best effort; kein öffentliches Listing)
#   - Himalayas       (öffentliche JSON-API, Remote)
#   - Jobicy          (öffentliche JSON-API, Remote)
#   - Remote OK       (öffentliche JSON-API, Remote)
#   - We Work Remotely (RSS, Remote)
#   - Arbeitnow       (öffentliche JSON-API, Wien/Remote)
#   - AI Austria      (HTML-Karten)
#   - DER STANDARD    (Next.js-Flight-Daten)
#   - AustrianStartups (Stub; Login-only)
#   - JOIN            (Stub; Login-only)
#   - LinkedIn        (Guest-Jobsuche, HTML-Fragmente)
#   - XING            (HTML-Karten)
#   - Wellfound       (Next.js/Apollo-State)
#   - Welcome to the Jungle (Stub; Matching/Login + WAF)
#   - WeAreDevelopers (Markdown-Endpunkt)
#   - The Hub         (HTML-Karten)
#   - EU Careers      (HTML-Karten)
#
# Neue Quelle hinzufügen:
#   1. Modul schreiben, das eine Liste normalisierter Job-Dicts liefert
#      (id, title, url, company, description, locations, home_office,
#       employment_type, posted, source, matched_terms)
#   2. Hier importieren und in SOURCES eintragen.

from util.aiaustria import fetch_aiaustria_jobs
from util.ams import fetch_ams_jobs
from util.arbeitnow import fetch_arbeitnow_jobs
from util.austrianstartups import fetch_austrianstartups_jobs
from util.brutkasten import fetch_brutkasten_jobs
from util.derstandard import fetch_derstandard_jobs
from util.devjobs import fetch_devjobs_jobs
from util.epunkt import fetch_epunkt_jobs
from util.eucareers import fetch_eucareers_jobs
from util.himalayas import fetch_himalayas_jobs
from util.indeed import fetch_indeed_jobs
from util.itkarriere import fetch_itkarriere_jobs
from util.jobicy import fetch_jobicy_jobs
from util.jobs import dedupe_by_url
from util.jobsat import fetch_jobsat_jobs
from util.join import fetch_join_jobs
from util.karriere import fetch_karriere_jobs
from util.linkedin import fetch_linkedin_jobs
from util.metajob import fetch_metajob_jobs
from util.remoteok import fetch_remoteok_jobs
from util.relocate import fetch_relocate_jobs
from util.remotive import fetch_remotive_jobs
from util.stepstone import fetch_stepstone_jobs
from util.thehub import fetch_thehub_jobs
from util.wearedevelopers import fetch_wearedevelopers_jobs
from util.welcometothejungle import fetch_welcometothejungle_jobs
from util.wellfound import fetch_wellfound_jobs
from util.weworkremotely import fetch_weworkremotely_jobs
from util.willhaben import fetch_willhaben_jobs
from util.workinaustria import fetch_workinaustria_jobs
from util.xing import fetch_xing_jobs

SOURCES = (
    ("karriere.at", fetch_karriere_jobs),
    ("devjobs.at", fetch_devjobs_jobs),
    ("metajob.at", fetch_metajob_jobs),
    ("epunkt", fetch_epunkt_jobs),
    ("it-karriere.at", fetch_itkarriere_jobs),
    ("jobs.at", fetch_jobsat_jobs),
    ("willhaben.at", fetch_willhaben_jobs),
    ("remotive.com", fetch_remotive_jobs),
    ("relocate.me", fetch_relocate_jobs),
    ("stepstone.at", fetch_stepstone_jobs),
    ("indeed.at", fetch_indeed_jobs),
    ("ams.at", fetch_ams_jobs),
    ("brutkasten.com", fetch_brutkasten_jobs),
    ("workinaustria.com", fetch_workinaustria_jobs),
    ("himalayas.app", fetch_himalayas_jobs),
    ("jobicy.com", fetch_jobicy_jobs),
    ("remoteok.com", fetch_remoteok_jobs),
    ("weworkremotely.com", fetch_weworkremotely_jobs),
    ("arbeitnow.com", fetch_arbeitnow_jobs),
    ("aiaustria.com", fetch_aiaustria_jobs),
    ("jobs.derstandard.at", fetch_derstandard_jobs),
    ("austrianstartups.com", fetch_austrianstartups_jobs),
    ("join.com", fetch_join_jobs),
    ("linkedin.com", fetch_linkedin_jobs),
    ("xing.com", fetch_xing_jobs),
    ("wellfound.com", fetch_wellfound_jobs),
    ("welcometothejungle.com", fetch_welcometothejungle_jobs),
    ("wearedevelopers.com", fetch_wearedevelopers_jobs),
    ("thehub.io", fetch_thehub_jobs),
    ("eu-careers.europa.eu", fetch_eucareers_jobs),
)


def fetch_all_jobs():
    """Holt Jobs aus allen aktiven Quellen und dedupliziert nach URL."""
    jobs = []

    for name, fetch in SOURCES:
        try:
            jobs.extend(fetch())
        except Exception as exc:
            # Eine kaputte Quelle darf den restlichen Lauf nicht verhindern.
            print(f"⚠️ Quelle {name} fehlgeschlagen: {exc}")

    return dedupe_by_url(jobs)
