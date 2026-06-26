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


class PyairtableBackend:
    def __init__(self, table):
        self.table = table

    def find_by_dedup_key(self, key):
        from pyairtable.formulas import match

        return self.table.first(formula=match({"dedup_key": key}))

    def all(self) -> list[dict]:
        # pyairtable returns records as {"id", "fields", "createdTime"}.
        return self.table.all()

    def create(self, fields) -> str:
        return self.table.create(fields)["id"]

    def update(self, record_id, fields) -> None:
        self.table.update(record_id, fields)


def backend_from_env() -> PyairtableBackend:
    from pyairtable import Api

    api = Api(os.environ["AIRTABLE_API_KEY"])
    table = api.table(os.environ["AIRTABLE_BASE_ID"], os.environ["AIRTABLE_TABLE_NAME"])
    return PyairtableBackend(table)
