"""Models for the scraped items."""

from scrapy.item import Field, Item


class DocumentItem(Item):
    source_file_url = Field()  # nom_fichier, as an absolute url

    # DocumentCloud fields
    title = Field()
    description = Field()  # folder label on the front-end: one folder per declarant

    # Declarant (same for all documents of a person)
    declarant_id = Field()  # url_dossier, without /pages_nominatives/
    source_page_url = Field()  # url_dossier, as an absolute url
    declarant_civility = Field()  # civilite
    declarant_first_name = Field()  # prenom
    declarant_last_name = Field()  # nom
    declarant_institution_member_id = Field()  # id_origine

    # Mandate the document was filed for
    mandate_type = Field()  # type_mandat, expanded
    mandate_title = Field()  # qualite
    mandate_department_code = Field()  # departement

    # Document
    document_type = Field()  # type_document, expanded
    # Dates in the front-end's format ("YYYY-MM-DD HH:MM:SS UTC")
    official_publication_date = Field()  # date_publication
    file_last_modified = Field()  # file's Last-Modified header: date of this version
    filing_date = Field()  # date_depot
    file_content_length = Field()  # file's Content-Length header, in bytes
    filename = Field()  # nom_fichier
    open_data_url = Field()  # open_data, as an absolute url

    # liste.csv row, as is
    raw_metadata = Field()


# Metadata fields to be stored in DocumentCloud
DC_METADATA_FIELDS = [
    "source_file_url",
    "declarant_id",
    "source_page_url",
    "declarant_civility",
    "declarant_first_name",
    "declarant_last_name",
    "declarant_institution_member_id",
    "mandate_type",
    "mandate_title",
    "mandate_department_code",
    "document_type",
    "official_publication_date",
    "file_last_modified",
    "filing_date",
    "file_content_length",
    "filename",
    "open_data_url",
]
