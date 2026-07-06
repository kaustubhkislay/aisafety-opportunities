from backend.store import RawStore


def test_cursor_roundtrip(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()

    assert store.get_cursor("10") is None

    store.set_cursor("10", "100")
    assert store.get_cursor("10") == "100"

    store.set_cursor("10", "200")  # upsert
    assert store.get_cursor("10") == "200"


def test_cursor_does_not_move_backwards(tmp_path):
    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.set_cursor("10", "200")
    store.set_cursor("10", "150")  # older snowflake -> must be ignored
    assert store.get_cursor("10") == "200"


def test_delete_server_also_clears_its_cursors(tmp_path):
    # Live T6.5+ finding: purge left cursors behind, so a reinstall skipped
    # the whole history and the board stayed empty. Uninstall means gone —
    # including the bookmarks.
    from backend.store import RawStore

    store = RawStore(str(tmp_path / "raw.db"))
    store.init_db()
    store.set_cursor("chan1", "100", server_id="srv1")
    store.set_cursor("chan2", "200", server_id="srv2")
    store.delete_server("srv1")
    assert store.get_cursor("chan1") is None  # purged server: cursor gone
    assert store.get_cursor("chan2") == "200"  # other servers untouched
