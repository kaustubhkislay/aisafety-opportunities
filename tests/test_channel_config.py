import json

from bot.channel_config import ChannelConfig


def test_explicit_private_channel_is_private():
    cfg = ChannelConfig(overrides={("s1", "c1"): "private"})
    assert cfg.channel_default("s1", "c1") == "private"


def test_unset_channel_uses_public_fallback_by_default():
    cfg = ChannelConfig()
    assert cfg.channel_default("s1", "c9") == "public"


def test_fallback_can_be_private_to_fail_closed():
    cfg = ChannelConfig(fallback="private")
    assert cfg.channel_default("s1", "cX") == "private"


def test_explicit_public_overrides_private_fallback():
    cfg = ChannelConfig(overrides={("s1", "c1"): "public"}, fallback="private")
    assert cfg.channel_default("s1", "c1") == "public"


def test_lookup_coerces_ids_to_str():
    cfg = ChannelConfig(overrides={("1", "2"): "private"})
    assert cfg.channel_default(1, 2) == "private"


def test_from_json_loads_overrides_and_fallback(tmp_path):
    path = tmp_path / "channels.json"
    path.write_text(json.dumps({
        "fallback": "private",
        "channels": {"s1:c1": "public", "s2:c2": "private"},
    }))
    cfg = ChannelConfig.from_json(str(path))
    assert cfg.channel_default("s1", "c1") == "public"
    assert cfg.channel_default("s2", "c2") == "private"
    assert cfg.channel_default("s9", "c9") == "private"  # fallback


def test_from_json_missing_file_defaults_to_all_public(tmp_path):
    cfg = ChannelConfig.from_json(str(tmp_path / "absent.json"))
    assert cfg.channel_default("s", "c") == "public"


def test_from_json_ignores_invalid_values(tmp_path):
    path = tmp_path / "channels.json"
    path.write_text(json.dumps({"channels": {"s1:c1": "bogus"}}))
    cfg = ChannelConfig.from_json(str(path))
    assert cfg.channel_default("s1", "c1") == "public"  # invalid -> falls back


def test_from_json_missing_file_warns(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="channel_config"):
        ChannelConfig.from_json(str(tmp_path / "absent.json"))
    assert any("public" in r.message for r in caplog.records)
