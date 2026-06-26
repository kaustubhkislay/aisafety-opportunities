from types import SimpleNamespace

import pytest

from backend.extract import Extractor, ExtractionError


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


OPP_JSON = (
    '{"is_opportunity": true, "title": "ML Fellow", "org": "Redwood", '
    '"type": "fellowship", "deadline": "2026-08-01", '
    '"link": "https://redwood.org/apply", "location": "Remote", "remote": true}'
)


def test_extract_returns_opportunity():
    client = FakeClient([OPP_JSON])
    opp = Extractor(client, "qwen-test").extract("Apply: https://redwood.org/apply")
    assert opp is not None
    assert opp.title == "ML Fellow"
    assert opp.type == "fellowship"
    assert opp.remote is True


def test_out_of_vocab_type_coerced_to_other():
    client = FakeClient(['{"is_opportunity": true, "type": "workshop"}'])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp.type == "other"


def test_non_opportunity_returns_none():
    client = FakeClient(['{"is_opportunity": false}'])
    assert Extractor(client, "qwen-test").extract("thanks!") is None


def test_invalid_json_then_valid_retries():
    client = FakeClient(["not json at all", OPP_JSON])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp.title == "ML Fellow"
    assert client.chat.completions.calls == 2


def test_two_failures_raise():
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(ExtractionError):
        Extractor(client, "qwen-test").extract("x")


def test_content_none_raises():
    client = FakeClient([None, None])
    with pytest.raises(ExtractionError):
        Extractor(client, "qwen-test").extract("x")
