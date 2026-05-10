"""Map a country name (in any common form) to its flag emoji and ISO code."""
from __future__ import annotations
import re

COUNTRY_TO_ISO = {
    "india": "IN", "usa": "US", "united states": "US", "america": "US",
    "uk": "GB", "united kingdom": "GB", "england": "GB", "britain": "GB",
    "china": "CN", "japan": "JP", "south korea": "KR", "korea": "KR",
    "australia": "AU", "new zealand": "NZ", "canada": "CA", "germany": "DE",
    "france": "FR", "italy": "IT", "spain": "ES", "portugal": "PT",
    "netherlands": "NL", "belgium": "BE", "sweden": "SE", "norway": "NO",
    "finland": "FI", "denmark": "DK", "ireland": "IE", "switzerland": "CH",
    "austria": "AT", "poland": "PL", "russia": "RU", "ukraine": "UA",
    "turkey": "TR", "greece": "GR", "south africa": "ZA", "egypt": "EG",
    "kenya": "KE", "ethiopia": "ET", "nigeria": "NG", "morocco": "MA",
    "brazil": "BR", "argentina": "AR", "mexico": "MX", "chile": "CL",
    "colombia": "CO", "peru": "PE", "uae": "AE", "saudi arabia": "SA",
    "israel": "IL", "iran": "IR", "iraq": "IQ", "pakistan": "PK",
    "bangladesh": "BD", "sri lanka": "LK", "nepal": "NP", "afghanistan": "AF",
    "thailand": "TH", "vietnam": "VN", "indonesia": "ID", "malaysia": "MY",
    "singapore": "SG", "philippines": "PH", "cuba": "CU", "jamaica": "JM",
    "ghana": "GH", "uganda": "UG", "zimbabwe": "ZW", "tanzania": "TZ",
    "czech republic": "CZ", "czechia": "CZ", "hungary": "HU", "romania": "RO",
    "serbia": "RS", "croatia": "HR", "bulgaria": "BG", "slovakia": "SK",
}


def iso_code(country: str | None) -> str | None:
    if not country:
        return None
    key = re.sub(r"[^a-z ]", "", country.lower()).strip()
    return COUNTRY_TO_ISO.get(key)


def flag_emoji(country: str | None) -> str:
    """Return the flag emoji for a country name, or empty string if unknown."""
    code = iso_code(country)
    if not code:
        return ""
    # Regional indicator symbols: A=0x1F1E6
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


def flag_data(country: str | None) -> dict:
    """Return both ISO code and emoji."""
    code = iso_code(country) or ""
    return {"iso": code, "emoji": flag_emoji(country)}
