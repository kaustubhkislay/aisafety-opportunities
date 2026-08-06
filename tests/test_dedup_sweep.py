"""Tests for the daily dedup sweep (spec: 2026-08-06-dedup-sweep-design.md)."""

from backend.dedup_sweep import run_dedup_sweep


def rec(id, title, org, deadline="2026-09-01", date_seen="2026-08-01",
        servers="Alpha", status="active", dedup_key=None):
    return {
        "id": id,
        "fields": {
            "title": title,
            "org": org,
            "deadline": deadline,
            "date_seen": date_seen,
            "source_servers": servers,
            "status": status,
            "dedup_key": dedup_key or f"url:{id}",
        },
    }


class FakeBackend:
    def __init__(self, records):
        self.records = records
        self.updates = []
        self.deletes = []
        self.fail_delete_ids = set()

    def all(self):
        return self.records

    def update(self, record_id, fields):
        self.updates.append((record_id, fields))

    def delete(self, record_id):
        if record_id in self.fail_delete_ids:
            raise RuntimeError("airtable down")
        self.deletes.append(record_id)


class FakeJudge:
    """Returns a canned verdict per unordered title pair; records calls."""

    def __init__(self, same=()):
        self.same = {frozenset(pair) for pair in same}
        self.calls = []

    def judge(self, a, b):
        self.calls.append((a["title"], b["title"]))
        return frozenset((a["title"], b["title"])) in self.same


class FakeGuard:
    def __init__(self, budget):
        self.budget = budget

    def try_acquire(self):
        if self.budget <= 0:
            return False
        self.budget -= 1
        return True


# The prefilter needs 2 of 3 signals; same deadline + same org qualifies
# even with disjoint titles.
def pair():
    # A fresh copy per test: the sweep mutates survivor fields in place.
    return [
        rec("a", "ML Safety Fellowship", "Redwood", date_seen="2026-07-01"),
        rec("b", "Fellowship in ML Safety", "Redwood", date_seen="2026-07-20",
            servers="Beta"),
    ]


def test_no_candidates_no_calls_no_writes():
    backend = FakeBackend([
        rec("a", "ML Safety Fellowship", "Redwood", deadline="2026-09-01"),
        rec("b", "Biosecurity Grant", "OpenPhil", deadline="2026-10-15"),
    ])
    judge = FakeJudge()
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 0, "merged": 0}
    assert judge.calls == [] and backend.updates == [] and backend.deletes == []


def test_confirmed_pair_merges_into_older_record():
    backend = FakeBackend(pair())
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 1, "merged": 1}
    assert backend.updates == [("a", {"source_servers": "Alpha, Beta"})]
    assert backend.deletes == ["b"]


def test_missing_date_seen_counts_as_newer():
    a, b = rec("a", "ML Safety Fellowship", "Redwood", date_seen="2026-07-01"), \
        rec("b", "Fellowship in ML Safety", "Redwood", servers="Beta")
    del b["fields"]["date_seen"]
    backend = FakeBackend([b, a])  # newer record fetched first
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    run_dedup_sweep(backend, judge)
    assert backend.deletes == ["b"]
    assert backend.updates[0][0] == "a"


def test_judge_says_distinct_no_writes():
    backend = FakeBackend(pair())
    judge = FakeJudge()
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 1, "merged": 0}
    assert backend.updates == [] and backend.deletes == []


def test_spend_cap_exhausted_skips_remaining_pairs():
    records = pair() + [
        rec("c", "Governance Course", "BlueDot", deadline="2026-11-01"),
        rec("d", "Course on Governance", "BlueDot", deadline="2026-11-01",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge, spend_guard=FakeGuard(1))
    assert counts == {"pairs_judged": 1, "merged": 1}
    assert len(judge.calls) == 1  # second pair waits for tomorrow


def test_merged_loser_not_compared_again():
    records = pair() + [
        rec("c", "ML Safety Fellowship 2026", "Redwood", date_seen="2026-07-25",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("ML Safety Fellowship", "ML Safety Fellowship 2026"),
    ])
    counts = run_dedup_sweep(backend, judge)
    assert counts["merged"] == 2
    assert backend.deletes == ["b", "c"]
    # b was merged away; it must never appear in a later judgment
    losers_judged = [c for c in judge.calls if set(c) ==
                     {"Fellowship in ML Safety", "ML Safety Fellowship 2026"}]
    assert losers_judged == []


def test_survivor_accumulates_servers_across_merges():
    records = pair() + [
        rec("c", "ML Safety Fellowship 2026", "Redwood", date_seen="2026-07-25",
            servers="Gamma"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("ML Safety Fellowship", "ML Safety Fellowship 2026"),
    ])
    run_dedup_sweep(backend, judge)
    assert backend.updates[-1] == ("a", {"source_servers": "Alpha, Beta, Gamma"})


def test_expired_record_never_screened():
    records = [
        rec("a", "ML Safety Fellowship", "Redwood", status="expired"),
        rec("b", "Fellowship in ML Safety", "Redwood", servers="Beta"),
    ]
    backend = FakeBackend(records)
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    counts = run_dedup_sweep(backend, judge)
    assert counts == {"pairs_judged": 0, "merged": 0}


def test_delete_failure_logs_and_continues():
    records = pair() + [
        rec("c", "Governance Course", "BlueDot", deadline="2026-11-01"),
        rec("d", "Course on Governance", "BlueDot", deadline="2026-11-01",
            servers="Gamma", date_seen="2026-08-02"),
    ]
    backend = FakeBackend(records)
    backend.fail_delete_ids = {"b"}
    judge = FakeJudge(same=[
        ("ML Safety Fellowship", "Fellowship in ML Safety"),
        ("Governance Course", "Course on Governance"),
    ])
    counts = run_dedup_sweep(backend, judge)
    assert counts["merged"] == 1  # first merge failed, second landed
    assert backend.deletes == ["d"]


def test_revalidator_fires_only_on_merge():
    pings = []
    backend = FakeBackend(pair())
    run_dedup_sweep(backend, FakeJudge(), revalidator=lambda: pings.append(1))
    assert pings == []
    backend = FakeBackend(pair())
    judge = FakeJudge(same=[("ML Safety Fellowship", "Fellowship in ML Safety")])
    run_dedup_sweep(backend, judge, revalidator=lambda: pings.append(1))
    assert pings == [1]
