# Release v2.1.2

**Date:** 2026-09-03  
**Branch:** v2.1 → main  
**Tests:** 3,492 (all pass)

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

### Nebula and Star Cluster proper characterisation (issue #184)

Replaces the Giants-class fallback for Nebula and Star Cluster peculiar environments
with dedicated young Class V star generation (WBH p.219). Anomaly retains Giants fallback.

- `_generate_cluster_age()` rolls 1D×1D×50 Myr → Gyr (max 1.80 Gyr)
- `_generate_young_star_env()` produces a Class V primary with cluster age and a
  DM+1 bias toward hotter spectral types for very young clusters (age < 0.2 Gyr)
- Nebula systems return empty orbit lists (no formed worlds)
- Star Cluster systems generate worlds normally
- Anomaly systems return empty orbit lists (existing behaviour, now made explicit)

## Bug fixes

None.

## Version policy

`traveller_system_schema.json` is a new schema contract, triggering a patch release per the CLAUDE.md version policy.
