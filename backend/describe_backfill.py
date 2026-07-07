"""One-off backfill: LLM descriptions for records published before the field existed.

Re-runs the extractor on each record's stored ``raw_text`` and writes back only
the ``description`` — every other published field is left untouched, and a
record is never deleted here even if the model no longer calls it an
opportunity (publication decisions stay with the live pipeline).

Run on the production machine (secrets live there):
    fly ssh console -a aisopportunities-backend -C "python -m backend.describe_backfill"
"""

import logging
import os

from backend.airtable import AirtableStore, backend_from_env
from backend.extract import Extractor
from backend.revalidate import make_revalidator
from backend.spend import SpendGuard

log = logging.getLogger("describe_backfill")


def backfill_descriptions(store, extractor, spend_guard=None) -> dict:
    """Fill empty description fields from raw_text. Returns counts."""
    counts = {"updated": 0, "skipped": 0, "no_description": 0, "capped": 0}
    for record in store.backend.all():
        fields = record["fields"]
        if (fields.get("description") or "").strip():
            counts["skipped"] += 1
            continue
        raw = (fields.get("raw_text") or "").strip()
        if not raw:
            counts["skipped"] += 1
            continue
        if spend_guard is not None and not spend_guard.try_acquire():
            counts["capped"] += 1
            continue
        opp = extractor.extract(raw)
        if opp is None or not (opp.description or "").strip():
            counts["no_description"] += 1
            continue
        store.backend.update(record["id"], {"description": opp.description})
        counts["updated"] += 1
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    extractor = Extractor(client, os.environ["OPENAI_MODEL"])
    store = AirtableStore(backend_from_env())
    spend_guard = SpendGuard.from_env(os.environ)

    counts = backfill_descriptions(store, extractor, spend_guard)
    log.info("description backfill: %s", counts)

    if counts["updated"]:
        revalidator = make_revalidator(os.environ)
        if revalidator is not None:
            revalidator()


if __name__ == "__main__":
    main()
