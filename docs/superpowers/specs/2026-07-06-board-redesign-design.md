# The Board — restrained-paper noticeboard redesign

Approved 2026-07-06. Direction: community bulletin board × insider utility —
compact but not crowded. Presentation-layer only; no data/logic changes.

## Visual language
- Palette: warm paper. Page `#FAF9F6`; cards warm white w/ soft shadow, no
  borders; ink text `#1C1917`; amber accent (links, focus, subscribe, closing-
  soon); muted category colors for type badges (fellowship amber, job slate,
  grant green, event plum, course teal, others grey).
- Type: Fraunces (serif, via next/font) for site name + section headings +
  card titles; Geist for UI/body. "found in …" = uppercase letterspaced
  stamp-style label with dotted border.

## Structure (max-w-5xl)
1. Masthead row: name left; muted stats right ("N open · M closing soon ·
   K communities"); one muted tagline line with "add yours" install link
   (README install section).
2. Sticky control bar: search, type select, community select, remote/past
   toggles as compact pills; subscribe collapsed to a "Daily digest" button
   expanding an inline email input.
3. Board: sections "Closing this week" (amber accent, thin amber card top
   edge), "Open", "Past" (only when toggle on). CSS grid 3/2/1 cols,
   equal-height cards.
4. Footer: restyled, same links.

## Card (~5 lines, uniform height)
Top row: type badge + deadline chip ("closes Jul 12"; "3 days left" when ≤7).
Title (serif, 2-line clamp, links out). Muted org · location · remote line.
Bottom: stamp label "found in …".

## Non-goals / invariants
Data flow, filtering logic, status derivation, RSS, subscribe API, a11y
labels, tests for behavior all unchanged. No new runtime deps (font via
next/font). Tests updated only where markup assertions change; grouping gets
new tests.
