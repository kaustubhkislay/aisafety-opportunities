from pydantic import BaseModel, field_validator


class IngestMessage(BaseModel):
    server_id: str
    server_name: str = ""
    channel_id: str
    message_id: str
    author_id: str
    content: str
    created_at: str


class RetractMessage(BaseModel):
    message_id: str


class PurgeServer(BaseModel):
    server_id: str


class SubscribeRequest(BaseModel):
    email: str


_CATEGORIES = {"tech", "gov", "ops", "other"}


class Opportunity(BaseModel):
    is_opportunity: bool
    title: str | None = None
    org: str | None = None
    type: str | None = None
    deadline: str | None = None
    link: str | None = None
    location: str | None = None
    remote: bool = False
    categories: list[str] = ["other"]
    description: str | None = None

    @field_validator("categories", mode="before")
    @classmethod
    def _clean_categories(cls, v):
        # Multi-label tech/gov/ops/other; unknown labels dropped, empty -> other.
        if not isinstance(v, list):
            v = [v] if isinstance(v, str) else []
        cleaned = [c.strip().lower() for c in v if isinstance(c, str)]
        cleaned = [c for c in cleaned if c in _CATEGORIES]
        return cleaned or ["other"]

    @field_validator("is_opportunity", "remote", mode="before")
    @classmethod
    def _coerce_boolish(cls, v):
        # LLM JSON sometimes carries "true"/"false" strings or null for bools.
        if v is None:
            return False
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in ("true", "yes"):
                return True
            if lowered in ("false", "no", ""):
                return False
        return v
