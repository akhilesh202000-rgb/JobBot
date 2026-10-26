# AGENTS.md

Context for AI agents and contributors working on **JobBot**.

## 1. What this project is

JobBot is a small Python job-hunting pipeline for a **React / React Native
frontend & mobile developer based in Vienna, Austria**.

It:
1. Pulls Vienna job listings from **karriere.at**, **devjobs.at**,
   **metajob.at**, **epunkt**, **IT-Karriere.at**, **jobs.at**, **Willhaben**,
   **Remotive**, **Relocate.me**, **StepStone Österreich**, **Indeed
   Österreich**, the **AMS eJob-Room**, **Himalayas**, **Jobicy**,
   **Remote OK**, **We Work Remotely**, **Arbeitnow**, **AI Austria Jobs**,
   **DER STANDARD Jobs**, **LinkedIn Jobs**, **XING Jobs**, **Wellfound**,
   **WeAreDevelopers**, **The Hub** and **EU Careers**. AustrianStartups,
   JOIN and Welcome to the Jungle are best-effort stubs because their
   listings are login/Matching/WAF-gated.
   - karriere.at: no API key; results are embedded as JSON in
     `window.VUE_INITIAL_STATE`.
   - devjobs.at: server-rendered SEO pages (`/jobs/<tech>-wien-109166`),
     Cloudflare-protected, fetched with `cloudscraper`.
   - metajob.at: own JSON-RPC (`/_irpc/joyservice/se`) plus a browser-set
     anti-bot cookie and search token; fetched with Playwright headless Chromium.
   - epunkt: Laravel/Inertia app; the job list is JSON in `data-page`.
   - IT-Karriere.at: PHP search page (`search.php?search_company=…&search_city=124`).
     The TLS certificate is expired, so `verify=False`.
   - jobs.at: HTML cards with `data-*` attributes; the target URL is
     base64-encoded in `data-c-redirect`.
   - Willhaben: public JSON API (`publicapi.willhaben.at/jobs/v2/adverts`).
   - Remotive: public remote-jobs JSON API; only roles open to
     Vienna/Europe/Worldwide are kept and mapped to `Wien (Remote)`.
   - Relocate.me: HTML cards; only Austria/Vienna cards are kept (often none).
   - StepStone Österreich / Indeed Österreich / AMS eJob-Room: Playwright,
     because requests are blocked or the API requires a browser session.
   - brutkasten and Work in Austria are attempted but currently have no
     publicly scrapeable listing (Getro board 404 / login-only portal).
2. Deduplicates by URL across search terms and sources.
3. Drops roles that are not a fit (senior/lead, internships, Angular/Vue/Flutter,
   backend-only, testers, …).
4. Requires a React mention somewhere (title, description, tech pills, or the
   search term that found the job).
5. Scores each match 0–10 for a **mid-level (2–5 years)** React/RN developer.
6. Ranks the shortlist by **commute distance from Kaisermühlen U1**, nearest first
   (Vienna district centroids, offline).
7. Appends only **new** URLs to **Airtable** — existing rows are never deleted.
   `--purge-legacy` is the one explicit exception (old remote-only rows).

There is no web UI, API, database, or server. The entry point is one script.

## 2. Quick start

```bash
# from the project root
env/bin/python -m pip install -r requirements.txt
env/bin/python -m playwright install chromium   # once, for metajob/StepStone/Indeed/AMS
env/bin/python job_pipeline.py --dry-run   # filter + print, Airtable untouched
env/bin/python job_pipeline.py             # filter + append new jobs to Airtable
env/bin/python job_pipeline.py --backfill  # fill missing metadata on existing rows
env/bin/python job_pipeline.py --purge-legacy   # delete old remote-only rows
env/bin/python -m unittest discover -s tests -t . -v
```

The venv uses **Python 3.14**. Runtime deps: `requests`, `python-dotenv`,
`cloudscraper` (devjobs.at behind Cloudflare), `playwright` (metajob.at needs a
real browser session). Playwright's Chromium is a separate one-time download.

CLI flags:
- `--dry-run` – no Airtable reads/writes.
- `--limit N` – max jobs per run (default `MAX_JOBS_PER_RUN`).
- `--min-score X` – minimum fit score (default `MIN_FIT_SCORE`).
- `--backfill` – fetch all sources, match existing rows by normalized URL, and
  fill only missing optional metadata. Ignores `--limit` / `--min-score` and
  cannot be combined with `--dry-run`.
- `--purge-legacy` – delete only old `weworkremotely.com` / `remoteok.com`
  rows **without a `Source` field** from Airtable, then exit. New rows from
  these sources are protected by their `Source` value.

## 3. Directory map

```
README.md              Public overview, setup, usage and privacy notes
.env.example           Template for the required Airtable environment variables
job_pipeline.py        Entry point: fetch → filter/score → distance sort → Airtable append
config/constants.py    All tunables: sources, search terms, exclusions, scoring, home location, districts
util/karriere.py       karriere.at fetch + VUE_INITIAL_STATE JSON parsing
util/devjobs.py        devjobs.at SEO pages via cloudscraper + HTML card parsing
util/metajob.py        metajob.at JSON-RPC (Playwright cookie + token)
util/epunkt.py         epunkt Inertia data-page JSON
util/itkarriere.py     IT-Karriere.at search page + HTML cards
util/jobsat.py         jobs.at HTML cards + base64 redirect decoding
util/willhaben.py      Willhaben public job-search JSON API
util/remotive.py       Remotive remote-jobs JSON API
util/relocate.py       Relocate.me HTML cards (Austria/Vienna only)
util/stepstone.py      StepStone.at via Playwright
util/indeed.py         Indeed.at via Playwright (fresh context per term)
util/ams.py            AMS eJob-Room via Playwright (Angular SPA)
util/brutkasten.py     best effort; board currently 404
util/workinaustria.py  best effort; no public listing
util/himalayas.py      Himalayas public JSON API + cursor pagination
util/jobicy.py         Jobicy remote JSON API
util/remoteok.py       Remote OK JSON feed
util/weworkremotely.py We Work Remotely RSS feeds
util/arbeitnow.py      Arbeitnow job-board API (Wien/Remote)
util/aiaustria.py      AI Austria Notion/Super.so HTML cards
util/derstandard.py    DER STANDARD Jobs Next.js flight-data parser
util/austrianstartups.py best-effort stub; member/login gated
util/join.py           best-effort stub; login gated
util/linkedin.py       LinkedIn guest job-search HTML fragments
util/xing.py           XING job-search HTML cards
util/wellfound.py      Wellfound Next.js/Apollo-state parser
util/welcometothejungle.py best-effort stub; Matching/Login + AWS WAF
util/wearedevelopers.py WeAreDevelopers Markdown endpoint
util/thehub.py         The Hub HTML cards
util/eucareers.py      EU Careers HTML cards
util/scraper.py        Source aggregator: fetch_all_jobs() + URL dedupe
util/jobs.py           Pure filter/score logic (no network, unit-tested)
util/geo.py            Vienna district/PLZ → centroid → distance from home
util/airtable.py       Read URLs, batch create, backfill missing metadata, legacy cleanup
tests/test_jobs.py     unittest suite for filtering, scoring, location parsing
tests/test_devjobs.py  unittest suite for devjobs card parsing
tests/test_metajob.py  unittest suite for metajob payload/row normalization
tests/test_extra_sources.py unittest suite for the additional source parsers
tests/test_airtable.py unittest suite for Airtable fields + legacy host matching
data/                  Local-only resumes/PII (gitignored; never commit)
.env                   Secrets (gitignored): AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME
env/                   Local virtualenv (gitignored)
```

## 4. Data flow

```
util.karriere.fetch_karriere_jobs()   ┐
util.devjobs.fetch_devjobs_jobs()     │
util.metajob.fetch_metajob_jobs()     │
util.epunkt.fetch_epunkt_jobs()       │
util.itkarriere.fetch_itkarriere_jobs()│
util.jobsat.fetch_jobsat_jobs()       ├─ list[dict]  (id, title, url, company,
util.willhaben.fetch_willhaben_jobs() │               description, locations,
util.remotive.fetch_remotive_jobs()   │               home_office, employment_type,
util.relocate.fetch_relocate_jobs()   │               posted, source, matched_terms)
util.stepstone.fetch_stepstone_jobs() │
util.indeed.fetch_indeed_jobs()       │
util.ams.fetch_ams_jobs()             │
util.brutkasten.fetch_brutkasten_jobs()│
util.workinaustria.fetch_workinaustria_jobs()│
util.himalayas.fetch_himalayas_jobs() │
util.jobicy.fetch_jobicy_jobs()       │
util.remoteok.fetch_remoteok_jobs()   │
util.weworkremotely.fetch_weworkremotely_jobs()│
util.arbeitnow.fetch_arbeitnow_jobs() │
util.aiaustria.fetch_aiaustria_jobs() │
util.derstandard.fetch_derstandard_jobs()│
util.austrianstartups.fetch_austrianstartups_jobs()│
util.join.fetch_join_jobs()           │
util.linkedin.fetch_linkedin_jobs()   │
util.xing.fetch_xing_jobs()           │
util.wellfound.fetch_wellfound_jobs() │
util.welcometothejungle.fetch_welcometothejungle_jobs()│
util.wearedevelopers.fetch_wearedevelopers_jobs()│
util.thehub.fetch_thehub_jobs()       │
util.eucareers.fetch_eucareers_jobs() ┘
        ▼
util.scraper.fetch_all_jobs()          (each source wrapped in try/except)
        ▼
util.jobs.dedupe_by_url()
        ▼
util.jobs.evaluate() per job
        ├─ is_title_excluded()      → senior/lead/intern/Angular/Java/.NET/...
        ├─ is_dev_role()            → title must look like a dev role
        ├─ is_react_relevant()      → React in title/description/matched_terms
        ├─ best_vienna_location()   → must resolve to a Vienna location
        └─ score_job()              → drop if fit < MIN_FIT_SCORE
        ▼
sort by (distance_km asc, fit desc) → cap at MAX_JOBS_PER_RUN
        ▼
Airtable: get_existing_urls() → skip duplicates → create_records() in 10er batches
```

### Sources (`config/constants.py`)

- `KARRIERE_SEARCH_TERMS` – 8 terms; ~15 results each because pagination is
  client-side.
- `DEVJOBS_TECH_SLUGS` – `react`, `react-native`, `typescript`, `javascript`,
  `node-js`, `next-js`, `graphql`; each yields up to 15 cards for
  `DEVJOBS_LOCATION_SLUG = wien-109166`. Unknown slugs 404 and are skipped.
- `METAJOB_*` – RPC URL, op hash, location, page size (`20`), max pages,
  search terms. `METAJOB_USE_BROWSER = True` uses Playwright: it loads the
  homepage, captures the `a0.s` search token from one UI search, then calls the
  RPC directly for every term/page. `False` uses plain `requests` (currently
  blocked by the cookie check).
- `EPUNKT_*` – base URL, Wien slug, max pages (`4`). epunkt has no search
  filter that actually filters, so all ~94 Wien jobs are fetched and the
  normal filter decides.
- `ITKARRIERE_*` – search URL, Wien city ID (`124`), search terms.
- `JOBSAT_*` – base URL, location (`Wien`), search terms.
- `WILLHABEN_*` – API URL, public job URL prefix, search terms, max pages.
- `REMOTIVE_*` – API URL, search terms, allowed remote regions. Remote jobs are
  mapped to `Wien (Remote)` so the distance sort uses the city centroid.
- `RELOCATE_*` – base URL, search terms, max pages. Only `/austria/` or
  Vienna/Wien cards survive.
- `STEPSTONE_*` – base URL, `in-wien` slug, search terms.
- `INDEED_*` – base URL, location, search terms, max scrolls. Indeed triggers a
  security check after a few searches, so each term gets a fresh browser
  context and a 10-second pause.
- `AMS_*` – SPA base URL and search terms. The SPA is loaded with
  `?query=<term>&location=Wien`; cards are read from the rendered DOM.
- `BRUTKASTEN_JOBS_URL`, `WORKINAUSTRIA_JOBS_URL` – best-effort endpoints for
  sources that currently have no public listing.

### Weitere Plattformen (`config/constants.py`)

- `REMOTE_ALLOWED_LOCATIONS` – gemeinsame Allowlist für Remote-Boards
  (Worldwide/Anywhere/Europe/EMEA/Österreich/Remote). Einzelne Länder wie
  `USA` oder `Ukraine` reichen nicht; solche Jobs werden verworfen.
- `HIMALAYAS_API`, `HIMALAYAS_MAX_PAGES` – öffentliche JSON-API, 20 Jobs pro
  Seite, Cursor-Pagination. Die API ignoriert `search`/`limit`; lokal wird auf
  React und die Remote-Allowlist gefiltert.
- `JOBICY_API`, `JOBICY_COUNT`, `JOBICY_GEO`, `JOBICY_MAX_PAGES` – Remote-API;
  `geo=europe` filtert grob, `tag=react` filtert nicht. Lokal filtern.
- `REMOTEOK_API` – JSON-Feed; das erste Listenelement ist ein
  Metadaten-Objekt und wird übersprungen. Der Titel steht in `position`.
- `WWR_RSS_FEEDS` – drei RSS-Feeds (Programming, Full-Stack, Front-End).
  Regionen wie `USA Only` werden verworfen; `Anywhere`/`Europe` bleiben.
- `ARBEITNOW_API`, `ARBEITNOW_MAX_PAGES` – 300 Jobs pro Seite, `links.next`.
  Wien-Treffer bleiben, echte Remote-Jobs werden zu `Wien (Remote)`.
- `AIAUSTRIA_JOBS_URL` – Notion/Super.so-Karten ohne Beschreibung; nur Titel
  und Standort-Pill. Wien und Remote bleiben.
- `DERSTANDARD_BASE`, `DERSTANDARD_SEARCH_TERMS` – Next.js-Flight-Daten
  (`self.__next_f.push`) mit `JobListingResponse`-Objekten; Tags wie `React`
  zählen als React-Beleg.
- `AUSTRIANSTARTUPS_JOBS_URL` – bewusster Stub; Opportunity-Board ist
  mitglieder-/login-gated.
- `JOIN_JOBS_URL` – bewusster Stub; `/jobs` leitet auf `auth.join.com` um.
- `LINKEDIN_GUEST_API`, `LINKEDIN_LOCATION`, `LINKEDIN_SEARCH_TERMS`,
  `LINKEDIN_MAX_PAGES` – öffentliche Guest-Suche, 10 Karten/Seite. Die
  Job-ID aus `data-entity-urn` wird zur kanonischen URL.
- `XING_SEARCH_URL`, `XING_SEARCH_TERMS` – HTML-Karten; die Seite ist UTF-8,
  `response.encoding` wird explizit gesetzt.
- `WELLFOUND_JOBS_URL` – Next.js/Apollo-State in `__NEXT_DATA__`; meist
  US-Jobs. Nur Wien/Austria oder erlaubte Remote-Regionen bleiben.
- `WELCOMETOTHEJUNGLE_JOBS_URL` – bewusster Stub; Matching/Login + AWS WAF.
- `WEAREDEVELOPERS_JOBS_MD`, `WEAREDEVELOPERS_COUNTRY`,
  `WEAREDEVELOPERS_SEARCH_TERMS` – Markdown-Endpunkt `jobs.md`;
  `q=<term>&country=AT` funktioniert, `page` nicht.
- `THEHUB_JOBS_URL`, `THEHUB_SEARCH_TERMS` – Nuxt-Board mit HTML-Karten;
  Fokus Nordeuropa/UK, Wien-Treffer sind selten.
- `EUCAREERS_JOBS_URL`, `EUCAREERS_MAX_PAGES` – 20 Karten/Seite, `?page=N`.
  Die meisten Stellen sind in Brüssel/Luxemburg.

### Filtering rules (`config/constants.py`)

- `ALWAYS_EXCLUDE` – senior, sr, lead, staff, principal, architect, manager,
  teamlead, junior, intern/praktikum/werkstudent, tester/QA, consultant,
  designer, Projekt-Ingenieur, IT-Solutions, support, admin, devops,
  data scientist, backend, SAP/ServiceNow/Salesforce/SharePoint, …
- `FRAMEWORK_EXCLUDE` – Angular, Vue, Flutter, Swift, Kotlin, Xamarin, Obj-C.
  Applied only when the title does **not** also mention React.
- `BACKEND_EXCLUDE` – Java, .NET, C#, PHP, Python, Ruby, Go, Rust, Scala, NestJS,
  WordPress, TYPO3, Magento, Shopify. Applied only when the title is neither
  React nor frontend oriented. `\bjava\b` deliberately does not match "JavaScript".
- `DEV_ROLE` – title must contain developer/engineer/entwickler/frontend/mobile/…
- `REACT_IN_TEXT` – `react`, `react.js`, `reactjs`, `react-native`, `react native`.

### Scoring (`util/jobs.py:score_job`)

| Condition | Delta |
|---|---|
| base score | 5 |
| React in title | +2 |
| React only in `matched_terms` (empty summary) | +1 |
| `react native` in matched terms | +1 |
| `react native` / `expo` in text | +2 |
| `typescript` | +1 |
| full-stack in title | −1 |
| backend tech in title while React present | −1 |
| Angular/Vue/Flutter/Xamarin mentioned | −1 |
| 5+ years required | −2 |
| 2–4 years required | +1 |
| ≤1 year required | −1 |

Clamped to `[0, 10]`. Jobs below `MIN_FIT_SCORE` (default 5) are dropped.

### Distance (`util/geo.py`)

- Home reference: `HOME_LAT` / `HOME_LNG` (default Kaisermühlen U1, 1220).
- `parse_location()` handles `Wien 22. Bezirk (Donaustadt)`, `1220 Wien`,
  `Wien`, `Südliches Wien`, and optional suburbs (`INCLUDE_SUBURBS = False`).
- District centroids from `DISTRICTS`; unknown "Wien" falls back to the city
  centroid. This is an approximation, not a routing API.
- Result is **straight-line km**, not transit time.

## 5. Airtable

- **Append-only by default.** `clear_airtable_table()` still exists but is
  **not called** by the pipeline. Do not reintroduce the wipe.
- `--purge-legacy` deletes only rows whose URL host is in `LEGACY_URL_HOSTS`
  (`weworkremotely.com`, `remoteok.com`) **and whose `Source` field is empty**.
  Matching is exact/subdomain, so look-alike domains are safe. The `Source`
  check protects newly added Remote OK / We Work Remotely rows, because both are
  active sources again.
- Existing URLs are read with full pagination (`AIRTABLE_PAGE_SIZE`) and skipped.
- New jobs are POSTed in batches of 10 (`AIRTABLE_BATCH_SIZE`) with `typecast`.
- Deletes also run in 10er batches via `records[]` query params.
- 429 responses honour `Retry-After`.
- If the table lacks an optional field, the 422 response is parsed, the field is
  dropped, and the batch is retried. Optional fields:
  `Company`, `Location`, `District`, `Distance (km)`, `Home Office`, `Source`,
  `Posted`, `Employment Type`.
- `--backfill` reads existing rows, matches them by normalized URL (`https`, no
  `www.`, no trailing slash), and fills **only empty** optional fields. Existing
  values are never overwritten. Rows whose URL no longer appears in a fresh fetch
  derive metadata from the stored `Cover Letter / Anschreiben`.
- Field types are Airtable-managed: `District` is a **number** (`1`–`23`),
  `Distance (km)` is a number, `Home Office` is a checkbox, `Posted` is a
  **date**. `normalize_posted()` converts relative source dates
  (`"vor 3 Tagen"`) to ISO `YYYY-MM-DD`; unparseable dates are dropped so a
  batch cannot fail on one bad value.
- Required fields: `Job Title`, `URL`, `Description`, `Match Score`,
  `Cover Letter / Anschreiben`, `Status` (`"To Review"`).

## 6. Conventions

- Code/comments are a **mix of German and English**; runtime logs are German with
  emoji. Keep that style.
- Imports are absolute from the project root (`from config.constants import …`).
  Run from the repo root.
- `config/` is a namespace package (no `__init__.py`); `util/__init__.py` exists.
- New tunables belong in `config/constants.py`, not inline.
- Secrets via `os.getenv` after `load_dotenv()`. Never commit or print them.
- Filter/score logic must stay network-free in `util/jobs.py` so it can be tested.

## 7. Known issues / gotchas

1. **karriere.at pagination is client-side.** `?page=2` is ignored server-side;
   each search term yields ~15 results. Coverage comes from multiple terms.
2. **Search summaries are often empty.** `matched_terms` compensates, but the
   score is coarser for those jobs.
3. **Most listings only say "Wien".** They all fall back to the city centroid, so
   many jobs share ~3.5 km and tie in the distance sort.
4. **No geocoding / routing.** Distance is straight-line from a district centroid.
5. **devjobs.at sits behind Cloudflare.** Plain `requests`/`curl` get 403;
   `cloudscraper` works. The SEO pages expose at most 15 cards each and ignore
   `?page=` / `?p=`, so coverage comes from multiple tech slugs.
6. **metajob.at needs Playwright.** The RPC requires a browser-set cookie and a
   per-session search token (`a0.s`). `util/metajob.py` loads the SPA, captures
   the token from one UI search, then queries the RPC directly. If Playwright or
   Chromium is missing, it falls back to `requests`, which is blocked and yields
   `[]` with a warning. The private RPC can change without notice.
7. **metajob uses click-through URLs.** Rows have no direct employer URL, so the
   stored link is `https://www.metajob.at/dres/jc?p=<jid>`, which redirects.
8. **Cross-source duplicates are not merged.** Dedupe is by URL, so the same
   job listed on karriere.at and devjobs.at can appear twice.
9. **Airtable schema is user-managed.** Missing optional fields are skipped with a
   warning; the metadata API is not available with the current PAT. Field types
   must be inferred: `District` is numeric (`1`–`23`), `Posted` is a date,
   `Distance (km)` is numeric and `Home Office` is a checkbox.
10. **`data/` is local-only and gitignored.** Never commit resumes or other
    personal data.
11. **No retry/backoff for Airtable writes** beyond 429 + unknown-field retries.
12. `requirements.txt` has no lockfile.
13. **The venv `pip` shebang may be stale** if the repo was moved. Use
    `env/bin/python -m pip install …` instead of `env/bin/pip`.
14. **StepStone and Indeed block plain requests.** StepStone times out or
    returns 403; Indeed returns 403/401. Both work through Playwright.
15. **Indeed rate-limits after a few searches.** A shared browser context hits
    the "Security Check" page. `util/indeed.py` uses a fresh context per term
    and a 10-second pause, which works reliably but makes the run slower.
16. **AMS API is 401 outside the SPA.** `/public/emps/api/search` needs the
    browser session. `util/ams.py` therefore reads the rendered search page
    instead of calling the API.
17. **IT-Karriere.at has an expired TLS certificate.** `verify=False` is
    deliberate; only public listings are read. Titles containing `C#` need
    `#` → `%23` encoding in the stored URL.
18. **epunkt ignores `query`.** `?query=react` still returns all jobs. All Wien
    pages are fetched and the normal React filter decides.
19. **Relocate.me has almost no Vienna jobs.** The module filters to
    `/austria/` or Vienna/Wien cards and often returns `[]`.
20. **Remotive is remote-only.** Jobs open to Europe/Worldwide are mapped to
    `Wien (Remote)`; the description is the full text, so `matched_terms` is
    intentionally empty to avoid fuzzy search hits.
21. **brutkasten and Work in Austria are currently dead ends.** The brutkasten
    Getro board redirects to `/not-found`; Work in Austria only links to a
    login-only applicant portal. Both modules return `[]` with a warning.
22. **Willhaben's `location=Wien` API filter is too strict.** The module
    searches by keyword only and filters `LOCATION` attributes for "Wien"
    itself.
23. **AustrianStartups, JOIN and Welcome to the Jungle are deliberate stubs.**
    AustrianStartups' opportunity board is member/login-gated, JOIN's job
    search redirects to `auth.join.com`, and Welcome to the Jungle now requires
    Matching/Login and is protected by AWS WAF (HTTP 202). They return `[]`
    with a warning and can be dropped if they stay unavailable.
24. **Remote boards only keep jobs open to Vienna/Europe/Worldwide.** Himalayas,
    Jobicy, Remote OK, We Work Remotely and Wellfound are filtered against
    `REMOTE_ALLOWED_LOCATIONS`. A job restricted to `USA`, `Ukraine`, etc. is
    dropped instead of being mislabelled as `Wien (Remote)`.
25. **RemoteOK and We Work Remotely are active sources again.** `--purge-legacy`
    therefore only deletes legacy-host rows **without** a `Source` field; new
    rows are protected. Do not change this back to a pure host-based delete.
26. **Arbeitnow, The Hub, EU Careers and Wellfound have very low Vienna
    coverage.** Arbeitnow is Germany-focused, The Hub is Nordic/UK-focused, EU
    Careers is mostly Brussels/Luxembourg, and Wellfound is mostly US. Zero
    results are normal; the modules still parse correctly (covered by fixtures).
27. **DER STANDARD and Wellfound rely on framework internals.** DER STANDARD
    embeds jobs as Next.js flight data; Wellfound uses Apollo state in
    `__NEXT_DATA__`. Both can break when the sites change their frontend.
28. **`fetch_all_jobs()` now performs many more HTTP requests.** The new sources
    add roughly 40 request loops (including multiple search terms). Remote
    boards are fetched sequentially with `POLITE_DELAY_SECONDS`; a full run is
    slower than before but still request-based (no extra Playwright except the
    existing StepStone/Indeed/AMS/metajob sources).

## 8. Suggested next steps (not yet done)

- Enrich empty summaries by fetching job detail pages for the shortlist.
- Validate shortlisted URLs (some Remotive listings expire and return 404/410).
- Optional geocoding + real transit time if precision matters.
- Merge cross-source duplicates by (company, title) if the table gets noisy.
- Re-check brutkasten / Work in Austria / AustrianStartups / JOIN / Welcome to
  the Jungle periodically; drop the stubs if they stay unavailable.
- Add an Airtable `Run Date` / `First Seen` field and a "new this week" view.
