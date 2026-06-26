from backend.store import RawStore

SAMPLE = {
    "server_id": "1",
    "channel_id": "10",
    "message_id": "100",
    "author_id": "5",
    "content": "Fellowship open, apply at https://example.org",
    "created_at": "2026-06-25T12:00:00+00:00",
}


def test_insert_then_read(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.insert_message(SAMPLE) is True

    rows = store.get_messages()
    assert len(rows) == 1
    assert rows[0]["message_id"] == "100"
    assert rows[0]["content"] == SAMPLE["content"]


def test_duplicate_message_id_is_ignored(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.insert_message(SAMPLE) is True
    assert store.insert_message(SAMPLE) is False  # same message_id

    assert len(store.get_messages()) == 1
