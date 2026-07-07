import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

from backend.digest import is_valid_email, verify_token
from backend.models import (
    IngestMessage,
    PurgeServer,
    RetractMessage,
    SubscribeRequest,
)
from backend.purge import purge_server
from backend.revalidate import make_revalidator
from backend.slack import router as slack_router
from backend.store import RawStore
from backend.subscribers import SubscriberStore

app = FastAPI(title="aisafety-opportunities ingestion")

app.include_router(slack_router)

_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
_store.init_db()

_subscribers = SubscriberStore(os.environ.get("SUBSCRIBER_DB_PATH", "subscribers.db"))
_subscribers.init_db()

_revalidator = make_revalidator(os.environ)


def _ping_site() -> None:
    if _revalidator is not None:
        _revalidator()


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
    if deleted:
        _ping_site()  # retraction should disappear from the site immediately
    return {"deleted": deleted, "message_id": msg.message_id}


@app.post("/purge")
def purge(
    body: PurgeServer,
    _: None = Depends(require_secret),
    store=Depends(get_airtable_store),
) -> dict:
    counts = purge_server(store, _store, body.server_id)
    if counts.get("airtable"):
        _ping_site()
    return {"server_id": body.server_id, **counts}


@app.get("/ingested/{server_id}")
def ingested(server_id: str, _: None = Depends(require_secret)) -> dict:
    # Owner-visibility: what has been ingested from this server.
    messages = _store.get_messages_by_server(server_id)
    return {"server_id": server_id, "count": len(messages), "messages": messages}


@app.post("/subscribe")
def subscribe(body: SubscribeRequest) -> dict:
    # Public endpoint (the website's subscribe form posts here).
    if not is_valid_email(body.email):
        raise HTTPException(status_code=400, detail="invalid email")
    added = _subscribers.add(body.email)
    return {"subscribed": added, "email": body.email.strip().lower()}


@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str) -> HTMLResponse:
    secret = os.environ.get("UNSUBSCRIBE_SECRET", "")
    email = verify_token(token, secret) if secret else None
    if email is None:
        return HTMLResponse("<p>Invalid or expired unsubscribe link.</p>", status_code=400)
    _subscribers.remove(email)
    return HTMLResponse(f"<p>{email} has been unsubscribed.</p>")
