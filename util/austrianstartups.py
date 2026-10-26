# util/austrianstartups.py
#
# AustrianStartups betreibt ein Opportunity-Board auf Hivebrite:
#     https://austrianstartups.com/opportunities
#
# Die Seite ist mitglieder-/login-gated; `/jobs` und `/job-board` liefern
# 404. Ohne Account gibt es keine öffentliche Jobliste. Das Modul ist
# deshalb ein bewusster Stub und liefert eine leere Liste mit Warnung.

from config.constants import AUSTRIANSTARTUPS_JOBS_URL


def fetch_austrianstartups_jobs():
    """Kein öffentliches Listing verfügbar (Login-only)."""
    print(
        "⚠️ AustrianStartups: Opportunity-Board ist nur für eingeloggte "
        f"Mitglieder sichtbar ({AUSTRIANSTARTUPS_JOBS_URL})."
    )
    return []
