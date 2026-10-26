# JobBot

A small Python pipeline that collects Vienna job listings from multiple job
boards, filters them for mid-level React / React Native roles, scores fit,
ranks by straight-line distance from a configurable home location, and appends
new matches to Airtable.

## What it does

- Fetches listings from karriere.at, devjobs.at, metajob.at, epunkt,
  IT-Karriere.at, jobs.at, Willhaben, Remotive, Relocate.me, StepStone
  Österreich, Indeed Österreich, AMS eJob-Room, Himalayas, Jobicy, Remote OK,
  We Work Remotely, Arbeitnow, AI Austria Jobs, DER STANDARD Jobs, LinkedIn
  Jobs, XING Jobs, Wellfound, WeAreDevelopers, The Hub and EU Careers.
- Deduplicates by URL.
- Drops senior/lead/intern/tester/backend-only/non-React roles.
- Scores each match 0–10 for a mid-level (2–5 years) React/RN developer.
- Ranks by straight-line distance from the home location.
- Appends only new URLs to Airtable (append-only by default).

## Requirements

- Python 3.14
- `requests`, `python-dotenv`, `cloudscraper`, `playwright`
- Playwright Chromium (for metajob.at, StepStone, Indeed and AMS)

## Setup

```bash
python -m venv env
env/bin/python -m pip install -r requirements.txt
env/bin/python -m playwright install chromium
cp .env.example .env
# fill in your Airtable credentials
```

`.env`:

```dotenv
AIRTABLE_PAT=your_airtable_pat_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
AIRTABLE_TABLE_NAME=Jobs
```

## Usage

```bash
env/bin/python job_pipeline.py --dry-run
env/bin/python job_pipeline.py
env/bin/python job_pipeline.py --backfill
env/bin/python job_pipeline.py --purge-legacy
env/bin/python -m unittest discover -s tests -t . -v
```

Options: `--limit N`, `--min-score X`.

## Privacy

`.env`, `env/` and `data/` are gitignored. Do not commit API tokens, resumes or
other personal data. The home location in `config/constants.py` is a public
transit landmark; adjust `HOME_LAT` / `HOME_LNG` for your own use.

## Notes

Some sources are best-effort stubs because their listings are login- or
WAF-gated. Remote boards are filtered to roles open to Vienna/Europe/Worldwide.
