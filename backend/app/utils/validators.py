import re
from typing import Optional


_PHONE_RE = re.compile(r"[+]?\d[\d\s\-()]{6,}")


def normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return None
    if raw.strip().startswith('+'):
        return '+' + digits
    return digits

