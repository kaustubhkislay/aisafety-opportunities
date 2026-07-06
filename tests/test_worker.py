from backend.models import Opportunity
from backend.worker import build_fields, process_message, run_worker


ROW = {
    "message_id": "100",
    "server_id": "srv1",
    "channel_id": "chan1",
    "content": "Apply: https://redwood.org/apply — fellowship, deadline 2026-08-01",
    "created_at": "2026-06-25T12:00:00+00:00",
    "ingested_at": "2026-06-25 12:00:05",
}


class StubExtractor:
    def __init__(self, result):
        self._result = result

    def extract(self, content):
        return self._result


class RecordingStore:
    def __init__(self):
        self.upserts = []

    def upsert(self, fields, dedup_key):
        self.upserts.append((fields, dedup_key))
        return "rec1", "created"


def _opp(**kw):
    base = {"is_opportunity": True}
    base.update(kw)
    return Opportunity(**base)


def test_build_fields_maps_row_and_opportunity():
    opp = _opp(title="ML Fellow", org="Redwood", type="fellowship",
               deadline="2026-08-01", link="https://redwood.org/apply",
               location="Remote", remote=True)
    fields = build_fields(opp, ROW, "url:redwood.org/apply", "qwen-test")
    assert fields["title"] == "ML Fellow"
    assert fields["type"] == "fellowship"
    assert fields["remote"] is True
    assert fields["source_server"] == "srv1"
    assert fields["source_channel"] == "chan1"
    assert fields["raw_text"] == ROW["content"]
    assert fields["date_seen"] == "2026-06-25"
    assert fields["dedup_key"] == "url:redwood.org/apply"
    assert fields["llm_model"] == "qwen-test"


def test_process_filtered_out():
    status = process_message(
        {"message_id": "1", "content": "thanks!"},
        extractor=StubExtractor(None), store=RecordingStore(), model_name="m",
    )
    assert status == "skipped_filter"


def test_process_not_opportunity():
    status = process_message(
        ROW, extractor=StubExtractor(None), store=RecordingStore(), model_name="m",
    )
    assert status == "not_opportunity"


def test_process_withheld_on_unsafe_link():
    opp = _opp(title="x", link="https://bit.ly/abc")
    store = RecordingStore()
    status = process_message(ROW, extractor=StubExtractor(opp), store=store, model_name="m")
    assert status == "withheld"
    assert store.upserts == []  # nothing published


def test_process_creates_record():
    opp = _opp(title="ML Fellow", org="Redwood", link="https://redwood.org/apply")
    store = RecordingStore()
    status = process_message(ROW, extractor=StubExtractor(opp), store=store, model_name="m")
    assert status == "created"
    assert len(store.upserts) == 1


class FakeRawStore:
    def __init__(self, batches):
        self._batches = list(batches)
        self.marked = []

    def claim_unprocessed(self, limit):
        return self._batches.pop(0) if self._batches else []

    def mark_processed(self, message_id):
        self.marked.append(message_id)


def test_run_worker_marks_success_and_leaves_failures():
    rows = [{"message_id": "ok"}, {"message_id": "boom"}]
    raw = FakeRawStore([rows])

    def process_fn(row):
        if row["message_id"] == "boom":
            raise RuntimeError("LLM down")
        return "created"

    run_worker(raw, process_fn, batch_size=10, poll_interval=0,
               sleep=lambda _s: None, max_loops=1)

    assert raw.marked == ["ok"]  # "boom" left unprocessed for retry


def test_run_worker_sleeps_when_no_progress():
    rows = [{"message_id": "boom"}]
    raw = FakeRawStore([rows])
    slept = []

    def process_fn(row):
        raise RuntimeError("provider down")

    run_worker(raw, process_fn, batch_size=10, poll_interval=5,
               sleep=lambda s: slept.append(s), max_loops=1)

    assert raw.marked == []   # nothing succeeded
    assert slept == [5]       # paced retry, not a hot-spin


def test_build_fields_uses_server_name_for_attribution():
    opp = _opp(title="X")
    fields = build_fields(opp, dict(ROW, server_name="AI Safety Hub"), "k", "m")
    assert fields["source_servers"] == "AI Safety Hub"
    fields = build_fields(opp, ROW, "k", "m")  # legacy row without server_name
    assert fields["source_servers"] == "srv1"


def test_missing_deadline_is_enriched_from_link():
    opp = _opp(title="X", org="O", link="https://org.example/apply", deadline=None)
    store = RecordingStore()
    status = process_message(
        ROW, extractor=StubExtractor(opp), store=store, model_name="m",
        deadline_enricher=lambda url: "2026-07-22",
    )
    assert status == "created"
    assert store.upserts[0][0]["deadline"] == "2026-07-22"


def test_present_deadline_skips_enrichment():
    opp = _opp(title="X", link="https://org.example/apply", deadline="2026-08-01")
    calls = []
    process_message(
        ROW, extractor=StubExtractor(opp), store=RecordingStore(), model_name="m",
        deadline_enricher=lambda url: calls.append(url) or "2026-01-01",
    )
    assert calls == []


def test_worker_repairs_year_resolution_errors():
    opp = _opp(title="X", link="https://org.example/a", deadline="2024-07-22")
    store = RecordingStore()
    process_message(
        dict(ROW, ingested_at="2026-07-06 00:00:00"),
        extractor=StubExtractor(opp), store=store, model_name="m",
    )
    assert store.upserts[0][0]["deadline"] == "2026-07-22"
