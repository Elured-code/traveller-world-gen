# deferred-features.md — Deferred and out-of-scope features

Features explicitly noted as not yet implemented. WBH page references are to
the Sept 2023 edition. Remove a row when a feature is fully implemented.

| Feature | WBH pages | Status / blocking dependency |
|---------|-----------|------------------------------|
| Secondary world independent government (Case 2) | p. 162 | Not started. Roll `2D-7 + Population` when government ≠ 6. All secondaries currently use the Case 1 dependent table. |
| Secondary world classifications | p. 163 | Not started. Colony, Farming, Freeport, Military Base, Mining Facility, Penal Colony, Research Base — trade-code-style labels for secondaries. |
| Tidal effects — multi-star DM | pp. 105–106 | Partially implemented. Eccentricity DM (Session 50), moon-size DM in star-lock, and planet-locked-to-moon check (Session 51) implemented. Remaining: multi-star DM (`DM − number of stars orbited` when > 1). Currently simplified to `num_stars_orbited=1`. Full support requires counting stars orbited per world. |
| World physical detail beyond basic | pp. 78–130 | Partially done. Diameter, density, composition, mass, gravity, escape velocity, axial tilt, day length (`traveller_world_physical.py`). Atmosphere detail Phases 1–5 (`traveller_world_gen.py`). Hydrographic detail Phase 1 — surface liquid % (`traveller_hydro_detail.py`, Session 37). Seismic stress (RSS, Tidal Seismic Stress, Tidal Stress Factor, TSS, seismic temperature, Sessions 56 + 60). Surface tidal amplitude in metres (Session 58, issue #68). Biomass rating (Session 61). Optional biomass rule — oxygen atmosphere minimum biomass 1 (Session 61). Remaining: hydrographic composition beyond surface liquid % (ocean type, ice caps, depth). Biocomplexity rating (WBH p.130) — deferred; `has_biologic_taint` hook exists in `generate_biomass_rating()` but biologic taint generation is currently dormant (biologic results reroll). |
| Atmosphere taints, exotic/corrosive/insidious subtypes, altitudes, gas composition | pp. 82–93 | Phases 2–5 done (Sessions 32–35). Remaining: Biologic taint (p. 83) — biologic subtype results currently reroll; `generate_biomass_rating()` has `has_biologic_taint` parameter ready for when this is implemented. |
| Atmospheric retention check (escape velocity × temperature K) | p. 88 | Needs mean temperature in K (pipeline tracks category strings only). Formula: `v_e² × 8 / T_K`; gas retained if `gas_escape_value ≤ world_escape_value`. Gas-mix sub-range DMs also need K. Tracked in GitHub issue #44. |
| Runaway greenhouse (optional rule) | p. 79 | Not started. Needs a mean-temperature value (not just the category). Pipeline currently rolls temperature *category* only. |
| Post-stellar special circumstances | pp. 219+ | Not started. White dwarfs (`D`) and brown dwarfs (`BD`) are detected and labelled during stellar generation but not physically characterised. Neutron stars, black holes, and pulsars not yet modelled. |
