import re

_URL_RE = re.compile(r"https?://", re.IGNORECASE)

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
    if not _URL_RE.search(content):
        return False
    text = content.lower()
    return any(keyword in text for keyword in _KEYWORDS)
