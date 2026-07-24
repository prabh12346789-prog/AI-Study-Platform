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
    SourceAdapter("PIB", "pib.gov.in", "primary"),
    SourceAdapter("RBI", "rbi.org.in", "primary"),
    SourceAdapter("MEA", "mea.gov.in", "primary"),
    SourceAdapter("Sansad TV", "sansadtv.nic.in", "primary", "video"),
    SourceAdapter("DD News", "ddnews.gov.in", "primary", "video"),
    SourceAdapter("ForumIAS", "forumias.com", "daily_analysis"),
    SourceAdapter("InsightsIAS", "insightsonindia.com", "daily_analysis"),
    SourceAdapter("Drishti IAS", "drishtiias.com", "daily_analysis"),
    SourceAdapter("GS SCORE", "iasscore.in", "mains_editorial"),
    SourceAdapter("Vision IAS", "visionias.in", "monthly_revision"),
)

TIER_ORDER = {"primary": 4, "daily_analysis": 3, "mains_editorial": 2, "monthly_revision": 1}

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
    {"source": "PIB", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "category": "primary"},
    {"source": "RBI", "url": "https://website.rbi.org.in/web/rbi/press-releases-rss-feed", "category": "primary"},
    {"source": "MEA", "url": "https://www.mea.gov.in/rss-feeds.htm", "category": "primary"},
    {"source": "InsightsIAS", "url": "https://www.insightsonindia.com/feed/", "category": "daily_analysis"},
    {"source": "Drishti IAS", "url": "https://www.drishtiias.com/rss", "category": "daily_analysis"},
    {"source": "ForumIAS", "url": "https://forumias.com/blog/feed/", "category": "daily_analysis"},
)

DISCOVERY_LISTINGS = (
    *({"source": "PWOnlyIAS", "url": hub, "category": "primary"} for hub in PWONLYIAS_HUBS),
    {"source": "PIB", "url": "https://pib.gov.in/AllRelease.aspx", "category": "primary"},
    {"source": "RBI", "url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx", "category": "primary"},
    {"source": "MEA", "url": "https://www.mea.gov.in/media-briefings.htm", "category": "primary"},
)


def source_adapter(url: str) -> SourceAdapter | None:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    return next((item for item in SOURCE_ADAPTERS if host == item.domain or host.endswith("." + item.domain)), None)


def is_pwonlyias_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    return host == "pwonlyias.com" or host.endswith(".pwonlyias.com")


def controlled_queries(stamp: str) -> list[str]:
    return [
        f"site:pwonlyias.com current affairs {stamp}",
    ]
