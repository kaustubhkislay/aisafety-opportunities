"""Uninstall purge (Slice 5 / T3.4).

When an owner removes the bot from their server, everything ingested from that
server is deleted: published records (Airtable) and the verbatim raw rows
(RawStore). This is the data-ownership guarantee — uninstall means gone.
"""

import logging

log = logging.getLogger("purge")


def purge_server(airtable_store, raw_store, server_id: str) -> dict:
    """Delete all of a server's data from both stores. Returns the counts removed."""
    # Collect the community's display name(s) before the raw rows go away —
    # source_servers attribution on merged records uses the name (or falls
    # back to the server id), and both must be scrubbed.
    names = {server_id}
    for row in raw_store.get_messages_by_server(server_id):
        if row.get("server_name"):
            names.add(row["server_name"])
    airtable = airtable_store.delete_by_server(server_id)
    scrubbed = airtable_store.remove_server_attribution(names)
    raw = raw_store.delete_server(server_id)
    log.info(
        "purged server %s: %d airtable record(s), %d attribution scrub(s), %d raw row(s)",
        server_id, airtable, scrubbed, raw,
    )
    return {"airtable": airtable, "scrubbed": scrubbed, "raw": raw}
