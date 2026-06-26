import os

from fastapi import Depends, FastAPI, Header, HTTPException

from backend.models import IngestMessage, RetractMessage
from backend.store import RawStore

app = FastAPI(title="aisafety-opportunities ingestion")

_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
_store.init_db()


def require_secret(x_ingest_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("INGEST_SHARED_SECRET")
    if not expected or x_ingest_secret != expected:
        raise HTTPException(status_code=401, detail="invalid ingest secret")


def get_airtable_store():
    # Lazy so the ingest API can run/import without Airtable env; overridden in tests.
    from backend.airtable import AirtableStore, backend_from_env

    return AirtableStore(backend_from_env())


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(msg: IngestMessage, _: None = Depends(require_secret)) -> dict:
    stored = _store.insert_message(msg.model_dump())
    return {"stored": stored, "message_id": msg.message_id}


@app.post("/retract")
def retract(
    msg: RetractMessage,
    _: None = Depends(require_secret),
    store=Depends(get_airtable_store),
) -> dict:
    deleted = store.delete_by_message(msg.message_id)
    # Tombstone the raw message so the worker never (re)extracts a retracted item,
    # even if retraction arrives before extraction.
    _store.mark_processed(msg.message_id)
    return {"deleted": deleted, "message_id": msg.message_id}
