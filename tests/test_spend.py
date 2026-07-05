import logging

import pytest

from backend.models import Opportunity
from backend.spend import SpendCapExceeded, SpendGuard
from backend.worker import process_message, run_worker


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
        self.calls = 0

    def extract(self, content):
        self.calls += 1
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


class FakeClock:
    def __init__(self, period):
        self.period = period

    def __call__(self):
        return self.period


def test_try_acquire_counts_up_to_cap():
    guard = SpendGuard(2, clock=FakeClock("2026-07-05"))
    assert guard.try_acquire() is True
    assert guard.try_acquire() is True
    assert guard.try_acquire() is False  # cap hit
    assert guard.try_acquire() is False  # stays refused within the period


def test_counter_resets_on_new_period():
    clock = FakeClock("2026-07-05")
    guard = SpendGuard(1, clock=clock)
    assert guard.try_acquire() is True
    assert guard.try_acquire() is False
    clock.period = "2026-07-06"
    assert guard.try_acquire() is True  # fresh budget next period


def test_from_env_returns_guard_or_none():
    assert SpendGuard.from_env({}) is None
    assert SpendGuard.from_env({"LLM_DAILY_CALL_CAP": "0"}) is None
    guard = SpendGuard.from_env({"LLM_DAILY_CALL_CAP": "5"})
    assert isinstance(guard, SpendGuard)
    assert guard.cap == 5


def test_process_under_cap_proceeds():
    opp = _opp(title="ML Fellow", org="Redwood", link="https://redwood.org/apply")
    store = RecordingStore()
    guard = SpendGuard(10, clock=FakeClock("2026-07-05"))
    status = process_message(
        ROW, extractor=StubExtractor(opp), store=store, model_name="m", spend_guard=guard,
    )
    assert status == "created"
    assert len(store.upserts) == 1


def test_process_over_cap_skips_extraction_and_logs(caplog):
    extractor = StubExtractor(_opp(title="x"))
    store = RecordingStore()
    guard = SpendGuard(0, clock=FakeClock("2026-07-05"))
    with caplog.at_level(logging.WARNING, logger="spend"):
        with pytest.raises(SpendCapExceeded):
            process_message(
                ROW, extractor=extractor, store=store, model_name="m", spend_guard=guard,
            )
    assert extractor.calls == 0  # LLM never called
    assert store.upserts == []  # nothing published
    assert any("cap" in r.message.lower() for r in caplog.records)


def test_filtered_rows_do_not_consume_spend():
    guard = SpendGuard(1, clock=FakeClock("2026-07-05"))
    status = process_message(
        {"message_id": "1", "content": "thanks!"},
        extractor=StubExtractor(None), store=RecordingStore(), model_name="m",
        spend_guard=guard,
    )
    assert status == "skipped_filter"
    assert guard.try_acquire() is True  # budget untouched by the cheap filter


class FakeRawStore:
    def __init__(self, batches):
        self._batches = list(batches)
        self.marked = []

    def claim_unprocessed(self, limit):
        return self._batches.pop(0) if self._batches else []

    def mark_processed(self, message_id):
        self.marked.append(message_id)


def test_worker_leaves_row_unprocessed_when_cap_hit():
    opp = _opp(title="ML Fellow", org="Redwood", link="https://redwood.org/apply")
    guard = SpendGuard(1, clock=FakeClock("2026-07-05"))
    store = RecordingStore()
    extractor = StubExtractor(opp)
    rows = [dict(ROW, message_id="a"), dict(ROW, message_id="b")]
    raw = FakeRawStore([rows])

    def process_fn(row):
        return process_message(
            row, extractor=extractor, store=store, model_name="m", spend_guard=guard,
        )

    run_worker(raw, process_fn, batch_size=10, poll_interval=0,
               sleep=lambda _s: None, max_loops=1)

    assert raw.marked == ["a"]  # "b" left unprocessed — retries next period
    assert extractor.calls == 1
