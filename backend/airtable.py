import os


def _union_servers(existing: str | None, incoming: str | None) -> str:
    """Comma-joined union of community names, first-seen order preserved.

    An opportunity deduped across communities keeps every server it was found
    in ("found in" attribution on the site)."""
    out: list[str] = []
    for blob in (existing, incoming):
        for name in (blob or "").split(","):
            name = name.strip()
            if name and name not in out:
                out.append(name)
    return ", ".join(out)


class AirtableStore:
    def __init__(self, backend):
        self.backend = backend

    def upsert(self, fields: dict, dedup_key: str) -> tuple[str, str]:
        existing = self.backend.find_by_dedup_key(dedup_key)
        if existing is not None:
            merged = dict(fields)
            merged["source_servers"] = _union_servers(
                existing["fields"].get("source_servers"),
                fields.get("source_servers"),
            )
            self.backend.update(existing["id"], merged)
            return existing["id"], "updated"
        record_id = self.backend.create(fields)
        return record_id, "created"

    def delete_by_message(self, message_id: str) -> bool:
        """Delete the record whose source message matches; used for retraction.

        Returns True if a record was found and deleted. (A record deduped across
        multiple source messages tracks its latest source_message_id; retracting
        an older source of such a record is a known v1 limitation.)
        """
        existing = self.backend.find_by_message_id(message_id)
        if existing is None:
            return False
        self.backend.delete(existing["id"])
        return True

    def delete_by_server(self, server_id: str) -> int:
        """Delete every record sourced from a server (uninstall purge). Returns count."""
        records = self.backend.find_by_server(server_id)
        for record in records:
            self.backend.delete(record["id"])
        return len(records)

    def remove_server_attribution(self, names: set[str]) -> int:
        """Scrub a purged community from surviving records' ``source_servers``.

        A record deduped across communities lists every community it was seen
        in; deleting only records whose *latest* source is the purged server
        would leave the purged community attributed (and on the partners page)
        via merged records. Returns the number of records updated.
        """
        updated = 0
        for record in self.backend.all():
            blob = record["fields"].get("source_servers") or ""
            parts = [p.strip() for p in blob.split(",") if p.strip()]
            kept = [p for p in parts if p not in names]
            if kept != parts:
                self.backend.update(record["id"], {"source_servers": ", ".join(kept)})
                updated += 1
        return updated


_RETRYABLE = {429, 500, 502, 503}
_MAX_ATTEMPTS = 4


class PyairtableBackend:
    def __init__(self, table, sleep=None):
        self.table = table
        if sleep is None:
            import time

            sleep = time.sleep
        self._sleep = sleep

    def _call(self, fn, *args, **kwargs):
        """Run an Airtable call with exponential backoff on 429/transient 5xx.

        Airtable allows ~5 req/s; without this, a burst of publishes makes the
        worker re-run (and re-bill) whole extractions on every rate-limit hit.
        """
        delay = 0.5
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as err:  # noqa: BLE001 - inspect for retryability
                status = getattr(getattr(err, "response", None), "status_code", None)
                if status not in _RETRYABLE or attempt == _MAX_ATTEMPTS:
                    raise
                self._sleep(delay)
                delay *= 2

    def find_by_dedup_key(self, key):
        from pyairtable.formulas import match

        return self._call(self.table.first, formula=match({"dedup_key": key}))

    def all(self) -> list[dict]:
        # pyairtable returns records as {"id", "fields", "createdTime"}.
        return self._call(self.table.all)

    def find_by_message_id(self, message_id):
        from pyairtable.formulas import match

        return self._call(self.table.first, formula=match({"source_message_id": message_id}))

    def find_by_server(self, server_id):
        from pyairtable.formulas import match

        return self._call(self.table.all, formula=match({"source_server": server_id}))

    def create(self, fields) -> str:
        return self._call(self.table.create, fields)["id"]

    def update(self, record_id, fields) -> None:
        self._call(self.table.update, record_id, fields)

    def delete(self, record_id) -> None:
        self._call(self.table.delete, record_id)


def backend_from_env() -> PyairtableBackend:
    from pyairtable import Api

    api = Api(os.environ["AIRTABLE_API_KEY"])
    table = api.table(os.environ["AIRTABLE_BASE_ID"], os.environ["AIRTABLE_TABLE_NAME"])
    return PyairtableBackend(table)
