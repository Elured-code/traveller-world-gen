# Traveller World Generator — v2.1.0 Release Notes

**3271 tests pass (5 skipped). Pylint 10.00/10.**

Feature release adding speculative trade cargo generation (CRB pp.244-245),
freight lot generation (CRB p.239), multi-star tidal DM correction (WBH pp.105-106),
and cargo/freight UI in both the FastAPI web app and the gen-ui desktop app.

---

## New Feature — Speculative Trade Cargo Generation (Session 193, Issue #181)

A new module `traveller_world_cargo_gen.py` generates a cargo manifest of
available speculative trade lots at a mainworld, following CRB pp.244-245.

**What is generated:**

- All 36 D66 trade goods from CRB Table 7-2 are implemented.
- Common Goods (D66 11-16) are always available at any world with a starport.
- Trade Goods (D66 21-56) are available only when the world has at least one
  matching trade code.
- Illegal/black-market goods (D66 61-65) are excluded from normal cargo lists.
- Exotics (D66 66) are not yet available (requires random supplier roll).
- Worlds with Starport X return an empty manifest.

**Purchase price mechanics (CRB p.244):**

- Roll 3D (not 2D — corrected vs. earlier implementation).
- Add the largest matching purchase DM from the world's trade codes.
- Subtract the largest matching sale DM from the world's trade codes.
- Subtract supplier broker skill (assumed Broker 2).
- Clamp the result to [−3, 25] and look up the percentage of base price from
  the Modified Price table (ranging from 300% down to 15% of base).

**Output dataclasses:**

| Dataclass | Fields |
|-----------|--------|
| `CargoLot` | `d66`, `trade_good`, `tons`, `base_price_cr`, `purchase_dm`, `purchase_price_cr` |
| `CargoManifest` | `world_name`, `lots: List[CargoLot]`, `total_tons` |

Both support `.to_dict()` / `.to_json()` for serialisation.

**Public API:** `generate_cargo_manifest(world, rng=None) → CargoManifest`

---

## New Feature — Multi-Star Tidal DM (Session 193, Issue #179)

Worlds in multi-star systems now receive the correct tidal stress floor from
WBH pp.105-106: the stress floor is reduced by the number of additional stars
that the world orbits (beyond the first).

**New function:** `count_stars_orbited(orbit, stellar_system) → int` in
`traveller_orbit_gen.py`. Returns 1 for circumsecondary orbits; for primary-star
orbits returns 1 + the number of close/near/far secondaries whose orbit number
is less than the world's orbit number.

This is wired into `system_pipeline._apply_moon_tidal()` and
`fastapi._apply_mainworld_moon_tidal()` via the `num_stars_orbited` parameter.

---

## New Feature — Cargo UI in FastAPI Web App (Session 194)

A **Cargo** button appears in the seed/save bar of the FastAPI web UI after a
**Full** system generation. Clicking it:

1. Posts the mainworld JSON (plus the current seed) to `POST /api/cargo`.
2. Renders the resulting manifest as an inline table in a new **Cargo** tab.
3. The tab shows: D66, Trade Good, Tons, Base Cr, DM, Purchase Cr.

The button is disabled for non-Full generations (no world JSON is returned).
The `include_mw_card` response now includes `"mw_json"` (the mainworld
`World.to_dict()`) so the frontend can pass it to the cargo endpoint.

---

## New Feature — Freight Lot Generation (Session 195, Issue #180)

`generate_freight_lots(world, rng=None) → FreightManifest` implements CRB p.239
freight lot generation for a mainworld.

**How it works:**

- DMs are derived from population (−4 for pop ≤ 1; +2 for pop 6-7; +4 for pop ≥ 8),
  starport (A: +2, B: +1, E: −1, X: −3), tech level (≤ 6: −1; ≥ 9: +2), and
  travel zone (Amber: −2, Red: −6).
- Three tier rolls determine lot counts for Incidental (base_dm+2), Minor (base_dm),
  and Major (base_dm−4) freight using the Freight Traffic table.
- Each lot's tonnage is rolled: Incidental 1D t, Minor 1D×5 t, Major 1D×10 t.
- Mail: a 4th 2D+base_dm roll of 12+ yields 1D mail containers (5 t each).

**Output dataclasses:**

| Dataclass | Fields |
|-----------|--------|
| `FreightLots` | `incidental`, `minor`, `major` (int — lot count per tier) |
| `FreightManifest` | `world_name`, `lots: FreightLots`, `total_incidental_tons`, `total_minor_tons`, `total_major_tons`, `mail_containers`, `total_tons` |

Both support `.to_dict()` / `.to_json()` for serialisation.

**API:** `POST /api/freight` — same pattern as `/api/cargo`; accepts world JSON + optional seed.

---

## New Feature — Freight UI in FastAPI Web App (Session 195)

A **Freight** button appears in the seed/save bar alongside the Cargo button after
a Full system generation. Clicking it:

1. Posts the mainworld JSON (plus the current seed) to `POST /api/freight`.
2. Renders a compact tier-summary table in a new **Freight** tab.
3. The table shows: Tier (Incidental / Minor / Major / Mail), Lots, Total Tons.
4. The Mail row is only shown when mail containers > 0.

---

## New Feature — Freight UI in gen-ui Desktop App (Session 195)

A **Freight** button appears in the header row of both system mode and world-only
mode alongside the Cargo button. Clicking it opens a `FreightWindow` — a compact
native table with Tier / Lots / Total Tons columns (3–4 rows). Multiple freight
windows can be open simultaneously; `_freight_windows` keeps them alive against GC.

---

## New Feature — Cargo UI in gen-ui Desktop App (Session 194)

A **Cargo** button appears in the header row of both system mode and world-only
mode in the desktop app. Clicking it opens a `CargoWindow` — a native
`QTableWidget` with the same 6 columns as the web UI. Multiple cargo windows
can be open simultaneously. Results are seeded from `_pending_seed` for
reproducibility.

---

## API Change — `POST /api/cargo` (Session 193, upgraded Session 194)

Accepts a mainworld JSON object (as produced by `World.to_dict()` or `/api/world`)
plus an optional `seed` integer. Returns `CargoManifest.to_dict()`.

```json
{
  "world_name": "Regina",
  "lots": [
    {
      "d66": 11,
      "trade_good": "Common Electronics",
      "tons": 80,
      "base_price_cr": 20000,
      "purchase_dm": 1,
      "purchase_price_cr": 21000
    }
  ],
  "total_tons": 80
}
```

---

## Tests

3271 tests pass (5 skipped). New tests since v2.0.3:

- `tests/test_cargo_gen.py` — 85 tests (43 cargo + 42 freight): availability rules,
  price mechanics, starport-X empty manifest, trade code matching, DM accumulation
  (max not sum), supplier broker DM, price table clamping, serialisation roundtrip;
  freight lot counts, tier DMs, tonnage totals, mail mechanics, determinism, and
  `POST /api/freight` endpoint integration.
- `tests/test_orbit_gen.py` — 97 tests including new `count_stars_orbited`
  coverage: single-star system returns 1, primary orbit counts secondary stars
  with lower orbit numbers, circumsecondary orbit always returns 1.
