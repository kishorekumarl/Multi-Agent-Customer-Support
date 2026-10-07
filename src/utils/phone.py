"""Phone number normalization utilities."""

import re


def normalize_phone(phone: str | None) -> str:
    """Strip all non-digit characters from `phone`, keeping a leading '+' if present.

    Returns "" for None or empty input.
    """
    if not phone:
        return ""
    has_plus = phone.strip().startswith("+")
    digits = re.sub(r"\D", "", phone)
    return f"+{digits}" if has_plus else digits
