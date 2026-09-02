# Traveller World Generator — v2.1.1 Release Notes

**3463 tests pass (5 skipped). Pylint 10.00/10.**

Schema maintenance release adding `traveller_system_schema.json` — a
machine-readable JSON Schema 2020-12 contract for system-level API output.

---

## New — `traveller_system_schema.json` (Issue #183)

A JSON Schema 2020-12 file covering the full `TravellerSystem.to_dict()`
output shape returned by `GET /api/system`, `POST /api/full-system`, and
related endpoints.

The schema covers five types:

| Type | Schema location |
|---|---|
| `TravellerSystem` | Top-level object |
| `StarSystem` / `Star` | `$defs/Star` (array under `stars`) |
| `SystemOrbits` | `$defs/SystemOrbits` (under `orbits`) |
| `StarZone` | `$defs/StarZone` (values of `orbits.star_zones`) |
| `OrbitSlot` | `$defs/OrbitSlot` (items of `orbits.orbits` and `orbits.mainworld_orbit`) |

The `mainworld` property and `OrbitSlot.detail` reference
`traveller_world_schema.json` via `$ref` using the schema `$id` URI
(`https://example.com/traveller_world_schema.json`). Consumers should load
both files and register the world schema in a `referencing.Registry` before
validating system output.

### Schema constraints

- `additionalProperties: false` on all five types — extra fields are rejected.
- `Star.spectral_type` enum: A B F G K M O D BD NS PSR BH
- `Star.role` enum: primary companion close near far
- `OrbitSlot.world_type` enum: belt gas_giant terrestrial empty star
- `OrbitSlot.temperature_zone` enum: boiling hot temperate cold frozen
- `TravellerSystem.settlement_type` enum: standard long_settled well_settled backwater unsettled
- `OrbitSlot.radiation_zone` is only emitted when `true`; schema uses `const: true`.
- `Star.diameter_solar` minimum is 0 (not exclusive) — black holes emit 0.0.
- `Star.bh_schwarzschild_km` is optional; only present for BH primaries.

### Files

- `src/traveller_gen/traveller_system_schema.json` — canonical schema
- `azure-api/traveller_gen/traveller_system_schema.json` — azure-api copy
- `tests/test_system_schema.py` — 40 tests: schema integrity, structural checks,
  jsonschema validation for normal, multi-star, unusual-stars, dead-star, and
  environment-type systems

---

## Protostar Characterisation — WBH p.219 Full Rules (Session 197)

Replaces the Giants-class fallback for Protostar environment primaries with the
full WBH p.219 procedure.

- **Type:** Star Type table roll with DM+1; treated as Class V (not a Giant).
- **Mass:** ±50% variance from the Class V base value.
- **Diameter:** Class V base × `(1 + (2D−2) ÷ 10)`, giving a 1.0–2.0× range.
- **Luminosity:** recomputed from the modified diameter via the Stefan-Boltzmann formula.
- **Companion stars:** all other stars in a Protostar system are also generated as
  protostars, per WBH: "if the primary star is a protostar, any other stars in the
  system are also protostars."

Nebula, Star Cluster, and Anomaly environment types continue to use the Giants-class
fallback. Age cap (< 0.01 Gyr) and empty-world rule are unchanged.

---

## Bug Fixes (Session 197)

### Unusual Stars: environment-type primaries now display in Stars table

Nebula, Protostar, Star Cluster, and Anomaly environment types use a
Giants-class fallback star, making them visually indistinguishable from a
normal giant in the UI. The `special_notes` field is now included in the
star table data and rendered as a conditional **Note** column in
`system_card.html`. The column appears only when at least one star has a
note; normal systems are unaffected.

### Protostar environment: age capped at < 0.01 Gyr

Protostar primaries were receiving a normally-rolled system age (often
several Gyr). The age is now constrained to 0.001–0.009 Gyr, consistent
with the protostar threshold used elsewhere in the generator.

### Protostar environment: no worlds generated

Protostar systems are < 0.01 Gyr old — no fully formed worlds exist.
`generate_orbits()` now returns an empty `SystemOrbits` immediately for
protostar primaries, matching the empty-return path for dead stars with no
surviving planetary system.

---

## System Map — Unusual Star Glyph Rendering (Session 198)

The system map now renders protostar, neutron star, and pulsar primaries and companions
with distinctive visual glyphs instead of falling back to a tiny yellow dot or being
omitted entirely.

- **Protostar:** diffuse radial-gradient halo (4× star radius, opacity fades to transparent)
  drawn before the solid sphere. Zone AU scale floor raised to 5.0 AU for a readable
  display when no worlds orbit.
- **Neutron star (NS):** deep blue-white sphere (#88AAFF) with a tight corona glow
  (3× star radius, rapid opacity drop) to convey extreme surface temperature.
- **Pulsar (PSR):** same as NS plus a horizontal beam line (8× star radius each side,
  rounded caps, 55% opacity) representing the rotating radiation beam.

All three types are now guaranteed an arc zone even when they have no orbit slots
and no companion stars.

---

## Tests

3463 tests pass (5 skipped). New tests since v2.1.0:

- `tests/test_system_schema.py` — 44 tests (was 40) — added NS seed 38209 and PSR
  seed 9277 schema validation.
- `tests/test_unusual_stars_phases234.py` — added `TestProtostarCharacterization`
  (mass/diameter/luminosity range checks via `_star_properties`, primary age range,
  companion `age_gyr is None`, roundtrip); NS `subtype_none` and `luminosity_positive`;
  PSR `temperature_positive`, `subtype_none`, `luminosity_positive`.
- `tests/test_system_map.py` — three new classes: `TestProtostarMapRendering`,
  `TestNeutronStarMapRendering`, `TestPulsarMapRendering` — SVG-level assertions
  (gradient ids, beam line, circle count, cross-contamination negative tests).
