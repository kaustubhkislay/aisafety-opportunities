import re

_URL_RE = re.compile(r"https?://", re.IGNORECASE)

# Some opportunities are apply-by-email only; an email address counts as a
# contact vector just like a URL does.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

_KEYWORDS = (
    "apply",
    "deadline",
    "fellowship",
    "grant",
    "hiring",
    "internship",
    "intern",
    "cohort",
    "stipend",
    "scholarship",
    "position",
    "role",
    "rfp",
    "open call",
    "applications open",
    "now accepting",
    "residency",
    "bootcamp",
    "funding",
    "career",
    "program",
)


def is_candidate(content: str) -> bool:
    if not (_URL_RE.search(content) or _EMAIL_RE.search(content)):
        return False
    text = content.lower()
    return any(keyword in text for keyword in _KEYWORDS)
