from slackbot.ids import message_id, server_id, ts_to_iso


def test_server_id_prefixed():
    assert server_id("T0123ABC") == "slack:T0123ABC"


def test_message_id_composite():
    assert (
        message_id("T0123ABC", "C0456DEF", "1751852400.000200")
        == "slack:T0123ABC:C0456DEF:1751852400.000200"
    )


def test_ts_to_iso_utc():
    # 1751852400 = 2025-07-07T01:40:00+00:00 (verified with datetime.fromtimestamp)
    assert ts_to_iso("1751852400.000200") == "2025-07-07T01:40:00+00:00"
