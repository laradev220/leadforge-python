"""Centralized platform definitions for social crawling.

This module provides consistent platform definitions across all social crawling components,
eliminating code duplication and making it easier to add new platforms.
"""

from __future__ import annotations

import re

from leadforge_shared.types import SocialPlatform


# Social platform domains mapping
SOCIAL_DOMAINS = {
    "facebook.com": SocialPlatform.FACEBOOK,
    "fb.com": SocialPlatform.FACEBOOK,
    "instagram.com": SocialPlatform.INSTAGRAM,
    "linkedin.com": SocialPlatform.LINKEDIN,
    "youtube.com": SocialPlatform.YOUTUBE,
    "tiktok.com": SocialPlatform.TIKTOK,
    "twitter.com": SocialPlatform.TWITTER,
    "x.com": SocialPlatform.TWITTER,
}

# Business-like email domains (higher confidence)
BUSINESS_EMAIL_DOMAINS = {
    "company.com", "business.com", "corp.com", "llc.com",
    "inc.com", "org", "net", "edu", "gov", "mil", "co.uk",
    "com.au", "ca", "de", "fr", "es", "it", "nl", "be",
}

# Free email domains (lower confidence)
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "mail.com", "aol.com", "protonmail.com",
    "me.com", "mac.com", "live.com", "msn.com",
}

# Generic/system email prefixes to discard (non-person, unmonitored)
DISCARD_EMAIL_PREFIXES = {
    "noreply", "no-reply", "donotreply", "example", "test",
    "webmaster", "postmaster", "hostmaster", "abuse",
}

# Social platform names for Google search
SOCIAL_PLATFORM_NAMES = [
    "linkedin", "facebook", "instagram", "twitter", "tiktok",
    "threads", "youtube", "x",
]

# Business indicators for free email domains
BUSINESS_EMAIL_INDICATORS = [
    "info", "hello", "contact", "support", "admin", "sales", "help", "enquiries",
]

# Social platform display names
SOCIAL_PLATFORM_DISPLAY_NAMES = {
    SocialPlatform.FACEBOOK: "Facebook",
    SocialPlatform.INSTAGRAM: "Instagram",
    SocialPlatform.LINKEDIN: "LinkedIn",
    SocialPlatform.YOUTUBE: "YouTube",
    SocialPlatform.TIKTOK: "TikTok",
    SocialPlatform.TWITTER: "Twitter",
}


def get_social_platform_from_domain(domain: str) -> SocialPlatform | None:
    """Get social platform from domain name.
    
    Args:
        domain: Domain name (with or without www prefix)
        
    Returns:
        SocialPlatform if found, None otherwise
    """
    if domain.startswith("www."):
        domain = domain[4:]
    return SOCIAL_DOMAINS.get(domain.lower())


def is_business_email(email: str) -> bool:
    """Check if an email address looks like a business email.
    
    Args:
        email: Email address to check
        
    Returns:
        True if the email looks like a business email, False otherwise
    """
    if "@" not in email:
        return False

    local_part = email.split("@")[0]
    domain = email.split("@")[1].lower()
    local_part = local_part.lower()

    if not local_part or not domain:
        return False

    # Discard generic/system emails
    if any(local_part.startswith(prefix) for prefix in DISCARD_EMAIL_PREFIXES):
        return False
        
    # Business-like domains (higher confidence)
    if domain in BUSINESS_EMAIL_DOMAINS:
        return True
        
    # Free email domains (lower confidence)
    if domain in FREE_EMAIL_DOMAINS:
        # Check if local part looks business-like
        if any(indicator in local_part for indicator in BUSINESS_EMAIL_INDICATORS):
            return True
        return False
        
    # Other domains (org, net, etc.) - assume business
    return True


def get_social_platform_search_terms() -> list[str]:
    """Get social platform search terms for Google searches.
    
    Returns:
        List of social platform search terms
    """
    return SOCIAL_PLATFORM_NAMES.copy()


def get_social_platform_display_name(platform: SocialPlatform) -> str:
    """Get display name for a social platform.
    
    Args:
        platform: SocialPlatform enum value
        
    Returns:
        Display name for the platform
    """
    return SOCIAL_PLATFORM_DISPLAY_NAMES.get(platform, platform.value)


def is_valid_phone_number(phone: str) -> bool:
    """Basic validation for phone numbers.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if the phone number looks valid, False otherwise
    """
    if not phone:
        return False

    # Skip obviously invalid formats before cleaning
    if re.search(r'order\s*#', phone, re.I):
        return False

    # Remove common formatting characters
    cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', phone)

    # Basic length validation
    digits_only = re.sub(r'[^\d]', '', cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False

    return True

