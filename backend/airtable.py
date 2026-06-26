import os


class AirtableStore:
    def __init__(self, backend):
        self.backend = backend

    def upsert(self, fields: dict, dedup_key: str) -> tuple[str, str]:
        existing = self.backend.find_by_dedup_key(dedup_key)
        if existing is not None:
            self.backend.update(existing["id"], fields)
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


class PyairtableBackend:
    def __init__(self, table):
        self.table = table

    def find_by_dedup_key(self, key):
        from pyairtable.formulas import match

        return self.table.first(formula=match({"dedup_key": key}))

    def all(self) -> list[dict]:
        # pyairtable returns records as {"id", "fields", "createdTime"}.
        return self.table.all()

    def find_by_message_id(self, message_id):
        from pyairtable.formulas import match

        return self.table.first(formula=match({"source_message_id": message_id}))

    def create(self, fields) -> str:
        return self.table.create(fields)["id"]

    def update(self, record_id, fields) -> None:
        self.table.update(record_id, fields)

    def delete(self, record_id) -> None:
        self.table.delete(record_id)


def backend_from_env() -> PyairtableBackend:
    from pyairtable import Api

    api = Api(os.environ["AIRTABLE_API_KEY"])
    table = api.table(os.environ["AIRTABLE_BASE_ID"], os.environ["AIRTABLE_TABLE_NAME"])
    return PyairtableBackend(table)
