# # Item Pipelines

import datetime
import json
import logging
import os

from scrapy.exceptions import DropItem

from .items import DC_METADATA_FIELDS
from .log import SilentDropItem
from .mappings import DOCUMENT_TYPES, MANDATE_TYPES
from .spiders.hatvp import HATVPSpider


class SpiderPipeline:
    """Base class for pipelines that need access to the spider instance.

    Provides from_crawler() to store spider as self.spider.
    Inherit from this class instead of defining from_crawler() in each pipeline.
    """

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.spider = crawler.spider
        return pipeline


class UploadLimitPipeline(SpiderPipeline):
    """Sends the signal to close the spider once the upload limit is attained."""

    def open_spider(self):
        self.number_of_docs = 0

    def process_item(self, item):
        self.number_of_docs += 1

        if (
            self.spider.upload_limit == 0
            or self.number_of_docs <= self.spider.upload_limit
        ):
            return item
        else:
            self.spider.upload_limit_attained = True
            raise SilentDropItem("Upload limit exceeded.")


class CleanMetadataPipeline(SpiderPipeline):
    """Sets the clean metadata fields from raw_metadata"""

    def open_spider(self):
        # {(raw field, code): {"count": number of documents, "example": file_url}}
        self.unknown_codes = {}

    def record_unknown_code(self, field, code, item):
        """Records an unknown code, to be reported at the end of the run."""

        key = (field, code)
        if key not in self.unknown_codes:
            self.unknown_codes[key] = {"count": 0, "example": item["source_file_url"]}
        self.unknown_codes[key]["count"] += 1

    def process_item(self, item):
        raw = item["raw_metadata"]

        # Drop documents with an unknown code: they will be processed on the
        # next run, once the mappings are updated
        unknown = [
            (field, raw[field])
            for field, mapping in [
                ("type_mandat", MANDATE_TYPES),
                ("type_document", DOCUMENT_TYPES),
            ]
            if raw[field] is not None and raw[field] not in mapping
        ]
        if unknown:
            for field, code in unknown:
                self.record_unknown_code(field, code, item)
            raise DropItem(f"Unknown code(s): {unknown}")

        url_dossier = raw["url_dossier"]

        # Declarant
        item["declarant_id"] = HATVPSpider.declarant_id(url_dossier)
        item["source_page_url"] = (
            HATVPSpider.SITE_URL + url_dossier if url_dossier else None
        )
        item["declarant_civility"] = raw["civilite"]
        item["declarant_first_name"] = raw["prenom"]
        item["declarant_last_name"] = raw["nom"]
        item["declarant_institution_member_id"] = raw["id_origine"]

        # Mandate
        item["mandate_type"] = MANDATE_TYPES.get(raw["type_mandat"])
        item["mandate_title"] = raw["qualite"]
        item["mandate_department_code"] = raw["departement"]

        # Document
        item["document_type"] = DOCUMENT_TYPES.get(raw["type_document"])
        item["filing_date"] = raw["date_depot"]
        item["filename"] = raw["nom_fichier"]
        item["open_data_url"] = (
            HATVPSpider.FILES_BASE_URL + raw["open_data"] if raw["open_data"] else None
        )

        # Both dates in the front-end's datetime format
        item["official_publication_date"] = (
            f"{raw['date_publication']} 00:00:00 UTC"
            if raw["date_publication"]
            else None
        )
        item["file_last_modified"] = (
            datetime.datetime.fromisoformat(raw["last_modified"]).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            if raw.get("last_modified")
            else None
        )
        item["file_content_length"] = raw.get("content_length") or None

        filed = (
            "déposée le "
            + datetime.date.fromisoformat(raw["date_depot"]).strftime("%d/%m/%Y")
            if raw["date_depot"]
            else None
        )
        item["title"] = " - ".join(filter(None, [item["document_type"], filed]))
        item["description"] = " ".join(
            filter(None, [raw["civilite"], raw["prenom"], raw["nom"]])
        )

        return item

    def close_spider(self):
        """Send an email prompting to update the mappings if unknown codes were found."""

        if not self.unknown_codes:
            return

        run_name = getattr(self.spider, "run_name", "local run")
        subject = (
            f"HATVP Scraper - Unknown codes found, scraper update needed [{run_name}]"
        )

        lines = [
            f"- {field}: {code!r} ({info['count']} documents, e.g. {info['example']})"
            for (field, code), info in sorted(self.unknown_codes.items())
        ]
        content = "\n".join(
            [
                "Codes without an expansion were found in liste.csv:",
                "",
                *lines,
                "",
                (
                    "The affected documents were not uploaded. Add the missing "
                    "expansions to scraper/mappings.py: they will be uploaded on the "
                    "next run."
                ),
            ]
        )

        # send_mail is passed by main.py (add-on runs only)
        send_mail = getattr(self.spider, "send_mail", None)
        if send_mail and not getattr(self.spider, "dry_run", False):
            send_mail(subject, content)
        else:
            self.spider.logger.warning(f"{subject}\n\n{content}")


class UploadPipeline(SpiderPipeline):
    """Uploads documents to DocumentCloud & stores event data."""

    # Number of uploads between two saves of the event data on DocumentCloud
    EVENT_DATA_SAVE_INTERVAL = 25

    def count_documents(self):
        """Counts the number of uploaded documents (one per file version) in event_data"""
        return sum(
            len(entry["versions"])
            for files in self.spider.event_data.values()
            for entry in files.values()
        )

    @staticmethod
    def event_data_key(item):
        """Unique id of an uploaded document: one per file version"""
        key = f"{item['declarant_id']}/{item['filename']}"
        last_modified = item["raw_metadata"].get("last_modified")
        if last_modified:
            key += "/" + datetime.datetime.fromisoformat(last_modified).strftime(
                "%Y%m%dT%H%M%SZ"
            )
        return key

    def open_spider(self):
        spider = self.spider

        logging.getLogger("documentcloud").setLevel(logging.WARNING)
        logging.getLogger("squarelet").setLevel(logging.WARNING)

        self.uploaded = 0
        self.upload_errors = 0
        self.unsaved_uploads = 0

        # Loaded before the spider parses liste.csv, which skips uploaded documents.
        # No error handling: running without event data would upload duplicates.
        # Also loaded in dry runs (never stored), to list what a real run would upload
        if spider.event_id:
            spider.logger.info("Loading event data from DocumentCloud...")
            spider.event_data = spider.load_event_data() or {}
        elif os.path.exists(spider.EVENT_DATA_FILE):
            spider.logger.info(f"Loading event data from {spider.EVENT_DATA_FILE}...")
            with open(spider.EVENT_DATA_FILE) as file:
                spider.event_data = json.load(file)
        else:
            spider.event_data = {}

        spider.logger.info(
            f"Loaded event data ({len(spider.event_data)} declarants, "
            f"{self.count_documents()} documents)"
        )

    def store_event_data(self):
        """Stores the event data on DocumentCloud (scheduled events only)."""

        spider = self.spider

        if not spider.event_id:
            return

        try:
            spider.store_event_data(spider.event_data)
        except Exception as e:
            # Kept in memory: stored with the next batch or when the spider closes
            spider.logger.warning(f"Error storing event data: {e!r}")
        else:
            self.unsaved_uploads = 0
            spider.logger.info(
                f"Stored event data ({len(spider.event_data)} declarants, "
                f"{self.count_documents()} documents, "
                f"{len(json.dumps(spider.event_data)) / 1000:.1f} KB)"
            )

    def process_item(self, item):
        spider = self.spider

        # DocumentCloud data values must be strings
        data = {field: item[field] for field in DC_METADATA_FIELDS if item.get(field)}
        data["event_data_key"] = self.event_data_key(item)
        data["source_scraper"] = "HATVP Scraper"

        if spider.dry_run:
            return item

        try:
            spider.client.documents.upload(
                item["source_file_url"],
                project=spider.target_project,
                title=item["title"],
                description=item["description"],
                source="hatvp.fr",
                language="fra",
                access=spider.access_level,
                data=data,
            )
        except Exception as e:
            # Not added to event data, so that the upload is retried on the next run
            self.upload_errors += 1
            spider.crawler.stats.inc_value("hatvp/upload_error")
            spider.logger.error(f"Upload error for {item['source_file_url']}: {e!r}")
            raise SilentDropItem("Upload error.")

        self.uploaded += 1
        spider.logger.debug(f"Uploaded {item['source_file_url']} to DocumentCloud")

        raw = item["raw_metadata"]
        entry = spider.event_data.setdefault(item["declarant_id"], {}).setdefault(
            item["filename"], {"checked": None, "versions": []}
        )
        entry["versions"].append([raw.get("last_modified"), raw.get("content_length")])
        spider.mark_checked(entry)

        # Stored by batches of uploads, to keep the requests to DocumentCloud few.
        # A run killed by the GitHub Actions time limit or an error uploads at most
        # EVENT_DATA_SAVE_INTERVAL - 1 documents again on the next run
        self.unsaved_uploads += 1
        if self.unsaved_uploads >= self.EVENT_DATA_SAVE_INTERVAL:
            self.store_event_data()

        return item

    def close_spider(self):
        """Stores event data when the spider closes."""

        spider = self.spider

        if spider.dry_run:
            return

        spider.logger.info(
            f"Uploaded {self.uploaded} documents ({self.upload_errors} upload errors)"
        )

        # Always stored: the spider also updates the "checked" dates of the files
        # checked again (mark_checked), even when nothing is uploaded
        self.store_event_data()

        if spider.run_id:
            if spider.upload_event_data:
                # Upload the event_data to the DocumentCloud interface
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"event_data_HATVP_{timestamp}.json"

                with open(filename, "w+") as event_data_file:
                    json.dump(spider.event_data, event_data_file)
                    spider.upload_file(event_data_file)
                spider.logger.info("Uploaded event data to the DocumentCloud interface")
        else:
            with open(spider.EVENT_DATA_FILE, "w") as file:
                json.dump(spider.event_data, file)
            spider.logger.info(
                f"Saved {spider.EVENT_DATA_FILE} ({len(spider.event_data)} declarants, "
                f"{self.count_documents()} documents)"
            )


class MailPipeline(SpiderPipeline):
    """Sends a report after every run."""

    # Documents listed in the mail: the first run uploads thousands of documents
    MAX_LISTED_DOCUMENTS = 100

    def open_spider(self):
        self.items = []

    def process_item(self, item):
        # Uploaded documents (all documents in a dry run)
        self.items.append(item)
        return item

    def close_spider(self):
        spider = self.spider
        stats = spider.crawler.stats
        dry_run = getattr(spider, "dry_run", False)
        run_name = getattr(spider, "run_name", "local run")

        years = HATVPSpider.years_label(spider.target_years)

        upload_errors = stats.get_value("hatvp/upload_error", 0)
        subject = (
            f"HATVP Scraper {years} (New: {len(self.items)} | "
            f"Upload errors: {upload_errors}) [{run_name}]"
        )

        uploaded_label = "Documents (dry run, not uploaded)" if dry_run else "Uploaded"
        sections = [
            "\n".join(
                [
                    f"{uploaded_label}: {len(self.items)}",
                    "New versions of uploaded files: "
                    + str(stats.get_value("hatvp/new_version", 0)),
                    f"Upload errors (retried on the next run): {upload_errors}",
                    "Listed files not found online (404): "
                    + str(stats.get_value("hatvp/file_not_found", 0)),
                ]
            )
        ]

        if self.items:
            lines = [
                f"- {item['description']} – {item['title']} – {item['source_file_url']}"
                for item in self.items[: self.MAX_LISTED_DOCUMENTS]
            ]
            if len(self.items) > self.MAX_LISTED_DOCUMENTS:
                lines.append(
                    f"… and {len(self.items) - self.MAX_LISTED_DOCUMENTS} more"
                )
            sections.append("\n".join([f"{uploaded_label.upper()}", "", *lines]))

        content = "\n\n".join(sections)

        # send_mail is passed by main.py (add-on runs only)
        send_mail = getattr(spider, "send_mail", None)
        if send_mail and not dry_run:
            send_mail(subject, content)
        else:
            spider.logger.warning(f"{subject}\n\n{content}")
