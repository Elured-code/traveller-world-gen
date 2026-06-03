# Traveller World Generator — v1.5.0 Release Notes

**1906 tests pass. Pylint 10.00/10.**

Sessions 88–98. Adds a FastAPI server, mainworld selection, secondary social
pipeline, secondary world classifications, population detail, FastAPI web UI
split, settlement type population modifiers, full web UI options parity,
save-to-file, and assorted gen-ui and compliance fixes.

---

## FastAPI Web UI — Full Options Parity + Save (Session 98)

The Full System web page now matches every generation option in the desktop app.

**New controls on system.html:**
- NHZ Atmospheres, Biomass Rule, Runaway Greenhouse, Independent Government
  checkboxes (enabled only when Detail or Full is checked).
- Population Detail checkbox (standalone — always available).
- Settlement Type dropdown (Standard / Long-settled / Well-settled / Backwater /
  Unsettled).

**Save functionality (both pages):** after generation a Save group appears in
the seed badge row with download buttons. system.html offers HTML, Text, and
JSON; index.html offers HTML and JSON. Downloads are re-fetched using the
original seed and options, so the file exactly matches what was displayed.

**Backend:** `fastapi/helpers.py` gains `parse_settlement_type()` and
`parse_population_detail()`; system endpoints 3, 5, 7, and 8 in `fastapi/app.py`
now accept and propagate both params. Console output gains timestamps via a
`logging.config.dictConfig` call at module import.

1906 tests pass. No schema changes.

---

## Settlement Type Population Modifiers (Session 97, issue #128)

The gen-ui Options dialog now includes a **Settlement type** group with five
radio buttons. Selecting a type shifts the mainworld population roll up or
down based on the world's atmosphere:

| Type | Effect |
|------|--------|
| Standard (default) | No modifier |
| Long-settled | +1 to +3 (best on breathable atmospheres) |
| Well-settled | −1 to +2 |
| Backwater | −5 to +1 |
| Unsettled | −7 to −4 |

The result is always clamped to the standard 0–10 population range. Not
applied to worlds fetched from TravellerMap. 22 new tests. 1906 tests pass.

---

## FastAPI Web UI — Two-Page Split (Session 96)

The FastAPI web UI is now two separate full-width pages:

- **Mainworld Only** (`/static/index.html`) — generates a mainworld with
  atmosphere and hydrographic detail only (no physical or biological cards).
  Output matches the gen-ui app with System detail and Population detail both
  unchecked.
- **Full System** (`/static/system.html`) — generates a star system with
  tabbed results. The **Mainworld** tab shows the full world card (all detail
  cards via `detail=true`); the **System** tab shows the orbital survey. Detail,
  Full, and Select MW options are available.

Both pages have nav links to each other in the header.

`/api/world/{name}/card` (FastAPI) now accepts a `detail` query parameter:
- `detail=false` (default) — minimal path; atmosphere and hydrographic detail
  only.
- `detail=true` — full path; generates the complete star system, runs
  `attach_detail()`, and returns the mainworld card with all cards shown.

### gen-ui Options dialog

The "System detail" option is now a plain checkbox matching the size of all
other options. Previously it was rendered as a `QGroupBox` title indicator,
which was smaller and differently styled. The sub-options widget is hidden
(not just disabled) when "System detail" is unchecked.

---

## Population Detail — PCR, Urbanisation, Major Cities (Session 95, issue #95)

New `traveller_world_social_detail` module implements the WBH Social
Characteristics checklist for population. When the "Population detail" option
is enabled in the gen-ui Options dialog, every inhabited mainworld and secondary
world receives a full population profile.

**Population Concentration Rating (PCR)** — a 0–9 score indicating how
concentrated the population is. Extremely Dispersed (0) means no major cities;
Extremely Concentrated (9) means the entire population occupies one settlement.
The PCR is rolled on a 1D table with DMs for world size, tech level, government
code, and trade codes.

**Urbanisation** — the percentage of the total population living in towns or
cities of 10,000+ people. Rolled on a 2D range table with DMs including PCR,
population code, and tech level. Some DMs carry hard floors or ceilings on the
result (e.g. Population 9 worlds have a minimum urbanisation of 18 + 1D%).

**Major cities** — determined by one of five cases based on population code and
PCR. Case 1 (PCR 0) produces no major cities; Cases 2–4 handle small or highly
concentrated populations; Case 5 applies the WBH formula
`ceil(2D − PCR + urb% × 20 / PCR)` for large, moderately concentrated worlds.
Individual city populations are allocated from a common pool using the WBH chunk
algorithm (cycling through cities, rolling 1D chunks until the pool is exhausted).

**Population profile string** — a five-part compressed summary: `P-p-C-%-M`
(population code, P value, PCR, urbanisation %, major city count). Example: a
Population 7 world with P=1, PCR=3, 39% urbanisation, and 7 major cities records
`7-1-3-39-7`.

The new `PopulationDetail` object is serialised via `World.to_dict()` and
restored by `World.from_dict()`. The same procedure applies to secondary worlds
(`WorldDetail.population_detail`). A dedicated "Population detail" card appears
on the mainworld HTML display below the Habitability card.

### Schema changes (v1.5.0)

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `population_detail` | World | object (optional) | Added |
| `population_detail.total_population` | World | integer | Added |
| `population_detail.p_value` | World | integer 1–9 | Added |
| `population_detail.pcr` | World | integer 0–9 | Added |
| `population_detail.pcr_label` | World | string | Added |
| `population_detail.urbanisation_pct` | World | integer 0–100 | Added |
| `population_detail.urban_population` | World | integer | Added |
| `population_detail.major_city_count` | World | integer | Added |
| `population_detail.major_city_total_population` | World | integer | Added |
| `population_detail.cities` | World | array of City objects | Added |
| `population_detail.population_profile` | World | string | Added |

The Population detail card appears after Biological detail on the Mainworld tab.
All card section headings are now rendered in bold.

23 new tests in `TestPopulationDetail`. 1884 tests pass.

### Bug fixes

- Fixed `AttributeError: 'World' object has no attribute 'physical'` raised when
  Population detail was enabled. The `attach_population_detail()` function was
  referencing `mw.physical` instead of the correct `mw.size_detail` attribute.

---

## Secondary World Classifications (Session 94, issue #18)

WBH p.163 defines seven roles a secondary world can play in its system. The code
now checks eligibility and rolls in table order, assigning at most one
classification per inhabited secondary world or moon.

| Classification | Code | Requirements | Roll |
|---|---|---|---|
| Colony | Cy | Secondary Pop 5+, Gov 6 | Automatic |
| Farming | Fa | HZ, Atm 4–9, Hyd 2+ | Automatic |
| Freeport | Fp | Secondary Gov 0–5, TL 8+ | 10+; DM−2 if MW starport A/B |
| Military Base | Mb | MW TL 8+, not Poor, Gov 6 | 12+; DM+4 if MW has bases; DM+2 if secondary Gov 6 |
| Mining Facility | Mi | MW Industrial, secondary Pop 2+ | Belt: 6+; Terrestrial: 10+ |
| Penal Colony | Pe | MW TL 9+, LL 8+, Gov 6 | 10+; DM+2 if secondary LL 8+ |
| Research Base | Rb | MW Pop 6+, TL 8+, not Poor | 10+; DM+2 if MW TL 12+ |

`WorldDetail` gains `classification: Optional[str]` (emitted in JSON when set).
The code is also appended to `WorldDetail.trade_codes` so it appears in profile
displays. `_apply_classification()` is called from `generate_system_detail()`,
`_moon_detail()`, and `apply_secondary_social()`. `system_body_table()` appends
`[Classification Name]` to orbit and moon rows.

14 new tests in `TestSecondaryWorldClassification`. 1861 tests pass.

---

## Secondary Social Generation After Mainworld Selection (Session 92 cont.)

After mainworld selection gives the mainworld its real UWP, `apply_secondary_social()`
re-applies social data to every secondary WorldDetail using the correct mainworld
baseline. This includes re-rolling the population cap (`mw_pop − 1D`), and
regenerating population, government, law level, TL, spaceport, and trade codes for
all secondary orbit slots and their moons. The satellite WorldDetail created by
`attach_detail()` (which used placeholder values) is also synced.

---

## Mainworld Selection (Session 92, issue #125)

`select_mainworld(system, rng)` in `traveller_system_gen.py` scores all terrestrial
candidates and promotes the highest-scoring world to mainworld (WBH pp.155–156).
Scoring weights: Habitability ×50, Native sophonts ×50, Resource rating ×30,
Best refuelling ×10 (GG satellite = 2, hydro ≥ 5 = 1, else 0). On a 3D roll of
18 a candidate is selected randomly instead. When a secondary wins, the new
mainworld is regenerated via `generate_mainworld_at_orbit()` and the old
mainworld is demoted to a `WorldDetail`. Returns `True` when a swap occurred.

`WorldDetail` gains `native_sophont: bool` (set by `_set_biocomplexity()` when
biocomplexity ≥ 8; emitted in JSON only when `True`).

Exposed on system endpoints as `select_mainworld=true`; wired in the FastAPI UI as
a "Select MW" checkbox. Not applied on TravellerMap or `from-world` paths.

11 new tests. 1847 tests pass.

---

## Deferred Social Generation — Physical-Only Worlds (Session 91, issue #124)

`generate_mainworld_at_orbit()` now returns a **physical-only** world (SAH,
atmosphere detail, hydrographic detail, gas giant/belt counts). Social steps
(population, government, law, starport, TL, bases, trade codes, travel zone)
are no longer rolled during system generation.

The new `apply_mainworld_social(world, rng=None)` function in
`traveller_world_gen.py` performs the deferred steps and must be called after
mainworld selection. Until then, system-generated worlds carry interim placeholder
values: `starport='X'`, all social codes 0, empty bases and trade code lists, and
`travel_zone='Green'`.

Also fixes a **runaway greenhouse bug**: `atmosphere_detail` and `generate_gas_mix`
are now regenerated when the atmosphere code changes to A/B/C after a greenhouse
conversion in `function_app.py` and `gen-ui/app.py`.

**Note:** seed-breaking change — `generate_full_system()` now produces a different
social outcome for any previously used seed.

---

## FastAPI Web UI (Session 93)

`fastapi/static/index.html` is served at `/`. Two-panel dark-themed page:

- **Mainworld panel** — calls `/api/world/{name}/card` or `/api/world` (JSON);
  shows card, JSON, or text output with a copyable seed badge.
- **System panel** — calls card, full, or JSON endpoints; Detail / Full / Select MW
  checkboxes.
- **Server status indicator** — pings `/api/world?seed=1` on page load.

Other Session 93 changes:

- **gen-ui Chromium noise suppressed** — `QTWEBENGINE_CHROMIUM_FLAGS=--log-level=3`
  set before `QApplication` construction; silences the harmless
  `TASK_CATEGORY_POLICY` stderr line on macOS.
- **CLI flowcharts** — four Mermaid flowcharts added to `docs/`:
  `traveller_world_gen_flowchart.md`, `traveller_system_gen_flowchart.md`,
  `traveller_map_fetch_flowchart.md`, `system_map_flowchart.md`.

---

## FastAPI Server (Session 90)

A parallel REST server (`fastapi/`) exposes all 11 endpoints of the Azure
Functions API using FastAPI + uvicorn instead of Azure Functions.

- **No authentication** — designed to run behind a gateway or reverse proxy.
- **Rate limiting** — SlowAPI per-IP limiter; configurable via
  `RATE_LIMIT_PER_MINUTE` env var (default `100/minute`).
- **Run locally** — `cd fastapi && uvicorn app:app --reload` (port 8000).
- **Test coverage** — 130 new tests in `tests/test_fastapi_app.py` using
  FastAPI's `TestClient`; no Azure SDK stubs needed.
- `fastapi/helpers.py` is a flat module (not `shared/`) to avoid import
  namespace conflicts with `azure-api/shared/` when both are on `sys.path`.

---

## Secondary World Independent Government (Session 89, issue #17)

Secondary worlds can now be generated as independently governed (WBH p.162
Case 2) instead of always using the captive/dependent government table (Case 1).
When the new **Independent government** option is enabled in the Options dialog,
every inhabited secondary world (terrestrial, belt, and moon) rolls government as
`2D − 7 + Population` — the same formula as a mainworld — instead of the 1D
captive table. The law level for Case 2 worlds with government 6 uses the
standard `2D − 7 + 6` formula instead of the captive-government relationship
table. `WorldDetail` gains an `is_independent_government` boolean field emitted
in JSON when `True`. The option is disabled by default and persisted in QSettings.

7 new tests in `TestIndependentGovernment`. 1706 tests pass.

---

## Larger Worlds for Non-Mainworld Terrestrial Bodies (Session 88, issue #113)

Secondary terrestrial worlds with size 10–15 (eHex A–F) now use the full WBH
`2D-7+Size` atmosphere formula. Previously both `_terrestrial_sah()` and
`_moon_detail()` in `traveller_world_detail.py` capped the size at 9 when
calling `generate_atmosphere()`, meaning a size-12 super-Earth got the same
thin atmosphere roll as a size-9 world. The cap is replaced with
`min(generate_atmosphere(size), 15)`, applying the correct size DM while
clamping to code 15 (F — Unusual Atmosphere) to exclude NHZ-only codes 16–17.
SAH encoding (`to_hex()`) and `WorldDetail.profile` parsing already handled
sizes A–F correctly; no other changes required.

10 new tests in `TestLargeSecondaryWorldAtmosphere`. 1699 tests pass.
