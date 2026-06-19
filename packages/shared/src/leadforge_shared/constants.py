"""Constants. Mirrors TS packages/shared/src/constants.ts."""

from __future__ import annotations

from typing import Final


class QueueNames:
    DISCOVERY: Final[str] = "discovery"
    WEBSITE: Final[str] = "website"
    CONTACT: Final[str] = "contact"
    SOCIAL: Final[str] = "social"
    SCORING: Final[str] = "scoring"
    EXPORT: Final[str] = "export"


QUEUE_NAMES: Final[tuple[str, ...]] = (
    QueueNames.DISCOVERY,
    QueueNames.WEBSITE,
    QueueNames.CONTACT,
    QueueNames.SOCIAL,
    QueueNames.SCORING,
    QueueNames.EXPORT,
)


CONTACT_PRIORITY: Final[dict[str, int]] = {
    "EMAIL": 1,
    "CONTACT_FORM": 2,
    "WHATSAPP": 3,
    "LINKEDIN": 4,
    "FACEBOOK": 5,
    "INSTAGRAM": 6,
    "PHONE": 7,
}


SOCIAL_PLATFORMS: Final[tuple[str, ...]] = (
    "FACEBOOK",
    "INSTAGRAM",
    "LINKEDIN",
    "YOUTUBE",
    "TIKTOK",
    "TWITTER",
)


EXPORT_FORMATS: Final[tuple[str, ...]] = ("CSV", "XLSX", "JSON")


class ScrapingDefaults:
    MAX_DEPTH: Final[int] = 2
    MAX_PAGES: Final[int] = 20
    MAX_RETRIES: Final[int] = 3
    REQUEST_DELAY_MS: Final[int] = 2000


SCRAPING_DEFAULTS: Final[dict[str, int]] = {
    "MAX_DEPTH": ScrapingDefaults.MAX_DEPTH,
    "MAX_PAGES": ScrapingDefaults.MAX_PAGES,
    "MAX_RETRIES": ScrapingDefaults.MAX_RETRIES,
    "REQUEST_DELAY_MS": ScrapingDefaults.REQUEST_DELAY_MS,
}
