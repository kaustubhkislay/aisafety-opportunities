from pydantic import BaseModel


class IngestMessage(BaseModel):
    server_id: str
    channel_id: str
    message_id: str
    author_id: str
    content: str
    created_at: str
