from datetime import datetime, timezone

from bot.scope import is_ingest_channel, oldest_allowed_snowflake


def test_only_opportunities_channels_ingest():
    assert is_ingest_channel("opportunities") is True
    assert is_ingest_channel("ai-opportunities") is True
    assert is_ingest_channel("OPPORTUNITIES-board") is True
    assert is_ingest_channel("general") is False
    assert is_ingest_channel("jobs") is False
    assert is_ingest_channel(None) is False


def test_custom_filter_via_needle():
    assert is_ingest_channel("jobs", needle="jobs") is True


def test_oldest_allowed_snowflake_is_two_weeks_back():
    now = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    snowflake = oldest_allowed_snowflake(now, 14)
    # Discord epoch math: snowflake >> 22 ms since 2015-01-01
    from datetime import timedelta
    ms = (now - timedelta(days=14) - datetime(2015, 1, 1, tzinfo=timezone.utc)) / timedelta(milliseconds=1)
    assert snowflake >> 22 == int(ms)
