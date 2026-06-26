from pydantic import BaseModel


class IngestMessage(BaseModel):
    server_id: str
    channel_id: str
    message_id: str
    author_id: str
    content: str
    created_at: str


class Opportunity(BaseModel):
    is_opportunity: bool
    title: str | None = None
    org: str | None = None
    type: str | None = None
    deadline: str | None = None
    link: str | None = None
    location: str | None = None
    remote: bool = False
