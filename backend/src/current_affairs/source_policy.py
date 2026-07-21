from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceAdapter:
    name: str
    domain: str
    tier: str
    content_kind: str = "article"


SOURCE_ADAPTERS = (
    SourceAdapter("PWOnlyIAS", "pwonlyias.com", "primary"),
)

TIER_ORDER = {"primary": 4}

PWONLYIAS_HUBS = [
    "https://pwonlyias.com/current-affairs/",
    "https://pwonlyias.com/daily-current-affairs/",
    "https://pwonlyias.com/upsc-weekly-current-affairs/",
    "https://pwonlyias.com/stage/weekly-current-affairs-pdf",
    "https://pwonlyias.com/pwonlyias-manthan-current-affairs-monthly-magazine/",
    "https://pwonlyias.com/current-affairs-pdf/",
    "https://pwonlyias.com/downloads/",
    "https://pwonlyias.com/upsc-free-study-material/",
    "https://pwonlyias.com/daily-monthly-pdf/",
]

DISCOVERY_FEEDS = (
    {"source": "PWOnlyIAS", "url": "https://pwonlyias.com/feed/", "category": "primary"},
)
DISCOVERY_LISTINGS = (
    {"source": "PWOnlyIAS", "url": hub, "category": "primary"}
    for hub in PWONLYIAS_HUBS
)


def source_adapter(url: str) -> SourceAdapter | None:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    if host == "pwonlyias.com" or host.endswith(".pwonlyias.com"):
        return SOURCE_ADAPTERS[0]
    return None


def is_pwonlyias_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    return host == "pwonlyias.com" or host.endswith(".pwonlyias.com")


def controlled_queries(stamp: str) -> list[str]:
    return [
        f"site:pwonlyias.com current affairs {stamp}",
    ]

