"""
Custom scraper add-on for DocumentCloud.
"""

import datetime
import os
import sys
import traceback

from documentcloud.addon import AddOn
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scraper import settings as scraper_settings
from scraper.spiders.hatvp import HATVPSpider

# First year with publications in liste.csv, used when from_year is not set
DEFAULT_FROM_YEAR = 2020


class DiscloseHATVPScraper(AddOn):
    """Scraper for HATVP documents (https://www.hatvp.fr)."""

    def check_permissions(self):
        """Check if the user is a verified journalist & can upload a document."""

        self.set_message("Checking permissions...")

        try:
            user = self.client.users.get("me")

            if not user.verified_journalist:
                self.set_message(
                    "You need to be verified to use this add-on. Please verify your "
                    "account here: https://airtable.com/shrZrgdmuOwW0ZLPM"
                )
                self.send_mail(
                    "You must verify your account to use Disclose's Scraper Add-On",
                    "You need to be verified to use the scraper add-on. Please verify your "
                    "account here: https://airtable.com/shrZrgdmuOwW0ZLPM",
                )

                sys.exit(1)
        except Exception:
            subject = "HATVP Scraper - Error connecting to DocumentCloud"
            content = f"Error:\n{traceback.format_exc()}"
            self.send_mail(subject, content)
            sys.exit(1)

    def get_project_id(self):
        """Returns the id of the target project."""

        project = self.data["project"]

        try:
            # if project is an integer, use it as a project ID
            project = int(project)
            return project
        except ValueError:
            # otherwise, get the project id from its title
            # or create it if it does not exist
            project, _created = self.client.projects.get_or_create_by_title(project)
            return project.id

    def main(self):
        """Add-on main functionality."""

        # User agent
        self.client.session.headers.update(
            {"User-Agent": "Disclose HATVP Scraper Add-On"}
        )

        # Add-on inputs

        self.run_name = self.data.get("run_name", "no name")

        # Checked by the add-on framework, against the enum of config.yaml
        self.access_level = self.data["access_level"]

        self.from_year = self.data.get(
            "from_year", DEFAULT_FROM_YEAR
        )  # first year of publications if not set

        self.to_year = self.data.get(
            "to_year", datetime.date.today().year
        )  # current year if not set

        if self.from_year > self.to_year:
            self.set_message(
                f"Year to scrape from ({self.from_year}) must not be after "
                f"year to scrape to ({self.to_year})."
            )
            sys.exit(1)

        self.target_years = range(self.from_year, self.to_year + 1)

        self.upload_limit = self.data.get("upload_limit", 0)
        self.time_limit = self.data.get(
            "time_limit", 345
        )  # Default to 5h45 as Github actions have a 6 hour limit

        self.dry_run = self.data.get("dry_run")

        self.upload_event_data = self.data.get("upload_event_data")

        if not self.dry_run:
            # Check if the user has upload permissions (verified account), before
            # get_project_id can create a project
            self.check_permissions()

            try:
                self.project = self.get_project_id()
            except Exception as e:
                raise Exception(f"Project error: {e}") from e
        else:
            self.project = ""

        # Load scraper settings and create process

        os.environ.setdefault("SCRAPY_SETTINGS_MODULE", scraper_settings.__name__)
        settings = get_project_settings()

        if self.time_limit:
            settings.set("CLOSESPIDER_TIMEOUT", self.time_limit * 60)

        process = CrawlerProcess(settings)

        # Launch scraper

        process.crawl(
            HATVPSpider,
            target_years=self.target_years,
            upload_limit=self.upload_limit,
            client=self.client,
            target_project=self.project,
            access_level=self.access_level,
            dry_run=self.dry_run,
            run_id=self.id,
            event_id=self.event_id,
            run_name=self.run_name,
            send_mail=self.send_mail,
            load_event_data=self.load_event_data,
            store_event_data=self.store_event_data,
            upload_file=self.upload_file,
            upload_event_data=self.upload_event_data,
        )

        # Run

        years = HATVPSpider.years_label(self.target_years)
        self.set_message(f"Scraping HATVP documents {years} [{self.run_name}]")
        process.start()
        self.set_message("Scraping complete!")


if __name__ == "__main__":
    DiscloseHATVPScraper().main()
