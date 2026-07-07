from types import SimpleNamespace

from backend.airtable import AirtableStore
from backend.describe_backfill import backfill_descriptions


class FakeBackend:
    def __init__(self, records):
        self.records = {r["id"]: dict(r["fields"]) for r in records}
        self.updates: list[tuple[str, dict]] = []

    def all(self):
        return [{"id": rid, "fields": dict(f)} for rid, f in self.records.items()]

    def update(self, record_id, fields):
        self.records[record_id].update(fields)
        self.updates.append((record_id, fields))


class FakeExtractor:
    def __init__(self, description="A great fellowship for researchers."):
        self.description = description
        self.calls: list[str] = []

    def extract(self, content):
        self.calls.append(content)
        if content == "not-an-opp":
            return None
        return SimpleNamespace(description=self.description)


def _store(records) -> AirtableStore:
    return AirtableStore(FakeBackend(records))


def test_fills_only_records_missing_description():
    store = _store([
        {"id": "r1", "fields": {"raw_text": "Fellowship: apply now", "description": ""}},
        {"id": "r2", "fields": {"raw_text": "Job posting", "description": "Already has one."}},
        {"id": "r3", "fields": {"raw_text": ""}},
    ])
    extractor = FakeExtractor()

    counts = backfill_descriptions(store, extractor)

    assert counts == {"updated": 1, "skipped": 2, "no_description": 0, "capped": 0}
    assert extractor.calls == ["Fellowship: apply now"]
    assert store.backend.records["r1"]["description"] == "A great fellowship for researchers."
    assert store.backend.records["r2"]["description"] == "Already has one."


def test_never_deletes_when_model_says_not_opportunity():
    store = _store([{"id": "r1", "fields": {"raw_text": "not-an-opp", "description": ""}}])
    counts = backfill_descriptions(store, FakeExtractor())
    assert counts["no_description"] == 1
    assert "r1" in store.backend.records  # record untouched


def test_skips_when_model_returns_no_description():
    store = _store([{"id": "r1", "fields": {"raw_text": "Vague post", "description": ""}}])
    counts = backfill_descriptions(store, FakeExtractor(description=""))
    assert counts["no_description"] == 1
    assert store.backend.updates == []


def test_respects_spend_cap():
    store = _store([
        {"id": "r1", "fields": {"raw_text": "One https://a.example"}},
        {"id": "r2", "fields": {"raw_text": "Two https://b.example"}},
    ])

    class OneCallGuard:
        def __init__(self):
            self.left = 1

        def try_acquire(self):
            if self.left:
                self.left -= 1
                return True
            return False

    counts = backfill_descriptions(store, FakeExtractor(), OneCallGuard())
    assert counts["updated"] == 1
    assert counts["capped"] == 1
