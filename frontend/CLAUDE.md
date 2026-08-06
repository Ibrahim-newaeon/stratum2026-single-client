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

- **Theme**: Claymorphism "vivid jewel clay" (2026-08) — dual mode, dark
  default. Indigo-obsidian clay surfaces with turquoise / radiant-gold /
  electric-violet accents and coral/amber/mint statuses; light mode is
  lavender porcelain. Token tables and the clay utility list live in
  `backend/docs/03-frontend/figma-theme.md`; `frontend/src/index.css`
  outranks everything.
- **Surfaces**: Molded-clay depth — layered outer drop shadow + inner
  top highlight + inner bottom shade (`.clay-raised`, `.clay-raised-sm`,
  `.clay-inset`), plush 20px+ radii, pill-shaped controls with a
  tactile press state (`.clay-pressable`), embossed/debossed type.
  Dashboard and console shells sit on `.bg-clay-ambient` (fixed
  studio-lighting radials) with glassy translucent topbars.

**History**: claymorphism replaced SuperAds blue (`#3B82F6`), which
replaced Opal Hotel gold (`#C2A670`), which replaced ink + ember
(`#FF5A1F`). Every predecessor's docs outlived its code — check
`frontend/src/index.css` before trusting any palette documented
anywhere, including this file.

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
