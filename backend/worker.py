import logging
import os
import time

from backend.airtable import AirtableStore, backend_from_env
from backend.dedup import stable_key
from backend.extract import Extractor
from backend.filter import is_candidate
from backend.linksafety import is_safe
from backend.enrich import resolve_past_deadline
from backend.revalidate import make_revalidator, maybe_revalidate
from backend.spend import SpendCapExceeded, SpendGuard
from backend.store import RawStore

log = logging.getLogger("worker")


def build_fields(opp, row, dedup_key: str, model_name: str) -> dict:
    seen = row.get("ingested_at") or row["created_at"]
    return {
        "title": opp.title or "",
        "org": opp.org or "",
        "type": opp.type or "other",
        "deadline": opp.deadline,
        "link": opp.link or "",
        "location": opp.location or "",
        "remote": bool(opp.remote),
        "categories": list(opp.categories or ["other"]),
        "description": opp.description or "",
        "source_server": row["server_id"],
        "source_servers": row.get("server_name") or row["server_id"],
        "source_channel": row["channel_id"],
        "source_message_id": row["message_id"],
        "raw_text": row["content"],
        "date_seen": seen[:10],
        "dedup_key": dedup_key,
        "llm_model": model_name,
    }


def process_message(
    row,
    *,
    extractor,
    store,
    model_name: str,
    filter_fn=is_candidate,
    link_check=is_safe,
    key_fn=stable_key,
    spend_guard=None,
    is_tombstoned=None,
    deadline_enricher=None,
    semantic_match=None,
) -> str:
    content = row["content"]
    if not filter_fn(content):
        return "skipped_filter"
    if spend_guard is not None and not spend_guard.try_acquire():
        log.warning(
            "LLM spend cap hit; leaving %s unprocessed until next period",
            row.get("message_id"),
        )
        raise SpendCapExceeded(row.get("message_id"))
    opp = extractor.extract(content)  # raises on hard failure -> caller leaves unprocessed
    if opp is None:
        return "not_opportunity"
    if opp.link:
        safe, reason = link_check(opp.link)
        if not safe:
            log.warning("withheld %s (%s): %s", row.get("message_id"), reason, opp.link)
            return "withheld"
    # No deadline in the message itself? Best-effort: read the application
    # page and repopulate the date (fail-soft; empty stays empty).
    if opp.deadline is None and opp.link and deadline_enricher is not None:
        opp.deadline = deadline_enricher(opp.link)
    seen = (row.get("ingested_at") or row.get("created_at") or "")[:10]
    if opp.deadline and seen:
        opp.deadline = resolve_past_deadline(opp.deadline, seen)
    # Retraction race: a /retract may tombstone this message while extraction
    # was in flight (found live in T6.5). Re-check just before publishing so a
    # retraction always wins.
    if is_tombstoned is not None and is_tombstoned(row.get("message_id")):
        log.info("message %s retracted during extraction; not publishing", row.get("message_id"))
        return "retracted"
    key = key_fn(opp)
    fields = build_fields(opp, row, key, model_name)
    if semantic_match is not None:
        _record_id, action = store.upsert(fields, key, semantic_match=semantic_match)
    else:
        _record_id, action = store.upsert(fields, key)
    return action


def run_worker(
    raw_store,
    process_fn,
    *,
    batch_size: int,
    poll_interval: float,
    sleep=time.sleep,
    max_loops=None,
) -> None:
    loops = 0
    while max_loops is None or loops < max_loops:
        rows = raw_store.claim_unprocessed(batch_size)
        progressed = False
        for row in rows:
            try:
                process_fn(row)
            except Exception:  # noqa: BLE001 - leave unprocessed, retry next loop
                log.exception(
                    "processing failed for %s; leaving unprocessed",
                    row.get("message_id"),
                )
                continue
            raw_store.mark_processed(row["message_id"])
            progressed = True
        if not rows or not progressed:
            sleep(poll_interval)
        loops += 1


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raw_store = RawStore(os.environ.get("RAW_DB_PATH", "raw.db"))
    raw_store.init_db()

    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    model = os.environ["OPENAI_MODEL"]
    extractor = Extractor(client, model)
    store = AirtableStore(backend_from_env())
    spend_guard = SpendGuard.from_env(os.environ)
    if spend_guard is None:
        log.warning("LLM_DAILY_CALL_CAP unset — extraction spend is uncapped")
    revalidator = make_revalidator(os.environ)
    if revalidator is None:
        log.warning("SITE_URL/REVALIDATE_SECRET unset — site refresh is hourly ISR only")

    from backend.enrich import DeadlineFinder, enrich_deadline, page_text
    from backend.semantic_dedup import DuplicateJudge, make_semantic_matcher

    finder = DeadlineFinder(client, model)
    semantic_match = make_semantic_matcher(
        store.backend, DuplicateJudge(client, model), spend_guard=spend_guard,
    )

    def deadline_enricher(url):
        return enrich_deadline(
            url, page_text_fn=page_text, find_fn=finder.find, spend_guard=spend_guard,
        )

    def process_fn(row):
        status = process_message(
            row, extractor=extractor, store=store, model_name=model,
            spend_guard=spend_guard, is_tombstoned=raw_store.is_processed,
            deadline_enricher=deadline_enricher, semantic_match=semantic_match,
        )
        maybe_revalidate(status, revalidator)
        return status

    run_worker(
        raw_store,
        process_fn,
        batch_size=int(os.environ.get("WORKER_BATCH_SIZE", "20")),
        poll_interval=float(os.environ.get("WORKER_POLL_INTERVAL", "10")),
    )


if __name__ == "__main__":
    main()
