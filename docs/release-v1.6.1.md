# Traveller World Generator — v1.6.1 Release Notes

**3032 tests pass. Pylint 10.00/10.**

Schema maintenance release — records the full set of generation options used
to produce a system or world alongside its seed, closing a reproducibility
gap where the same seed could appear to produce different output depending
on which options were selected in the UI. Also fixes a world-numbering
off-by-one past the mainworld.

---

## Generation Options on TravellerSystem and World (Reproducibility)

A saved system or world JSON already recorded its `seed`, but not the full
set of options used alongside it — so "the same seed" could look
non-reproducible if different options (Select MW, Biomass Rule, Independent
Government, Settlement Type, …) were selected than when the file was first
generated.

`TravellerSystem` gains eight new fields, stamped from `PipelineOptions` by
`run_detail_pipeline()` regardless of how far the pipeline actually runs:
`runaway_greenhouse`, `independent_government`, `optional_biomass`,
`optional_inhospitable`, `relic_tech`, `settlement_type`, `select_mainworld`,
`social_detail`. Together with the three existing flags (`nhz_atmospheres`,
`orbital_eccentricity`, `orbital_inclination`) and `seed`, a saved system now
records everything needed to reproduce it exactly.

`World` gains `settlement_type` — the only one of these options that
genuinely affects a standalone mainworld's own rolled values (the others
only ever apply via `attach_detail()`/`attach_tech_detail()`, which require
a `TravellerSystem`, so they're already covered there even in endpoints that
only return the mainworld). Stamped inside `generate_world()`.

In the desktop app, opening a saved JSON (File > Open JSON) now restores the
seed field and every option in the Options dialog to match the file, instead
of silently generating with whatever options this session last had
selected — so a subsequent Generate click actually reproduces the loaded
system or world.

---

## Bug Fix: World Numbering Past the Mainworld

Placeholder world names number bodies by position outbound from their star
(e.g. `"Homeworld A-2"`), but the mainworld's own orbit slot didn't consume
a number — so a world past the mainworld was numbered one lower than its
true ordinal position. The mainworld's slot now consumes a number like any
other body; it still displays no numbered suffix, but later worlds are
numbered correctly.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `settlement_type` | world top-level | string enum | Added, required. Settlement-type population DM applied when this world's population was generated. Default `"standard"`. |
| `runaway_greenhouse`, `independent_government`, `optional_biomass`, `optional_inhospitable`, `relic_tech`, `select_mainworld`, `social_detail` | `$defs.system_generation_options` (documentation only, system-endpoint responses) | boolean | Added |
| `settlement_type` | `$defs.system_generation_options` (documentation only, system-endpoint responses) | string enum | Added |

---

## Backward Compatibility

`World.from_dict()` and `TravellerSystem.from_dict()` default every new
field (`settlement_type` → `"standard"`, all new booleans → `False`) when
absent, so JSON saved before v1.6.1 loads without error.

---

## Tests

3032 tests pass (up from 3023): round-trip coverage for every new field on
both `TravellerSystem` and `World`, an end-to-end reproducibility test that
regenerates a system purely from its saved seed + options and asserts a
byte-identical UWP and tech profile, two gen-ui tests covering Open JSON
option restoration for both system and world JSON, and a regression test
for the mainworld world-numbering fix.
