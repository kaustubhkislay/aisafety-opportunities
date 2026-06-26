from backend.store import RawStore


def test_cursor_roundtrip(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.get_cursor("10") is None

    store.set_cursor("10", "100")
    assert store.get_cursor("10") == "100"

    store.set_cursor("10", "200")  # upsert
    assert store.get_cursor("10") == "200"
