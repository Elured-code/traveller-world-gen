# Release v2.1.2

**Date:** 2026-09-03  
**Branch:** v2.1 → main  
**Tests:** 3,476 (all pass)

## New features

### `traveller_system_schema.json` (issue #183)

Machine-readable JSON Schema 2020-12 contract for `TravellerSystem.to_dict()` / `to_json()` output.

- Covers all types not already in `traveller_world_schema.json`: `TravellerSystem` (top level), `Star`, `StarSystem`, `SystemOrbits`, `OrbitSlot`, and `StarZone`.
- `mainworld` and `OrbitSlot.detail` are referenced via `$ref` to `traveller_world_schema.json`; the two schema files are designed to be used together with the `referencing` library.
- `additionalProperties: false` throughout — any unrecognised field will produce a validation error.
- Dead-star and unusual-star types (`NS`, `PSR`, `BH`, `D`, `BD`) are included in the `spectral_type` and `luminosity_class` enums.
- Environment types (Nebula, Star Cluster, Anomaly) that fall back to a Giants-class star appear as normal spectral types with `special_notes` populated; their `$ref` to the world schema remains valid.
- Schema is shipped alongside `traveller_world_schema.json` in both `src/traveller_gen/` and `azure-api/traveller_gen/`.

### `tests/test_system_schema.py` extended

Full validation test suite already present prior to this release; confirms schema is correct against:

- 30+ normal-star seeds
- Unusual-star seeds covering BH, NS, PSR, Protostar, Nebula, Star Cluster, Anomaly
- Systems with eccentricity, inclination, and radiation zones enabled
- Negative tests: missing required fields and invalid enum values produce schema errors

## Bug fixes

None.

## Version policy

`traveller_system_schema.json` is a new schema contract, triggering a patch release per the CLAUDE.md version policy.
