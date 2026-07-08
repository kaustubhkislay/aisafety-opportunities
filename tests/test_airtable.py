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


def test_upsert_unions_source_servers():
    backend = FakeBackend()
    store = AirtableStore(backend)
    store.upsert({"title": "X", "dedup_key": "k", "source_servers": "AI Safety Hub"}, "k")
    # Same opportunity seen in a second community: names accumulate, no dupes.
    store.upsert({"title": "X", "dedup_key": "k", "source_servers": "WAISI"}, "k")
    store.upsert({"title": "X", "dedup_key": "k", "source_servers": "WAISI"}, "k")
    record = backend.find_by_dedup_key("k")
    assert record["fields"]["source_servers"] == "AI Safety Hub, WAISI"


class StubMatcher:
    def __init__(self, record):
        self._record = record
        self.calls = []

    def __call__(self, fields):
        self.calls.append(fields)
        return self._record


def test_upsert_merges_into_semantic_duplicate_without_overwriting():
    backend = FakeBackend()
    store = AirtableStore(backend)
    rid, _ = store.upsert(
        {"title": "Heron Fellowship", "link": "https://heronsec.ai/researchfellowship",
         "dedup_key": "url:heronsec.ai/researchfellowship", "source_servers": "WAISI"},
        "url:heronsec.ai/researchfellowship",
    )

    incoming = {"title": "Heron Fellowship (Sept-Nov)", "link": "https://heron.fillout.com/fellowship",
                "dedup_key": "url:heron.fillout.com/fellowship", "source_servers": "CMU AIS"}
    matcher = StubMatcher(backend.find_by_dedup_key("url:heronsec.ai/researchfellowship"))
    rid2, action = store.upsert(incoming, "url:heron.fillout.com/fellowship", semantic_match=matcher)

    assert (rid2, action) == (rid, "updated")
    assert len(backend.records) == 1  # merged, not duplicated
    # First-seen record's content wins; only the attribution is unioned.
    assert backend.records[rid]["title"] == "Heron Fellowship"
    assert backend.records[rid]["link"] == "https://heronsec.ai/researchfellowship"
    assert backend.records[rid]["dedup_key"] == "url:heronsec.ai/researchfellowship"
    assert backend.records[rid]["source_servers"] == "WAISI, CMU AIS"


def test_upsert_creates_when_semantic_match_misses():
    backend = FakeBackend()
    store = AirtableStore(backend)
    _, action = store.upsert({"title": "X", "dedup_key": "k1"}, "k1", semantic_match=lambda fields: None)
    assert action == "created"


def test_upsert_exact_match_skips_semantic_matcher():
    backend = FakeBackend()
    store = AirtableStore(backend)
    store.upsert({"title": "X", "dedup_key": "k1"}, "k1")
    matcher = StubMatcher(None)
    _, action = store.upsert({"title": "X", "dedup_key": "k1"}, "k1", semantic_match=matcher)
    assert action == "updated"
    assert matcher.calls == []  # exact key hit — no LLM spend
