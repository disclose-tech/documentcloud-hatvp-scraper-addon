import csv
import datetime
import io
from email.utils import parsedate_to_datetime
from typing import ClassVar

import scrapy
from scrapy.exceptions import CloseSpider

from ..items import DocumentItem


def load_row(raw):
    """Clean a liste.csv row and return a dict."""
    return {
        key: (value.strip() or None) if value is not None else None
        for key, value in raw.items()
    }


class HATVPSpider(scrapy.Spider):
    name = "HATVP_spider"

    allowed_domains: ClassVar[list] = ["www.hatvp.fr"]

    start_urls: ClassVar[list] = ["https://www.hatvp.fr/livraison/opendata/liste.csv"]

    SITE_URL = "https://www.hatvp.fr"

    # Documents (pdf & xml) are available at this address + nom_fichier (source: notice des données)
    FILES_BASE_URL = "https://www.hatvp.fr/livraison/dossiers/"

    DECLARANT_PAGES_PATH = "/pages_nominatives/"

    # Event data file for local runs
    EVENT_DATA_FILE = "event_data.json"

    upload_limit_attained = False

    # Passed by main.py. Defaults (e.g. with `scrapy crawl`): no upload limit, all years,
    # dry run (no DocumentCloud client)
    upload_limit = 0
    target_years = None
    dry_run = True
    run_id = None
    event_id = None
    upload_event_data = False

    event_data: dict  # set by UploadPipeline.open_spider

    @staticmethod
    def years_label(target_years):
        """Label of the target years: "all years", "2024" or "2020-2026"."""
        if not target_years:
            return "all years"
        if len(target_years) == 1:
            return str(target_years[0])
        return f"{target_years[0]}-{target_years[-1]}"

    @classmethod
    def declarant_id(cls, url_dossier):
        """url_dossier is the unique identifier of the declarant (source: notice des données)"""
        return (
            url_dossier.removeprefix(cls.DECLARANT_PAGES_PATH) if url_dossier else None
        )

    # Check that each file is online (HEAD request). Disable for quick local tests with
    # `scrapy crawl HATVP_spider -a check_files=false`: no 404 filtering, no Last-Modified,
    # and uploaded files are not checked again
    check_files = True

    def check_upload_limit(self):
        """Closes the spider if the upload limit is attained."""
        if self.upload_limit_attained:
            raise CloseSpider("Closed due to max documents limit.")

    def in_target_years(self, day):
        """Checks if a YYYY-MM-DD date string is within the target years."""
        return self.target_years is None or int(day[:4]) in self.target_years

    def file_entry(self, row):
        """Returns the event data entry of an uploaded file, or None for a new file."""
        declarant_files = self.event_data.get(self.declarant_id(row["url_dossier"]), {})
        return declarant_files.get(row["nom_fichier"])

    @staticmethod
    def mark_checked(entry):
        """Records that an uploaded file was checked today (re-checks go oldest first)."""
        entry["checked"] = (
            datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        )

    def parse(self, response):
        """Explore liste.csv for entries"""

        self.check_upload_limit()

        # Load liste.csv, with the right type for each column (source: notice des données)
        # The file is served as application/octet-stream, so response.text is not available
        text = response.body.decode("utf-8-sig")
        reader = csv.DictReader(
            io.StringIO(text, newline=""), delimiter=";", quotechar='"'
        )

        # Values passed with `scrapy crawl -a` are strings
        check_files = str(self.check_files).lower() not in ("false", "0", "no")

        new, skipped, other_years, missing_date = 0, 0, 0, 0

        # Uploaded files to check again, as (entry, row)
        rechecks = []

        # Iterate over rows
        for raw in reader:
            self.check_upload_limit()

            row = load_row(raw)

            # Remove rows without a file: empty nom_fichier (publication pending)
            # or "dispense" (declarant exempted)
            if not row["nom_fichier"] or not row["nom_fichier"].endswith(".pdf"):
                skipped += 1
                continue

            # Remove rows published outside the target years
            if row["date_publication"] and not self.in_target_years(
                row["date_publication"]
            ):
                other_years += 1
                continue

            # Files uploaded by a previous run are checked after the new ones
            entry = self.file_entry(row)
            if entry is not None:
                rechecks.append((entry, row))
                continue

            new += 1
            if not row["date_publication"]:
                missing_date += 1

            item = self.document_item(row)

            if not check_files:
                yield item
                continue

            yield self.head_request(item, entry=None, priority=1)

        self.logger.info(
            f"liste.csv: {new} new documents ({missing_date} without "
            f"date_publication), {len(rechecks)} uploaded documents to check again, "
            f"{other_years} outside target years, {skipped} rows without file skipped"
        )

        if not check_files:
            return

        # Least recently checked first, so that files at the end of liste.csv are
        # not always left out when a run is stopped by the time limit. The scheduler
        # queue is FIFO (SCHEDULER_MEMORY_QUEUE), so requests go in this order
        rechecks.sort(key=lambda recheck: recheck[0].get("checked") or "")
        for entry, row in rechecks:
            yield self.head_request(self.document_item(row), entry, priority=0)

    def document_item(self, row):
        return DocumentItem(
            source_file_url=self.FILES_BASE_URL + row["nom_fichier"],
            raw_metadata=row,
        )

    def head_request(self, item, entry, priority):
        """HEAD request for a file, to check that it is online (some listed files are
        not published, e.g. parliamentarians' asset declarations, only viewable in
        prefecture) and get its Last-Modified date."""
        return scrapy.Request(
            item["source_file_url"],
            method="HEAD",
            callback=self.parse_document_headers,
            cb_kwargs={"item": item, "entry": entry},
            meta={"handle_httpstatus_list": [404]},
            priority=priority,
        )

    def parse_document_headers(self, response, item, entry):
        """Yields new files and new versions of uploaded files (new Last-Modified).
        entry is the file's event data entry, None for a new file."""

        self.check_upload_limit()

        # New files are not recorded anywhere, so that they are checked again on the
        # next run. Uploaded files that went offline are left to the metadata updater
        if response.status == 404:
            self.crawler.stats.inc_value("hatvp/file_not_found")
            self.logger.debug(f"File not found: {item['source_file_url']}")
            if entry is not None:
                self.mark_checked(entry)
            return

        raw = item["raw_metadata"]
        last_modified = response.headers.get("Last-Modified")

        if not last_modified:
            self.logger.warning(
                f"No Last-Modified header for {item['source_file_url']}"
            )
            if entry is not None:
                # No way to tell a new version: checked again on the next run
                return
        else:
            last_modified = parsedate_to_datetime(last_modified.decode("utf-8"))
            raw["last_modified"] = last_modified.astimezone(
                datetime.timezone.utc
            ).isoformat()

            # No publication date: keep the rows modified within the target years
            if not raw["date_publication"] and not self.in_target_years(
                raw["last_modified"]
            ):
                return

        raw["content_length"] = response.headers.get("Content-Length", b"").decode()

        if entry is not None:
            if entry["versions"] and entry["versions"][-1][0] == raw["last_modified"]:
                self.crawler.stats.inc_value("hatvp/file_unchanged")
                self.mark_checked(entry)
                return

            # Recorded as checked once uploaded (UploadPipeline)
            self.crawler.stats.inc_value("hatvp/new_version")
            self.logger.info(f"New version of {item['source_file_url']}")

        yield item

    def closed(self, reason):
        stats = self.crawler.stats
        not_found = stats.get_value("hatvp/file_not_found", 0)
        self.logger.info(f"{not_found} listed files were not found online (404)")
        self.logger.info(
            f"Uploaded files checked again: "
            f"{stats.get_value('hatvp/file_unchanged', 0)} unchanged, "
            f"{stats.get_value('hatvp/new_version', 0)} new versions"
        )
