# Bulletin-board card restyle

Restyle opportunity cards to match the `bulletin_model_1.png` mockup direction:
varied paper styles and fixtures per card, urgency-colored fixtures, and
expandable descriptions. The board surface itself keeps its current cream
stipple and silver frame.

## Decisions (from design discussion)

- Cards are **collapsed by default**; a `+` button in the bottom-right expands
  the description inline, `−` collapses it. The hover tooltip is removed.
- Tags are **full-word hollow pills** — type and categories as bordered
  uppercase boxes (`[FELLOWSHIP] [TECH]`), replacing the colored type text and
  the single-letter T/G/O chips.
- **No handwriting fonts**; typography stays uniform.
- **Board background unchanged** (cream, not cork).
- Pure CSS paper styles + inline SVG fixtures. No image assets, no
  `Math.random`.

## Card look assignment

A small integer hash of `dedupKey` (fallback: title+link) deterministically
picks:

- **Paper style** (5): white graph, kraft, lined notebook, torn-edge white,
  sticky note (green/salmon variants — treated as one style with two tints).
- **Fixture** (3): pushpin (existing SVG, recolored), tape strip, paperclip.
- **Rotation**: one of a few fixed steps between −1.5° and +1.5°.

Same card → same look on every render (SSR-safe, test-safe).

## Urgency signalling

- Fixture color: **amber/orange** when `deriveStatus` is `closing-soon`,
  neutral silver/gray otherwise. The purple pin goes away.
- Status dot before the deadline text: red = closing soon, blue = dated
  deadline, green = rolling/no deadline.

## Card anatomy

Collapsed: fixture → title (2-line clamp, links out) → org / location /
remote → tag pills → footer (status dot + deadline text, `+` button
bottom-right).

Expanded: description appears between the org line and the tag pills.
Button toggles `+`/`−`, sets `aria-expanded`, per-card `useState`.

## Implementation surface

- `web/app/globals.css`: paper-style classes (gradients for graph/lined,
  tints for kraft/sticky, `clip-path` torn edge).
- `web/app/opportunity-list.tsx`: hash helper, `Fixture` components (Pin /
  Tape / Clip), pill rendering, expand state. `CATEGORY_CHIP` letters removed.
- Tests: hash stability/spread, expand/collapse (description hidden →
  visible → hidden), fixture urgency class, pill rendering; update existing
  chip tests.

## Verification

Unit suite + typecheck in CI; Playwright screenshots of the Vercel preview
(desktop + 375px mobile, collapsed and expanded) before merge.
