# Frontend — Design Context

Moved out of the root `CLAUDE.md` so it loads only when working under
`frontend/`. Full token table lives in
`backend/docs/03-frontend/figma-theme.md`.

## Users

Marketing agencies managing multiple client accounts across ad
platforms. Extended sessions, professional setting, data-heavy
workflows.

## Brand Personality

**Bold, intelligent, premium.** Sophisticated power through restraint.
Bloomberg terminal meets luxury brand.

## Aesthetic Direction

- **Theme**: SuperAds — dual mode, dark default. Source of truth
  `design-system-template/themes/superads.xml`. Palette hexes,
  data-series slots and geometry are in
  `backend/docs/03-frontend/figma-theme.md`; that file is the copy to
  read, and `frontend/src/index.css` outranks it.
- **Surfaces**: Elevation by drop-shadow across a three-tier stack
  (page → surface → elevated). `--bg-glass` translucency is available
  for overlay surfaces.

> **Grounding.** The template extracted fonts, accents, gradients and the
> light/dark structure from the real source, but its README flags
> **surfaces, radii, spacing, shadows and motion timings as inferred** —
> the upstream `shared/styles.css` was never provided. Those values are a
> best estimate, not measured, and should be corrected if the original
> stylesheet turns up.

**History**: this replaced an Opal Hotel gold theme (`#C2A670` on black),
which had itself replaced the original ink + ember figma theme
(`#FF5A1F`). Earlier revisions described ember long after the code had
moved to gold — check `frontend/src/index.css` before trusting any
palette documented anywhere.

## Design Principles

1. **Quiet authority** — Power through precision, not noise
2. **Information density without clutter** — Strong hierarchy, not hidden data
3. **Premium materiality** — Tinted neutrals, subtle depth, no flat gray
4. **Decisive contrast** — Bold type hierarchy, 1.5x+ ratio between steps
5. **Earn every pixel** — Every element serves the user's task
6. **Action-first home** — The dashboard is a triage queue, not a
   dashboard. Sort by intervention required.

## Component contract

The dashboard composes from typed primitives, not bespoke surfaces.
**Reuse before building** — `ls frontend/src/components/primitives/` for
the current set; each ships with a `*.test.tsx`, and ARIA + keyboard
support are first-class, not afterthoughts.
