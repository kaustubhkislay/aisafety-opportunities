"""Daily status/expiry job (Slice 4).

Recomputes each Airtable opportunity's ``status`` from its ``deadline`` and writes
back only the records whose status changed. Status semantics mirror the website's
``web/lib/status.ts`` ``deriveStatus`` exactly (UTC-day based):

- no / blank deadline      -> "active"
- malformed (non-ISO) date -> "active" (logged)
- deadline in the past     -> "expired"
- within 7 days inclusive  -> "closing-soon"
- otherwise                -> "active"

The site derives status on the fly, so this job exists to keep the canonical
store and the email digest consistent, not to feed the site.
"""

import logging
import os
from datetime import date

log = logging.getLogger("status_job")

Status = str  # "active" | "closing-soon" | "expired"


def derive_status(deadline: str | None, today: date) -> Status:
    if not deadline:
        return "active"
    try:
        due = date.fromisoformat(deadline.strip()[:10])
    except (ValueError, AttributeError):
        log.warning("malformed deadline %r; treating as active", deadline)
        return "active"
    days = (due - today).days
    if days < 0:
        return "expired"
    if days <= 7:
        return "closing-soon"
    return "active"


def run_status_job(backend, today: date) -> dict[str, int]:
    """Re-evaluate every record's status; update only those that changed.

    ``backend`` must provide ``all() -> list[{"id", "fields"}]`` and
    ``update(record_id, fields)``. Returns counts per computed status plus the
    number of records changed.
    """
    counts = {"active": 0, "closing-soon": 0, "expired": 0, "changed": 0}
    for record in backend.all():
        fields = record["fields"]
        new_status = derive_status(fields.get("deadline"), today)
        counts[new_status] += 1
        if fields.get("status") != new_status:
            backend.update(record["id"], {"status": new_status})
            counts["changed"] += 1
    log.info("status job: %s", counts)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from backend.airtable import backend_from_env

    run_status_job(backend_from_env(), date.today())


if __name__ == "__main__":
    main()
