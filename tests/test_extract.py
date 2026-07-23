import json
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


def test_persistent_malformed_output_returns_none(caplog):
    # Deterministic malformed output is a poison pill: retrying forever would
    # burn the spend cap. After the retry, treat it as not-an-opportunity.
    import logging

    client = FakeClient(["nope", "still nope"])
    with caplog.at_level(logging.WARNING, logger="extract"):
        assert Extractor(client, "qwen-test").extract("x") is None
    assert client.chat.completions.calls == 2
    assert any("malformed" in r.message for r in caplog.records)


def test_content_none_returns_none():
    client = FakeClient([None, None])
    assert Extractor(client, "qwen-test").extract("x") is None


def test_transport_errors_still_raise():
    # Network/provider failures are transient: they must propagate so the
    # worker leaves the row unprocessed and retries later.
    class _BoomCompletions:
        def create(self, **kwargs):
            raise ConnectionError("provider down")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_BoomCompletions()))
    with pytest.raises(ConnectionError):
        Extractor(client, "qwen-test").extract("x")


def test_boolish_strings_are_coerced():
    client = FakeClient(['{"is_opportunity": "true", "title": "X", "remote": "false"}'])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp is not None and opp.remote is False


def test_null_bools_are_coerced():
    client = FakeClient(['{"is_opportunity": true, "title": "X", "remote": null}'])
    opp = Extractor(client, "qwen-test").extract("x")
    assert opp is not None and opp.remote is False


def test_prompt_includes_todays_date():
    # The model cannot resolve "July 22nd" to the right year without knowing
    # the current date (live bug: resolved to 2024 -> instantly expired).
    captured = {}

    class _Capture:
        def create(self, **kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=OPP_JSON))]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Capture()))
    Extractor(client, "m", today_fn=lambda: "2026-07-06").extract("x")
    assert "2026-07-06" in captured["system"]


def test_categories_are_validated_and_multi():
    client = FakeClient(['{"is_opportunity": true, "title": "X", "categories": ["tech", "gov"]}'])
    opp = Extractor(client, "m").extract("x")
    assert opp.categories == ["tech", "gov"]


def test_ops_is_a_valid_category():
    client = FakeClient(['{"is_opportunity": true, "title": "X", "categories": ["ops"]}'])
    opp = Extractor(client, "m").extract("x")
    assert opp.categories == ["ops"]


def test_bogus_categories_fall_back_to_other():
    client = FakeClient(['{"is_opportunity": true, "title": "X", "categories": ["banana"]}'])
    opp = Extractor(client, "m").extract("x")
    assert opp.categories == ["other"]


def test_missing_categories_default_to_other():
    client = FakeClient(['{"is_opportunity": true, "title": "X"}'])
    opp = Extractor(client, "m").extract("x")
    assert opp.categories == ["other"]


def test_description_passes_through():
    client = FakeClient([json.dumps({
        "is_opportunity": True, "title": "ML Fellow", "org": "Org",
        "type": "fellowship", "deadline": None, "link": "https://example.org",
        "location": None, "remote": True, "categories": ["tech"],
        "description": "A 12-week research fellowship for early-career ML engineers.",
    })])
    opp = Extractor(client, "m").extract("msg")
    assert opp.description == "A 12-week research fellowship for early-career ML engineers."


def test_missing_description_defaults_to_none():
    client = FakeClient([json.dumps({
        "is_opportunity": True, "title": "T", "org": "O", "type": "job",
        "deadline": None, "link": None, "location": None, "remote": False,
        "categories": ["other"],
    })])
    opp = Extractor(client, "m").extract("msg")
    assert opp.description is None
