"""Airtable calls retry with backoff on rate limits / transient 5xx."""

import pytest

from backend.airtable import PyairtableBackend


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


class _Err(Exception):
    def __init__(self, status_code):
        self.response = _Resp(status_code)


class FlakyTable:
    def __init__(self, failures, status=429):
        self.calls = 0
        self._failures = failures
        self._status = status

    def create(self, fields):
        self.calls += 1
        if self.calls <= self._failures:
            raise _Err(self._status)
        return {"id": "rec1"}

    def all(self, **kw):
        self.calls += 1
        if self.calls <= self._failures:
            raise _Err(self._status)
        return []


def test_retries_429_with_backoff_then_succeeds():
    slept = []
    backend = PyairtableBackend(FlakyTable(failures=2), sleep=slept.append)
    assert backend.create({"title": "X"}) == "rec1"
    assert len(slept) == 2
    assert slept[1] > slept[0]  # exponential backoff


def test_gives_up_after_max_attempts():
    backend = PyairtableBackend(FlakyTable(failures=99), sleep=lambda s: None)
    with pytest.raises(Exception):
        backend.create({"title": "X"})


def test_non_retryable_errors_propagate_immediately():
    table = FlakyTable(failures=99, status=422)
    backend = PyairtableBackend(table, sleep=lambda s: None)
    with pytest.raises(Exception):
        backend.create({"title": "X"})
    assert table.calls == 1  # no retries on 4xx (except 429)
