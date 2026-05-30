# Traveller World Generator — v1.4.1 Release Notes

**1686 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds `resource_rating` to `WorldPhysical` and
`system_generation_options` to `$defs`.

---

## Terrestrial Resource Rating (Session 87, issue #105)

Every Size 1+ world generated through `generate_world_physical()` now receives a
**Resource Rating** (WBH p.131). The rating is an integer in [2, 12] computed as:

```
2D − 7 + Size + density_DM
```

where `density_DM` is +2 for dense worlds (>1.12 g/cm³) and −2 for low-density
worlds (<0.50 g/cm³). When `attach_detail()` is subsequently called, biological
DMs (biomass, biodiversity, compatibility) are applied **deterministically** —
no additional dice roll — and the rating is re-clamped to [2, 12].

- Stored in `WorldPhysical.resource_rating: Optional[int]`
- Emitted in JSON as `"resource_rating"`
- Displayed on the world card after Escape Velocity

### Schema changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `resource_rating` | `WorldPhysical` | `integer [2, 12]` | Added |

---

## System Generation Options in Schema (Session 87, issue #122)

All system endpoints now accept `?nhz_atmospheres=true` (query string or JSON
body), completing the set of generation option flags alongside the existing
`orbital_eccentricity` and `orbital_inclination` parameters. The flag is stored
in `TravellerSystem.nhz_atmospheres` and reflected in all system JSON responses.

`generate_system_from_world()` and `generate_system_from_map()` also gained the
`nhz_atmospheres` parameter so the value is preserved end-to-end even when the
canonical UWP is fixed.

A new `$defs.system_generation_options` definition in the schema formally
documents the three boolean flags (`nhz_atmospheres`, `orbital_eccentricity`,
`orbital_inclination`) that, together with `seed`, allow byte-identical
reproduction of any system response.

### Schema changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `system_generation_options` | `$defs` | object (documentation) | Added |
| `seed` description | World schema | — | Updated to reference `$defs/system_generation_options` |

---

## Other Session 87 Changes

### Moon Eccentricity/Inclination in Orbit Table (issue #118)

Non-ring moons with non-zero eccentricity or inclination now display those values
in the `e/i` column of the system card orbit table
(e.g. `0.042/12.3°`). Previously the column was blank for all moon sub-rows.

### Gas Giant Mass and Density in Notes Column (issue #119)

The orbit table Notes column now shows the mass (M⊕) and derived density
(g/cm³) for gas giants. The density is computed from the rolled `gg_mass_earth`
and the SAH-decoded diameter.

### Gen-UI Onboarding Card (issue #84)

The startup placeholder text has been replaced with a styled card (`QFrame`)
explaining the three-step workflow, including a TravellerMap mode hint. The card
uses `QFrame#onboard-card` for automatic light/dark theme via the existing CSS
mechanism.
