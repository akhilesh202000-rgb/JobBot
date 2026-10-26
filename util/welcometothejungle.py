# util/welcometothejungle.py
#
# Welcome to the Jungle hat die öffentliche Jobsuche auf ein "Matching"
# umgestellt. Ohne Login zeigt `/en/jobs` nur noch eine Marketing-Seite;
# die frühere Liste ist nicht mehr erreichbar. Zusätzlich schützt AWS WAF
# die Seite (HTTP 202 / Challenge). Das Modul ist ein bewusster Stub.

from config.constants import WELCOMETOTHEJUNGLE_JOBS_URL


def fetch_welcometothejungle_jobs():
    """Kein öffentliches Listing verfügbar (Matching/Login + AWS WAF)."""
    print(
        "⚠️ Welcome to the Jungle: öffentliche Jobsuche wurde auf Matching "
        f"umgestellt und ist ohne Login nicht scrapebar ({WELCOMETOTHEJUNGLE_JOBS_URL})."
    )
    return []
