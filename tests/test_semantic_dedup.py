from types import SimpleNamespace

from backend.semantic_dedup import DuplicateJudge, find_candidates, make_semantic_matcher
from backend.spend import SpendGuard


def _rec(rid, **fields):
    return {"id": rid, "fields": fields}

# The live case that motivated this module: one announcement cross-posted to
# two communities, with the extractor picking a different URL from the same
# message each time (info page vs application form).
HERON_A = dict(
    title="Heron AI Security Research Fellowship (Autumn 2026)",
    org="Heron",
    deadline="2026-07-08",
    dedup_key="url:heronsec.ai/researchfellowship",
    status="open",
)
HERON_B = dict(
    title="Heron AI Security Research Fellowship (Sept-Nov 2026)",
    org="Heron AI Security",
    deadline="2026-07-08",
    dedup_key="url:heron.fillout.com/fellowship",
    status="open",
)


def test_find_candidates_matches_same_opportunity_with_different_links():
    records = [_rec("rec1", **HERON_A)]
    assert find_candidates(HERON_B, records) == records


def test_find_candidates_ignores_exact_key_and_expired_records():
    same_key = _rec("rec1", **{**HERON_A, "dedup_key": HERON_B["dedup_key"]})
    expired = _rec("rec2", **{**HERON_A, "status": "expired"})
    assert find_candidates(HERON_B, [same_key, expired]) == []


def test_find_candidates_needs_more_than_a_shared_deadline():
    # Deadlines cluster (end of month, etc.) — a date alone is not a signal
    # strong enough to spend an LLM call on.
    other = _rec(
        "rec1",
        title="MATS Winter Cohort",
        org="MATS",
        deadline=HERON_B["deadline"],
        dedup_key="url:matsprogram.org/apply",
        status="open",
    )
    assert find_candidates(HERON_B, [other]) == []


def test_find_candidates_caps_the_candidate_list():
    records = [_rec(f"rec{i}", **HERON_A) for i in range(10)]
    assert len(find_candidates(HERON_B, records, limit=3)) == 3


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        content = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def test_judge_returns_true_on_same_opportunity():
    client = FakeClient(['{"same_opportunity": true}'])
    assert DuplicateJudge(client, "qwen-test").judge(HERON_B, HERON_A) is True


def test_judge_returns_false_on_distinct_opportunity():
    client = FakeClient(['{"same_opportunity": false}'])
    assert DuplicateJudge(client, "qwen-test").judge(HERON_B, HERON_A) is False


def test_judge_treats_persistently_malformed_output_as_not_same():
    # Fail-soft: a broken judge must never suppress a record — worst case is
    # a duplicate on the board, same as before this module existed.
    client = FakeClient(["not json"])
    assert DuplicateJudge(client, "qwen-test").judge(HERON_B, HERON_A) is False
    assert client.chat.completions.calls == 2  # one retry, then give up


class StubBackend:
    def __init__(self, records):
        self._records = records

    def all(self):
        return self._records


class StubJudge:
    def __init__(self, verdict):
        self._verdict = verdict
        self.calls = []

    def judge(self, new_fields, existing_fields):
        self.calls.append((new_fields, existing_fields))
        return self._verdict


def test_matcher_returns_judged_duplicate():
    record = _rec("rec1", **HERON_A)
    judge = StubJudge(True)
    matcher = make_semantic_matcher(StubBackend([record]), judge)
    assert matcher(HERON_B) == record
    assert len(judge.calls) == 1


def test_matcher_returns_none_when_judge_rejects():
    judge = StubJudge(False)
    matcher = make_semantic_matcher(StubBackend([_rec("rec1", **HERON_A)]), judge)
    assert matcher(HERON_B) is None


def test_matcher_skips_judging_when_spend_cap_hit():
    guard = SpendGuard(cap=1)
    assert guard.try_acquire()  # exhaust the day's budget
    judge = StubJudge(True)
    matcher = make_semantic_matcher(StubBackend([_rec("rec1", **HERON_A)]), judge, spend_guard=guard)
    assert matcher(HERON_B) is None
    assert judge.calls == []


def test_matcher_fails_soft_when_backend_errors():
    class BrokenBackend:
        def all(self):
            raise RuntimeError("airtable down")

    matcher = make_semantic_matcher(BrokenBackend(), StubJudge(True))
    assert matcher(HERON_B) is None
