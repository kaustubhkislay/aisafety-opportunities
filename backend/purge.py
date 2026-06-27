"""Uninstall purge (Slice 5 / T3.4).

When an owner removes the bot from their server, everything ingested from that
server is deleted: published records (Airtable) and the verbatim raw rows
(RawStore). This is the data-ownership guarantee — uninstall means gone.
"""

import logging

log = logging.getLogger("purge")


def purge_server(airtable_store, raw_store, server_id: str) -> dict:
    """Delete all of a server's data from both stores. Returns the counts removed."""
    airtable = airtable_store.delete_by_server(server_id)
    raw = raw_store.delete_server(server_id)
    log.info("purged server %s: %d airtable record(s), %d raw row(s)", server_id, airtable, raw)
    return {"airtable": airtable, "raw": raw}
