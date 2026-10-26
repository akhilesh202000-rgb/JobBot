# util/join.py
#
# JOIN ist eine Recruiting-Plattform für Arbeitgeber. Die öffentliche
# Jobsuche (`/jobs`) leitet auf auth.join.com um; `/jobs/active` verlangt
# ebenfalls einen Login. Ohne Zugangsdaten gibt es keine durchsuchbare
# Jobliste. Das Modul ist deshalb ein bewusster Stub.

from config.constants import JOIN_JOBS_URL


def fetch_join_jobs():
    """Kein öffentliches Listing verfügbar (Login-only)."""
    print(
        "⚠️ JOIN: Jobsuche ist login-gated und ohne öffentliche Liste "
        f"nicht scrapebar ({JOIN_JOBS_URL})."
    )
    return []
