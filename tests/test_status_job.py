from datetime import date

from backend.status_job import derive_status, run_status_job


class FakeBackend:
    """Stand-in for PyairtableBackend: holds records and records update calls."""

    def __init__(self, records):
        self._records = records  # list of {"id": str, "fields": dict}
        self.updates = []  # list of (record_id, fields)

    def all(self):
        return self._records

    def update(self, record_id, fields):
        self.updates.append((record_id, fields))


TODAY = date(2026, 6, 26)


def test_derive_status_no_deadline_is_active():
    assert derive_status(None, TODAY) == "active"
    assert derive_status("", TODAY) == "active"


def test_derive_status_past_is_expired():
    assert derive_status("2026-06-25", TODAY) == "expired"


def test_derive_status_today_is_closing_soon():
    assert derive_status("2026-06-26", TODAY) == "closing-soon"


def test_derive_status_within_seven_days_inclusive_is_closing_soon():
    assert derive_status("2026-07-03", TODAY) == "closing-soon"  # +7 days


def test_derive_status_beyond_seven_days_is_active():
    assert derive_status("2026-07-04", TODAY) == "active"  # +8 days


def test_derive_status_malformed_deadline_is_active():
    assert derive_status("not-a-date", TODAY) == "active"
    assert derive_status("2026-13-99", TODAY) == "active"


def test_run_status_job_updates_only_changed_records():
    records = [
        {"id": "r1", "fields": {"deadline": "2026-06-20", "status": "active"}},   # -> expired (changed)
        {"id": "r2", "fields": {"deadline": "2026-06-28", "status": "closing-soon"}},  # unchanged
        {"id": "r3", "fields": {"deadline": "2026-09-01", "status": "expired"}},  # -> active (changed)
        {"id": "r4", "fields": {"deadline": None, "status": "active"}},  # unchanged
    ]
    backend = FakeBackend(records)
    counts = run_status_job(backend, TODAY)

    assert {rid for rid, _ in backend.updates} == {"r1", "r3"}
    assert ("r1", {"status": "expired"}) in backend.updates
    assert ("r3", {"status": "active"}) in backend.updates
    assert counts == {"active": 2, "closing-soon": 1, "expired": 1, "changed": 2}


def test_run_status_job_no_writes_when_nothing_changed():
    records = [
        {"id": "r1", "fields": {"deadline": "2026-06-20", "status": "expired"}},
        {"id": "r2", "fields": {"deadline": None, "status": "active"}},
    ]
    backend = FakeBackend(records)
    counts = run_status_job(backend, TODAY)
    assert backend.updates == []
    assert counts["changed"] == 0


def test_run_status_job_handles_missing_status_field():
    records = [{"id": "r1", "fields": {"deadline": "2026-06-20"}}]  # no status key yet
    backend = FakeBackend(records)
    run_status_job(backend, TODAY)
    assert backend.updates == [("r1", {"status": "expired"})]
