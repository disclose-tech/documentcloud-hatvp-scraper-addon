# Scrapy settings for scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from .items import DC_METADATA_FIELDS
from .log import PoliteLogFormatter

LOG_FORMATTER = PoliteLogFormatter

BOT_NAME = "HATVP Scraper"

SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Disclose DocumentCloud Add-On - contact tech@disclose.ngo"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
# CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 1
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Requests of equal priority in the order they were yielded (default: LIFO), so that
# the spider's re-checks go least recently checked first
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.FifoMemoryQueue"
# CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
# Set to false following advice from Scrapy's docs
# https://docs.scrapy.org/en/latest/topics/practices.html#avoiding-getting-banned
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    "scraper.middlewares.ScraperSpiderMiddleware": 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
# DOWNLOADER_MIDDLEWARES = {
#    "scraper.middlewares.ScraperDownloaderMiddleware": 543,
# }

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
# }

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "scraper.pipelines.CleanMetadataPipeline": 450,
    "scraper.pipelines.UploadLimitPipeline": 500,
    "scraper.pipelines.UploadPipeline": 800,
    "scraper.pipelines.MailPipeline": 900,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
AUTOTHROTTLE_TARGET_CONCURRENCY = 1
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = True

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 604800  # 7 days
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"


TELNETCONSOLE_ENABLED = False

RETRY_TIMES = 4

# Development settings
AUTOTHROTTLE_DEBUG = False
HTTPCACHE_ENABLED = False
HTTPCACHE_IGNORE_HTTP_CODES = [503]
HTTPCACHE_EXPIRATION_SECS = 86400 * 1  # 1 day
DEPTH_STATS_VERBOSE = False
LOG_LEVEL = "INFO"
FEEDS = {
    #     # "data.json": {"format": "json", "encoding": "utf8", "indent": 4, "overwrite": True},
    "data.csv": {
        "format": "csv",
        "encoding": "utf8",
        "overwrite": True,
        "fields": ["title", "description", *DC_METADATA_FIELDS],
    },
}
