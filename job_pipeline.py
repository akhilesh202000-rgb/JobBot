# job_pipeline.py
#
# Ablauf:
#   1. Jobs von karriere.at, devjobs.at und metajob.at (Wien) holen
#   2. Auf React/RN + Mid-Level filtern und bewerten
#   3. Nach Pendelweg von Kaisermühlen U1 sortieren (nächster zuerst)
#   4. Nur neue URLs nach Airtable schreiben (bestehende bleiben erhalten)
#
# Nutzung:
#   python job_pipeline.py                 # scrapen + nach Airtable schreiben
#   python job_pipeline.py --dry-run       # nur anzeigen, Airtable bleibt unberührt
#   python job_pipeline.py --limit 15 --min-score 6
#   python job_pipeline.py --backfill      # fehlende Metadaten bestehender Zeilen ergänzen
#   python job_pipeline.py --purge-legacy  # alte WWR/RemoteOK-Zeilen ohne Source löschen

import argparse
import os

from dotenv import load_dotenv

from config.constants import MAX_JOBS_PER_RUN, MIN_FIT_SCORE
from util.airtable import (
    create_records,
    delete_legacy_urls,
    get_existing_urls,
    normalize_url,
    update_records,
)
from util.jobs import build_shortlist
from util.scraper import fetch_all_jobs

load_dotenv()

AIRTABLE_PAT = os.getenv("AIRTABLE_PAT")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")


def parse_args():
    parser = argparse.ArgumentParser(description="JobBot – Wien-Jobs filtern und nach Airtable schreiben.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur filtern und anzeigen, Airtable wird nicht angefasst.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=MAX_JOBS_PER_RUN,
        help=f"Maximale Anzahl Jobs pro Lauf (Standard: {MAX_JOBS_PER_RUN}).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=MIN_FIT_SCORE,
        help=f"Minimaler Fit-Score 0-10 (Standard: {MIN_FIT_SCORE}).",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Fehlende Metadaten (Standort, Distanz, Quelle, …) bestehender Airtable-Zeilen ergänzen.",
    )
    parser.add_argument(
        "--purge-legacy",
        action="store_true",
        help="Nur alte Einträge (WeWorkRemotely/RemoteOK) ohne Source-Feld aus Airtable löschen und beenden.",
    )
    return parser.parse_args()


def print_shortlist(jobs):
    print("🏆 SHORTLIST – nähester Pendelweg zuerst")
    print("-" * 100)
    print(f"{'#':>3} | {'Fit':>3} | {'km':>4} | {'Bezirk':<24} | {'Titel':<48} | Firma")
    print("-" * 100)

    for index, job in enumerate(jobs, start=1):
        district = (job.get("district") or "Wien")[:24]
        title = (job.get("title") or "")[:48]
        company = (job.get("company") or "")[:28]
        print(f"{index:>3} | {job['fit']:>3.0f} | {job['distance_km']:>4.1f} | {district:<24} | {title:<48} | {company}")

    print("-" * 100)


def main():
    args = parse_args()

    print("🚀 JobBot startet – Fokus: React / React Native, Wien, Mid-Level\n")

    if not args.dry_run:
        missing = [
            name
            for name, value in (
                ("AIRTABLE_PAT", AIRTABLE_PAT),
                ("AIRTABLE_BASE_ID", AIRTABLE_BASE_ID),
                ("AIRTABLE_TABLE_NAME", AIRTABLE_TABLE_NAME),
            )
            if not value
        ]
        if missing:
            print(f"❌ Fehlende .env-Werte: {', '.join(missing)}")
            print("   Tipp: mit --dry-run testen, ohne Airtable zu brauchen.")
            return 1

    if args.purge_legacy:
        if args.dry_run:
            print("❌ --purge-legacy löscht Zeilen und ist mit --dry-run nicht kombinierbar.")
            return 1
        deleted = delete_legacy_urls(
            AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_PAT
        )
        print(f"🧹 {deleted} alte Einträge gelöscht.")
        return 0

    if args.backfill:
        if args.dry_run:
            print("❌ --backfill schreibt und ist mit --dry-run nicht kombinierbar.")
            return 1

        print("🩹 Backfill: fehlende Airtable-Metadaten ergänzen ...\n")
        all_jobs = fetch_all_jobs()
        jobs_by_url = {
            normalize_url(job["url"]): job
            for job in all_jobs
            if job.get("url")
        }
        updated, unchanged, unmatched, failed = update_records(
            AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_PAT, jobs_by_url
        )
        print(
            f"\n🩹 Backfill fertig: {updated} aktualisiert, "
            f"{unchanged} unverändert, {unmatched} ohne frischen Quelltreffer, "
            f"{failed} fehlgeschlagen."
        )
        return 0

    # 1. Quellen
    all_jobs = fetch_all_jobs()

    # 2. Filtern + bewerten + nach Entfernung sortieren
    shortlist = build_shortlist(all_jobs, limit=args.limit, min_fit=args.min_score)

    print(f"🔎 {len(all_jobs)} Jobs geholt → {len(shortlist)} passen zu dir "
          f"(Fit ≥ {args.min_score:g}, max. {args.limit})\n")

    if not shortlist:
        print("😕 Keine passenden Jobs gefunden. Suchbegriffe in config/constants.py erweitern?")
        return 0

    print_shortlist(shortlist)

    if args.dry_run:
        print("\n🧪 Dry-Run: Airtable wurde nicht verändert.")
        return 0

    # 3. Airtable: bestehende URLs überspringen
    existing_urls = get_existing_urls(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_PAT)
    new_jobs = [job for job in shortlist if job["url"] not in existing_urls]
    skipped = len(shortlist) - len(new_jobs)

    print(f"\n💾 Airtable: {len(existing_urls)} Links bereits vorhanden, "
          f"{skipped} Duplikate übersprungen, {len(new_jobs)} neu.")

    if not new_jobs:
        print("✨ Alles schon gespeichert – nichts zu tun.")
        return 0

    # 4. Upload
    created, failed = create_records(
        AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_PAT, new_jobs
    )

    print(f"\n🎉 Fertig: {created} neue Jobs in Airtable, {failed} fehlgeschlagen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
