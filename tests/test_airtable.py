from backend.airtable import AirtableStore


class FakeBackend:
    def __init__(self):
        self.records: dict[str, dict] = {}
        self._counter = 0

    def find_by_dedup_key(self, key):
        for rid, fields in self.records.items():
            if fields.get("dedup_key") == key:
                return {"id": rid, "fields": fields}
        return None

    def create(self, fields) -> str:
        self._counter += 1
        rid = f"rec{self._counter}"
        self.records[rid] = dict(fields)
        return rid

    def update(self, record_id, fields) -> None:
        self.records[record_id].update(fields)


def test_upsert_creates_then_updates():
    backend = FakeBackend()
    store = AirtableStore(backend)

    rid, action = store.upsert({"title": "ML Fellow", "dedup_key": "url:org.org/apply"}, "url:org.org/apply")
    assert action == "created"
    assert backend.records[rid]["title"] == "ML Fellow"

    rid2, action2 = store.upsert(
        {"title": "ML Fellow (updated deadline)", "dedup_key": "url:org.org/apply"},
        "url:org.org/apply",
    )
    assert action2 == "updated"
    assert rid2 == rid  # same record, not a duplicate
    assert backend.records[rid]["title"] == "ML Fellow (updated deadline)"
    assert len(backend.records) == 1
