# tests/test_extra_sources.py
#
# Netzwerkfreie Tests für die zusätzlichen Quellen:
# epunkt, IT-Karriere.at, jobs.at, Willhaben, Remotive, Relocate.me,
# StepStone, Indeed, AMS, brutkasten, Work in Austria, Himalayas, Jobicy,
# Remote OK, We Work Remotely, Arbeitnow, AI Austria, DER STANDARD,
# LinkedIn, XING, Wellfound, WeAreDevelopers, The Hub und EU Careers.

import base64
import html
import json
import unittest

from util.aiaustria import parse_cards as aiaustria_cards
from util.ams import normalize_cards as ams_cards
from util.arbeitnow import parse_jobs as arbeitnow_jobs
from util.brutkasten import parse_cards as brutkasten_cards
from util.derstandard import parse_flight as derstandard_flight
from util.epunkt import parse_jobs as epunkt_jobs
from util.eucareers import parse_page as eucareers_page
from util.himalayas import parse_jobs as himalayas_jobs
from util.indeed import normalize_cards as indeed_cards
from util.itkarriere import parse_cards as itkarriere_cards
from util.jobicy import parse_jobs as jobicy_jobs
from util.jobsat import parse_cards as jobsat_cards
from util.linkedin import parse_cards as linkedin_cards
from util.remoteok import parse_jobs as remoteok_jobs
from util.relocate import parse_cards as relocate_cards
from util.remotive import parse_jobs as remotive_jobs
from util.stepstone import normalize_cards as stepstone_cards
from util.thehub import parse_cards as thehub_cards
from util.wearedevelopers import parse_markdown as wearedevelopers_markdown
from util.wellfound import parse_page as wellfound_page
from util.weworkremotely import parse_feed as weworkremotely_feed
from util.willhaben import parse_adverts as willhaben_jobs
from util.workinaustria import parse_cards as workinaustria_cards
from util.xing import parse_cards as xing_cards


class EpunktTests(unittest.TestCase):
    def test_parse_inertia_payload(self):
        payload = {
            "props": {
                "jobPostings": {
                    "data": [
                        {
                            "id": 42,
                            "title": "Fullstack Entwickler (w/m/x)",
                            "route_uri": "fullstack-entwickler-wmx-42",
                            "location": "Wien",
                            "future_role": "<p>React und TypeScript</p>",
                            "created_at": "2026-10-01T10:00:00.000000Z",
                            "home_office": "2Tage",
                            "employment_types": [{"name": "Vollzeit"}],
                            "working_regions": [{"name": "Wien"}],
                        }
                    ]
                }
            }
        }
        page = (
            '<div id="app" data-page="'
            + html.escape(json.dumps(payload), quote=True)
            + '"></div>'
        )

        jobs = epunkt_jobs(page)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["id"], "42")
        self.assertEqual(job["company"], "epunkt")
        self.assertEqual(job["url"], "https://job.epunkt.com/jobs/fullstack-entwickler-wmx-42")
        self.assertTrue(job["home_office"])
        self.assertIn("React", job["description"])
        self.assertIn("Wien", job["locations"])


class ItKarriereTests(unittest.TestCase):
    def test_parse_card_and_encode_hash(self):
        page = """
        <a href="https://www.it-karriere.at/66011/0/Senior-C#-Developer---Angular-(w-m-d)">
          <div class="column-middle">
            <h1>Senior C# Developer / Angular (w/m/d)</h1>
            <h3>apsa personnel concepts gmbh</h3>
            <p class="job-info">Wien | Software Development<!-- | 18.03.2026 --><br></p>
          </div>
        </a>
        """
        jobs = itkarriere_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["title"], "Senior C# Developer / Angular (w/m/d)")
        self.assertEqual(job["company"], "apsa personnel concepts gmbh")
        self.assertEqual(job["locations"], ["Wien"])
        self.assertEqual(job["posted"], "18.03.2026")
        self.assertIn("%23", job["url"])
        self.assertNotIn("#", job["url"])


class JobsAtTests(unittest.TestCase):
    def test_parse_card_with_base64_redirect(self):
        target = "https://www.jobs.at/i/7910848"
        encoded = base64.b64encode(target.encode()).decode()
        page = f"""
        <li data-job="7910848" data-job-date="1792501877">
          <h2 data-job-title>
            <a data-c-title="Senior Frontend Developer (m/w/d)"
               data-c-redirect="{encoded}">Senior Frontend Developer (m/w/d)</a>
          </h2>
          <div>Firma xxxldigital Standort Wien , Wels , Linz Job teilen</div>
        </li>
        """
        jobs = jobsat_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["title"], "Senior Frontend Developer (m/w/d)")
        self.assertEqual(job["company"], "xxxldigital")
        self.assertEqual(job["locations"], ["Wien", "Wels", "Linz"])
        self.assertEqual(job["url"], target)
        self.assertTrue(job["posted"])


class WillhabenTests(unittest.TestCase):
    def test_parse_advert_and_filter_vienna(self):
        payload = {
            "advertSummaryList": [
                {
                    "id": "13269121",
                    "description": "React Developer (m/w/d)",
                    "attributes": [
                        {"name": "ORGNAME", "values": ["ACME GmbH"]},
                        {"name": "LOCATION", "values": ["Wien"]},
                        {"name": "EMPLOYMENT_TYPE", "values": ["Vollzeit"]},
                        {"name": "PUBLISHED", "values": ["1792021800040"]},
                    ],
                },
                {
                    "id": "999",
                    "description": "React Developer Graz",
                    "attributes": [
                        {"name": "LOCATION", "values": ["Graz"]},
                    ],
                },
            ]
        }
        jobs = willhaben_jobs(payload, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "ACME GmbH")
        self.assertEqual(job["locations"], ["Wien"])
        self.assertEqual(job["url"], "https://www.willhaben.at/jobs/job/13269121")
        self.assertEqual(job["posted"], "2026-10-15")


class RemotiveTests(unittest.TestCase):
    def test_filter_remote_regions(self):
        payload = {
            "jobs": [
                {
                    "id": 1,
                    "title": "React Developer",
                    "company_name": "ACME",
                    "candidate_required_location": "Europe",
                    "url": "https://remotive.com/jobs/1",
                    "description": "<p>React und TypeScript</p>",
                    "publication_date": "2026-10-01T10:00:00",
                },
                {
                    "id": 2,
                    "title": "React Developer USA",
                    "company_name": "ACME",
                    "candidate_required_location": "USA",
                    "url": "https://remotive.com/jobs/2",
                    "description": "<p>React</p>",
                },
            ]
        }
        jobs = remotive_jobs(payload, term="react")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["locations"], ["Wien (Remote)"])
        self.assertTrue(jobs[0]["home_office"])
        self.assertIn("React", jobs[0]["description"])


class RelocateTests(unittest.TestCase):
    def test_only_austria_cards(self):
        page = """
        <div class="job__title">
          <a href="/austria/vienna/acme/react-developer-123"><b>React Developer</b></a>
        </div>
        <div class="job__title">
          <a href="/spain/madrid/acme/react-developer-456"><b>React Developer</b></a>
        </div>
        """
        jobs = relocate_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "Acme")
        self.assertEqual(job["locations"], ["Wien"])
        self.assertEqual(job["url"], "https://relocate.me/austria/vienna/acme/react-developer-123")


class StepStoneTests(unittest.TestCase):
    def test_normalize_card_and_vienna(self):
        cards = [
            {
                "title": "React Developer (m/w/d)",
                "url": "https://www.stepstone.at/stellenangebote--React-Developer-Wien-ACME--123-inline.html",
                "company": "ACME",
                "location": "Vienna",
                "text": "React Developer ACME Vienna",
            }
        ]
        jobs = stepstone_cards(cards, term="react")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "123")
        self.assertEqual(jobs[0]["locations"], ["Wien"])
        self.assertEqual(jobs[0]["source"], "stepstone.at")


class IndeedTests(unittest.TestCase):
    def test_normalize_card(self):
        cards = [
            {
                "jk": "abc123",
                "title": "React Native Developer",
                "company": "ACME",
                "location": "Wien, W",
                "text": "React Native Developer ACME Wien",
            }
        ]
        jobs = indeed_cards(cards, term="react native")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["url"], "https://at.indeed.com/viewjob?jk=abc123")
        self.assertEqual(jobs[0]["locations"], ["Wien, W"])
        self.assertEqual(jobs[0]["matched_terms"], ["react native"])


class AmsTests(unittest.TestCase):
    def test_normalize_card(self):
        cards = [
            {
                "title": "React Developer (w/m/d)",
                "url": "https://jobs.ams.at/public/emps/jobs/c1eda7d9-abf3-3f20-bdfe-215bcb01de09",
                "text": (
                    "React Developer (w/m/d)\n"
                    "bei FB Consulting & Trade GmbH\n"
                    "Unternehmen:\n"
                    "FB Consulting & Trade GmbH\n"
                    "Arbeitsort:\n"
                    "1070, Wien,Neubau\n"
                ),
            }
        ]
        jobs = ams_cards(cards, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "FB Consulting & Trade GmbH")
        self.assertIn("Wien", job["locations"])
        self.assertEqual(job["id"], "c1eda7d9-abf3-3f20-bdfe-215bcb01de09")


class DisabledSourceTests(unittest.TestCase):
    def test_brutkasten_parses_old_cards(self):
        page = (
            '<a href="https://brutkasten.com/jobs/job/full-stack-developer-123">'
            "Full Stack Developer</a>"
        )
        jobs = brutkasten_cards(page)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Full Stack Developer")

    def test_workinaustria_ignores_navigation(self):
        page = (
            '<a href="https://www.workinaustria.com/fachkraefte/jobs">Jobs</a>'
            '<a href="https://jobs.example.com/job/react-123">React Developer</a>'
        )
        jobs = workinaustria_cards(page)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "React Developer")


class HimalayasTests(unittest.TestCase):
    def test_parse_filters_react_and_remote_region(self):
        payload = {
            "jobs": [
                {
                    "title": "React Developer",
                    "companyName": "ACME",
                    "locationRestrictions": ["Europe"],
                    "description": "<p>React und TypeScript</p>",
                    "guid": "https://himalayas.app/companies/acme/jobs/react-developer",
                    "applicationLink": "https://himalayas.app/companies/acme/jobs/react-developer?utm_source=api",
                    "pubDate": 1793000000,
                    "employmentType": "Full Time",
                    "categories": ["React"],
                },
                {
                    "title": "React Developer USA",
                    "companyName": "USA Corp",
                    "locationRestrictions": ["USA"],
                    "description": "<p>React</p>",
                    "guid": "https://himalayas.app/companies/usa/jobs/react-developer",
                },
                {
                    "title": "Backend Engineer",
                    "companyName": "Java Corp",
                    "locationRestrictions": ["Europe"],
                    "description": "<p>Java und Spring</p>",
                    "guid": "https://himalayas.app/companies/java/jobs/backend",
                },
            ]
        }
        jobs = himalayas_jobs(payload)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["locations"], ["Wien (Remote)"])
        self.assertEqual(jobs[0]["company"], "ACME")
        self.assertTrue(jobs[0]["url"].endswith("/react-developer"))


class JobicyTests(unittest.TestCase):
    def test_parse_filters_react_and_geo(self):
        payload = {
            "jobs": [
                {
                    "id": 1,
                    "url": "https://jobicy.com/jobs/1",
                    "jobTitle": "React Developer",
                    "companyName": "ACME",
                    "jobGeo": "Europe",
                    "jobType": ["Full-Time"],
                    "jobDescription": "<p>React</p>",
                    "pubDate": "2026-10-01 10:00:00",
                },
                {
                    "id": 2,
                    "url": "https://jobicy.com/jobs/2",
                    "jobTitle": "React Developer USA",
                    "companyName": "USA Corp",
                    "jobGeo": "USA",
                    "jobDescription": "<p>React</p>",
                },
                {
                    "id": 3,
                    "url": "https://jobicy.com/jobs/3",
                    "jobTitle": "Backend Developer",
                    "companyName": "Java Corp",
                    "jobGeo": "Europe",
                    "jobDescription": "<p>Java</p>",
                },
            ]
        }
        jobs = jobicy_jobs(payload)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["employment_type"], "Full-Time")
        self.assertEqual(jobs[0]["locations"], ["Wien (Remote)"])


class RemoteOkTests(unittest.TestCase):
    def test_parse_skips_metadata_and_filters_react(self):
        payload = [
            {"last_updated": 1793000000, "legal": "terms"},
            {
                "id": "1",
                "slug": "acme-react-developer",
                "position": "React Developer",
                "company": "ACME",
                "description": "<p>React</p>",
                "url": "https://remoteok.com/remote-jobs/acme-react-developer",
                "date": "2026-10-01T10:00:00+00:00",
                "tags": ["react", "full time"],
            },
            {
                "id": "2",
                "slug": "acme-java-developer",
                "position": "Java Developer",
                "company": "ACME",
                "description": "<p>Java</p>",
                "url": "https://remoteok.com/remote-jobs/acme-java-developer",
                "tags": ["java"],
            },
        ]
        jobs = remoteok_jobs(payload)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "React Developer")
        self.assertEqual(jobs[0]["employment_type"], "Full Time")


class WeWorkRemotelyTests(unittest.TestCase):
    def test_parse_rss_and_region(self):
        xml = """
        <rss><channel>
          <item>
            <title>Acme: React Developer</title>
            <region>Anywhere in the World</region>
            <category>Full-Stack Programming</category>
            <description>&lt;p&gt;React und TypeScript&lt;/p&gt;</description>
            <pubDate>Mon, 05 Oct 2026 07:31:05 +0000</pubDate>
            <link>https://weworkremotely.com/remote-jobs/acme-react-developer</link>
          </item>
          <item>
            <title>USA Corp: React Developer</title>
            <region>USA Only</region>
            <description>&lt;p&gt;React&lt;/p&gt;</description>
            <pubDate>Mon, 05 Oct 2026 07:31:05 +0000</pubDate>
            <link>https://weworkremotely.com/remote-jobs/usa-react-developer</link>
          </item>
          <item>
            <title>Acme: Java Developer</title>
            <region>Europe</region>
            <description>&lt;p&gt;Java&lt;/p&gt;</description>
            <link>https://weworkremotely.com/remote-jobs/acme-java-developer</link>
          </item>
        </channel></rss>
        """
        jobs = weworkremotely_feed(xml)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertEqual(jobs[0]["title"], "React Developer")
        self.assertEqual(jobs[0]["posted"], "2026-10-05")
        self.assertEqual(jobs[0]["locations"], ["Wien (Remote)"])


class ArbeitnowTests(unittest.TestCase):
    def test_parse_keeps_vienna_and_remote(self):
        payload = {
            "data": [
                {
                    "slug": "react-vienna",
                    "company_name": "ACME",
                    "title": "React Developer",
                    "description": "<p>React</p>",
                    "remote": False,
                    "url": "https://www.arbeitnow.com/view/react-vienna",
                    "tags": ["react"],
                    "job_types": ["full-time"],
                    "location": "Vienna",
                    "created_at": 1793000000,
                },
                {
                    "slug": "react-remote",
                    "company_name": "Remote Corp",
                    "title": "React Developer",
                    "description": "<p>React</p>",
                    "remote": True,
                    "url": "https://www.arbeitnow.com/view/react-remote",
                    "tags": ["react"],
                    "job_types": ["full-time"],
                    "location": "Berlin",
                    "created_at": 1793000000,
                },
                {
                    "slug": "react-graz",
                    "company_name": "Graz Corp",
                    "title": "React Developer",
                    "description": "<p>React</p>",
                    "remote": False,
                    "url": "https://www.arbeitnow.com/view/react-graz",
                    "tags": ["react"],
                    "job_types": ["full-time"],
                    "location": "Graz",
                    "created_at": 1793000000,
                },
                {
                    "slug": "java-vienna",
                    "company_name": "Java Corp",
                    "title": "Backend Developer",
                    "description": "<p>Java</p>",
                    "remote": False,
                    "url": "https://www.arbeitnow.com/view/java-vienna",
                    "tags": ["java"],
                    "job_types": ["full-time"],
                    "location": "Vienna",
                    "created_at": 1793000000,
                },
            ]
        }
        jobs = arbeitnow_jobs(payload)
        self.assertEqual(len(jobs), 2)
        locations = {tuple(job["locations"]) for job in jobs}
        self.assertIn(("Vienna",), locations)
        self.assertIn(("Wien (Remote)",), locations)


class AiAustriaTests(unittest.TestCase):
    def test_parse_cards_filters_vienna(self):
        page = """
        <div class="notion-collection-list__item ">
          <a id="block-1" href="https://example.com/react-developer"
             class="notion-link notion-collection-list__item-anchor"
             data-server-link="true"></a>
          <div class="notion-property notion-property__title notion-semantic-string">
            React Developer
          </div>
          <div class="notion-collection-list__item-content">
            <span class="notion-pill notion-semantic-string">Vienna</span>
          </div>
        </div>
        <div class="notion-collection-list__item ">
          <a id="block-2" href="https://example.com/backend-developer"
             class="notion-link notion-collection-list__item-anchor"
             data-server-link="true"></a>
          <div class="notion-property notion-property__title notion-semantic-string">
            Backend Developer
          </div>
          <div class="notion-collection-list__item-content">
            <span class="notion-pill notion-semantic-string">Linz</span>
          </div>
        </div>
        """
        jobs = aiaustria_cards(page)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "React Developer")
        self.assertEqual(jobs[0]["locations"], ["Wien"])
        self.assertEqual(jobs[0]["url"], "https://example.com/react-developer")


class DerStandardTests(unittest.TestCase):
    def test_parse_flight_objects(self):
        vienna = {
            "__typename": "JobListingResponse",
            "id": "abc",
            "title": "React Developer",
            "hiringOrganization": {"name": "ACME"},
            "jobLocationsRaw": ["Wien", "Home-Office"],
            "displayDate": "2026-10-19T16:18:02.890Z",
            "tags": ["React", "Frontend"],
            "employmentTypes": ["FULL_TIME"],
            "benefits": ["home_office"],
            "jobSummary": None,
        }
        graz = {
            "__typename": "JobListingResponse",
            "id": "def",
            "title": "React Developer",
            "hiringOrganization": {"name": "Graz Corp"},
            "jobLocationsRaw": ["Graz"],
            "displayDate": "2026-10-19T16:18:02.890Z",
            "tags": ["React"],
            "employmentTypes": ["FULL_TIME"],
        }
        flight = (
            '{"JobListingResponse:abc":'
            + json.dumps(vienna)
            + ',"JobListingResponse:def":'
            + json.dumps(graz)
            + "}"
        )
        jobs = derstandard_flight(flight, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "ACME")
        self.assertEqual(job["url"], "https://jobs.derstandard.at/detail/abc")
        self.assertEqual(job["posted"], "2026-10-19")
        self.assertEqual(job["employment_type"], "Vollzeit")
        self.assertTrue(job["home_office"])
        self.assertEqual(job["matched_terms"], ["react"])


class LinkedInTests(unittest.TestCase):
    def test_parse_cards_filters_vienna(self):
        page = """
        <li>
          <div data-entity-urn="urn:li:jobPosting:123"
               class="base-card base-search-card job-search-card">
            <h3 class="base-search-card__title">React Developer</h3>
            <h4 class="base-search-card__subtitle">
              <a href="https://at.linkedin.com/company/acme">ACME</a>
            </h4>
            <span class="job-search-card__location">Vienna, Vienna, Austria</span>
            <time class="job-search-card__listdate" datetime="2026-10-01"></time>
          </div>
        </li>
        <li>
          <div data-entity-urn="urn:li:jobPosting:456"
               class="base-card base-search-card job-search-card">
            <h3 class="base-search-card__title">React Developer</h3>
            <h4 class="base-search-card__subtitle">Berlin Corp</h4>
            <span class="job-search-card__location">Berlin, Germany</span>
          </div>
        </li>
        """
        jobs = linkedin_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "ACME")
        self.assertEqual(
            jobs[0]["url"], "https://www.linkedin.com/jobs/view/123"
        )
        self.assertEqual(jobs[0]["posted"], "2026-10-01")


class XingTests(unittest.TestCase):
    def test_parse_cards_filters_vienna(self):
        page = """
        <article data-testid="job-search-result" aria-label="React Developer">
          <a href="/jobs/wien-react-developer-123" target="_blank"></a>
          <h2 data-testid="job-teaser-list-title">React Developer</h2>
          <p class="body-copy-styles__BodyCopy-sc-1 job-teaser-list-item-styles__Company-sc-2">
            ACME
          </p>
          <div class="multi-location-display-styles__Container-sc-3">
            <p class="body-copy-styles__BodyCopy-sc-4">Wien<b> + 0 weitere</b></p>
          </div>
          <p class="job-teaser-list-item-styles__PublicationDate-sc-5">vor 2 Tagen</p>
        </article>
        <article data-testid="job-search-result" aria-label="React Developer Graz">
          <a href="/jobs/graz-react-developer-456" target="_blank"></a>
          <h2 data-testid="job-teaser-list-title">React Developer Graz</h2>
          <p class="job-teaser-list-item-styles__Company-sc-2">Graz Corp</p>
          <div class="multi-location-display-styles__Container-sc-3">
            <p class="body-copy-styles__BodyCopy-sc-4">Graz</p>
          </div>
        </article>
        """
        jobs = xing_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["title"], "React Developer")
        self.assertEqual(job["company"], "ACME")
        self.assertEqual(job["locations"], ["Wien"])
        self.assertEqual(job["url"], "https://www.xing.com/jobs/wien-react-developer-123")
        self.assertEqual(job["posted"], "vor 2 Tagen")


class WellfoundTests(unittest.TestCase):
    def test_parse_page_filters_vienna_and_remote(self):
        state = {
            "Startup:1": {"__typename": "Startup", "id": "1", "name": "ACME"},
            "JobListing:1": {
                "__typename": "JobListing",
                "id": "1",
                "slug": "react-developer",
                "title": "React Developer",
                "locationNames": ["Vienna"],
                "acceptedRemoteLocationNames": [],
                "remote": False,
                "liveStartAt": 1793000000,
                "startup": {"__ref": "Startup:1"},
                "primaryRole": {"slug": "developer"},
            },
            "JobListing:2": {
                "__typename": "JobListing",
                "id": "2",
                "slug": "react-developer-remote",
                "title": "React Developer Remote",
                "locationNames": ["Berlin"],
                "acceptedRemoteLocationNames": ["Europe"],
                "remote": True,
                "liveStartAt": 1793000000,
                "startup": {"__ref": "Startup:1"},
                "primaryRole": {"slug": "developer"},
            },
            "JobListing:3": {
                "__typename": "JobListing",
                "id": "3",
                "slug": "react-developer-usa",
                "title": "React Developer USA",
                "locationNames": ["New York"],
                "acceptedRemoteLocationNames": ["United States"],
                "remote": True,
                "liveStartAt": 1793000000,
                "startup": {"__ref": "Startup:1"},
                "primaryRole": {"slug": "developer"},
            },
        }
        page = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(
                {"props": {"pageProps": {"apolloState": {"data": state}}}}
            )
            + "</script>"
        )
        jobs = wellfound_page(page)
        self.assertEqual(len(jobs), 2)
        by_id = {job["id"]: job for job in jobs}
        self.assertEqual(by_id["1"]["locations"], ["Vienna"])
        self.assertEqual(by_id["1"]["company"], "ACME")
        self.assertEqual(
            by_id["1"]["url"],
            "https://wellfound.com/jobs/1-react-developer",
        )
        self.assertEqual(by_id["2"]["locations"], ["Wien (Remote)"])
        self.assertTrue(by_id["2"]["home_office"])


class WeAreDevelopersTests(unittest.TestCase):
    def test_parse_markdown_filters_vienna(self):
        markdown = """
        # Developer Jobs

        Region: Austria

        ## React Developer

        - **Company:** ACME
        - **Location:** Wien, Austria
        - **Contract:** Permanent contract
        - **Published:** October 22, 2026
        - [View job](https://www.wearedevelopers.com/jobs/ext/1-react-developer)
        - [Apply](https://example.com/apply)

        ## React Developer Graz

        - **Company:** Graz Corp
        - **Location:** Graz, Austria
        - **Contract:** Permanent contract
        - **Published:** October 22, 2026
        - [View job](https://www.wearedevelopers.com/jobs/ext/2-react-developer)
        """
        jobs = wearedevelopers_markdown(markdown, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "ACME")
        self.assertEqual(job["posted"], "2026-10-22")
        self.assertEqual(job["locations"], ["Wien, Austria"])
        self.assertEqual(
            job["url"],
            "https://www.wearedevelopers.com/jobs/ext/1-react-developer",
        )


class TheHubTests(unittest.TestCase):
    def test_parse_cards_filters_vienna(self):
        page = """
        <div class="card card-job-find-list" data-v-1>
          <div class="card__content">
            <div class="card-job-find-list__title">
              <span class="card-job-find-list__position">React Developer</span>
              <div class="bullet-inline-list text-gray-600 fw500">
                <span>ACME</span> <span>Vienna</span> <span>Full-time</span>
              </div>
            </div>
            <a href="/jobs/abc123" class="card-job-find-list__link"></a>
          </div>
        </div>
        <div class="card card-job-find-list" data-v-2>
          <div class="card__content">
            <div class="card-job-find-list__title">
              <span class="card-job-find-list__position">React Developer London</span>
              <div class="bullet-inline-list text-gray-600 fw500">
                <span>London Corp</span> <span>London</span> <span>Full-time</span>
              </div>
            </div>
            <a href="/jobs/def456" class="card-job-find-list__link"></a>
          </div>
        </div>
        """
        jobs = thehub_cards(page, term="react")
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "ACME")
        self.assertEqual(job["locations"], ["Vienna"])
        self.assertEqual(job["url"], "https://thehub.io/jobs/abc123")


class EuCareersTests(unittest.TestCase):
    def test_parse_page_filters_vienna(self):
        page = """
        <div class="eujmp-vacancy-result">
          <ul class="eujmp-vacancy-result__top-meta">
            <li>European Commission</li>
            <li><time datetime="2026-10-27T10:59:00+00:00">27 October 2026</time></li>
          </ul>
          <a href="/jobs/it-officer-react_en"
             class="ecl-link ecl-link--standalone eujmp-vacancy-result__title">
            IT Officer - React
          </a>
          <ul class="eujmp-vacancy-result__bottom-meta">
            <li>Contract staff</li><li>FG IV</li>
            <li><span class="location-icon"></span>Vienna, Austria</li>
          </ul>
        </div>
        <div class="eujmp-vacancy-result">
          <ul class="eujmp-vacancy-result__top-meta">
            <li>European Commission</li>
            <li><time datetime="2026-10-27T10:59:00+00:00">27 October 2026</time></li>
          </ul>
          <a href="/jobs/it-officer-brussels_en"
             class="ecl-link ecl-link--standalone eujmp-vacancy-result__title">
            IT Officer - Brussels
          </a>
          <ul class="eujmp-vacancy-result__bottom-meta">
            <li>Contract staff</li><li>FG IV</li>
            <li><span class="location-icon"></span>Brussels, Belgium</li>
          </ul>
        </div>
        """
        jobs = eucareers_page(page)
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["company"], "European Commission")
        self.assertEqual(job["posted"], "2026-10-27")
        self.assertEqual(job["locations"], ["Vienna, Austria"])
        self.assertEqual(job["employment_type"], "Contract staff / FG IV")
        self.assertEqual(
            job["url"], "https://eu-careers.europa.eu/jobs/it-officer-react_en"
        )


if __name__ == "__main__":
    unittest.main()
