# deferred-features.md — Deferred and out-of-scope features

Features explicitly noted as not yet implemented. WBH page references are to
the Sept 2023 edition. Remove a row when a feature is fully implemented.

| Feature | WBH pages | Status / blocking dependency |
|---------|-----------|------------------------------|
| Moon orbit adjacency DMs (3 of 4) | p. 56 | Blocked by moon orbital positions. Only the `orbit_number < 1.0` DM is applied. The other three require knowledge of companion MAO zones, Close/Near exclusion zones, and outermost Far-star slot proximity. |
| Basic Rotation Rate tidal DMs | p. 103 | Not started. `_roll_day_length()` applies only the age DM. Additional DMs (orbit number, star luminosity/mass, moon presence) require moon orbital positions. Blocked by issue #16 (moon orbit placement). Tracked in GitHub issue #11. |
| Secondary world independent government (Case 2) | p. 162 | Not started. Roll `2D-7 + Population` when government ≠ 6. All secondaries currently use the Case 1 dependent table. |
| Secondary world classifications | p. 163 | Not started. Colony, Farming, Freeport, Military Base, Mining Facility, Penal Colony, Research Base — trade-code-style labels for secondaries. |
| Tidal effects — residual DMs | pp. 105–107 | Partially implemented. Eccentricity DM implemented Session 50. Remaining: moon-size DM in star-lock (blocked by moon orbital positions), planet-locked-to-moon check (same block), multi-star DM (simplified to 1 star). |
| World physical detail beyond basic | pp. 78–130 | Partially done. Diameter, density, composition, mass, gravity, escape velocity, axial tilt, and day length are in `traveller_world_physical.py`. Atmosphere detail (Phases 1–5) in `traveller_world_gen.py`. Hydrographic detail Phase 1 (surface liquid percentage) in `traveller_hydro_detail.py` (Session 37). Remaining: seismic stress, tidal heating, hydrographic composition beyond surface liquid % (ocean type, ice caps, depth), native life ratings. |
| Atmosphere taints, exotic/corrosive/insidious subtypes, altitudes, gas composition | pp. 82–93 | Phases 2–5 done (Sessions 32–35). Remaining: Biologic taint (p. 83) blocked on native-life ratings (pp. 127–131). |
| Atmospheric retention check (escape velocity × temperature K) | p. 88 | Needs mean temperature in K (pipeline tracks category strings only). Formula: `v_e² × 8 / T_K`; gas retained if `gas_escape_value ≤ world_escape_value`. Gas-mix sub-range DMs also need K. Tracked in GitHub issue #44. |
| Runaway greenhouse (optional rule) | p. 79 | Not started. Needs a mean-temperature value (not just the category). Pipeline currently rolls temperature *category* only. |
| Post-stellar special circumstances | pp. 219+ | Not started. White dwarfs (`D`) and brown dwarfs (`BD`) are detected and labelled during stellar generation but not physically characterised. Neutron stars, black holes, and pulsars not yet modelled. |
