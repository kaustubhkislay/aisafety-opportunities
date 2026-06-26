# Slice 2 — Extraction pipeline — design spec

Turns raw Discord messages (captured by Slice 1) into structured, deduped opportunity records in Airtable. This is the "intelligence" half of the system: filter → extract → safety-gate → dedup → publish to the canonical store.

Status: design approved 2026-06-25, pre-implementation. Builds on Slice 1 (`backend/store.py` `RawStore`, branch `feat/discord-ingestion-slice` / PR #1).

## Core idea

A background worker polls the raw store for unprocessed messages. A free keyword pre-filter discards obvious non-opportunities; survivors go to a single hosted open-weights LLM call (Qwen/Kimi via an OpenAI-compatible API) that classifies *is-this-an-opportunity*, extracts structured fields, and normalizes away personal contact info (PII) in one pass. Confirmed opportunities pass a rule-based link-safety gate, are deduped against existing records by a stable key (updating in place when a newer version appears), and are upserted into Airtable — the canonical store the future website reads from. Each raw message is marked processed only after it completes; failures leave it unprocessed so it retries.

## Locked decisions

- **Run model:** background worker over unprocessed rows (decoupled from ingestion; restart-safe; reprocessing = reset the processed marker). Separate process (`python -m backend.worker`), not an in-app asyncio task.
- **LLM runtime:** hosted open-weights model via an OpenAI-compatible client. `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` from env (default a Qwen instruct model; swappable to Kimi or another provider — OpenRouter / Together / Fireworks / Moonshot). Not the Anthropic SDK.
- **Pre-filter:** free keyword/heuristic, tuned to over-include. The open model runs only on candidates.
- **Extraction:** one LLM call does classify + extract + PII-normalize. Output constrained to JSON (OpenAI-compatible `response_format`), validated against a Pydantic schema, one retry on an invalid/short response.
- **PII:** handled inside the extraction prompt — personal contact details (personal email/phone/DM handle) are replaced with the official application link/email and dropped, not a separate pass.
- **Link-safety:** deterministic rule-based gate (allowlist / denylist / brand-new-domain + shortener + lookalike heuristic). No external reputation API for v1. Suspicious items are withheld (not written) and flagged for review.
- **Dedup:** key-based exact match. Stable key = normalized application URL, else a hash of `org+title+deadline`. New key inserts; existing key updates the record. Semantic / near-duplicate dedup deferred.
- **Canonical store:** Airtable, upsert by stable key via the REST API (`pyairtable`). `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME` from env.
- **Stack:** Python via uv (same project as Slice 1); deterministic stages (filter, link-safety, dedup) are plain Python with no LLM.

## Data flow

```
raw store (messages WHERE processed_at IS NULL)
   |  worker claims a batch
   v
[keyword pre-filter, free] --not a candidate--> mark processed, done
   | candidate
   v
[open-model extract]  classify is_opportunity + fields + PII-normalize
   |   (OpenAI-compatible call; JSON -> Pydantic validate; retry once on miss)
   | is_opportunity?
   +-- no --> mark processed, done
   | yes
   v
[link-safety gate]  suspicious/brand-new/known-bad link? --> withhold + flag, mark processed
   | clean
   v
[dedup-with-update]  stable key -> insert new OR update existing record
   v
Airtable upsert --> mark processed
```

## Components

Each is independently understandable and testable.

- **Worker** (`backend/worker.py`) — poll loop: `claim_unprocessed(limit)` → run each message through the pipeline → `mark_processed`. A pipeline error (LLM/Airtable failure) leaves the row unprocessed so it retries on the next loop. Configurable batch size and poll interval from env.
- **Pre-filter** (`backend/filter.py`) — `is_candidate(content: str) -> bool`: true when the message contains a URL **and** opportunity keywords (apply, deadline, fellowship, grant, hiring, internship, cohort, stipend, scholarship, role, position, RFP, …). Pure, free, over-includes by design.
- **Extractor** (`backend/extract.py`) — `extract(content: str) -> Opportunity | None`. Builds the OpenAI-compatible request (system + user prompt, `response_format` JSON schema), calls the configured model, parses + validates against a Pydantic `Opportunity` model, retries once on invalid JSON. Returns `None` when `is_opportunity` is false. The client (base URL, key, model) is injectable for tests.
- **Link-safety** (`backend/linksafety.py`) — `is_safe(url: str) -> (bool, reason: str)`. Allowlist of known-good domains, denylist, and heuristics for shorteners / lookalike / freshly-registered-looking domains. Pure function. When unsafe, the worker records the message id + url + reason via logging and does **not** write to Airtable; a human-facing review queue/UI is deferred (out of scope).
- **Dedup** (`backend/dedup.py`) — `stable_key(opp) -> str` only: normalized application URL, else a hash of `org+title+deadline`. The insert-vs-update decision lives in the Airtable client (find-by-key), keyed on this value.
- **Airtable client** (`backend/airtable.py`) — `upsert(opp, dedup_key)`: find the record whose `dedup_key` field matches, update it if present else create a new one. REST via `pyairtable`; client injectable for tests.
- **Pydantic models** (`backend/models.py`, extending Slice 1) — `Opportunity` with the canonical fields.

## Store change (Slice 1's `RawStore`)

Backward-compatible additions to `backend/store.py`:
- Add a nullable `processed_at` column to `messages` (added in `init_db()` if absent; existing rows default NULL) plus an index on `processed_at`.
- `claim_unprocessed(limit: int) -> list[dict]` — rows where `processed_at IS NULL`, oldest first, capped at `limit`.
- `mark_processed(message_id: str) -> None` — set `processed_at` to now.

Reprocessing history = `UPDATE messages SET processed_at = NULL` (a one-liner / admin helper), after which the worker re-runs everything through an improved pipeline.

## Data model (Airtable record)

`title`, `org`, `type`, `deadline`, `link`, `location`, `remote`, `status`, `source_server`, `source_channel`, `raw_text`, `date_seen`, `dedup_key`, `llm_model` (14 fields).

- LLM-extracted: `title, org, type, deadline, link, location, remote`
- Provenance (from the raw message): `source_server, source_channel, raw_text, date_seen`
- System-set: `dedup_key` (upsert lookup key), `status` (deadline lifecycle, set by the daily status job — Slice 1 spec), `llm_model`

`type` vocabulary: `job | internship | fellowship | grant | event | course | reading-group | other`.
`status` (deadline lifecycle, from Slice 1 spec): `active | closing-soon | expired` — re-evaluated by a scheduled job (Slice 1 spec's daily status job; not built here).

## Extraction contract

The model receives the message text and returns JSON matching the `Opportunity` schema. Prompt instructs it to:
- set `is_opportunity` false for chatter, questions, reactions, or anything without a concrete opening/deadline/application path;
- extract `title, org, type (from the fixed vocab), deadline (ISO or null), link (the official application URL), location/remote`;
- **PII-normalize**: replace personal contact (personal email/phone/DM handle) with the official application link/email; never emit an individual's private contact details;
- prefer the application URL as `link`; null it if none is present.

Invalid JSON or schema-invalid output → one retry with the same input; second failure → leave the row unprocessed and log (no silent drop).

## Error handling

- **LLM failure** (timeout, 5xx, rate limit): row stays unprocessed → retried next loop. Same recovery shape as Slice 1's success-gated cursor.
- **Airtable write failure**: row stays unprocessed → retried.
- **Invalid model JSON**: one retry, then leave unprocessed + log.
- **Withheld by link-safety**: mark processed (it was handled — deliberately not published) and record the flag; does not block the row forever.
- No message is silently dropped: every row is either marked processed (filtered out, not-an-opportunity, withheld, or published) or left for retry.

## Testing

Each unit tested in isolation with fixtures:
- pre-filter: message → candidate boolean table (positive + negative cases);
- extractor: mocked OpenAI-compatible HTTP (fake transport) → schema-valid object; invalid-JSON path → retry then `None`/unprocessed;
- link-safety: url → allow/withhold table (allowlisted, denylisted, shortener, lookalike, plain);
- dedup: same opportunity twice → one record; newer version (changed deadline) → existing record updated, not duplicated;
- Airtable client: mock REST → create-when-absent, update-when-present;
- worker: fixture raw rows end-to-end → correct Airtable upserts and `mark_processed`; a forced LLM/Airtable failure leaves the row unprocessed.

## Build order (incremental)

1. `RawStore` additions: `processed_at` column + `claim_unprocessed` + `mark_processed`.
2. Pre-filter (pure).
3. `Opportunity` Pydantic model + extractor (mocked client).
4. Link-safety (pure).
5. Dedup key + insert/update logic.
6. Airtable client (mocked REST).
7. Worker wiring the stages end-to-end.

## Out of scope (this slice)

Semantic / embedding-based dedup; external link-reputation APIs (Safe Browsing); the public website + RSS + search (Slice 3); the email digest; the daily deadline-status job (specified in Slice 1, built later); multi-language handling; backoff/queue infrastructure beyond "leave unprocessed and retry."

## Open risks to watch

- Open-model JSON reliability varies by model/size — the schema-validate-and-retry guard plus a capable-enough default model (mid-size Qwen instruct) mitigates; monitor the retry/failure rate and bump the model if needed.
- Airtable free-tier record cap (~1,200/base) and rate limits — the first wall; Postgres migration path noted in Slice 1 spec.
- Link-safety heuristics will have false positives/negatives — withheld items are flagged for review rather than hard-deleted; tune the lists over time.
- Per-token cost is low but unbounded if the pre-filter under-filters — monitor candidate rate; tighten keywords if the open model runs too often.
