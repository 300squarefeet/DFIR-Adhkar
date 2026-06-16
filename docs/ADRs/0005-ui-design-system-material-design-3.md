# 0005. UI design system — Material Design 3, dense + dark default

- Status: Accepted
- Date: 2026-06-16
- Deciders: project lead
- Tags: design-system, frontend, accessibility

## Context and Problem Statement

The original Phase 0 spec (§6) adopted shadcn/ui + Tailwind + custom tokens with a SOC-focused dense dark aesthetic. After approval, the project lead requested Material Design 3 alignment, citing visual cohesion with the current Google product family as the goal.

Two M3 adoptions are possible:
- (a) Full M3 consumer aesthetic (Google Health, Fitbit, Wallet) — light-default, generous padding, calm tonal surfaces, big rounded cards.
- (b) M3-aligned dense dark variant — same token system / shape system / type scale, but with density overrides comparable to GitHub Primer v15+, Tines, or Hunters.

## Decision Drivers

- Visual coherence with the current Google / Material design language.
- Preserved information density — SOC analysts process hundreds of alerts per shift; padding loss = backlog growth.
- Preserved dark default — long-shift ergonomics in dim NOC / monitor-wall environments.
- FIRST.org TLP color taxonomy is mandated and must override any system color semantics.
- Keyboard accessibility must remain class-leading.
- Bundle size + cold-start budget.

## Considered Options

1. **M3-aligned dense dark, layered on Tailwind + Radix primitives** (chosen). Keep our tooling, swap tokens, shape, typography, motion, icon family to M3 vocabulary. Override density and color semantics where domain demands.
2. Full M3 (Material Web Components / MUI v6) — Google Health-style, consumer aesthetic — rejected. Density loss unfit for SOC analyst workflow; Material Web's Lit runtime adds React integration friction and SSR risk; MUI v6 with experimental M3 carries 200 KB+ bundle weight and lock-in.
3. Reject M3, retain original shadcn-only direction — rejected. Project lead explicitly requested M3 alignment.

## Decision Outcome

Adopt M3 tokens (Material Theme Builder export → CSS variables), M3 shape system, M3 typography scale, Material Symbols Rounded icon family (variable font with fill/wght/grad/opsz axes), and M3 button variants (filled, tonal, outlined, text, error-filled). Layer them on Tailwind v4 (`@theme` maps M3 tokens to utility classes) and shadcn/Radix primitives (Radix gives the ARIA + keyboard nav that stock Material Web does not match).

Diverge from stock M3 in three explicit areas:

### Density overrides

| Component | Stock M3 | Adhkar |
|---|---|---|
| TopAppBar height | 64 px | 48 px |
| Navigation drawer item height | 56 px | 36 px |
| List row height (Phase 2+ data grids) | 56 px | 32 px |
| Default card padding | 16–24 px | 12 px |
| Dense list grid | 8 px | 4 px sub-grid available |

Reasons documented inline in the design-system Storybook docs.

### Dark default

M3 dark surface tones are the default; `light` theme is opt-in (toggle in TopAppBar). Surface containers honor M3's tonal-elevation hierarchy:
- `surface-container-lowest`
- `surface-container-low`
- `surface-container` (default card surface)
- `surface-container-high`
- `surface-container-highest`

### Domain color overrides

Severity 1–4 ramp and FIRST.org TLP white/green/amber/amber-strict/red **override** M3's `error` / `warning` / `tertiary` color slots wherever those domain semantics are displayed. Domain semantics outrank theme semantics — full stop. The M3 `error` slot is still used for destructive button + form-validation errors.

## Positive Consequences

- Visually identifies as a contemporary M3 product without compromising analyst velocity.
- Token system enables clean per-customer rebranding (cf. NOTICE / Apache-2.0 permissive trademark policy).
- Material Symbols Rounded covers every icon need (variable font, single dependency).
- Radix primitives keep accessibility — DropdownMenu, Dialog, Popover, ScrollArea, Tabs — that M3 specifies behaviorally but Material Web implements incompletely.
- Tailwind v4 `@theme` maps M3 tokens to utilities (`bg-surface-container-high`, `text-on-surface`, `rounded-shape-large`).

## Negative Consequences

- Material Symbols font adds ~50 KB (variable font subset; lazy-loaded via `font-display: swap`).
- Diverging density from stock M3 means design-system docs must explicitly call out the deltas so reviewers don't push us back to stock spec.
- M3 evolves continuously; we will track release notes and refresh tokens annually (added to Phase 10 hardening backlog).

## Links

- Material Theme Builder: https://m3.material.io/theme-builder
- M3 specification: https://m3.material.io
- Material Symbols: https://fonts.google.com/icons
- Radix UI primitives: https://www.radix-ui.com
- Supersedes the UI direction baked into spec §6 v1. Subsequent edits to the spec will reflect the M3 vocabulary.
