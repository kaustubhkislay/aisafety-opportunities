import os
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from backend.digest import (
    is_valid_email,
    make_token,
    resend_sender_from_env,
    verify_token,
)
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
    if counts.get("airtable") or counts.get("scrubbed"):
        _ping_site()
    return {"server_id": body.server_id, **counts}


@app.get("/ingested/{server_id}")
def ingested(server_id: str, _: None = Depends(require_secret)) -> dict:
    # Owner-visibility: what has been ingested from this server.
    messages = _store.get_messages_by_server(server_id)
    return {"server_id": server_id, "count": len(messages), "messages": messages}


# Public endpoint abuse guard: N signups per IP per window (in-process is
# fine — a single uvicorn serves this).
_SUBSCRIBE_WINDOW = 60 * 60
_SUBSCRIBE_LIMIT = 5
_SUBSCRIBE_MAX_BUCKETS = 10_000
_subscribe_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Behind Fly's proxy request.client.host is the proxy address shared by
    # everyone; the real client arrives in Fly-Client-IP.
    return request.headers.get("fly-client-ip") or (
        request.client.host if request.client else "unknown"
    )


def _rate_limited(ip: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    if len(_subscribe_hits) > _SUBSCRIBE_MAX_BUCKETS:
        for stale in [k for k, h in _subscribe_hits.items() if not h or now - h[-1] > _SUBSCRIBE_WINDOW]:
            del _subscribe_hits[stale]
    hits = _subscribe_hits[ip]
    while hits and now - hits[0] > _SUBSCRIBE_WINDOW:
        hits.popleft()
    if len(hits) >= _SUBSCRIBE_LIMIT:
        return True
    hits.append(now)
    return False


def _confirm_sender():
    # Indirection so tests can stub the sender; None when Resend is unconfigured.
    return resend_sender_from_env(os.environ)


# Email-bombing guard: at most N confirmation emails per address per window
# (>1 so a legitimate retry after a spam-foldered first email still works).
_CONFIRM_WINDOW = 24 * 60 * 60
_CONFIRM_LIMIT = 3
_confirm_sends: dict[str, deque] = defaultdict(deque)


def _confirm_send_allowed(email: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    sends = _confirm_sends[email]
    while sends and now - sends[0] > _CONFIRM_WINDOW:
        sends.popleft()
    if len(sends) >= _CONFIRM_LIMIT:
        return False
    sends.append(now)
    return True


@app.post("/subscribe")
def subscribe(body: SubscribeRequest, request: Request) -> dict:
    # Public endpoint (the website's subscribe form posts here). Double-opt-in:
    # anyone can type any address, so nothing activates until the owner of the
    # inbox clicks the signed confirm link.
    if not is_valid_email(body.email):
        raise HTTPException(status_code=400, detail="invalid email")
    if _rate_limited(_client_ip(request)):
        raise HTTPException(status_code=429, detail="too many signups; try later")
    email = body.email.strip().lower()
    _subscribers.add_pending(email)
    sender = _confirm_sender()
    secret = os.environ.get("UNSUBSCRIBE_SECRET", "")
    if sender is not None and secret:
        if not _confirm_send_allowed(email):
            # Same response as the sent case so the endpoint doesn't leak
            # subscription state or that a cap exists.
            return {"pending": True, "email": email}
        base = os.environ.get("BACKEND_URL", "http://localhost:3000").rstrip("/")
        link = f"{base}/subscribe/confirm?token={make_token(email, secret, purpose='confirm')}"
        sender(
            email,
            "Confirm your AI Safety Opportunities digest",
            f'<p>Click to confirm your daily digest subscription: <a href="{link}">confirm</a>.</p>'
            "<p>If you didn't request this, ignore this email and nothing happens.</p>",
            f"Confirm your subscription: {link}\nIf you didn't request this, ignore this email.",
        )
    else:
        # Dev fallback: no email provider configured — activate directly.
        _subscribers.activate(email)
    return {"pending": True, "email": email}


_CONFIRM_TOKEN_MAX_AGE = 3 * 86400  # confirm links go stale quickly
_UNSUBSCRIBE_TOKEN_MAX_AGE = 90 * 86400  # old digest footers keep working


@app.get("/subscribe/confirm", response_class=HTMLResponse)
def subscribe_confirm(token: str) -> HTMLResponse:
    secret = os.environ.get("UNSUBSCRIBE_SECRET", "")
    email = (
        verify_token(token, secret, purpose="confirm", max_age=_CONFIRM_TOKEN_MAX_AGE)
        if secret
        else None
    )
    if email is None:
        return HTMLResponse("<p>Invalid or expired confirmation link.</p>", status_code=400)
    _subscribers.activate(email)
    return HTMLResponse(f"<p>{email} is subscribed to the daily digest.</p>")


@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str) -> HTMLResponse:
    secret = os.environ.get("UNSUBSCRIBE_SECRET", "")
    email = verify_token(token, secret, max_age=_UNSUBSCRIBE_TOKEN_MAX_AGE) if secret else None
    if email is None:
        return HTMLResponse("<p>Invalid or expired unsubscribe link.</p>", status_code=400)
    _subscribers.remove(email)
    return HTMLResponse(f"<p>{email} has been unsubscribed.</p>")
