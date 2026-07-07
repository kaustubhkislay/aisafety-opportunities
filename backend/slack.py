"""Slack ingestion routes (Events API + OAuth), mounted into backend.app.

Design: docs/superpowers/specs/2026-07-07-slack-adapter-design.md. Slack
pushes events here; exclusion runs in slackbot.events.translate before
anything is stored. Every verified event is ACKed 200 (even when ignored)
so Slack does not auto-disable the app; signature failures get 401.
"""

import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.purge import purge_server
from backend.revalidate import make_revalidator
from backend.store import RawStore
from slackbot.backfill import backfill_channel
from slackbot.channels import ChannelScope
from slackbot.events import Backfill, Drop, Ingest, Purge, Retract, translate
from slackbot.tokens import TokenStore
from slackbot.verify import verify_slack_signature
from slackbot.web import SlackApiError, SlackWeb

logger = logging.getLogger(__name__)

router = APIRouter()

_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
_store.init_db()

_tokens = TokenStore(os.environ.get("SLACK_TOKEN_DB_PATH", "slack_tokens.db"))
_tokens.init_db()

_web = SlackWeb()

_scope = ChannelScope()

_revalidator = make_revalidator(os.environ)


def _ping_site() -> None:
    if _revalidator is not None:
        _revalidator()


def get_airtable_store():
    # Lazy, mirroring backend.app: importable without Airtable env; overridden in tests.
    from backend.airtable import AirtableStore, backend_from_env

    return AirtableStore(backend_from_env())


async def _run_backfill(token: str, team_id: str, team_name: str,
                        bot_user_id: str, channel_id: str) -> None:
    try:
        await backfill_channel(
            _web, token, team_id, team_name, bot_user_id, channel_id,
            _store, now=datetime.now(timezone.utc),
        )
    except Exception:
        logger.exception("slack backfill failed channel=%s", channel_id)


@router.post("/slack/events")
async def slack_events(request: Request, background: BackgroundTasks) -> dict:
    body = await request.body()
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not verify_slack_signature(
        secret,
        request.headers.get("x-slack-request-timestamp", ""),
        body,
        request.headers.get("x-slack-signature", ""),
        now=time.time(),
    ):
        raise HTTPException(status_code=401, detail="bad slack signature")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}
    if payload.get("type") != "event_callback":
        return {"ok": True}

    team_id = payload.get("team_id", "")
    install = _tokens.get(team_id)
    event = payload.get("event") or {}
    if install is None:
        # Uninstalled/unknown workspace: nothing to do, but still ACK.
        logger.info("slack event from unknown team=%s type=%s", team_id, event.get("type"))
        return {"ok": True}

    action = translate(event, team_id=team_id, team_name=install["team_name"],
                       bot_user_id=install["bot_user_id"])

    if isinstance(action, Ingest):
        # Membership alone is not consent: the name filter gates the live path
        # exactly like backfill (invited AND name contains "opportunities").
        # A failed scope lookup must not 500 (sustained non-200s make Slack
        # disable event delivery); consent unverified → drop, ACK, and let the
        # next delivery retry the lookup.
        try:
            in_scope = await _scope.in_scope(_web, install["bot_token"],
                                             action.msg["channel_id"])
        except Exception:
            logger.exception("slack scope check failed channel=%s",
                             action.msg["channel_id"])
            in_scope = False
        if in_scope:
            _store.insert_message(action.msg)
        else:
            logger.info("slack drop team=%s reason=out-of-scope channel=%s",
                        team_id, action.msg["channel_id"])
    elif isinstance(action, Retract):
        airtable = get_airtable_store()
        deleted = airtable.delete_by_message(action.message_id)
        _store.mark_processed(action.message_id)
        if deleted:
            _ping_site()
    elif isinstance(action, Purge):
        airtable = get_airtable_store()
        counts = purge_server(airtable, _store, action.server_id)
        _tokens.delete(team_id)
        if counts.get("airtable") or counts.get("scrubbed"):
            _ping_site()
        logger.info("slack purge team=%s counts=%s", team_id, counts)
    elif isinstance(action, Backfill):
        _scope.invalidate(action.channel_id)  # fresh invite: re-check name/membership
        background.add_task(_run_backfill, install["bot_token"], team_id,
                            install["team_name"], install["bot_user_id"],
                            action.channel_id)
    elif isinstance(action, Drop):
        logger.info("slack drop team=%s reason=%s", team_id, action.reason)

    return {"ok": True}


_SCOPES = "channels:history,channels:read,reactions:read,team:read"


@router.get("/slack/install")
def slack_install():
    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    redirect = os.environ.get("SLACK_REDIRECT_URL", "")
    url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}&scope={_SCOPES}&redirect_uri={redirect}"
    )
    return RedirectResponse(url)


@router.get("/slack/oauth/callback", response_class=HTMLResponse)
async def slack_oauth_callback(code: str | None = None) -> HTMLResponse:
    if not code:
        return HTMLResponse("<p>Missing OAuth code.</p>", status_code=400)
    try:
        data = await _web.oauth_access(
            os.environ.get("SLACK_CLIENT_ID", ""),
            os.environ.get("SLACK_CLIENT_SECRET", ""),
            code,
            os.environ.get("SLACK_REDIRECT_URL", ""),
        )
    except SlackApiError as exc:
        logger.warning("slack oauth exchange failed: %s", exc.error)
        return HTMLResponse(f"<p>Slack install failed: {exc.error}</p>", status_code=502)
    team = data.get("team") or {}
    if not team.get("id") or not data.get("access_token") or not data.get("bot_user_id"):
        logger.warning("slack oauth response missing team/token fields")
        return HTMLResponse("<p>Slack install failed: malformed OAuth response.</p>",
                            status_code=502)
    _tokens.save(
        team["id"],
        team.get("name", ""),
        data["access_token"],
        data["bot_user_id"],
    )
    logger.info("slack installed team=%s", team.get("id"))
    return HTMLResponse(
        "<h1>Installed!</h1>"
        "<p>Now <code>/invite</code> the bot into your opportunities channel "
        "(its name must contain “opportunities”). The last 14 days backfill "
        "automatically, and new posts appear on the board within seconds.</p>"
    )
