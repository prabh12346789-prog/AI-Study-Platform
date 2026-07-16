from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceAdapter:
    name: str
    domain: str
    tier: str
    content_kind: str = "article"


SOURCE_ADAPTERS = (
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

DISCOVERY_FEEDS = (
    {"source": "PIB", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "category": "primary"},
    {"source": "RBI", "url": "https://website.rbi.org.in/web/rbi/press-releases-rss-feed", "category": "primary"},
    {"source": "MEA", "url": "https://www.mea.gov.in/rss-feeds.htm", "category": "primary"},
    {"source": "InsightsIAS", "url": "https://www.insightsonindia.com/feed/", "category": "daily_analysis"},
    {"source": "Drishti IAS", "url": "https://www.drishtiias.com/rss", "category": "daily_analysis"},
    {"source": "ForumIAS", "url": "https://forumias.com/blog/feed/", "category": "daily_analysis"},
)

DISCOVERY_LISTINGS = (
    {"source": "PIB", "url": "https://pib.gov.in/AllRelease.aspx", "category": "primary"},
    {"source": "RBI", "url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx", "category": "primary"},
    {"source": "MEA", "url": "https://www.mea.gov.in/media-briefings.htm", "category": "primary"},
)


def source_adapter(url: str) -> SourceAdapter | None:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    return next((item for item in SOURCE_ADAPTERS if host == item.domain or host.endswith("." + item.domain)), None)


def controlled_queries(stamp: str) -> list[str]:
    return [
        f"site:pib.gov.in OR site:rbi.org.in OR site:mea.gov.in India current affairs {stamp}",
        f"site:gov.in India ministry regulator policy {stamp}",
        f"site:forumias.com 9 PM Brief {stamp}",
        f"site:insightsonindia.com daily current affairs {stamp}",
        f"site:drishtiias.com daily news analysis {stamp}",
        f"site:iasscore.in mains current affairs {stamp}",
        f"site:visionias.in monthly current affairs {stamp}",
    ]
