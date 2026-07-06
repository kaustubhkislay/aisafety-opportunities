from backend.store import RawStore


def _msg(mid):
    return {
        "server_id": "1",
        "channel_id": "10",
        "message_id": mid,
        "author_id": "5",
        "content": f"content {mid}",
        "created_at": "2026-06-25T12:00:00+00:00",
    }


def test_claim_and_mark_processed(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.insert_message(_msg("100"))
    store.insert_message(_msg("101"))

    claimed = store.claim_unprocessed(10)
    assert [r["message_id"] for r in claimed] == ["100", "101"]

    store.mark_processed("100")

    remaining = store.claim_unprocessed(10)
    assert [r["message_id"] for r in remaining] == ["101"]


def test_claim_respects_limit(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    for mid in ("100", "101", "102"):
        store.insert_message(_msg(mid))

    assert len(store.claim_unprocessed(2)) == 2


def test_is_processed_reflects_tombstone(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.insert_message(_msg("m1"))
    assert store.is_processed("m1") is False
    store.mark_processed("m1")
    assert store.is_processed("m1") is True
    assert store.is_processed("unknown") is False
