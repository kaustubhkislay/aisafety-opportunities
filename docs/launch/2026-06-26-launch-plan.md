# aisafety-opportunities — Launch Implementation Plan

> **For agentic workers:** This plan is executed by a checkpointed `/loop` (see
> `docs/launch/PROGRESS.md`). One task per pass. `[auto]` tasks are implemented via
> `superpowers:test-driven-development`; `[ckpt]` tasks stop the loop for the human.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the project from three open PRs to a launch-ready, deployed AI-safety
opportunities board with edge privacy, a daily status job, an email digest, and legal pages.

**Architecture:** Thin Discord bot → ingest API → raw SQLite store → extraction worker
(filter → LLM extract → link-safety → dedup-upsert) → Airtable → Next.js ISR site + RSS.
Privacy is enforced at the edge (in the bot, before transmit) and via retraction/purge.

**Tech Stack:** Python 3.12 (FastAPI, discord.py, pydantic, openai, pyairtable) managed
with `uv`; Next.js 16 / React 19 / Tailwind 4 on Vercel, tested with Vitest; Airtable as
the canonical store; GitHub Actions for CI.

## Global Constraints

- Python: `requires-python >=3.12`; deps via `uv` from `pyproject.toml`; tests `uv run pytest` (config: `pythonpath=["."]`, `asyncio_mode=auto`).
- Web: Node + npm in `web/`; tests `npm test` (= `vitest run`); build `npm run build` (`next build`).
- Secrets: never commit tokens/keys. All config via env vars; `.env.example` carries blank placeholders only.
- Privacy invariant: excluded/private messages MUST be dropped in the bot **before** any network transmit. No silent-drop without a log line.
- License/transparency: MIT, single public monorepo, open-source bot AND backend.
- Type vocabulary (canonical): `job | internship | fellowship | grant | event | course | reading-group | other`.

## Execution dependency note

`backend/` and `bot/` are empty (`.gitkeep`) on `main`. Their real modules land only when
M1 merges PRs #1/#2 and the website PR #3. Therefore:

- **M0–M1 are fully specified below** (actionable against `main` / the existing PRs today).
- **M2–M6 `[auto]` tasks are task briefs** — files, interfaces, concrete test cases, and
  acceptance criteria. Each `/loop` pass expands its brief into line-level TDD steps against
  the *then-current* merged tree (the only point at which the upstream signatures are real).
  This is deliberate, not a placeholder: writing final code against unmerged internals would
  be guesswork. The brief is the contract; the loop writes the code.

---

## M0 — Foundation

### Task T0.1: CI workflow `[auto]`

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a `ci` workflow with two jobs (`backend`, `web`) triggered on `pull_request` and `push` to `main`. Later PRs inherit it once rebased (T0.2).

- [ ] **Step 1: Create the workflow**

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Python 3.12
        run: uv python install 3.12
      - name: Skip if no backend code
        id: guard
        run: |
          if [ -f pyproject.toml ]; then echo "run=true" >> "$GITHUB_OUTPUT"; else echo "run=false" >> "$GITHUB_OUTPUT"; fi
      - name: Tests
        if: steps.guard.outputs.run == 'true'
        run: uv run --group dev pytest -q

  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - name: Skip if no web app
        id: guard
        run: |
          if [ -f package.json ]; then echo "run=true" >> "$GITHUB_OUTPUT"; else echo "run=false" >> "$GITHUB_OUTPUT"; fi
      - uses: actions/setup-node@v4
        if: steps.guard.outputs.run == 'true'
        with:
          node-version: 20
      - name: Install
        if: steps.guard.outputs.run == 'true'
        run: npm ci
      - name: Test
        if: steps.guard.outputs.run == 'true'
        run: npm test
      - name: Build
        if: steps.guard.outputs.run == 'true'
        run: npm run build
```

The per-job guards let the workflow pass on `main` (where `pyproject.toml`/`web/package.json`
are absent) and run for real on the feature PRs once rebased.

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add backend (pytest) + web (vitest/build) GitHub Actions"
```

- [ ] **Step 4: Open the PR for this branch** `[ckpt-light]`

This plan lives on `docs/launch-plan`. Open a PR to `main`:
```bash
gh pr create --base main --head docs/launch-plan --title "docs+ci: launch plan, ledger, CI" --body "Launch plan, progress ledger, and CI workflow."
```
Merge after the CI job goes green on the PR. (Merging this first puts the workflow on `main`.)

### Task T0.2: Branch sequencing `[auto]` (drives `[ckpt]` merges in M1)

**Goal:** make the three feature PRs CI-checked and cleanly mergeable in dependency order.

- [ ] **Step 1: After T0.1 is on `main`, rebase PR #1**

```bash
git fetch origin
git switch feat/discord-ingestion-slice
git rebase origin/main          # picks up .github/workflows/ci.yml
git push --force-with-lease
```
Expected: CI runs on PR #1; `backend` job runs pytest (pyproject now present on the branch), `web` job skips.

- [ ] **Step 2: Confirm #2 is based on #1, #3 on main**

```bash
git merge-base --is-ancestor feat/discord-ingestion-slice feat/extraction-pipeline && echo "#2 contains #1"
git merge-base --is-ancestor origin/main feat/public-website && echo "#3 off main"
```
Expected: both lines print. (If #2 is not an ancestor-descendant of #1, rebase #2 onto #1.)

- [ ] **Step 3: Record the merge order in the ledger**

Order is: PR #1 → (rebase #2 onto updated main) → PR #2 → PR #3. Note it in `PROGRESS.md` T1.x rows.

---

## M1 — Merge slices 1–3  `[ckpt]`

These are human review gates; the loop stops and asks. For each PR the human (with loop
assistance preparing the diff summary): reviews, ensures CI is green, merges, then the loop
rebases the next branch onto the new `main`.

- **T1.1** Review + merge **PR #1** (bot ingestion). Then `git fetch && rebase feat/extraction-pipeline onto origin/main`.
- **T1.2** Review + merge **PR #2** (extraction). Then confirm `feat/public-website` still merges clean.
- **T1.3** Review + merge **PR #3** (website).

Loop assist per gate: post a summary of changed files, test count, and any SDD-ledger
caveats; run `gh pr checks <n>` and report; on human "merge", run `gh pr merge <n> --squash`.

After M1, `main` contains `bot/`, `backend/`, `web/` real code — M2+ briefs can be expanded.

---

## M2 — Slice 4: daily status/expiry job  `[auto]`

### Task T2.1: status job

**Files:**
- Create: `backend/status_job.py`, `tests/test_status_job.py`
- Reference: `backend/airtable.py` (existing `AirtableStore`), `backend/models.py`.

**Interfaces:**
- Produces: `derive_status(deadline: str | None, today: date) -> Literal["active","closing-soon","expired"]` and `run_status_job(store, today) -> dict[str,int]` (counts per status) that reads all records, recomputes `status`, and writes back only changed ones.
- Consumes: `AirtableStore` list + update methods (exact names resolved at expand time from the merged `backend/airtable.py`).

**Concrete test cases (write these as failing tests first):**
- `deadline=None` → `active`; `deadline` in the past → `expired`; within 7 days inclusive → `closing-soon`; >7 days → `active`. (Mirror `web/lib/status.ts` semantics exactly, UTC-day based.)
- Malformed/non-ISO deadline → `active` and a logged warning (folds in the "deadline ISO validation" deferred item).
- `run_status_job` updates only records whose computed status differs from stored; returns correct counts; makes zero writes when nothing changed.

**Acceptance:** `uv run pytest tests/test_status_job.py -q` green; status semantics identical to the website's `deriveStatus`; scheduling is left to M6 (cron on the backend host).

---

## M3 — Slice 5: installable bot + edge privacy (trust core)  `[auto]` + one `[ckpt]`

### Task T3.1: edge exclusion

**Files:** Create `bot/exclusion.py`, `tests/test_exclusion.py`. Modify the bot message
handler (`bot/coordinator.py` / `bot/messages.py`) to call exclusion **before** `Forwarder.forward`.

**Interfaces:**
- Produces: `should_exclude(content: str, channel_default: Literal["public","private"]) -> tuple[bool, str]` — returns `(True, reason)` for any message containing a tag from the vocabulary `{[private], school-specific, internal, do-not-share}` (case-insensitive, word-ish match) OR when `channel_default == "private"`.

**Concrete test cases:**
- Each tag, alone and mid-sentence, → excluded with that reason.
- `channel_default="private"` → excluded even with no tag (reason `private-channel`).
- Clean message in a public channel → not excluded.
- Exclusion happens before transmit: with a recording fake `Forwarder`, an excluded message yields zero `forward` calls and one log line.

**Acceptance:** privacy invariant holds in tests (no transmit on exclude); reason always logged.

### Task T3.2: per-channel public/private config

**Files:** Create `bot/channel_config.py`, `tests/test_channel_config.py`. Persist the map
(server/channel → default) captured at install; expose a lookup the handler uses for T3.1.

**Interfaces:** `channel_default(server_id, channel_id) -> "public" | "private"` with a
configurable global fallback (default `public`, overridable to `private` for fail-closed servers).

**Concrete test cases:** explicit private channel → `private`; unset channel → fallback;
fallback override respected.

### Task T3.3: retraction

**Files:** Create `bot/retraction.py` + handler wiring, `tests/test_retraction.py`; a backend
delete path in `backend/airtable.py` keyed by `dedup_key`/source message.

**Interfaces:** a lock-emoji reaction OR an edit adding `[private]` → emits a retraction signal
→ backend deletes the corresponding record from Airtable (and thus the site).

**Concrete test cases:** lock-emoji on a forwarded message → delete called once with the right
key; `[private]` edit → same; non-lock emoji / unrelated edit → no delete; retraction for an
unknown message → no-op, logged.

### Task T3.4: uninstall purge + owner view

**Files:** Create `backend/purge.py`, `tests/test_purge.py`; an owner-visibility read endpoint.

**Interfaces:** `purge_server(store, server_id) -> int` deletes all of a server's records and
raw rows; `ingested_for(server_id) -> list` returns what was ingested (for owner transparency).

**Concrete test cases:** purge removes only the target server's records (others untouched),
returns count; owner view lists that server's records only.

### Task T3.5: Discord OAuth app + install flow  `[ckpt]`

Human registers the Discord application (OAuth2, bot scopes: read message history + the
authorized channels), provides client id/secret + bot token via env. Loop then wires the
install/authorize redirect and channel-selection capture (`install_config`). **Loop stops
here and lists the exact Discord Developer Portal steps + the env keys to fill.**

---

## M4 — Slice 6: email digest

### Task T4.1: subscribe + store + digest + unsubscribe  `[auto]`

**Files (web):** subscribe form component + `web/app/api/subscribe/route.ts` + tests.
**Files (backend):** `backend/digest.py`, `tests/test_digest.py`; subscriber store (Airtable
table or a dedicated store).

**Interfaces:** `POST /api/subscribe {email}` validates + stores (idempotent on email);
`build_digest(opps, since) -> {html, text}` composes the period's active opportunities;
every send includes a working unsubscribe link/token.

**Concrete test cases:** valid email stored once (duplicate is a no-op); invalid email → 400;
digest body lists only `active`/`closing-soon` items added since `since`, sorted soonest-first;
unsubscribe token validates and removes the subscriber; empty period → no send.

### Task T4.2: email sender account  `[ckpt]`

Human creates a Resend (or Buttondown) account, adds the API key + from-address to env. Loop
then wires the sender behind `build_digest` and a scheduled trigger (cron in M6).

---

## M5 — Slice 7: legal pages

### Task T5.1: privacy + terms  `[auto]`

**Files:** `web/app/privacy/page.tsx`, `web/app/terms/page.tsx`, footer wiring (replace the
placeholder slot in the layout/footer); a small test that the footer links render and the
routes resolve.

**Content requirements (must reflect what is actually built):** edge exclusion + tag
vocabulary; retraction; uninstall purge + owner visibility; that opportunity data is public by
design and only curated fields (never `raw_text`) are shown; subscriber-email handling +
unsubscribe; contact for takedown. Plain English.

**Acceptance:** routes render; footer links point to them; copy matches the implemented
behavior (no promised-but-unbuilt claims).

---

## M6 — Deploy / launch infra

### Task T6.4: LLM spend cap  `[auto]`

**Files:** `backend/spend.py`, `tests/test_spend.py`; integrate into `backend/extract.py` /
`backend/worker.py`.

**Interfaces:** a counter/guard that tracks per-period token-or-call spend and **refuses
extraction once a configured cap is hit** (env: e.g. `LLM_DAILY_CALL_CAP`), logging the stop.

**Concrete test cases:** under cap → extraction proceeds; at/over cap → extraction skipped and
logged, worker leaves the row unprocessed (retries next period); counter resets per period.

### Tasks T6.1 / T6.2 / T6.3 / T6.5  `[ckpt]`

- **T6.1 Airtable:** create the base + `Opportunities` table (schema = the 13-field worker
  contract) + an automation that POSTs `/api/revalidate?secret=…` on record change. Provide
  `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`, `REVALIDATE_SECRET`.
- **T6.2 Backend host:** deploy the always-on container (Railway/Fly), set env, add cron for
  the status job (M2) and digest job (M4).
- **T6.3 Vercel:** deploy `web/`, set env vars, wire the Airtable automation to the live
  revalidate URL.
- **T6.5 End-to-end smoke:** install the bot into a server you control; post a sample
  opportunity; confirm it flows to the live site; test a retraction and an excluded message.
  *The live demo is the pitch.*

---

## Self-Review

- **Spec coverage:** every milestone in the design doc maps to a task here (M0 CI/sequencing;
  M1 merges; M2 status job; M3 edge exclusion/config/retraction/purge/OAuth; M4 digest; M5
  legal; M6 deploy + spend cap). Slack (M7) intentionally dropped.
- **Deferred fixes folded in:** deadline ISO validation → T2.1; link-safety heuristics →
  noted for T3.x pipeline hardening; cheap-filter URL requirement → revisit at filter touch;
  spend cap → T6.4.
- **Placeholders:** M0/M1 are concrete (code + commands). M2–M6 are explicitly *briefs by
  design* (upstream code not yet on `main`), each with files, interfaces, and concrete test
  cases — expanded to line-level by the loop pass at execution time.
- **Type consistency:** status semantics pinned to `web/lib/status.ts`; type vocabulary copied
  verbatim from the spec; dedup key + 13-field contract referenced, not redefined.
