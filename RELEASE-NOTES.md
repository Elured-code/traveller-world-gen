# Release Notes — v1.5.0 (draft)

**Branch:** `v1.5.0` → `main`
**Sessions:** 88–170
**Tests:** 2984

---

## New Default Body-Naming Scheme — Session 168–170

Stars, worlds, and moons are now named more systematically. Stars: `<systemname> <designation>`
(e.g. "Unknown A", "Unknown Ba") — companion stars are now named too, previously left blank.
Worlds and belts: `<systemname> <designation>-<n>`, numbered per star in order of orbital
radius (belts now share the same sequence as worlds, instead of their own separate counter).
The mainworld gets `<systemname> Prime` (e.g. "Unknown Prime"). Moons: `<parentname> <satellite>`,
using a phonetic letter-name spelling (ay, bee, cee, ... zed) instead of Greek letters.

---

## Bug Fixes: Orbit Numbering and Missing Secondary Star — Session 167

Fixed two bugs in systems where a companion's exclusion zone splits a star's own worlds into
an inner and outer placement zone: (1) the "#" orbit numbering in the system detail card's
Orbital survey table incorrectly restarted at 1 for the outer zone instead of continuing —
this also meant `attach_detail()` could silently misattribute a world's generated detail to
the wrong orbit in affected systems, now fixed at the source with continuous numbering.
(2) A close/near/far secondary star with no orbit slots of its own (e.g. all its worlds ended
up with the primary) was entirely invisible in that same table; it now shows as a row under
the primary, positioned by orbital radius, same as companion stars already were.

---

## System Detail Card: Companion Stars in Orbital Survey — Session 166

The system detail card's Orbital survey table (gen-ui, the FastAPI web app, and the A3 poster's
"Full system card" page) now lists each companion star (e.g. "Ba") as a row under its own
immediate parent star, positioned by orbital radius alongside the worlds that orbit that same
star — previously companion stars only appeared in the separate Stars table.

---

## System Map: Nested Companion Star Markers — Session 165

A secondary star's own companion (e.g. "Ba", orbiting secondary star "B") is now also drawn as a
small satellite orbit next to its parent's marker wherever that parent appears as dashed context
— e.g. inside the primary's arc zone — in addition to its already-correct placement in its own
zone. Uses the same orbital-path/shadow/connector-line styling as world orbits, scaled to an
appropriate local distance and matching its parent's own orbit inclination.

---

## Fix Issue #171: System Map Companion Star Placement — Session 164

Fixed a bug where a companion star of a *secondary* star (e.g. "Ba", orbiting secondary star
"B") was drawn in the system map's arc zone and table column for the **primary** star,
positioned right next to it, instead of next to its actual parent. Each star's zone/column now
shows only its own direct companion(s) as dashed context arcs.

---

## System Card: Primary Column in Stars Table — Session 163

The Stars table (gen-ui System tab and the FastAPI web app's system card — both share the
same `system_card.html` template) gains a **Primary** column between Desig and Class,
showing which star each star orbits: `"--"` for the primary star itself, and the parent
star's designation for every companion or close/near/far secondary star.

---

## gen-ui: File > New / New with New Seed — Session 162

Two new File menu actions: **New** (Ctrl+N) regenerates with the currently displayed seed
and options — the plain Generate button can't do this once a seed has been auto-filled, it
always rolls a fresh one. **New with New Seed** (Ctrl+Shift+N) always rolls a fresh seed,
keeping the current options.

---

## Fix Issue #170: Azure Monitor Alerts for Exception/Restart Frequency — Session 161

New `scripts/set_azure_exception_restart_alert.sh` provisions two Azure Monitor alerts on
the live `traveller-world-gen` Function App/App Insights resources, emailing on threshold
breach: exception-frequency (standard `exceptions/server` metric) and restart-frequency
(a log-query proxy — Flex Consumption exposes no platform restart-count metric). Vigilance,
not a control — surfaces whatever slips past the already-shipped body-size and schema
validation fixes (#167–169). Infrastructure-only; already run against the live resources.

---

## Fix Issue #169: Max-Length Validation on World JSON Fields — Session 160

`POST /api/system/from-world` now rejects (422) mainworld JSON bodies containing a string
over 500 characters, a list over 200 items, or nesting deeper than 20 levels, anywhere in
the payload — closing the last unvalidated body-accepting path in the API. Pairs with the
existing 16 KB whole-body size limit (issues #167/#168); this is the fine-grained,
schema-correctness half of that pair, not a replacement for it.

---

## A3 Poster: No Card Shadows in PDF, Page 2 Always Fits — Session 159

The floating cards on the poster's map page no longer have a drop shadow — it didn't
convert cleanly through the PDF export. The "Full system card" page now always fits on a
single page: if there's more detail than fits at full size, it shrinks to fit instead of
spilling onto a third page.

---

## A3 Poster: Centered Title Card — Session 157

The poster's title card now sits centered at the top of the page instead of the top-right
corner.

---

## A3 Poster: PDF Export + Page-2 Sizing — Session 156

Export A3 Poster… now offers a PDF filter alongside HTML — choosing it renders and saves a
proper 2-page PDF directly, no browser print step needed. The page-2 "Full system card" now
matches the map page's A3 size on screen. The bottom-center card added last session was
reverted per feedback.

---

## A3 Poster: Full System Card on Page 1 Too — Session 155

The poster's first page now also includes a condensed copy of the full system card
(stars + orbital survey table), positioned bottom-center between the Notable-bodies and
Mainworld cards. Given how little width is available there, most table values are heavily
truncated — the full, readable version remains on page 2.

---

## A3 Poster: Light-Mode Map + Smaller Cards — Session 154

The poster's map now renders in light mode (matching the page's paper aesthetic instead of
a dark navy map), and the Stars/Notable-bodies/Mainworld cards are scaled down a further
~33%, still anchored to their corners.

---

## A3 Poster: Cleaner Map, Repositioned Cards — Sessions 152–153

The poster's map no longer shows `system_map.py`'s embedded per-star orbit-data table (the
same data already appears on the poster's "Full system card" page), so the orbital diagram
now fills the entire map area. The Stars/Notable-bodies cards moved to the bottom-left and
the Mainworld card to the bottom-right (each capped at no more than a third of the page
height), and all card backgrounds are now semi-transparent so more of the map shows through.
Every other consumer of the system map (gen-ui's System Map window, CLI, FastAPI) is
unaffected.

---

## A3 Poster: Full-Bleed Map Layout — Session 151

The A3 poster's first page now extends the system map to all four page edges, with the
header and Stars/Mainworld/Notable-bodies cards floating on top of it in the same
positions they held before.

---

## A3 Poster: Full System Card as a Second Page — Session 150

The A3 poster export now appends the complete system card (full stars table + orbital
survey table with all secondary worlds and moons) as additional page(s) after the curated
highlights sheet, so nothing from the full system detail is left out of the printout.

---

## Fix: System Map Theme/Perspective Not Persisted (gen-ui) — Session 149

The System Map window's Light/Dark theme and Perspective/Top-down view toggles now persist
across windows — previously every newly opened map window silently reset to Dark theme and
Top-down view regardless of what you'd last chosen.

---

## A3 System Poster Export (gen-ui) — Session 148

New **File > Export A3 Poster…** action in gen-ui: saves a self-contained, print-ready HTML
page (`@page { size: A3 landscape }`) combining the perspective system map, a compact star
list, the mainworld's key stats, and up to 5 notable bodies (gas giants and inhabited
secondary worlds). A curated-highlights view by design, not the full system/world card
detail — built for print legibility. Open the saved file in any browser and use Print →
Save as PDF to print at A3.

---

## Runaway Greenhouse Extended to Secondary Worlds and Moons (Session 146)

**Extended the WBH p.79 runaway greenhouse check** beyond the mainworld to every eligible
secondary world and moon — never to gas giant bodies.

- New `_apply_secondary_runaway_greenhouse()` in `traveller_world_detail.py`, called from
  `attach_detail()` when `runaway_greenhouse=True`. Reuses the existing
  `check_runaway_greenhouse()` logic unchanged; derives temperature via the lighter-weight
  "Basic Mean Temperature" table (secondary worlds/moons have no full `WorldPhysical` body).
- Gas giant bodies (orbit-level and moons that are themselves small gas giants) are always
  excluded; rocky/icy moons orbiting a gas giant are still checked.
- Reuses the existing `runaway_greenhouse` flag/checkbox — no new toggle. Added the
  previously-missing `--runaway-greenhouse` CLI flag so the CLI can reach this feature
  (mainworld and secondary/moon behavior both) for the first time.
- `WorldDetail` gains a `runaway_greenhouse: bool` field (mirrors `WorldPhysical`'s field).
- Fixed a latent test-isolation gap: `traveller_world_atmosphere_detail`'s `_rng` sentinel
  was missing from `conftest.py`'s autouse reset list since the module was split out in
  Session 100.

---

## Flex Consumption Migration + Body-Size Backstop — Issue #168 (Session 145)

**Migrated `traveller-world-gen` from classic Consumption to Flex Consumption**,
required to set `FUNCTIONS_REQUEST_BODY_SIZE_LIMIT` as a platform-level
backstop underneath Session 144's ASGI middleware (issue #167).

- In-place migration (`az functionapp flex-migration start`) failed against
  the live app with `"Cannot change the site ... due to hosting constraints"`.
  Used a validate-then-cutover approach instead: `scripts/create_flex_function_app.sh`
  (stand up a temporary `-flex` app with its own storage account), `scripts/copy_app_settings_to_flex.sh`
  (carry settings across, excluding storage/runtime/identity keys that must
  stay app-specific), `scripts/cutover_flex_function_app.sh` (destructive,
  typed-confirmation-gated — deletes the old app and the temp app, recreates
  the original name on Flex Consumption, restores validated settings).
  `scripts/create_azure_function_app.sh`/`.ps1` (classic Consumption) left
  untouched as historical reference, not reused for Flex.
- `.github/workflows/azure-deploy.yml` updated for Flex Consumption's
  remote-build model: `sku: flexconsumption`, `remote-build: true`. Oryx now
  installs `azure-api/requirements.txt` remotely; the workflow no longer
  vendors dependencies into the deployment package itself.
- `FUNCTIONS_REQUEST_BODY_SIZE_LIMIT=1048576` (1 MB) set as an app setting —
  the issue #168 platform-level backstop under issue #167's 16 KB FastAPI
  middleware limit.
- **Security finding, remediated same session:** the cutover script's
  `az functionapp create` call didn't pass `--assign-identity`, so the
  recreated app silently fell back to connection-string/key-based auth for
  both `AzureWebJobsStorage` and the Flex deployment storage container — a
  regression from the original no-stored-keys design. A live storage account
  key was exposed in a diagnostic command's output as a result. Remediated
  live with zero downtime: assigned the identity, granted it `Storage Blob
  Data Owner`, switched both settings to identity-based auth, removed the
  key-based settings, then rotated both storage account keys to invalidate
  the exposed one. Both migration scripts were then fixed to perform this
  wiring automatically so future runs can't reproduce the gap.
- **Live-verified end-to-end** against the migrated app: a body over the
  FastAPI middleware's 16 KB limit but under the platform's 1 MB limit gets a
  clean `413 PAYLOAD_TOO_LARGE`; a body over both never reaches Python at all
  — the Azure Functions host (Kestrel) rejects it as a bare `500` with an
  empty body, invisible to `_AppInsightsMiddleware` or any app-level error
  handling. Confirms the platform setting is a backstop only, not a graceful
  control.
- Cleaned up orphaned resources left over from the failed in-place migration
  attempt and the old classic-Consumption app (two storage accounts) after
  confirming nothing live referenced them.
- No schema changes; no new tests (infrastructure/deployment work — see
  Session 144 for the 4 new `TestBodySizeLimit` tests). 2926 tests pass.

---

## ASGI Request Body-Size Limit — Issue #167 (Session 144)

**Streaming body-size limit on `fastapi/app.py`.** Neither Starlette nor
FastAPI impose a default request-body size limit, so `POST /api/system/from-world`
(and `/api/worlds`, and any other endpoint reading `Request.body()`) could have
its body buffered entirely in memory regardless of size, risking an OOM DoS.

- New `_BodySizeLimitMiddleware` — a **plain ASGI middleware**, not
  `BaseHTTPMiddleware`-based (the existing `_SecurityHeadersMiddleware` /
  `_AppInsightsMiddleware` are `BaseHTTPMiddleware` subclasses, but that base
  class constructs its own `Request` around the same stream, which is the
  wrong tool for intercepting the raw body). Rejects a request immediately if
  `Content-Length` announces an oversized body, and also counts bytes as they
  stream in via a wrapped `receive()`, so a missing or understated
  `Content-Length` (chunked transfer, a lying client) can't bypass the limit.
  Registered first (outermost) via `app.add_middleware()`.
- Default threshold 16 KB, configurable via `MAX_REQUEST_BODY_BYTES` env var —
  generous relative to the actual payload (a mainworld JSON object, a dozen
  scalar fields).
- Oversized requests get the project-standard `error()` JSON shape with the
  new `ERR_PAYLOAD_TOO_LARGE` code and HTTP 413.
- `azure-api/fastapi/app.py` is populated from this file at deploy time
  (`scripts/prepare_azure.sh`), so this is a single-source fix covering both
  deployment targets.
- 4 new tests in `tests/test_fastapi_app.py` (`TestBodySizeLimit`); 2926 tests
  pass; pylint 10.00/10 on `fastapi/app.py` and `fastapi/helpers.py`.

Related follow-ups tracked separately (not in this session): lowering the
Azure Functions platform-level body size limit as a defensive backstop
(#168), schema-level `max_length` validation on string fields (#169), and an
Application Insights alert on exception/restart frequency (#170).

---

## System Map World Icon Textures (Session 143)

**Procedural SVG textures on world icons.** Terrestrial and gas-giant glyphs in
the system map now carry visual texture information rather than a flat two-colour
(inhabited/uninhabited) scheme.

- **8 terrestrial archetypes** — `_world_archetype()` classifies each world's
  SAH codes + temperature zone into garden, ocean, desert, barren, ice, volcanic,
  hostile, or tundra. Each archetype gets a distinct 4-stop radial gradient
  (highlight → mid-light → midtone → shadow) that encodes physical world type at
  a glance. Garden worlds are blue-green; desert worlds orange/tan; ice worlds
  white/pale-blue; barren worlds grey; volcanic orange-red; etc.
- **Gas giant cloud banding** — GG glyphs now draw a horizontal stripe
  `<pattern>` (blue/white for small ice-giants, tan/beige for medium, orange/amber
  for large) with a sphere-shading overlay gradient (`sph_overlay`) on top to
  preserve the lit-sphere depth cue.
- **Legend updated** — replaced the inhabited/uninhabited colour items with four
  representative archetype colours (garden, desert, ice, barren).
- No API or schema changes. All 2922 tests pass.

---

## FastAPI Help Button + User Guide Modal (Session 142)

**Help button on the web app.** Both `index.html` and `system.html` gain a "?"
button that opens the User Guide (`docs/Traveller World Generator User Guide.md`)
in a native `<dialog>` modal via a lazy-loaded iframe pointed at a new
`/api/user-guide?theme=dark|light` endpoint. `_md_to_html_guide()` in
`fastapi/app.py` converts the Markdown (ATX headings, tables, fenced code,
bold/italic, inline code, links, lists, HR) to a themed standalone HTML page —
same converter pattern as gen-ui's Session 141 `_md_to_html()`. Theme toggling
refreshes the iframe's `src` in place.

**Follow-up fixes (same session):**
1. CodeQL alert #5 (`py/incomplete-url-substring-sanitization`) — `scripts/test_api.py`'s
   CSP jsdelivr check replaced a substring `"cdn.jsdelivr.net" in csp` test with
   exact token membership on the space-split CSP value, asserting the full
   `https://cdn.jsdelivr.net` scheme+host token.
2. The guide iframe's lazy-load guard checked `frame.src`, which reflects the
   document's own URL when the `src` attribute is unset (never falsy) —
   changed to `frame.getAttribute("src")`, which is `null` when absent.
3. `azure-api/`'s deploy never copied `docs/`, so `_USER_GUIDE_PATH` (which
   resolves relative to `__file__`) 404'd there — `.github/workflows/azure-deploy.yml`
   and `scripts/prepare_azure.sh` now copy `docs/` alongside `fastapi/`.
4. `X-Frame-Options: DENY` and `frame-ancestors 'none'` blocked the browser
   from rendering `/api/user-guide` inside the same-origin modal iframe —
   relaxed to `SAMEORIGIN` / `frame-ancestors 'self'` (cross-origin embedding
   is still blocked); `frame-src` updated `'none'` → `'self'` to match.
5. `.guide-dialog { display:flex }` was unconditional, overriding the UA
   stylesheet's `display:none` for closed `<dialog>` elements — the modal was
   visible on page load and `showModal()`/`close()` didn't work. Scoped the
   rule to `dialog[open]` in both `index.html` and `system.html`.
6. The Docker image (`Dockerfile`) had the same `docs/`-omission bug as Azure
   (fix #3 above) — `_USER_GUIDE_PATH` resolves to `/app/docs/...` in the
   container, which didn't exist. Added a `COPY "docs/Traveller World
   Generator User Guide.md" ./docs/` line. Found via a real TrueNAS/Docker
   deployment showing "User guide not available."

No schema changes; no new tests (`scripts/test_api.py` assertions updated in
place for the CSP/X-Frame-Options changes); 2922 tests pass; pylint 10.00/10.

---

## Gen-UI User Guide (Session 141)

**Help > User Guide** menu item added to the gen-ui desktop app. Selecting it
opens a non-modal `UserGuideWindow` that renders
`docs/Traveller World Generator User Guide.md` as styled HTML using the new
module-level `_md_to_html(md, dark)` helper.

`_md_to_html()` converts ATX headings, fenced code blocks, bold/italic, inline
code, links, unordered/ordered lists, horizontal rules, and paragraphs to a
complete `<!DOCTYPE html>` document with inline CSS. Colours are parametrised on
the `dark` flag so the window opens in the current theme. The window does not
update dynamically when the theme is toggled.

`AppWindow._user_guide_windows: list[object]` holds references to all open
windows (same GC-prevention pattern as `_map_windows` / `_survey_windows`).

No schema changes; no new tests; pylint 10.00/10.

---

## IISS Class IV Survey Form — Issue #161 (Session 140)

`TravellerSystem.to_survey_form_html_class4()` renders a self-contained IISS Form
0407F-IV Part C HTML page covering all social detail sections.

**Sections:** Population (profile, urbanisation, PCR), Government (type, profile,
factions, centralisation), Law Level (profile, presumption, death penalty, justice
profile), Technology (profile, TL High/Low/Space/Personal), Culture (8 traits in
4-per-row layout), Economics (importance, RF/LF/IF/EF, RU, GWP/Capita, GWP Total,
WTN), Starport (profile, base indicators, docking capacity, weekly traffic), Military
(profile, budget %, branches in paired rows).

Shows stub text (`— no X detail —`) for any section whose detail is not attached.
GWP Total uses `is not none` guard to correctly display zero-GWP worlds.

**Wired into:** FastAPI endpoints (`survey_class4_html` key), `system.html` survey
type dropdown, gen-ui `_on_survey_clicked()`.

42 new tests in `tests/test_survey_class4.py`; 9 canonical world count/bases tests
added to `tests/test_map_fetch_canonical.py`. No JSON schema changes.

## TravellerMap Canonical UWP Preservation — Issue #160 (Session 139)

**Bug:** `run_detail_pipeline()` called `apply_mainworld_social()` unconditionally, rolling fresh dice that overwrote canonical social UWP digits (population, government, law level, starport, tech level, trade codes) for TravellerMap fetched worlds.

**Fix:** `run_detail_pipeline()` now checks `mw_orbit.canonical_profile` before calling `apply_mainworld_social()`. This field is set to the canonical UWP string in `traveller_map_fetch.reconstruct_world()` when building from TravellerMap data; procedurally generated worlds leave it empty so the guard has no effect on the normal path.

**Root cause of test failures:** `conftest.py` inserts `azure-api/` at the front of `sys.path` so Azure/FastAPI test modules can import without a package install. Since `azure-api/traveller_gen/` is a complete copy of the package, pytest was importing `system_pipeline` from there (which lacked the fix) rather than from `src/`. Fixed by applying the same guard to `azure-api/traveller_gen/system_pipeline.py`.

**gen-ui RNG fix:** `_on_worker_result()` now constructs `random.Random(seed)` when `_pending_rng is None` (TravellerMap path), preventing the full detail pipeline from running with un-seeded global random.

28 new regression tests in `tests/test_map_fetch_canonical.py` (Aegir, Solomani Rim 1339, UWP A76A885-D).

## Class II/III Survey Form Dropdown — Issue #164 (Session 139)

`fastapi/static/system.html` was missing the `Class II/III Survey` `<option>` in the survey type `<select>` element. The `showTabs()` calls also only passed `class0i` HTML, never `class2iii`. Both fixed; the dropdown now offers both survey form types.

## App Icon & Favicon — Issue #158 (Session 139)

- New `fastapi/static/favicon.svg` — planet with orbital ring on dark space background.
- `<link rel="icon">` added to `system.html` and `index.html`.
- New `gen-ui/icons/icon.icns` / `icon.ico` / `icon.png` generated from the SVG via `scripts/make_icons.py` (uses `rsvg-convert`).
- `traveller_gen_ui.spec`: `icon=_icon` added to `EXE` block; `icon="gen-ui/icons/icon.icns"` set in `BUNDLE` block; `version` corrected from stale `"1.4.0"` to current value.

---

## Extended Travel Zone — Issue #103 (Session 138)

WBH §10 probabilistic travel zone determination, extending the basic CRB Amber/Red assignment with stellar flags, physical conditions, cultural characteristics, and military readiness.

**Rolls:** Two independent 2D rolls (Red ≥12, then Amber ≥12); Red takes priority. Starport X always Red. Green is default.

**Red Zone DMs:** Magnetar +10, Pulsar +8, Protostar +6, Seismic stress ≥200 +2, Xenophilia 1–2 +6−xenophilia, Militancy ≥12 +militancy−8, Factional uprisings +2, Ongoing war +4.

**Amber Zone DMs:** Primordial +2, Atmosphere 11–12 or ≥15 +2, Temp >373K +2, Pressure >50 bar +2, Seismic stress ≥100 +2, Government 0 +4 / =7 +2, Law level =0 +2 / >20 gov+law−16, Xenophilia 0–5 +6−xenophilia, Militancy ≥9 +militancy−8, Factional uprisings +2, Ongoing war +4.

New functions: `assign_travel_zone_extended()` (stochastic), `attach_travel_zone_extended()` (integrates with full world detail). No schema changes. 33 new tests. CI fix: `TYPE_CHECKING` block extended with forward-reference imports for pyright type checking.

---

## Help Menu & About Dialog — Issue #159 (Session 138)

Desktop (gen-ui) and web (FastAPI/browser) implementations of application credits.

**gen-ui:** New Help menu with About action. `_show_about()` opens non-resizable 520px QDialog (rich HTML) displaying app version, GitHub repo link, WBH credits (Geir Lanesskog, Isabella Treccani-Chinelli, Sandrine Thirache + illustrators), CRB credits (Matthew Sprange, Gareth Hanrahan + illustrators), Traveller Inner Circle list, MIT License + Mongoose Publishing disclaimer.

**world_card.html:** Fixed-position semi-transparent About button (bottom-right). Clicks open HTML `<dialog>` modal with credits content styled via existing CSS variables (dark-mode aware).

15 new UI tests (9 menu, 6 HTML content).

---

## Starport Detail — Issue #101 (Session 137)

Detailed starport characteristics for the mainworld, implementing WBH §8
(Starport Traffic and Port Capacity).

**Traffic:** `traffic_importance = importance + 1` when WTN ≥ 10 (A+). Maps
deterministically to an expected weekly ship arrival count via the WBH Traffic
table (0 ships for unexplored worlds up to 2,000 for major trade hubs).

**Docking Capacities:** Highport capacity computed for classes A–D when
`"H" in world.bases` using class-specific base + formula; downport is either
1D×10% of highport (when present) or standalone formula (when absent); Class X
returns 0. Largest pad is class-based: A/B=2,000 t, C=1,000 t, D/E=400 t.

**Shipyard Build Capacity:** Classes A/B/C only. Formula: `(EF + IF + 1D + DMs)
× TWP / divisor`. TL DMs (−4 / 0 / +2 / +4), trade DMs (Industrial +2,
Non-Industrial −2). Class A/B floors enforce minimum viable yards (A: 9,500 t,
B: 4,200 t). Class C returns None when result ≤ 0 (no functional yard). Annual
output: Class C = 10× capacity; A/B = capacity ÷ importance or capacity ×
(1 − importance) for low-importance worlds.

**Starport Profile:** `C-HX:DX:±#` format (e.g. `A-HY:DY:+4`).

New module: `traveller_world_starport_detail.py`. `World.starport_detail` field
added. Displayed at top of the Social card in `world_card.html`. Schema updated.
52 new tests. Secondary world spaceports deferred to v2.0 (issue #160).

**Also:** Fixed duplicate `starport_detail` context key in `world_card_context()`
— old facility-description string renamed to `starport_facility`.

---

## Inequality Rating & World Trade Number — Issue #100 (Session 136)

Two new economic indicators implemented for inhabited mainworlds.

**Inequality Rating:** `compute_inequality_rating()` rolls a 2D base scaled by
efficiency factor and applies government, law level, PCR, and infrastructure
DMs. Range 0–100; 50 = perfectly equal baseline. Higher values indicate more
skewed wealth distribution.

| Condition | DM |
|-----------|-----|
| Government 6, B (11), F (15) | +10 |
| Government 0, 1, 3, 9, C (12) | +5 |
| Government 4, 8 | −5 |
| Government 2 | −10 |
| Law Level ≥ 9 | +(Law Level − 8) |
| PCR | +PCR |
| Infrastructure Factor | −Infrastructure Factor |

One 2D roll per world during `attach_importance_detail()`. New field:
`WorldImportance.inequality_rating` (Optional[int]). **Schema change:**
`importance_detail.inequality_rating` property added (integer, 0–100).

**World Trade Number:** `compute_world_trade_number()` is deterministic.
Base WTN = population code + TL DM. Starport modifier from an 8×6 lookup table
(base WTN bands: 0–1, 2–3, 4–5, 6–7, 8–9, 10–11, 12–13, 14+; starport classes
A, B, C, D, E, X); clamped min 0. Stored as integer; displayed as eHex.
New field: `WorldImportance.world_trade_number` (Optional[int]).

**Development Score** now uses the actual inequality rating, so the formula is
correct end-to-end: `development_score = (gwp_pc / 1000) × (1 − ir / 100)`.

**UI Layout Split:** The world card Culture Detail section has been split into
two separate cards:
- **Culture Detail:** cultural profile (DXUS-CPEM), T5 Cultural Extension (Cx),
  and all 8 cultural trait rows (Diversity through Militancy).
- **Economic Detail:** world importance score, labour factor, infrastructure
  factor, resource factor, efficiency factor, resource units, GWP base/per-capita/
  total, inequality rating, development score, world trade number, and economics
  profile.

This separation clarifies the structure: culture traits and economics are
orthogonal concepts even though both are part of social characteristics.

**Test coverage:** 26 new tests added (`TestInequalityRating` and
`TestWorldTradeNumber` classes). Version bump: 1.5.33 → 1.5.34.

---

## T5 Cultural Extension (Cx) Forward Conversion — Issue #141 (Session 135)

T5 Cx HASS string is now computed for every inhabited world and displayed in the
world card Culture section. The forward conversion (rolled DXUS traits → HASS) applies
WBH p.254 clamping rules and is exposed via a new `_compute_cx()` helper:

- H (Heterogeneity) ← Diversity clamped to [max(1, Pop−5), Pop+5]
- A (Acceptance) ← Xenophilia clamped to [max(1, Imp+Pop−5), Imp+Pop+5]
- S (Strangeness) ← round(Uniqueness × 2/3)
- S2 (Symbols) ← Symbology clamped to [max(1, TL−5), TL+5]

`generate_culture_detail()` gains an `importance: int = 0` parameter; both standard
and Cx-derived cultures compute Cx. `CultureDetail` gains a `cultural_extension: str`
field (serializable). World card displays "Cultural Extension (T5)" row when non-empty.
**Schema change:** `culture_detail.cultural_extension` property added (string, 4 eHex chars).
Patch version bump: 1.5.32 → 1.5.33.

## App Insights Request Timestamp Precision — Issue #153 (Session 135)

The `_ai_post_request()` telemetry handler in `fastapi/app.py` previously hardcoded
`.000Z` milliseconds, resulting in all requests within the same wall-clock second
receiving identical timestamps. Fixed to use microsecond precision:
`datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"`.
This preserves request order in burst scenarios (e.g., parallel UI requests).

## Closed Issues (Session 135)

**#154** (Novelty TL placeholder) and **#145** (Tidal lock braking fix) were already
implemented in prior sessions. No code changes; issues closed as completed.

---

## Package Migration — src/traveller_gen/ (Session 134)

**Issues #155 and #156.** All 22 generation modules moved from the project root
to an installable `src/traveller_gen/` Python package. `pyproject.toml` added
with `setuptools.build_meta`; `pip install -e .` replaces all `sys.path` hacks
for local development.

**CLI entry points registered** in `pyproject.toml`:

- `traveller-world` → `traveller_gen.traveller_world_gen:main`
- `traveller-mapfetch` → `traveller_gen.traveller_map_fetch:main`

**Azure deployment simplified.** `scripts/prepare_azure.sh` and the CI workflow
now run `pip install --target azure-api/ --no-deps .` instead of a file-by-file
`cp` list. This eliminates the `azure-sync` maintenance step — adding a new module
to the package no longer requires touching either script.

**Import paths changed.**

- Within the package: all imports converted to relative (`from . import X`,
  `from .module import Y`), including function-body lazy imports.
- External callers: `from traveller_gen.traveller_X import Y`
  (`azure-api/function_app.py`, `fastapi/app.py`, `gen-ui/app.py`).
- Tests: `from traveller_gen.traveller_X import Y`; patch targets updated to
  `"traveller_gen.traveller_X.something"`.

**`conftest.py` rewritten** — removed `sys.path.insert(0, _root)`; generation
modules are now importable as a package without path manipulation.

**`scripts/compute_version.sh`** updated to write to
`src/traveller_gen/_version.py` (was project root `_version.py`).

**`pyrightconfig.json`** drops `"."` from `extraPaths` — editable install
provides the resolution path.

**Test count:** 2613 (unchanged — pure refactor, no new tests).

---

## Economic Characteristics (Session 133)

**Full WBH economic profile per world** (issue #100). `WorldImportance` gains
nine new fields computed by `attach_importance_detail()`:

- **Labour Factor** — `population − 1`, clamped ≥ 0; zero for uninhabited worlds
  and worlds of population 1.
- **Infrastructure Factor** — importance + population DMs; `None` for worlds with
  no infrastructure (below a threshold).
- **Efficiency Factor** — die-roll based (−5 to +5); pop 0 is fixed at −5; pops
  1–6 roll 2D6−7 + DMs; pops 7+ roll 2D3−4 + DMs. DMs from government type, law
  level, PCR, cultural progressiveness, and cultural expansionism. A result of 0
  is treated internally as +1 per WBH convention.
- **Resource Units** — RF × LF × IF × EF; any zero factor is treated as 1; only
  EF can yield a negative total.
- **GWP Base Value** — IF_adj + min(RF_adj, IF_adj); both adjusted to ≥ 1 for
  inhabited worlds, giving a maximum of 2 × IF.
- **GWP Per Capita / Total GWP** — base value scaled by TL, starport, government,
  and trade-code multipliers; positive EF multiplies, negative EF divides by
  (1 − EF). Total in MCr = per-capita × 10^population / 1,000,000.
- **Development Score** — (GWP_pc / 1000) × (1 − IR/100); Inequality Rating
  defaults to 0 until implemented (issue deferred).
- **Economics Profile** — compact string e.g. `"765+2"`: RF/LF/IF as eHex
  digits + EF as a signed integer.

**Resource Factor on WorldPhysical** — new `resource_factor` field on
`WorldPhysical` (and `World.to_dict()`): resource_rating adjusted by TL/trade
DMs (TL 9–12 → +1, 13–15 → +2, 16+ → +3; Ag −1, In +2, As −1, Ni −1, Ri +1),
clamped to [0, 12]. Computed by `attach_resource_factor()` in
`system_pipeline.py` after `apply_mainworld_social()`.

**Schema update.** `traveller_world_schema.json` updated with all new
`importance_detail` properties and the top-level `resource_factor` property.

**World card.** New rows in the culture detail section of `world_card.html`:
Labour Factor, Infrastructure Factor, Resource Factor, Efficiency Factor,
Resource Units (danger-highlighted when negative), GWP Base Value, GWP Per
Capita (formatted with comma separator), Total GWP (MCr), Development Score,
Economics Profile (highlighted).

**Deferred.** Tariff rates (WBH p.181) tracked in issue #157. Inequality Rating
base roll unconfirmed — deferred until source text is available.

**Test count:** 68 new tests; 2613 total (was 2545); pylint 10.00/10.

---

## World Importance Social Characteristic (Session 132)

**Deterministic world importance score per CRB.** New module
`traveller_world_importance.py` implements the world importance score as a
deterministic sum of eight modifiers (no dice): starport (A/B=+1, D/E/X=−1),
population (≤6=−1, ≥9=+1), tech level (≤8=−1, 9=0, 10–15=+1, ≥16=+2), and
presence of Ag/In/Ri trade codes (+1 each), two or more non-Corsair bases
(+1), and X-Boat waystation "W" base code (+1). The final signed score
(range −3 to +6) is displayed in the world card's culture detail section
as a single row; values > +3 are rendered bold. The component DMs are
available in JSON output for applications that need the breakdown.

**Template macro extension.** The `drow` macro in `world_card.html` gained a
`highlight` parameter to render text bold (font-weight:700) without color
change; this is used for importance values > +3 as a visual indicator of
high importance. The macro previously supported only `danger` (red) styling.

**Test coverage.** New module `tests/test_importance_detail.py` with 48 tests
covers all DM conditions, boundary cases, serialization, and the Unicode minus
sign (U+2212) in formatted output. Importance display tests added to
`tests/test_function_app.py` (6 tests in `TestSocialDetailOption`) and
`tests/test_genui_app.py` (5 tests in `TestSocialDetailGeneration`). UAT plan
extended with test cases UAT-089 through UAT-092.

**Bug fix.** The `azure-api/templates/world_card.html` template was out of sync
with the root version (missing both the `highlight` parameter and importance row).
This caused test failures in the full suite when `test_culture_detail.py` ran
first and triggered the azure-api module path. Fixed by syncing the azure-api
copy; both paths now produce consistent HTML. The issue highlights the value of
module import path ordering (conftest.py: fastapi/ > azure-api/ > root) for
dependency management, but templates must remain synchronized.

**Version bump.** `APP_VERSION` incremented from 1.5.30 to 1.5.31 (patch bump
for new JSON schema field).

**Test count:** 59 new tests; 2545 total (was 2478); pylint 10.00/10.

---

## Social Detail Test Coverage (Session 131)

**Test additions for social detail API + UI.** FastAPI endpoints and gen-ui
app now have comprehensive test coverage for the social detail feature
(implemented in Sessions 127–130). New `TestSocialDetailOption` class in
`tests/test_function_app.py` (12 tests) covers `parse_social_detail()` helper
and system/world card endpoints with the `social_detail` flag — verifies
culture_detail is present when flag is True, absent when False, profile format
compliance, and trait value floor (all ≥ 1). World card HTML includes/excludes
the Culture section based on the flag. New `TestSocialDetailGeneration` class
in `tests/test_genui_app.py` (6 tests) with `social_system_app_win` fixture
covers gen-ui path: culture_detail None/present with the option, profile format,
trait floors, and HTML presence/absence. UAT plan updated with §15 "Social
detail and cultural profile" (6 test cases) covering checkbox, culture
absent/present, profile format, trait floors, and secondary worlds.

**Test count:** 18 new tests; 2478 total (was 2460); pylint 10.00/10.

---

## T5 Cultural Extension Conversion (Session 130)

**Cx to cultural traits mapping.** When reading a mainworld from TravellerMap,
the T5 Cultural Extension (Cx) field is now available as 4 eHex characters (HASS:
Heterogeneity, Acceptance, Strangeness, Symbols). `generate_culture_detail_from_cx()`
converts these to the first four cultural traits (Diversity, Xenophilia,
Uniqueness, Symbology) with WBH-specified clamping rules based on population,
importance, and tech level. The remaining four traits (Cohesion, Progressiveness,
Expansionism, Militancy) are rolled with dice + DMs using the derived Diversity
and Xenophilia values to respect interplay constraints.

**Implementation details.** `MapWorldData` adds `cx: str` and `importance: int`
fields extracted from TravellerMap's `"Cx"` and `"Ix"` API fields. In
`generate_system_from_map()`, after mainworld reconstruction, `world.cx` and
`world.importance` are stamped as dynamic attributes. `attach_culture_detail()`
checks for the `cx` attribute and routes to the Cx conversion path when present;
otherwise uses standard generation. Secondary worlds never receive Cx attributes
(only available from TravellerMap mainworld). Backward compatibility: all missing
fields in `CultureDetail.from_dict()` default to 1 for old saved data.

**Schema change.** `CultureDetail.to_dict()` now emits 16 trait fields (8 values
+ 8 labels) plus `cultural_profile` — all new since v1.5.0 (Session 127–129
implemented the 8 traits). This requires a schema bump; version → **v1.5.28**.

**Tests:** 30 new tests covering `_parse_cx_string()`, `generate_culture_detail_from_cx()`
(all four derived mappings + rolled traits), and `attach_culture_detail()` routing.
2460 tests pass; pylint 10.00/10.

---

## Azure Monitoring & Cost Controls (Session 126)

**Application Insights per-request tracing.** FastAPI app now integrates Azure
Monitor OpenTelemetry. When deployed to Azure Functions with
`APPLICATIONINSIGHTS_CONNECTION_STRING` env var set, `configure_azure_monitor()`
is called at app startup (via try/except ImportError guard, so local dev is
unaffected). Enables per-request HTTP traces, dependency tracking, and log
forwarding to Application Insights. Requires `azure-monitor-opentelemetry>=1.6.0`
added to `azure-api/requirements.txt`.

**Daily execution quota & monthly budget controls.** `create_azure_function_app.sh`
now sets `dailyMemoryTimeQuota=1024000000` (1,000 GB-seconds/day, roughly 25,000
requests) as a safety guard. New script `set_azure_budget.sh` creates or updates
a monthly Cost Management budget ($10/month default) with email alerts at 80%
and 100% thresholds. Uses `az rest` to PUT directly to the budgets API.

**Model pinning.** `/update-docs` skill now uses `claude-haiku-4-5-20251001` model
for lower-cost documentation updates (via frontmatter `model:` field).

---

## Bug Fix: Vacuum World Temperature Range (Session 125)

**Issue #144.** Vacuum worlds (atmosphere code 0) incorrectly showed near-zero
temperature variance in the advanced high/low temperature fields. Root cause:
`ATMOSPHERE_PRESSURE_SPAN_BAR` has no entry for code 0, so `pressure_bar` was
`None`, triggering the 10-bar fallback in `generate_advanced_mean_temperature()`
intended for unbound high-pressure subtypes. This divided the luminosity variance
modifier by 11 instead of 1, collapsing the temperature range to ±6 K. Fixed in
`traveller_world_atmosphere_detail.py` — atmosphere 0 now always uses
`eff_pressure = 0.0`, producing physically correct extremes (e.g. 3 K night /
420 K day for a 720-hour-day vacuum world at 0.58 AU).

---

## Belt Profile Strings + IISS Survey Form (Session 123)

**Belt profile strings in system detail.** `BeltPhysical` gained a `profile_str`
computed property returning the WBH Class III shorthand `S-CC.CC.CC.CC-B-R-#-s`
(span in AU; M/S/C/Other composition percentages dot-separated; bulk; resource
rating; Size 1 body count; Size S body count). The profile string is displayed in
the Notes column of the system body table in all three interfaces — CLI
(`system_body_table()` in `traveller_world_detail.py`), gen-ui and FastAPI (both
via `TravellerSystem.to_html()`).

**IISS Class 0/I Survey form.** New `TravellerSystem.to_survey_form_html()` method
renders `templates/survey_class0i.html` — a structured HTML table matching the WBH
paper form. The form shows system designation, age (Gyr), stellar component count,
and a star table with columns for component, spectral class, mass, temperature,
diameter, luminosity, orbit number, AU, eccentricity, orbital period (always in
years), and HZCO. The Notes field lists sub-year orbital periods converted to
standard days with footnote superscripts. Notes and Comments boxes are 180 px tall.
Field labels use sans-serif; data fields use Courier New italic. Full light/dark
theming via CSS variables and `[data-theme]` attribute — same pattern as other card
templates.

In **gen-ui**, a "Survey Form" `QPushButton` and `QComboBox` (dropdown) appear in
the system result header before the "System Map" button. Clicking the button opens
a `SurveyFormWindow` (new class, `QMainWindow` + `QWebEngineView`) with the themed
HTML applied via `_themed_html()`. Multiple windows can coexist.

In **FastAPI**, the `include_mw_card` JSON response for `/api/system/full` and
`/api/map/system/full` now includes a third key `survey_class0i_html`. A new
Survey tab and seed-bar button/dropdown in `system.html` display the form in an
inline iframe; the iframe is reloaded on theme change.

7 new tests in `TestBeltPhysicalProfileStr`.

---

## pytest-qt GUI Test Suite (Session 124)

New `tests/test_genui_app.py` adds 121 automated GUI tests covering the
`gen-ui/app.py` desktop UI via pytest-qt.  Two stubs keep the suite fast and
self-contained: `_FakeSettings` (replaces `QSettings` — never touches disk)
and `_MockWebView` (replaces `QWebEngineView` — captures HTML without
launching Chromium).

The module is loaded via `importlib.util.spec_from_file_location` under the
name `genui_app` to avoid collision with `fastapi/app.py` when both are on
`sys.path` during the full test run.

Test classes and coverage:
- **TestAppWindowStartup** (19) — title, radio state, panel visibility,
  button/action initial state, empty window/system lists
- **TestSourceRadioToggle** (7) — TM panel show/hide on radio switch,
  entry widget presence
- **TestOptionsDialogConstruction** (12) — sub-widget visibility
  (`isVisibleTo()`), sub-option clearing, settlement buttons
- **TestOptionsDialogProperties** (11) — all property accessors, settlement
  type keys, sub-option behaviour when `full_system=False`
- **TestOptionsIntegration** (3) — OK/Cancel wired to `AppWindow._opt_*` via
  monkeypatched `_OptionsDialog` subclass
- **TestSeedHandling** (6) — invalid seed error, auto-population
- **TestTravellerMapErrors** (4) — missing sector / name+hex error paths,
  no worker started
- **TestProceduralWorldGeneration** (9) — world set, no system buttons,
  save enabled, reproducibility, name/empty-name
- **TestProceduralSystemGeneration** (14) — system set, tabs, buttons,
  survey combo, reproducibility
- **TestDarkMode** (8) — flag toggle, `_themed_html` injection, idempotency
- **TestSystemMapWindow** (12) — theme toggle, perspective toggle, SVG content
- **TestSurveyFormWindow** (4) — title, size, HTML delivered to stub view
- **TestHeaderButtons** (11) — click counts, window types, dark-mode HTML,
  no-op when no system

`pytest.ini` updated with `qt_api = pyside6`.

---

## FastAPI UI Polish (Session 122)

**System map light/dark theming.** The system map SVG now uses the page background
colour (`#f4f0e4`) in light mode rather than pure white. `fastapi/app.py` defines
`_PALETTE_LIGHT` (a copy of `PALETTE_LIGHT` with `bg="#f4f0e4"`) via
`dataclasses.replace`; CLI `--white-bg` behaviour is unchanged. `system.html`
`buildMapUrl()` passes `white_bg=true` when `data-theme=light`; `_applyTheme()`
re-fetches the map on every theme toggle; map container CSS uses `var(--bg)` so
the area around the SVG also matches.

**Template disclaimer cleanup.** The Mongoose copyright disclaimer `<p>` was
present at the bottom of each card template (`system_card.html`,
`system_detail.html`, `world_card.html`, `world_list.html`) even though it is
already displayed in the parent page footer. Removed the redundant per-card copy.

**Moon orbital table column alignment.** In both `system_card.html` and
`system_detail.html`, moon sub-rows now have an empty `#` cell so that the
orbital distance (`pd_str`) aligns with the Orbit# column, km distance aligns
with AU, and ecc/incl aligns with the e/i column. Previously the PD distance was
displayed one column too far left.

**run-gui.command restored.** `run-gui.command` and `run-gui.bat` removed from
`.gitignore`; `run-gui.command` restored from backup.

---

## WBH §5 Sub-Tech Level Corrections (Session 121)

All nine Quality-of-Life and Transportation sub-TL categories in
`traveller_world_tech_detail.py` now correctly implement WBH §5 rules.

**Bounds and base TL corrections** — every sub-TL previously used `tl_high` as
both base and clamp; each now uses the correct base TL specified in WBH:
- Energy: base = High TL; bounds = [High TL / 2, High TL × 1.2]
- Electronics: base = Energy TL; bounds = [Energy − 3, Energy + 1]
- Manufacturing: base = Electronics TL; bounds = [Electronics − 2, max(Energy, Electronics)]
- Medical: base = Electronics TL; bounds = [starport floor or 0, Electronics TL]
- Environmental: base = Manufacturing TL; bounds = [Energy − 5, Energy]
- Land Transport: base = Energy TL; bounds = [Electronics − 5, Energy]
- Sea Transport: base = Energy TL; bounds = [Electronics − 5 or 0, Energy]; hydro=0 uses DM −2 (no longer forced to 0)
- Air Transport: base = Energy TL; bounds = [Electronics − 5, Energy]; atm DMs only applied at TL 0–7
- Space Transport: base = Manufacturing TL; bounds = [min(Energy,Mfg) − 3, min(Energy,Mfg)]

**DMs added per WBH** — Pop9+/Industrial for Energy; Pop1-5/Pop9+/Industrial for
Electronics; Pop1-6/Pop8+/Industrial for Manufacturing; Rich/Poor for Medical;
habitability for Environmental; Hydro10/PCR for Land; Hydro8/9+/PCR for Sea;
atmosphere type for Air; Size0/1/+2, Pop1-5/-1, Pop9+/+1, StarportA/+2,
StarportB/+1 for Space.

**`_STARPORT_MED_FLOOR`** corrected: A→6, B→4, C→2 (was A→4, B→3, D→1, E→1, X→0).
Medical starport floor is also capped at Electronics TL to prevent floor > ceiling.

`generate_tech_detail()` gained `size: int = 0` and `trade_codes: Optional[list]`
parameters; both callers (`_tech_detail_for_det()` and `attach_tech_detail()`)
updated to pass them. Space isolated regions optional rule deferred.

**Personal Military TL** (WBH §5) corrected: base = Manufacturing TL, upper bound
= Electronics TL, lower bound = 0 (or min(Manufacturing, Electronics) when
Law Level = 0). DMs: Government 0 or 7 → +2; Law 0 or D+ (≥13) → +2; Law 1–4
or 9–C → +1. Old code forced personal military TL to 0 when Law Level = 0 — the
WBH rule instead raises the floor to Manufacturing TL. Government 7 (balkanised)
DM applies at world level; per-nation law/population DM variation is deferred.

**Heavy Military TL** (WBH §5) corrected: base = Manufacturing TL, upper bound
= Manufacturing TL, lower bound = 0. DMs: Population 1–6 → −1; Population 8+ → +1;
Government 7, A, B, F → +2; Law D+ (≥13) → +2; Industrial → +1. Old code
had no DMs and used High TL as base. Government 7 DM applies globally; per-nation
DMs for Government 7 deferred (see Personal Military note above).

62 new tests across `TestEnergyTL`, `TestElectronicsTL`, `TestManufacturingTL`,
`TestMedicalTL`, `TestEnvironmentalTL`, `TestLandTL`, `TestSeaTL`, `TestAirTL`,
`TestSpaceTL`, `TestMilitaryPersonalTL`, `TestMilitaryHeavyTL`;
`TestBoundsInvariants` expanded with `size` and all new sub-TL bounds assertions.

## Pipeline Unification via `system_pipeline.py` (Session 120)

New `system_pipeline.py` module consolidates the post-`generate_full_system()`
orchestration that was previously duplicated across all three entry points (CLI,
gen-ui, FastAPI).

**`PipelineOptions` dataclass** carries all generation flags:
`want_detail`, `want_select_mw`, `runaway_greenhouse`, `independent_government`,
`optional_biomass`, `optional_inhospitable`, `settlement_type`, `want_social_detail`.

**`run_detail_pipeline(system, rng, options)`** executes the full ordered pipeline:
`_attach_physical` → `attach_detail` → `attach_body_names` → `_apply_moon_tidal`
→ [optional `select_mainworld`] → `apply_mainworld_social`
→ [if swapped: `reattach_mainworld_orbit` + `_apply_moon_tidal`]
→ `apply_secondary_social`
→ [optional: `attach_population_detail` / `attach_government_detail` /
   `attach_law_detail` / `attach_tech_detail`]

This replaces approximately 130 lines of duplicated inline pipeline code in
`gen-ui/app.py` (`_finish_system_generation` + `_maybe_apply_runaway_greenhouse`),
`fastapi/app.py` (`_run_select_mainworld`), and `traveller_system_gen.py` `main()`.
The Advanced Mean Temperature calculation now always runs (previously was opt-in
in gen-ui via a checkbox that was removed).

**BeltPhysical guard**: `_apply_moon_tidal()` now skips worlds where
`mw.size_detail` is a `BeltPhysical` instance (belts have no diameter/mass
fields). Same guard added to `fastapi/app.py`'s `_apply_mainworld_moon_tidal()`.

16 new tests in `tests/test_system_pipeline.py` covering social-only, full detail,
`select_mainworld` swap, social detail sub-modules, RNG continuity, and
`None`-mainworld guard.

## Generation Pipeline Alignment — CLI, gen-ui, FastAPI (Session 119)

All three generation paths (CLI, gen-ui, FastAPI) now produce the same mainworld UWP
for the same seed and the same option selection.

**FastAPI RNG threading fix (`fastapi/app.py`):**
`_attach_mainworld_physical()` now accepts `rng: Optional[random.Random]` and passes
it to `generate_world_physical()`. Previously, the physical dice rolls (axial tilt,
rotation rate, etc.) advanced stdlib `random` instead of the seeded RNG object,
leaving the shared RNG M calls behind gen-ui at `apply_mainworld_social()` — causing
different starport/population/government/TL for the same seed. All 10 call sites
updated to pass `rng=rng`.

**CLI pipeline completion (`traveller_system_gen.py`):**
`main()` was missing `apply_mainworld_social()` entirely, so CLI mainworlds had
placeholder social data (starport `X`, all codes 0). `main()` now follows the full
pipeline: `generate_world_physical()` → `attach_detail()` → `attach_body_names()` →
`apply_mainworld_social()` → `apply_secondary_social()`. New flags added:
`--orbital-eccentricity`, `--orbital-inclination`. A per-iteration `random.Random`
is created and propagated so CLI seeds are reproducible.

**gen-ui eccentricity/inclination checkboxes (`gen-ui/app.py`):**
`_OptionsDialog` gains "Orbital eccentricity" and "Orbital inclination" checkboxes
(previously hardcoded `True`). Both are persisted in QSettings
(`opt_eccentricity`, `opt_inclination`). `generate_world_physical()` now receives
the actual orbit eccentricity value instead of 0.0.

**FastAPI system.html eccentricity/inclination (`fastapi/static/system.html`):**
Eccentricity and Inclination checkboxes added to the generation controls. Wired
into `sysParams()`, `buildMapUrl()`, `buildSysUrl()`, and all five `_lastGen`
assignment points. The `/api/system/svg` and `/api/map/system/svg` endpoints
now read and forward `ecc`/`incl` query params.

## Gas/Helium World Colonisation Bug Fix (Session 119)

`_minimal_tl()` in `traveller_world_detail.py` previously returned 8 for all
atmospheres above 9 (the `A+` catch-all). Atmosphere codes G and H (EHEX values 16/17
— Gas–Helium and Gas–Hydrogen) are produced by NHZ atmosphere tables and represent
worlds with no hard surface. These worlds are not colonisable. `_minimal_tl()` now
returns 99 for atmosphere ≥ 16, so secondary worlds with NHZ atmospheres are always
uninhabited regardless of mainworld TL.

## EHEX Atmosphere Crash Fix (`_sah_digit`) (Session 119)

`traveller_world_tech_detail.py` called `int(sah[1], 16)` to read the atmosphere
digit from a SAH string. Python's `int(x, 16)` only handles `0–F`; passing `G` or `H`
(atmosphere codes 16/17) raised `ValueError: invalid literal for int() with base 16`.
A new `_sah_digit(sah, idx)` helper uses `_EHEX.find()` instead, handling all valid
EHEX characters without error.

## Moon Table Column Alignment Fix (Session 119)

`system_card.html` and `system_detail.html` moon sub-rows had 11 `<td>` cells
against a 12-column header, misaligning every column from `ecc/incl` rightward.
An empty `<td>` inserted in the correct position in each template restores alignment.

---

## Mongoose Traveller Theme + Copyright Footer (Session 118)

Six HTML files rethemed and given a Mongoose Publishing copyright footer — no Python generation logic changed, test count unchanged.

**App shells (`fastapi/static/index.html`, `fastapi/static/system.html`):**
- Colour scheme: amber `#c87828` accent on near-black `#0c0e14` background, warm cream `#ddd4b0` text
- Header: 2 px amber bottom border; title uppercase with 0.08 em letter-spacing; `.badge` border-radius 2 px (angular)
- `result-frame` background: `transparent` (card templates now set their own background)
- Footer: single-line Mongoose Publishing IP notice at bottom of every page

**Card templates (`templates/world_card.html`, `world_list.html`, `system_card.html`, `system_detail.html`):**
- Light mode: warm parchment palette (`#f9f5ee` / `#eeeadb` / `#e4dfc8`)
- Dark mode: warm dark palette (`#141210` / `#1d1b17` / `#222018`)
- `--color-accent` / `--acc` CSS variable added; section labels (`.inner-label`, `.section-title`, `.inner-lbl`) set to amber with uppercase + 0.06 em tracking
- Copyright footer appended inside every rendered HTML document (visible in iframes and in saved standalone files)

**Iframe blank-display fix (root cause):**
- `loadFrame()` in `system.html` and `showFrame()` in `index.html`: `frame.classList.add("visible")` moved into the `onload` / `requestAnimationFrame` callback. The iframe is only made visible *after* its `srcdoc` has fully loaded, eliminating the intermittent blank mainworld card that appeared on first generate. The previous RAF + `h > 0` guard fixed the height-setting race but not the display race; this fix addresses the root cause.

---

## Bug fixes: issue #138 call order, CSP blob:, iframe height race (Session 117)

Three correctness fixes in the FastAPI layer — no Python generation logic changed.

1. **Issue #138 — `_attach_mainworld_physical` before `attach_detail` (7 endpoints)**
   `_attach_mainworld_physical()` was called *after* `attach_detail()` in every
   system and map endpoint except `/api/world/card`.  When the runaway greenhouse
   fired it mutated `mainworld.atmosphere` and `mainworld.hydrographics` after
   `attach_detail()` had already copied the pre-physical SAH into the mainworld
   orbit slot's `WorldDetail`, leaving the orbit slot with stale data (issue #138
   seed example: SAH `681` in orbit slot vs `6B0` on the mainworld object).
   Fixed in all 7 affected endpoints: `/api/system/full`, `/api/system/from-world`,
   `/api/system`, `/api/system/{name}/card`, `/api/system/{name}`,
   `_map_system_response`, `/api/map/system/full`, and `/api/map/world/card`.
   The existing SAH-sync block at the end of `_attach_mainworld_physical()`
   (lines 403–411) — added as a defensive patch — is now always a no-op in the
   correct call order and is retained as a safety net.
   The `is_mainworld_candidate` guard (already present) prevents the mainworld
   orbit slot from receiving duplicate social detail in
   `attach_population_detail()`, `attach_government_detail()`, and
   `attach_tech_detail()`.

2. **CSP `img-src 'self' blob:`** — the `_SecurityHeadersMiddleware` CSP was
   `img-src 'self'` which blocked `blob:` URLs created by `URL.createObjectURL()`
   in `loadMap()`.  System map SVGs fetched by the browser were converted to blob
   URLs and set as `<img src=blob:…>`, which browsers refused under the CSP.
   Added `blob:` to `img-src`.

3. **`loadFrame` iframe height race** — the `onload` handler in `system.html`
   read `frame.contentDocument.documentElement.scrollHeight` synchronously and
   could receive `0` (layout not yet computed after the tab panel was made
   visible).  Setting `style.height = "0px"` collapsed the iframe and left the
   mainworld card blank.  Fixed with `requestAnimationFrame` deferral and an
   `h > 0` guard.

---

## Internal refactor: RNG threading, `_MWCtx`, adjacency cache, `gg_diameter_from_sah` (Session 116)

Six source-level optimisations with no user-visible behaviour change:

1. **`hz_deviation_to_raw_roll` signature simplified** — removed unused `hzco: float`
   and `orbit: float` parameters from `hz_deviation_to_raw_roll()` and
   `generate_temperature_from_orbit()`. Cascade-updated all four callers in
   `traveller_system_gen.py` and `traveller_map_fetch.py`.

2. **`_MWCtx` NamedTuple** — replaced the 7-field `mw_*` keyword-argument explosion
   across all private helpers in `traveller_world_detail.py` with a single
   `_MWCtx(pop, gov, law, tl, trade_codes, bases, starport)`. `_mw_context(mainworld)`
   constructs one; public APIs are unchanged.

3. **Adjacency cache** — `generate_system_detail()` now pre-builds a
   `dict[tuple, dict]` of `_moon_adjacency_context()` results keyed by
   `(orbit_number, star_designation)` before the main orbit loop, eliminating
   redundant re-computation for systems with many orbits.

4. **`global _rng` removed** — all public entry points in `traveller_world_detail.py`
   (`attach_detail`, `apply_secondary_social`, `reattach_mainworld_orbit`,
   `generate_system_detail`) now resolve `rng = rng if rng is not None else _rng`
   locally. All private helpers now accept `rng: random.Random` as a required
   argument with no default.

5. **Intentional double-social documented** — `generate_system_detail()` calls
   `_social()` for every orbit during system-level generation, and `apply_secondary_social()`
   re-applies it after `apply_mainworld_social()` sets the correct mainworld values.
   This double pass is intentional and is now explained in a comment.

6. **`gg_diameter_from_sah` deduplicated** — moved from private copies in both
   `traveller_system_gen.py` (`_gg_diameter`) and `traveller_world_detail.py` to a
   single public function in `world_codes.py`. Both modules now import it from there.
   `APP_VERSION` bumped to `"1.5.1"` (schema-compatible maintenance release).

31 test call-sites updated to match new private-helper signatures. 2044 tests pass.

---

## FastAPI mainworld UWP mismatch fix + gen-ui Select mainworld option (Session 116)

FastAPI was making two separate API calls for the same seed — `/api/system/full` and
`/api/world/{name}/card` — which used different RNG paths and produced different UWPs.
Fixed by adding `include_mw_card=true` to `/api/system/full` and
`/api/map/system/full`: when `format=html&include_mw_card=true` the endpoint returns
`JSONResponse({"sys_html":…,"mw_html":…})` so both cards come from the same
generation. `parse_include_mw_card()` helper added to `fastapi/helpers.py`.
Frontend (`system.html`) updated to use a single fetch for both full modes.

gen-ui RNG was also diverging from FastAPI: `attach_detail` was starting from RNG
position 0 (fresh module-level `random.seed(seed)`) instead of continuing from
position P after stellar/orbit generation. Fixed by threading an explicit
`random.Random(seed)` through the entire pipeline in `_finish_system_generation()`.
Same-seed generations in gen-ui and FastAPI now use the same RNG continuation.

"Select mainworld" option added to gen-ui `_OptionsDialog` (sub-option under
"System detail"). Previously `select_mainworld()` ran unconditionally whenever
System detail was on; it is now opt-in. QSettings key: `opt_select_mw`.

## FastAPI security hardening (Session 115)

Five security issues found and fixed across `fastapi/app.py`, `fastapi/static/index.html`,
and `fastapi/static/system.html`.

**HIGH — XSS in `setStatus()` (both HTML files):** The loading branch injected user-supplied
`msg` (containing form field values such as sector name) directly into `innerHTML` via a
template literal. Fixed by keeping only the static spinner `<div>` in `innerHTML` and
appending `msg` through a created `<span>` with `textContent`.

**MEDIUM — Security HTTP headers via middleware (`app.py`):** Added
`_SecurityHeadersMiddleware(BaseHTTPMiddleware)` that attaches `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, and a full `Content-Security-Policy` to every response (including
static file responses from the `StaticFiles` mount). CSP key directives:
`script-src 'self' 'unsafe-inline'` (required for inline scripts), `img-src 'self'`,
`connect-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`.

**MEDIUM — Unsandboxed iframes (both HTML files):** All three `<iframe>` elements
(`w-frame`, `mw-frame`, `sys-frame`) now carry `sandbox="allow-scripts"`. Without `allow-same-origin`,
srcdoc content gets an opaque origin and cannot access the parent's localStorage, cookies, or window.

**MEDIUM — SVG content-type guard in `loadMap()` (`system.html`):** Replaced direct
`img.src = url` with `fetch()` → response `content-type` check → `URL.createObjectURL(blob)`.
Verifies `image/svg+xml` before rendering; logs error on mismatch. Previous blob URLs are
revoked on each call to prevent memory leaks.

**LOW — localStorage allowlist validation (both HTML files):** Enum-like preferences
(`format`, `settlement_type`, `src-mode`) are now validated against `Set` allowlists before
being written to form elements. Prevents unexpected form state from tampered or stale
localStorage entries.

---

## TravellerMap SVG endpoint + system_map.py CLI (Session 115)

**New endpoint: `GET /api/map/system/svg`** (`fastapi/app.py`) — fetches canonical UWP and
stellar data from TravellerMap via `generate_system_from_map()`, then renders an SVG system
map via `build_svg()`. Critical property: `_reconcile_orbit_types()` runs inside
`generate_system_from_map()`, setting each `OrbitSlot.world_type` to match the canonical
TravellerMap PBG world/belt/GG counts. The SVG therefore shows the correct body distribution
instead of a fresh procedural roll.

Accepts `sector` (required), `name` or `hex`, `seed`, `detail` (optionally run `attach_detail()`
so secondary UWPs appear in the orbit table), `perspective`, and `white_bg`. Returns
`image/svg+xml`. FastAPI only; 9 new tests in `TestMapSystemSvg`.

`system.html` `buildMapUrl()` updated to route TravellerMap-mode systems to
`/api/map/system/svg` (using `_lastGen.isMap`) rather than the procedural `/api/system/svg`.

**Route registration:** registered before `/api/map/system/{name}` to prevent "svg" being
matched as a path parameter.

**`system_map.py` CLI extended** with `--sector` and `--hex` flags. When `--sector` is present,
`generate_system_from_map()` is called instead of `generate_full_system()`, so the CLI honours
canonical PBG counts identically to the API endpoint. Usage:

```
python system_map.py --sector "Spinward Marches" --name Regina --seed 42
python system_map.py --sector "Spinward Marches" --hex 1910
```

---

## TravellerMap full-detail endpoint + SVG routing fix (Session 114)

**New endpoint: `GET/POST /api/map/system/full`** (`fastapi/app.py`) — fetches
canonical UWP and stellar data from TravellerMap then runs the complete detail
pipeline unconditionally:

- `attach_detail()` — secondary world SAH, moons, belts
- `attach_body_names()` — deterministic name assignment
- `_attach_mainworld_physical()` — diameter, density, gravity, temperature
- `_apply_mainworld_moon_tidal()` — tidal stress and lock
- `apply_secondary_social()` — secondary world UWP social digits
- Optionally: `attach_population_detail()`, `attach_government_detail()`,
  `attach_law_detail()` when `social_detail=true`

Accepts `format` (json/html/text), all optional orbital and social flags.
`sector` always required; `name` or `hex` identifies the world. Does **not**
call `select_mainworld()` or `apply_mainworld_social()` — canonical UWP from
TravellerMap is preserved. FastAPI only (11 new tests).

**Bug fix: `/api/system/svg` routing** — the SVG endpoint was registered after
`GET /api/system/{name}`, causing "svg" to be matched as a world name and
returning JSON instead of an SVG image. Fixed by moving the SVG endpoint
registration before both `{name}/card` and `{name}` wildcard routes.

---

## Drop-line prominence + inclination-gated orbit depth cues (Session 113)

`system_map.py` — two refinements to the Session 112 perspective depth cues:

- **Drop-line prominence:** all three drop-line `<line>` elements increased from
  `stroke-width="0.8" stroke-dasharray="2,3" opacity="0.55"` to
  `stroke-width="1.4" stroke-dasharray="3,3" opacity="0.75"` — roughly twice as
  visible against the background.
- **Inclination threshold for orbit split:** the near/far opacity split is now
  suppressed for orbits where `abs(inclination) < 3°` (`math.radians(3.0)`).
  Near-equatorial orbits draw as a single full-opacity arc, avoiding an
  imperceptible split that added no depth information. Applies to both world arcs
  and companion star dashed arcs; the threshold matches the existing shadow-arc
  minimum inclination convention.

---

## Perspective orbit depth cues and drop lines (Session 112)

`system_map.py` — two depth-cue enhancements for perspective mode:

**Orbit arc transparency split:** each perspective orbit arc is split at its midpoint
(α=0° rightmost point, screen index `n_seg//2`) into two path segments:

- **Near half** (upper screen, toward viewer): drawn at normal opacity.
- **Far half** (lower screen, receding from viewer): drawn at 40% of normal opacity
  (minimum 0.08), giving a clear visual cue that the back of the orbit lies behind
  the orbital plane.

Both halves share the same stroke colour, width, and dash pattern. Applied to regular
world/belt-fallback orbit arcs and companion star dashed arcs. Non-perspective (half-arc)
mode is unchanged.

**Drop lines:** when an orbit is inclined (body displaced above or below the reference
plane), a dotted `<line>` is drawn from the edge of the world or companion star sphere
down to its projected position on the x-y plane (z=0). The endpoint reuses `smy_z0`
already computed by the shadow-ellipse block (`cy − y4·persp_y`, no z contribution).
Style: `stroke=palette.axis`, `stroke-width=0.8`, `stroke-dasharray="2,3"`,
`opacity=0.55`. Suppressed when the displacement is ≤ symbol-radius + 1 px.

---

## 3-D sphere glyphs, ring systems, and belt-width arcs (Session 111)

`system_map.py` — three visual enhancements to star and world rendering:

- **3-D sphere glyphs:** all filled circles (primary star, companion stars, gas giants,
  terrestrial worlds) now use SVG radial gradient fills (`_sphere_gradient_def`/`_sph`).
  Each gradient has a lightened highlight at cx=35% cy=30%, the base colour at 50%, and
  a darkened edge at 100%, giving a convincing sphere-shading effect on all background
  colours. Gradients are emitted once in the SVG `<defs>` block, collected from all
  star and world colours in the system before the arc zones are drawn.
- **3-D ring systems:** gas giants with `is_ring=True` moon(s) now render a
  foreshortened ring annulus. `_gg_ring_px` reads `Moon.ring_centre_pd`/`ring_span_pd`
  to size the ring in pixels. `_ring_halves` produces two SVG annular arc paths: a rear
  half drawn before the sphere (opacity 0.40) and a front half drawn after (opacity 0.65),
  so the planet appears embedded in the ring plane. In top-down mode the ring appears
  circular; in perspective mode it is foreshortened by `persp_y = sin(15°)`.
- **Belt perspective bands:** belt orbits are no longer represented by a `<rect>` marker
  or thick stroke. `_belt_band_path` generates a filled annular band using
  `_orbit_screen_pts` for both the inner edge (`log1p(inner_au) × log_scale`) and outer
  edge (`log1p(outer_au) × log_scale`), with `e=0` (circular belt boundaries). The filled
  path is the correct perspective projection of a flat disc in the orbital plane, including
  inclination and z-rotation. In top-down mode the band appears as a symmetric annular
  arc; in perspective mode it is a foreshortened elliptical band. Where no
  `BeltPhysical` data is attached the fallback is a thin stroke arc. Belt orbits are
  excluded from the inclination shadow-arc rendering.

---

## Perspective map companion star + shadow polish (Session 109)

`system_map.py` — four targeted enhancements to the perspective rendering mode:

- **Companion star circles:** companion star markers now use `_star_r_px` to render
  a filled circle (same logic as the primary star glyph) instead of a ★ text character.
  Designation label repositioned above the circle.
- **Companion star shadows:** blurred shadow ellipse drawn at the orbital-plane
  projection of each companion star marker. Companion orbit shadows (blurred shadow arc)
  added for inclined companion orbits, matching world orbit shadow behaviour.
- **Flat shadow ellipses:** world and star shadows changed from `<circle>` to
  `<ellipse rx ry=rx·sin(15°)>` so they appear as flat ovals lying on the orbital
  reference plane at the correct 15° foreshortening.
- **Legend at top:** the arc-zone legend is now anchored at `y_top + 14` with a
  compact fixed 13 px row pitch (was `arc_zone_h × 9.2%`, far too large for tall zones)
  and brightened from opacity 0.75 to 0.92.

`gen-ui/app.py`:
- System map now rendered via `QWebEngineView` (Chromium) instead of
  `QSvgRenderer → QPixmap → QLabel`. Qt's SVG renderer silently produced
  incorrect output for SVGs containing `feGaussianBlur` filters (added for
  perspective shadow arcs), making the light-theme background appear black.
  Chromium renders all SVG features and respects palette background colours.
- Iso-grid opacity for dark mode raised 0.22 → 0.45 so the floor grid is visible
  against the near-black background.

---

## Perspective system map visual overhaul (Session 108)

`system_map.py` — comprehensive overhaul of the perspective rendering mode:

- **Full ellipse orbits:** perspective orbit and shadow arcs now use `half_deg=180°`,
  producing closed 360° polylines clipped to each arc zone via `<clipPath>`.
- **Z-rotation:** all orbit/shadow polylines rotated 30° CW around the z-axis
  (`_ROT_Z = radians(30°)`), giving a more natural perspective on the orbital plane.
- **Shadow arcs:** inclined orbits now project a blurred shadow onto the z=0 plane
  via `_shadow_orbit_arc`; drawn with `<feGaussianBlur stdDeviation="3">`.
- **Angle symbols:** small 6px arcs drawn at the α=0 and α=π crossings of each
  orbit and its shadow, showing the inclination angle visually.
- **World icon shadows:** blurred filled circles placed at the shadow-projected
  marker position for gas giant and terrestrial worlds.
- **World icon halved:** world glyph radii halved for less visual clutter.
- **Orbital inclinations enabled:** `--perspective` CLI flag now passes
  `orbital_inclination=True` to `generate_full_system`.
- **New helpers:** `_orbit_screen_pts`, `_shadow_orbit_arc`; `_orbit_half_deg` and
  `_orbit_marker` extended with `rot_z` parameter.

---

## Orbital plane disc + dashing cleanup (Session 107)

`system_map.py` — two changes:

- **Orbital plane disc:** in perspective mode each arc zone draws a faint
  `<ellipse>` centred on the star (`rx = max_r`, `ry = max_r × persp_y`),
  clipped to the zone and drawn beneath the isometric grid. Fill-opacity
  0.10/0.12, stroke-opacity 0.30/0.38 (dark/light mode). The disc makes the
  tilted orbital plane visible as a translucent surface.

- **Dashing reserved for inclination:** belt and empty orbit arcs changed from
  dashed to solid (`dash="none"`). Dashed lines now exclusively signal the
  "hidden behind the orbital plane" far arc (Session 106 near/far split).

---

## Near/far arc split for inclined orbits (Session 106)

`system_map.py` — in perspective mode, inclined orbits are now drawn as two
half-arcs. The solid **near arc** (above the orbital reference plane) and the
dashed **far arc** (below, `stroke-dasharray="5,4"`, ~45% opacity) are split at
the rightmost point of the arc, which is where the tilted orbit crosses the
reference plane in projection. Applied to all non-empty, non-companion-star arcs
when `orbital_inclination=True`. No effect in top-down mode.

---

## Perspective isometric floor grid (Session 105)

`system_map.py` — new `_iso_grid` helper generates an understated diamond-tiled
floor grid in perspective mode. Two families of diagonal lines (slopes ±`persp_y`)
are analytically clipped to each arc zone and drawn before orbit arcs. Opacity is
0.11 in dark mode and 0.17 in light mode, using `palette.axis` so the grid adapts
to both themes without additional palette fields. No effect in top-down mode.

---

## Perspective arc centring fix (Session 104)

Fixed two bugs in `system_map.py` affecting perspective mode when orbital
eccentricity or inclination are enabled:

- **Retrograde inclination bug:** orbits with inclination > 90° produced a
  negative `ry` via `cos(incl) < 0`, causing arcs to be drawn centred far to
  the right of the star. Fixed by using `abs(math.cos(incl_rad))` in
  `_orbit_half_deg`, `_orbit_arc`, and `_orbit_marker`.
- **Eccentricity float:** eccentric orbits used the ellipse focus
  (`star_cx + a_px * e`) as the arc centre rather than the star. In perspective
  mode, where more orbits reach `half_deg = 90°` (full semicircle) due to
  compressed `ry`, this caused arcs to visually float away from the star. Fixed
  by always centring arcs on `star_cx`. Eccentricity is still visible as a
  compressed y-radius (`b_px < a_px`).

---

## Graceful JSON version mismatch + hardened from_dict() (Session 103, issue #117)

**gen-ui/app.py — version mismatch warning:**
- Opening a JSON saved with a different app version now shows `QMessageBox.warning()`
  with Yes/No buttons ("Some fields may be missing or unrecognised. Continue
  loading?"). Previously: `QMessageBox.critical()` + hard abort regardless.

**Hardened `from_dict()` — replaced bare `d["key"]` with `.get()` + safe defaults:**
- `WorldDetail.from_dict()`: `d["sah"]` → `d.get("sah", "000")`
- `WorldPhysical.from_dict()`: 9 constructor fields (composition, diameter_km,
  density_g_cm3, mass_earth, gravity_g, escape_velocity_km_s, axial_tilt_deg,
  day_length_hours, tidal_status) → `.get()` with sensible defaults
- `BeltPhysical.from_dict()`: 11 constructor fields → `.get()` with sensible
  defaults (resource_rating defaults to 7; bulk defaults to 5)
- `Moon.from_dict()`: `d["size"]` → `d.get("size", "0")`

Unexpected keys were already silently ignored by all `from_dict()` methods (only
known keys are read). No changes needed there.

4 new tests in `TestFromDictMissingFields`.

**Issue #113 closed:** "Larger worlds for non-mainworld terrestrial bodies" was
implemented in Session 88. Closed with comment.

---

## Body Names for All System Bodies (Session 102, issue #131)

`attach_body_names(system)` added to `traveller_system_gen.py`. Must be called
after `attach_detail()` (moons don't exist until then). Deterministic and
idempotent. Naming scheme:

- Stars (non-companions): `<mw>-Primary`, `<mw>-Secondary`, …
- Companion stars: not named (name stays `""`)
- Non-mainworld worlds: `<mw>-A`, `<mw>-B`, … (terrestrials + GGs, one counter)
- Belts: `<mw>-Belt-A`, `<mw>-Belt-B`, … (separate counter)
- Non-ring moons: `<orbit>-alpha`, `<orbit>-beta`, … (rings skipped)

Data-structure changes (all `name: str = ""` or `field(default="", init=False)`):
- `Star.name` — regular init field; emitted unconditionally in `to_dict()`
- `OrbitSlot.name` — post-init field; emitted conditionally when non-empty
- `Moon.name` — post-init field; emitted conditionally when non-empty
- `WorldDetail.name` — `__slots__` entry; emitted conditionally; mirrored from parent orbit/moon

Display changes:
- `templates/system_card.html` — Name column added as leftmost column in orbital survey table (`.name-cell` CSS, max-width 16ch, text-overflow ellipsis); `TravellerSystem.to_html()` now includes `"name"` key in orbit and moon row dicts
- `templates/system_detail.html` — same Name column treatment for the standalone detail renderer
- `render_system_json.py` — `"name"` key added to orbit and moon row dicts

Caller wiring: `attach_body_names(system)` called immediately after every
`attach_detail()` call in `fastapi/app.py`, `gen-ui/app.py`, and
`azure-api/function_app.py`.

12 new tests in `TestBodyNames` class.

---

## City Population Rounding (Session 101)

`_round_sig(n: int, sig: int = 3) -> int` helper added to
`traveller_world_population_detail.py`. Applied to `major_city_total_population`
and each individual `City.population` immediately before they are stored in the
`PopulationDetail` dataclass. Raw values continue to drive internal distribution
arithmetic; only the stored/displayed values are rounded.

`test_city_pops_within_total` tolerance widened from `+1` to `max(1, total//200)`
(0.5%) — independent rounding means the sum of displayed city populations can
slightly exceed the rounded total.

---

## Bug Fix: Biodiversity Rating Formula (Session 100)

The WBH Biodiversity Rating formula was incorrectly implemented as
`2D − 7 + Biomass + ⌈Biocomplexity / 2⌉`. The correct WBH formula (confirmed
from book image) is `2D − 7 + ⌈(Biomass + Biocomplexity) / 2⌉` — average of
both ratings, ceiling-rounded. Two test values updated in `TestBiodiversityRating`:
`test_biocomplexity_ceil_odd` (8 → 7) and `test_high_biomass_raises_result` (14 → 9).

---

## Refactor: traveller_world_atmosphere_detail.py (Session 100)

Atmosphere-derived temperature procedures extracted from `traveller_world_physical.py`
into a new `traveller_world_atmosphere_detail.py` module (~310 lines relocated):

- Basic Mean Temperature table, DMs, and `_compute_mean_temperature`
- Albedo grouping constants and `_roll_albedo`
- Greenhouse factor grouping constants and `_roll_greenhouse_factor`
- High/Low temperature variance factors (`_axial_tilt_factor`, `_rotation_factor`,
  `_geographic_factor`)
- `generate_advanced_mean_temperature` (public API)
- `RunawayGreenhouseResult` dataclass and `check_runaway_greenhouse` (public API)

`traveller_world_physical.py` retains only physical body procedures
(composition, density, diameter, axial tilt, rotation, tidal lock, seismic stress,
resource rating). Import sites updated: `gen-ui/app.py`, `fastapi/app.py`,
`azure-api/function_app.py`, `traveller_belt_physical.py`, `tests/test_world_physical.py`.

---

## WBH Social: Government Detail (Session 99, issue #96)

New module `traveller_world_government_detail.py` implements WBH Social
Characteristics Checklist §3 (Government). Exposes an optional, separate
generation step mirroring the population detail pattern.

### Generation pipeline

- **Step 1 — Centralisation:** 2D + DMs (government code, PCR) →
  Confederal / Federal / Unitary.
- **Step 2 — Authority:** 2D + DMs (government code, centralisation) →
  Legislative / Executive / Judicial / Balanced.
- **Step 3 — Structure:** per-government special rules then the Functional
  Structure table (Demos / Single Council / Multiple Councils / Ruler).
  Balanced authority rolls all three branch structures separately.
- **Factions:** D3 + DM count (government code), each faction rolls
  government type (2D−7+pop), strength (2D), and relationship to ruling body
  (1D+DM). External factions start at numeral II.

### Government profile string

- Non-balanced: `G-CAS` (e.g., `4-FES` = Gov 4, Federal, Executive, Single Council)
- Balanced: `G-CB-LS-ES-JS` (e.g., `4-FB-LM-ES-JS`)

### New dataclasses

- `Faction` — numeral, government type/name, strength code/label, relationship code/label
- `GovernmentDetail` — centralisation, authority, primary structure (or three
  branch structures for Balanced), profile string, factions list

### Integration

- `World.government_detail` — new `Optional[GovernmentDetail]` field; emitted
  in `to_dict()` and restored by `from_dict()`.
- `WorldDetail.government_detail` — same pattern for secondary worlds.
- Government detail card added to `templates/world_card.html`.
- FastAPI: `parse_government_detail()` in `fastapi/helpers.py`;
  `attach_government_detail()` wired into 4 endpoints.

### Scope exclusions

- Government code 0 (no government) returns `None` — no procedure applies.
- Government code 7 (Balkanisation) returns `None` — Balkanised faction/nation
  procedure deferred to issue #130.

---

## FastAPI Web UI — Full Options Parity + Save (Session 98)

### system.html — full options parity with gen-ui

The Full System page now exposes every generation option available in the
desktop app. Controls are reorganised into two rows:

**Primary row:** Name, Seed, Format, Detail / Full / Select MW, Generate.

**Sub-row (new):**
- *System options* — NHZ Atm, Biomass Rule, Runaway GH, Indep Gov (disabled
  when neither Detail nor Full is checked, since they only apply when secondary
  world detail is generated).
- *Population* — Pop Detail checkbox (standalone; always enabled).
- *Settlement* — dropdown: Standard / Long-settled / Well-settled / Backwater /
  Unsettled.

Backend changes to `fastapi/helpers.py` and `fastapi/app.py`:
- `parse_settlement_type(request, body) → str` — validates against 5 keys;
  defaults to `"standard"`.
- `parse_population_detail(request, body) → bool` — standard bool flag.
- `_run_select_mainworld()` gains `settlement_type` param and passes it to
  `apply_mainworld_social()`.
- Endpoints 3 (`/api/world/{name}/card`), 5 (`/api/system/full`), 7
  (`/api/system`), and 8 (`/api/system/{name}/card`) now parse and act on both
  new params.

### Save functionality (both pages)

After each successful generation a **Save** group appears in the seed badge row:
- **index.html** (Mainworld Only): `HTML` and `JSON` buttons.
- **system.html** (Full System): `HTML`, `Text`, and `JSON` buttons.

Each button re-fetches from the API using the same seed and generation options,
then triggers a browser download with a meaningful filename
(`{slug}-world.html`, `{slug}-system.json`, etc.). The save state is cleared
whenever a new generation starts.

### Timestamped console logging

`fastapi/app.py` now calls `logging.config.dictConfig` at module level to
apply `"%(asctime)s %(levelname)-8s %(name)s: %(message)s"` to all console
output — both the app's own logger and uvicorn's access/error loggers.
`uvicorn.error` is set to WARNING to suppress duplicate startup banners.

1906 tests pass. No schema changes.

---

## Settlement Type Population Modifiers (Session 97, issue #128)

Four optional settlement types now apply atmosphere-dependent DMs to the
mainworld population roll, keeping the result within the 0–10 range.

| Settlement type | Atm 5/6/8 | Atm 4/7/9 | Atm 0/1/2/3 | All other |
|----------------|-----------|-----------|-------------|-----------|
| Standard       |    +0     |    +0     |     +0      |    +0     |
| Long-settled   |    +3     |    +2     |     +1      |    +0     |
| Well-settled   |    +2     |    +1     |     —       |    −1     |
| Backwater      |    +1     |    −1     |     −3      |    −5     |
| Unsettled      |    −4     |    −5     |     —       |    −7     |

Implementation: `_SETTLEMENT_DMS` and `_SETTLEMENT_DEFAULT_DM` module-level
dicts; `_population_settlement_dm(settlement_type, atmosphere) → int` private
helper; `generate_population(settlement_dm=0)` gains an optional DM parameter
(result clamped `min(10, roll(2, -2 + dm))`); `generate_world()` and
`apply_mainworld_social()` both gain `settlement_type: str = "standard"`.

Gen-ui: `_OptionsDialog` gains a `QGroupBox("Settlement type")` with five
`QRadioButton`s (Standard / Long-settled / Well-settled / Backwater / Unsettled).
Standard is the default. Persisted as `opt_settlement_type` in `QSettings`.
Not applied on TravellerMap paths.

No schema change. 22 new tests in `TestSettlementType`. 1906 tests pass.

---

## FastAPI Web UI Split and World Card Detail Endpoint (Session 96)

`fastapi/static/index.html` and `fastapi/static/system.html` are now two
separate pages with nav links between them:

- **Mainworld Only** (`index.html`) — single-page, full-width; calls
  `/api/world/{name}/card` (no physical or biological detail). Output matches
  gen-ui with System detail and Population detail both unchecked.
- **Full System** (`system.html`) — calls two API endpoints in parallel when
  format is HTML: `/api/world/{name}/card?detail=true` (Mainworld tab) and the
  system card endpoint (System tab). Detail / Full / Select MW options available.

`/api/world/{name}/card` gains a `detail` parameter (FastAPI only):

- `detail=false` (default) — minimal path: atmosphere detail + hydrographic
  detail only; no physical or biological cards. Matches gen-ui minimal output.
- `detail=true` — full path: generates a complete system, runs
  `attach_detail()`, and returns the mainworld HTML with all cards.

`_OptionsDialog` in `gen-ui/app.py`: the checkable `QGroupBox("System detail")`
replaced with a plain `QCheckBox` (matching the size and style of the
"Population detail" checkbox) plus an indented `QWidget` for sub-options. The
sub-options widget is hidden (not merely disabled) when System detail is
unchecked. `QGroupBox` import and its `_CSS_DARK` rule removed.

---

## Population Detail — PCR, Urbanisation, Major Cities (Session 95, issue #95)

New module `traveller_world_population_detail.py`. Dataclasses `City` and
`PopulationDetail`. Public functions `generate_pcr()`, `generate_urbanisation_pct()`,
`generate_population_detail()`, `attach_population_detail()`.

**PCR** — 1D + DMs (size, TL, gov, trade codes, tidal lock, atm) → 0–9.
Force-9 short-circuit when 1D > pop_code (pop < 6 only). Min PCR = 1 for pop ≥ 9.

**Urbanisation %** — 2D + DMs → range table (inner dice for exact %). Some DMs
carry hard min/max constraints (e.g. Pop 9 → min 18+1D%; TL 2 → max 20+1D%).
Minimum supersedes conflicting maximum (WBH rule).

**Major cities** — 5-case dispatch (PCR 0, pop≤5/PCR 9, pop≤5/PCR 1–8,
pop≥6/PCR 9, pop≥6/PCR 1–8). Case 5 formula: `ceil(2D−PCR+urb×20/PCR)`.
Case 5 total major pop: `(PCR/(1D+7)) × urban_pop`.

**City population distribution** — 2–3 cities: `(1D+3)×10%` proportional split.
4+ cities: chunk algorithm (remaining pool ÷ PCR chunks, cycled via 1D rolls).

**Population profile** — `{pop_hex}-{p}-{pcr}-{urb%}-{city_count}`.

`World.population_detail: Optional[PopulationDetail]` added (field, to_dict,
from_dict). `WorldDetail.population_detail: Optional[object]` added similarly.
`_world_html_ctx()` exposes `pop_detail` and pre-formatted population strings.
`world_card.html` gains a "Population detail" card positioned after Biological
detail. All `.inner-label` card headings rendered in bold (`font-weight: 600`).
`gen-ui/app.py` gains `_opt_population_detail` option (standalone checkbox in
Options dialog, not nested under System detail), persisted in QSettings.
`attach_population_detail()` called from both `_finish_generation()` and
`_finish_system_generation()` when the option is enabled.

**Bug fix:** `attach_population_detail()` was referencing `mw.physical` instead
of `mw.size_detail`, causing `AttributeError` at runtime. Fixed.

`traveller_world_schema.json` updated: `population_detail` object added (11
sub-fields). `APP_VERSION` bumped `1.4.1` → `1.5.0`.

23 new tests in `TestPopulationDetail`. 1884 total.

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
candidates and promotes the highest-scoring world to mainworld (WBH pp.155-156).
Scoring weights: Habitability ×50, Native sophonts ×50, Resource rating ×30,
Best refuelling ×10 (GG satellite = 2, hydro ≥ 5 = 1, else 0). On a 3D roll of
18 a candidate is selected randomly instead. When a secondary wins, the new
mainworld is regenerated via `generate_mainworld_at_orbit()` and the old
mainworld is demoted to a `WorldDetail`. Returns `True` when a swap occurred.

`WorldDetail` gains `native_sophont: bool` (set by `_set_biocomplexity()` when
biocomplexity ≥ 8; emitted in JSON only when `True`).

Exposed on system endpoints as `select_mainworld=true`; wired in FastAPI UI as
a "Select MW" checkbox. Not applied on TravellerMap or `from-world` paths.

---

## Deferred Social Generation — Physical-Only Worlds (Session 91, issue #124)

`generate_mainworld_at_orbit()` now returns a **physical-only** world (SAH,
atmosphere detail, hydrographic detail, gas giant/belt counts). Social steps
(population, government, law, starport, TL, bases, trade codes, travel zone)
are no longer rolled during system generation.

The new `apply_mainworld_social(world, rng=None)` function in
`traveller_world_gen.py` performs the deferred steps and must be called after
mainworld selection (a future issue). Until then, system-generated worlds carry
interim placeholder values: `starport='X'`, all social codes 0, empty bases and
trade code lists, and `travel_zone='Green'`.

**Note:** this is a seed-breaking change — any seed previously used with
`generate_full_system()` will now produce a different social outcome for the
mainworld because the social dice rolls have been removed from the sequence.

---

## FastAPI Web UI and gen-ui fixes (Session 93)

- **FastAPI web UI** — `fastapi/static/index.html` served at `/` (uvicorn redirects
  root to `/static/index.html`). Two-panel dark-themed page: Mainworld panel calls
  `/api/world/{name}/card` or `/api/world` (JSON); System panel calls card, full,
  or JSON endpoints with Detail/Full checkboxes. Seed badge is copyable. Server
  status indicator pings `/api/world?seed=1` on load.
- **gen-ui Chromium noise suppressed** — `QTWEBENGINE_CHROMIUM_FLAGS=--log-level=3`
  set before `QApplication` construction in `gen-ui/app.py`; silences the harmless
  `TASK_CATEGORY_POLICY: (os/kern) invalid argument` stderr line on macOS.
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
in JSON when `True`. The option is disabled by default and persisted in
QSettings.

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

---

# Release Notes — v1.4.0 (draft)

**Branch:** `v1.4.0` → `main`
**Sessions:** 55–87
**Tests:** 1686

---

## Terrestrial Resource Rating (Session 87, issue #105)

`WorldPhysical.resource_rating: Optional[int]` added. Computed at end of
`generate_world_physical()` as `max(2, min(12, 2D − 7 + Size + density_DM))`.
`density_DM`: +2 if density > 1.12 g/cm³, −2 if < 0.50. Always set for Size 1+
worlds. Public helper `apply_biological_resource_dms(rr, biomass, biodiversity,
compatibility)` applies deterministic DMs (no extra dice roll) inside
`attach_detail()` after `_apply_biomass()`. Displayed in world card and
`summary()` text output. `traveller_world_schema.json` updated with
`resource_rating` property in `WorldPhysical` section. 1686 tests pass.

## NHZ Atmospheres API Exposure (Session 87, issue #122)

`parse_nhz_atmospheres()` added to `shared/helpers.py` (same pattern as
`parse_orbital_eccentricity/inclination`). Wired into all five system
endpoint handlers in `function_app.py` and `_map_system_response()`.
`generate_system_from_world()` and `generate_system_from_map()` both gain
`nhz_atmospheres: bool = False` parameter and store it on the returned
`TravellerSystem`. Schema gains `$defs.system_generation_options` documenting
the three boolean flags that, together with `seed`, allow byte-identical system
reproduction. 9 new tests in `TestNhzAtmospheresOption`. Schema version bumped
to v1.4.1.

## Moon Ecc/Incl in Orbit Table (Session 87, issue #118)

`TravellerSystem` orbit-row builder now populates `"ecc_incl"` on each moon
dict. Non-ring moons with non-zero eccentricity or inclination show
`f"{eccentricity:.3f}/{inclination:.1f}°"`; rings and zero-value moons show `""`.
`system_card.html` moon sub-row `<td></td>` replaced with
`<td class="mono">{{ moon.ecc_incl }}</td>`.

## Gas Giant Mass/Density in Notes Column (Session 87, issue #119)

Orbit-row builder computes `gg_density = (gg_mass_earth / (gg_diam_km/12742)³) × 5.515`
when `gg_mass_earth` is set. Appended to `note_parts` as
`f"{gg_mass_earth:.0f} M⊕ · {gg_density:.2f} g/cm³"`. Notes column header
renamed from blank `<th></th>` to `<th>Notes</th>`.

## Gen-UI Onboarding Card (Session 87, issue #84)

`_show_placeholder()` replaced single dim label with `QFrame#onboard-card`
containing title, description, three-step workflow instructions, keyboard hint,
and TravellerMap note. `QFrame#onboard-card` added to both `_CSS` and `_CSS_DARK`.
Window resized to 1100×700 with minimum 780×500; `_apply_theme()` now substitutes
the actual system monospace font family name via
`QFontDatabase.systemFont(FixedFont).family()`.

## Injectable RNG for Deterministic Generation (Session 86, issue #42)

All generation modules now use injectable `random.Random` instances instead of
the global `random` module, eliminating shared-state hazards on warm Azure
Function instances and enabling isolated unit tests.

- **Module-level `_rng` pattern:** Each of the 8 generation modules
  (`traveller_hydro_detail`, `traveller_belt_physical`, `traveller_world_physical`,
  `traveller_world_gen`, `traveller_stellar_gen`, `traveller_orbit_gen`,
  `traveller_moon_gen`, `traveller_world_detail`) has a module-level
  `_rng: random.Random = random` sentinel. All `random.XXX()` calls replaced
  with `_rng.XXX()`. Public entry-point functions accept `rng: Optional[random.Random]
  = None`; when provided, they set `_rng = rng`.
- **`generate_world()` is seed-agnostic by default:** Only replaces `_rng` when
  an explicit `seed` or `rng` argument is given, preserving `random.seed()`
  behaviour for callers that rely on global state.
- **`generate_full_system()` always creates a fresh RNG:** `random.seed()` removed;
  replaced with `rng = random.Random(seed)` propagated to all sub-calls.
- **`TravellerSystem.seed` and `World.seed` fields added:** Both `to_dict()` emit
  `"seed"` when set; `from_dict()` restores it. Handlers in `function_app.py` no
  longer inject `d["seed"] = seed` manually — the seed comes from the object.
- **`apply_seed()` return type changed** from `int` to `Tuple[int, random.Random]`.
  All 13 handler call sites updated: `seed, rng = apply_seed(seed)`.
- **Cross-module propagation:** `traveller_map_fetch.generate_system_from_map()`
  uses `random.Random(seed)` and passes `rng` to `generate_orbits()`,
  `generate_hydrographic_detail()`, and `attach_detail()`.
- **`conftest.py` autouse fixture:** Resets every module's `_rng` to the global
  `random` module before/after each test, preventing order-dependent failures.

This is **not a seed-breaking change** — `random.Random(seed)` uses the same
Mersenne Twister as `random.seed(seed)`, producing identical sequences.

---

## GG Moons Near the Roche Limit (Session 85, issue #120)

Four related bugs in the gas-giant satellite tidal-stress pipeline, exposed by
seed 253115564 (TSF 644, TSS 1,256,530, total SS 1,257,174 — physically impossible).

- **TSS formula removed from GG block:** `_compute_tidal_ss` is calibrated for
  AU-scale star→planet distances; at moon distances (~0.1–0.8 Mkm) it amplifies
  results by ~10¹⁵×. The formula is no longer called for GG-satellite mainworlds;
  the `tidal_amp +=` amplitude contribution (already correct at all distances) is
  kept. Seed result: TSS drops from 1,256,530 to 0.
- **TSF capped at 500:** `tsf = min(math.floor(tidal_amp / 10), 500)`. Beyond
  ~500K-equivalent, material liquefaction limits further tidal dissipation. Seed
  result: TSF drops from 644 to 8.
- **Perigee Roche limit check:** After eccentricity/inclination rolls, any
  significant moon whose `orbit_pd × (1 − e) < 2.0` is tidally disrupted and
  converted to ring material. `ring_count` is incremented on the existing ring
  or a new ring created if none exists.
- **WBH GG mass roll:** New `_roll_gg_mass(gg_category)` in `traveller_orbit_gen.py`
  implements the WBH third-roll mass table (GS: 5×(1D+1)=10–35 M⊕; GM:
  20×(3D−1)=40–340 M⊕; GL: D3×50×(3D+4)=350–3,300 M⊕). Result stored as
  `OrbitSlot.gg_mass_earth` (Optional[float], serialised). Replaces the incorrect
  `gg_diameter ** 2` formula at all five call sites with a legacy-safe fallback
  (`orbit.gg_mass_earth if not None else float(diam ** 2)`). **This is a
  seed-breaking change** — adds 1–2 dice rolls per gas giant before the
  eccentricity block.

---

## gen-ui Dark Mode (Session 84, issue #81)

The desktop UI now supports a **dark mode** toggled via **View › Dark Mode**.

- `_CSS_DARK` stylesheet covers `QWidget` (main window background), `QGroupBox`,
  and all named `QLabel#` selectors with dark equivalents.
- Preference persisted across sessions via `QSettings("traveller-world-gen",
  "AppWindow")` key `dark_mode`.
- `_themed_html()` injects `data-theme="dark"` on the `<html>` tag at all three
  `setHtml()` call sites (world card, system card, mainworld tab), so HTML cards
  follow the in-app toggle rather than the OS `prefers-color-scheme` setting.
  `@media(prefers-color-scheme:dark)` blocks are preserved for API / browser export.
- `[data-theme=dark]` CSS blocks added to `system_card.html` (shorthand variables)
  and `world_card.html` (semantic variables).
- Toggling while a result is displayed live-refreshes the card without regenerating.

---

## System Card — MAO and HZ Columns (Session 83, issue #115)

The Stars table in the system HTML card now shows two additional columns:

- **MAO** — Minimum Armistice Orbit (Orbit# at stellar separation / 3). Populated
  from `SystemOrbits.star_mao`; shown as a 2-decimal-places Orbit# value. The
  primary star has no MAO and shows `—`.
- **HZ Orbit#** — inner edge, centre (HZCO), and outer edge of the star's
  Habitable Zone from `SystemOrbits.star_hz_inner`, `star_hzco`, `star_hz_outer`.
  Formatted as `inner – hzco – outer`; stars without an HZ show `—`.

`star_rows` in `TravellerSystem.to_html()` gains `mao`, `hz_inner`, `hzco`, and
`hz_outer` keys. The Stars table header gains `<th>MAO</th><th>HZ Orbit#</th>`.
No new tests needed — these fields are pre-computed at orbit-gen time and are
already covered by orbit-gen tests.

---

## System Card — Mainworld Detail Removed (Session 83, issue #114)

The `mw_data` construction block (~70 lines) has been removed from
`TravellerSystem.to_html()`, and the corresponding mainworld HTML section
(~200+ lines covering UWP stats, atmosphere, hydrographic, biological,
habitability, and notes) has been removed from `system_card.html`.

Mainworld detail now appears exclusively on the Mainworld tab in gen-ui via
`World.to_html()`. The System tab shows stellar data and orbital survey only.
Unused imports (`BeltPhysical`, `WorldPhysical`, `TIDAL_STATUS_LABELS`,
`BIOCOMPLEXITY_DESC`, `GOVERNMENT_NAMES`, `HYDROGRAPHIC_NAMES`,
`STARPORT_QUALITY_LABEL`, `format_atmosphere_profile`) were removed from
`traveller_system_gen.py`. No test changes needed.

---

## Ammonia Fluid Type Bug Fix (Session 83, issue #116)

`_fluid_type()` in `traveller_hydro_detail.py` incorrectly returned `"Ammonia"`
for Cold worlds with standard breathable atmospheres (codes 0–9). The WBH
specifies that ammonia oceans only form under exotic, corrosive, insidious, or
unusual atmospheres (codes 10–15). Standard atmospheres at Cold temperatures
should retain Water.

Fix: added `_AMMONIA_ELIGIBLE_ATMS: frozenset[int] = frozenset({10, 11, 12, 13,
14, 15})` and a guard in `_fluid_type()`:

```python
if temperature == "Cold" and atmosphere not in _AMMONIA_ELIGIBLE_ATMS:
    return "Water"
```

6 new tests replace the previous single `test_cold_is_ammonia` test: separate
parametrised checks over standard atmospheres (0–9 → Water) and exotic
atmospheres (10–15 → Ammonia), plus integration tests covering both cases via
`generate_hydrographic_detail()`.

---

## Habitability Rating (Session 82, issue #106)

`generate_habitability_rating()` in `traveller_world_detail.py` computes the
WBH p.131 habitability rating (base 10 + DMs) for all terrestrial worlds.
DMs cover size, atmosphere (all codes including B/C/F+), hydrographics, solar
tidal lock, temperature (full path when `WorldPhysical` is available; fallback
to category string otherwise), and gravity (defined or undefined formula).
Gravity boundaries apply the worst-DM rule. Result clamped to 0 minimum.

`habitability_description()` added to `tables.py`. Field added to `WorldDetail`,
`World`, `to_dict()` / `from_dict()`, JSON schema, and `world_card.html`.
`_apply_habitability()` is called after `_apply_biomass()` in `attach_detail()`.
81 new tests in `tests/test_habitability.py`.

---

## Basic Mean Temperature — 1D+5 for Extreme Cold (Session 81)

`_compute_mean_temperature()` now rolls 1D+5 (giving 6–11K) when the
extrapolated result would fall below 10K (modified roll ≤ −34), per the WBH
p.47 footnote. Previously the code just clamped to 3K. This edge case only
arises for worlds at hz_deviation ≥ ~18.5 (extremely distant orbits).

---

## Tidal Heating Baked into Advanced Mean Temperature (Sessions 79–80)

`_apply_seismic_stress()` (called via `apply_moon_tidal_effects()`) now updates
`advanced_mean_temperature_k`, `high_temperature_k`, and `low_temperature_k`
in-place using ⁴√(T⁴ + TSS⁴) when TSS > 0 and the rounded value changes. The
former separate `advanced_seismic_temperature_k` display field has been removed;
the tidal heating correction is now reflected in the canonical temperature fields
used downstream.

9 new tests cover the `optional_inhospitable_rule` flag added in Session 78:
rule disabled (individual rolls), group roll < 12 (all NHZ worlds zeroed),
natural 12 (winner gets biomass roll; loser and its moons get 0), in-HZ worlds
unaffected, no group roll when no NHZ worlds, and the `attach_detail`
flag pass-through.

---

## Biological Pipeline — Edge-Case Test Coverage (Session 78, issue #112)

WBH p.130 Suggested Usage confirmed: limiting the full biological pipeline
(biodiversity, compatibility, lifeform profile) to the mainworld is correct; secondary
worlds receive only biomass + biocomplexity per rulebook intent.

32 new targeted tests verify:

- **NHZ codes 16 (G) and 17 (H):** biomass clamped to code 15 (F) via `min(atm, 15)`;
  biocomplexity DM-2 applies (not in [4–9]); compatibility DM-8 (same as vacuum) confirmed
  in `_ATM_COMPAT_DM` and exercised end-to-end.
- **Extreme HZ deviation worlds (|hz_dev| ≥ 3):** frozen/boiling worlds with atmosphere 0,
  1, 16, or 17 always produce `biomass_rating = 0` — demonstrated on both the simplified
  temperature-zone path and the K-temperature (WorldPhysical) path.
- **`atmosphere_detail = None` guard:** all three taint checks (`biologic`, `has_low_o`,
  `has_taint`) default to `False` when `atmosphere_detail` is `None`; `_apply_biomass`
  runs without error.
- **Biomass=0 short-circuit:** biodiversity, compatibility, and lifeform_profile remain
  `None` when the world is lifeless.

---

## System Map — World Marker Position (Session 77)

World glyphs on the orbit arc diagram now appear **one third of the way down
the arc** from the top endpoint rather than at the top endpoint. The change
improves visual clarity: markers no longer cluster at the very tip of short
arcs and sit closer to the horizontal centreline of the diagram.

Implemented as a one-line change to `_marker_xy()` in `system_map.py`:
angle changed from `half_deg` to `half_deg / 3`.

---

## Biodiversity, Compatibility, and Lifeform Profile (Session 76, issue #104)

Mainworlds with `biomass_rating ≥ 1` now receive two additional ratings and a
four-character eHex lifeform profile. All three are computed at the end of
`_apply_biomass()`, after biocomplexity and sophont checks, so they add exactly
four dice rolls per inhabited mainworld with no seed disruption for uninhabited
worlds.

### Biodiversity Rating

```
max(0, 2D − 7 + Biomass + ⌈Biocomplexity / 2⌉)
```

Higher scores indicate a richer variety of distinct species. No maximum.

### Compatibility Rating

```
max(0, 2D − ⌊Biocomplexity / 2⌋ + DMs)
```

DMs from WBH p.130: atmosphere code (vacuum/corrosive DM−8 through standard
DM+2), system age > 8 Gyrs (DM−2), "otherwise tainted" atmosphere (DM−2 for a
taint on a non-inherently-tainted code such as D or E). Full table in
`_ATM_COMPAT_DM` in `traveller_world_detail.py`. A rating of A (10) equals full
Terran compatibility.

### Lifeform Profile

Four-character eHex string `MXDC`: Biomass, Biocomplexity, Biodiversity,
Compatibility. Displayed in the Biological detail card below Biocomplexity.

### Data structures

New fields on `World` (all `Optional`, `None` when biomass = 0):
`biodiversity_rating`, `compatibility_rating`, `lifeform_profile`.
Emitted in `World.to_dict()`, restored by `World.from_dict()`,
added to JSON schema, and displayed in `templates/world_card.html`.

New public functions in `traveller_world_detail.py`:
`generate_biodiversity_rating(biomass, biocomplexity) -> int` and
`generate_compatibility_rating(biocomplexity, atm, age_gyr, has_taint) -> int`.

17 new tests in `TestBiodiversityRating` and `TestCompatibilityRating`
in `tests/test_biomass.py`.

---

## WorldDetail Round-Trip — Secondary World Detail Restored on Load (Session 75, issue #109)

`OrbitSlot.from_dict()` now fully reconstructs the `WorldDetail` block for
every orbit slot when a saved system JSON is opened. Previously the `"detail"`
key was silently discarded, so secondary world profiles (SAH, social data,
moons, physical) were absent after loading.

Three new `from_dict()` classmethods implement the reconstruction chain:

- **`Moon.from_dict(d)`** in `traveller_moon_gen.py` — parses the `"size"`
  string back to a size code (`_EHEX.index()`), restores all post-init orbit
  fields (`orbit_pd`, `orbit_km`, `orbit_period_hours`, `orbit_eccentricity`,
  `orbit_inclination`), and recursively calls `WorldDetail.from_dict()` for
  nested moon detail via a local import.
- **`WorldDetail.from_dict(d)`** in `traveller_world_detail.py` — calls
  `__init__` with the constructor params, overrides `trade_codes` from the
  saved list, reconstructs `physical` (dispatching to `BeltPhysical.from_dict()`
  or `WorldPhysical.from_dict()` based on the `"inner_au"` key presence), and
  restores `biomass_rating` and `biocomplexity_rating`.
- **`OrbitSlot.from_dict()`** updated — when a `"detail"` key is present, the
  slot's `detail` attribute is populated by `WorldDetail.from_dict()` via a
  local import; `detail_attached` is treated as `True` by the HTML renderer.

Circular imports are handled with local imports (the same `# pylint: disable=import-outside-toplevel` pattern used elsewhere in the codebase).

19 new tests across `TestMoonFromDict`, `TestWorldDetailFromDict`, and
`TestOrbitDetailRoundtrip` in `tests/test_system_roundtrip.py`.

---

## Bug Fix — `has_gas_giant` Preserved in World JSON Round-Trip (Session 74, issue #110)

`World.from_dict()` was re-deriving `has_gas_giant` as `gas_giant_count > 0`
instead of reading the saved boolean directly. This produced incorrect results
for any world where `has_gas_giant` and `gas_giant_count` disagreed (e.g., a
world that never had a gas giant but for which the count was non-zero due to a
data quirk, or vice versa).

Fix: `has_gas_giant=bool(d.get("has_gas_giant", gas_giant_count > 0))` — reads
the saved boolean when present, falls back to `gas_giant_count > 0` for legacy
JSON files that predate the explicit field. Backward-compatible.

3 new tests in `TestWorldDetailRoundtrip` covering: explicit `True` with count 0,
explicit `False`, and absent key with count 3 (legacy fallback).

---

## Open System JSON (Session 73, issue #108)

File > Open JSON… now fully supports system JSON files (previously showed "not
yet supported"). The full reconstruction chain was added across three modules:

- `Star.from_dict()` and `StarSystem.from_dict()` in `traveller_stellar_gen.py`
- `OrbitSlot.from_dict()` and `SystemOrbits.from_dict()` in `traveller_orbit_gen.py`
- `TravellerSystem.from_dict()` in `traveller_system_gen.py`

On load the system renders in the two-tab view; Save As… and System Map are
enabled. `OrbitSlot.detail` is not reconstructed — the system displays with
`detail_attached=False` (secondary world profiles absent). 16 new tests in
`tests/test_system_roundtrip.py`.

---

## File Menu: Save As and Open JSON (Session 72, issues #75 + #107)

The result header action buttons (Open in Browser, format dropdown, Save) have
been moved to a standard **File** menu in the menu bar, and the Open in Browser
action has been replaced with **Open JSON**.

- **File > Open JSON…** — always enabled; opens a JSON file saved by the app,
  version-checks the embedded `_app_version` tag, and re-renders the world card.
- **File > Save As…** (`Ctrl+S` / `Cmd+S`) — enabled after generation; saves as
  HTML or JSON (Text format removed). JSON output includes `"_app_version": "1.4.0"`.
- Version mismatch on open shows a `QMessageBox` error dialog; system JSONs show
  a "not yet supported" informational dialog.
- `APP_VERSION = "1.4.0"` module-level constant in `gen-ui/app.py`.
- `_write_html()`, `_open_in_browser()`, and `self._html_path` removed (temp
  file was only needed for the now-gone Open in Browser action).

---

## Biologic Taint (Session 71, WBH p.83, issue #28)

Atmospheric taints can now produce a Biologic subtype. Previously subtype dice
rolls of 4 and 9 (which map to Biologic per WBH p.83) were silently rerolled
because native-life ratings did not yet exist. Now that biomass generation is
fully implemented (Session 61), the reroll guard is removed and biologic taints
are enabled.

- `_BIOLOGIC_SUBTYPE_ROLLS` frozenset removed from `traveller_world_gen.py`.
- Subtype entries `4: ("Biologic", "B")` and `9: ("Biologic", "B")` added to
  `_TAINT_SUBTYPE_TABLE`.
- Reroll guard removed from `_roll_single_taint()`.
- When a biologic taint fires, `generate_biomass_rating()` enforces
  `biomass ≥ 1` via the existing `has_biologic_taint=True` parameter
  (already wired in Session 61 via `_apply_biomass()` in
  `traveller_world_detail.py`).
- Affected atmosphere codes: 2 (Reducing), 4 (Thick/Tainted), 7 (Standard
  Tainted), 9 (Dense/Tainted).

---

## gen-ui UX + Build improvements (Session 70)

### Belt temperature for asteroid belt worlds (size 0)

`BeltPhysical` now carries a `mean_temperature_k` field computed via the same
WBH p.47 Basic Mean Temperature formula used by `WorldPhysical`, with
atmosphere DM fixed at 0 (belts have no atmosphere).

- `traveller_belt_physical.py`: imports `_compute_mean_temperature` from
  `traveller_world_physical`; `BeltPhysical` dataclass gains `mean_temperature_k: int`;
  `to_dict()` emits it; `generate_belt_physical()` computes and passes it.
- Display: "Mean temperature" row added to the Belt body card in
  `templates/world_card.html`, `templates/world_list.html`, and
  `templates/system_card.html`; `render_system_json.py` belt branch gains the
  same row.
- JSON schema: `mean_temperature_k` added to `BeltPhysical` `required` and
  `properties`.
- Test updated: `test_to_dict_keys` in `tests/test_belt_physical.py` extended
  to include `"mean_temperature_k"`.

### TravellerMap loading feedback — async worker (issue #77)

TravellerMap lookups now run on a `QThread` so the UI stays responsive during
network calls.

- New `_TravMapWorker(QThread)` class with `result`, `failed`, and `ambiguous`
  signals; `run()` calls `generate_system_from_map()`.
- `_show_loading(message)` replaces the status panel with a centred dim label
  the moment Generate is clicked.
- `_start_travellermap_worker()` shows the loading label, disables the
  Generate button, and starts the worker.
- `_on_worker_result / _error / _ambiguous` re-enable Generate and dispatch
  to the correct finish handler.
- Disambiguation retry also goes through the async path.
- Old blocking `_do_travellermap_generation()` removed.

### Checkbox dependency hierarchy — QGroupBox (issue #79)

The flat `[Mainworld only] [Full detail] [NHZ] [Oxygen] [Advanced] [Runaway]`
row is replaced by a `QGroupBox("System detail")` with `setCheckable(True)`.
When unchecked (default), Qt automatically grays out all four child checkboxes
— the dependency relationship is now visually self-documenting.

- `_radio_mainworld_only`, `_radio_full_detail`, and `_detail_group` removed.
- `self._system_group = QGroupBox(...)` stores the new checkable group.
- `_on_detail_toggled()` reduced to uncheck-on-collapse and `_map_btn` enable.
- `_on_generate()` and `_build_system_summary_header()` use
  `self._system_group.isChecked()`.

### PyInstaller binary size reduction (issue #91)

- **37 unused Qt modules** added to `excludes` (estimated 100–150 MB saving).
- **`optimize=2`** replaces `optimize=0` — strips docstrings and assertions.
- **`strip=True`** replaces `strip=False` in `EXE` and `COLLECT` (~10–20 MB
  on Linux/macOS).
- **Translation file filter** on `a.datas` strips Qt `.qm` files (~30–50 MB
  on macOS).
- **Image format plugin filter** on `a.binaries` keeps only `qsvg`, `qjpeg`,
  `qgif`, `qicns`, `qico` (~10–15 MB on macOS).
- **macOS CI split**: single `macos` matrix row replaced by `macos-arm64`
  (macos-latest) and `macos-x86_64` (macos-13); `TARGET_ARCH` env var passed
  to PyInstaller; `target_arch` in the spec reads from the env. Each build is
  ~half the size of a universal binary.
- **UPX installed in CI**: `apt-get install upx` (Ubuntu), `brew install upx`
  (macOS), `choco install upx` (Windows), `dnf install upx` (Fedora).
- Release job updated to publish five artifacts: `macos-arm64`, `macos-x86_64`,
  `windows`, `ubuntu`, `fedora`.
- `BUNDLE version` updated to `1.4.0`.

---

## gen-ui UX Improvements (Session 69)

### Orbit table horizontal scroll (issue #76)

`templates/system_card.html` orbit survey table (11 columns) now scrolls horizontally when content overflows the panel width.

- Added `.table-scroll{overflow-x:auto}` CSS class.
- Added `white-space:nowrap` to `th` to prevent header line-wrapping under scroll.
- Wrapped the orbit `<table>` in `<div class="table-scroll">`.
- Shortened `Ecc/Incl` header to `e/i` in both `system_card.html` and `system_detail.html`.

No Python or gen-ui changes — pure HTML/CSS template fix. The native Qt orbit table had previously been replaced by `QWebEngineView` (sessions 66–68), which handles browser-native scrolling once the HTML container has `overflow-x:auto`.

### TravellerMap panel show/hide (issue #78)

The TravellerMap input fields (Sector, Name, Hex) and their vertical separator are now hidden entirely when Procedural is selected, rather than shown grayed out.

- `self._tm_panel` (grid widget) and `self._tm_vsep` (separator) stored as instance attributes in `_build_source_row()`.
- `_on_source_toggled()` calls `setVisible()` on both instead of `setEnabled()` on individual fields.
- Default startup state: panel and separator hidden (Procedural is default).

---

## Advanced Mean Temperature (Session 65, WBH pp.47-48)

Physics-based mean temperature calculation now available in the gen-ui as an optional "Advanced temperature" checkbox under "Oxygen requires biomass" (enabled only with Full detail).

**Formula:** `T(K) = 279 × ⁴√(L × (1−A) × (1+G) / AU²)`
- `L` — combined luminosity of all stars interior to the world's orbit (stars with `orbit_au ≤ 0` or `orbit_au < mw_orbit_au`)
- `A` — rolled surface albedo [0.02, 0.98]
- `G` — rolled greenhouse factor
- `AU` — world's orbital distance in AU

**Albedo (`_roll_albedo`):** World type set by density and hz_deviation:
- Rocky (density > 0.5): `0.04 + (2D−2) × 0.02`
- Icy (density ≤ 0.5, hz_deviation ≤ 2.0): `0.20 + (2D−3) × 0.05`
- Icy-far (density ≤ 0.5, hz_deviation > 2.0): `0.25 + (2D−2) × 0.07` (with negative low-roll adjustment)

Atmosphere modifier (thin/mid/very-dense/heavy groups) and hydrographics modifier (2–5 or 6+) applied additively; result clamped to [0.02, 0.98].

**Greenhouse factor (`_roll_greenhouse_factor`):** Initial = `0.5 × √bar`; standard atmospheres add a positive roll; exotic atmospheres multiply by a variable factor; extreme atmospheres by a larger variable factor. Atm 0 returns 0.0. When `pressure_bar` is `None` (unbound-pressure subtypes), 10.0 bar is used as a floor estimate.

**New `WorldPhysical` fields:** `albedo`, `greenhouse_factor`, `advanced_mean_temperature_k`, `high_temperature_k`, `low_temperature_k` — all `Optional`, present only when `generate_advanced_mean_temperature()` is called.

**Display:** World card shows "Adv. mean temperature", "High temperature", "Low temperature", "Albedo", and "Greenhouse factor" rows below the basic mean temperature row.

**Tests:** 30 new tests across `TestRollAlbedo`, `TestRollGreenhouseFactor`, `TestGenerateAdvancedMeanTemperature`.

---

## High and Low Temperature (Session 65, WBH pp.48-50)

`generate_advanced_mean_temperature()` now also computes seasonal high and low temperatures using the 9-step WBH procedure.

**Steps 1–4 — Variance:**
- Step 1: Axial Tilt Factor = sin(effective tilt clamped to [0°, 90°]); orbital year < 0.1 → ÷2; year > 2.0 → factor + min(0.01×year, 0.25), capped at 1.0
- Step 2: Rotation Factor = min(1.0, √|day_hours|/50); 1:1 lock → 1.0
- Step 3: Geographic Factor = (10 − hydrographics) / 20
- Step 4: Variance = clamp(ATF + RTF + GTF, 0, 1)

**Steps 5–6 — Luminosity Modifier:**
- Step 5: Atmospheric Factor = 1 + pressure_bar
- Step 6: Luminosity Modifier = Variance / Atmospheric Factor

**Steps 7–9 — Extreme temperatures:**
- Step 7: High Lum = L×(1+LM); Low Lum = L×(1−LM)
- Step 8: Near AU = AU×(1−ecc); Far AU = AU×(1+ecc)
- Step 9: High T = 279×⁴√(HighLum × (1−A) × (1+G) / NearAU²); Low T = same with LowLum/FarAU

**Private helpers:** `_axial_tilt_factor()`, `_rotation_factor()`, `_geographic_factor()`.

**Tests:** 42 new tests across `TestAxialTiltFactor`, `TestRotationFactor`, `TestGeographicFactor`, `TestHighLowTemperature`.

---

## Biomass Temperature DM Split (Session 65, WBH p.127)

`generate_biomass_rating()` gains a `high_temp_k: Optional[int] = None` parameter. The WBH p.127 temperature DM table has five rows split across two measures:

| Row | Condition | DM |
|---|---|---|
| 1 | High temperature > 353K | −2 |
| 2 | High temperature < 273K | −4 |
| 3 | Mean temperature > 353K | −4 |
| 4 | Mean temperature < 273K | −2 |
| 5 | Mean temperature 279–303K | +2 |

When `high_temp_k` is passed (from `WorldPhysical.high_temperature_k`), rows 1–2 use it directly. When `None`, `mean_temp_k` is used as proxy (backward-compatible). `_apply_biomass()` reads `advanced_mean_temperature_k` and `high_temperature_k` off `WorldPhysical` via `getattr` (no import dependency).

**Tests:** 11 new tests in `TestHighTempKSplit`.

---

## Native Sophont Generation (Session 64, WBH p.131)

Worlds and moons with biocomplexity ≥ 8 now roll for the presence of a native sophont species.

**Generation:** `generate_sophont_checks(biocomplexity, age_gyr) -> tuple[bool, bool]` in `traveller_world_detail.py`. Called from `_apply_biomass()` when `biocomplexity_rating >= 8`.

- **Current sophont:** 2D + min(biocomplexity, 9) − 7 ≥ 13. No DMs.
- **Extinct sophont:** Same roll + DM+1 if system age > 5 Gyr. Only rolled when current sophont check fails.
- Biocomplexity above 9 is capped at 9 for both rolls.

**Data structures:** `World.native_sophont: bool` and `World.extinct_sophont: bool` — both default `False`; set by `_apply_biomass()`. Emitted to JSON only when `True` (omitted when false).

**Display:** World card biological detail section shows a "Native sophont" row: "Extant" when `native_sophont`, "Extinct (evidence present)" when `extinct_sophont`.

**Tests:** 11 new tests in `TestSophontChecks` (`tests/test_biomass.py`).

---

## gen-ui: Radio Toggle and Tab Display (Session 64)

### Detail mode radio buttons

The "System detail" + "Mainworld detail" checkboxes have been replaced with a `QRadioButton` pair backed by a `QButtonGroup`:
- **Mainworld only** — generates a single world (same behaviour as the old unchecked System detail state). Default.
- **Full detail** — calls `generate_full_system()` + `attach_detail()` + `apply_moon_tidal_effects()` together.

"NHZ Atmospheres" and "Oxygen requires biomass" checkboxes remain; they are enabled only when "Full detail" is selected and cleared when switching to "Mainworld only". The "System Map" button likewise enables/disables with Full detail.

`_on_system_detail_toggled()` renamed to `_on_detail_toggled()`. No functional change to the generation logic.

### Two-tab system result area

`_show_system_summary()` now builds a `QTabWidget` instead of a flat vertical layout:
- **Tab 1 — System:** stellar card + orbits card in a `QScrollArea` (scrolls independently of the main window).
- **Tab 2 — Mainworld:** `QWebEngineView` rendering `mw.to_html()` (the full world card HTML). Default tab when a mainworld exists.

The former "Stellar && Orbits" toggle checkbox has been removed; tab switching replaces it. `_build_system_summary_header()` return type simplified from `tuple[QWidget, QCheckBox]` to `QWidget`.

---

## Biocomplexity Rating Test Coverage and Schema Fix (Session 64)

### Test coverage added

41 new tests in `tests/test_biomass.py` verify every DM condition for `generate_biocomplexity_rating()`:

| Class | Tests | Coverage |
|---|---|---|
| `TestBiocomplexityAtmosphereDM` | 9 | Atmospheres 0,3,4,6,9,10,12,13,15 |
| `TestBiocomplexityLowOxygenDM` | 3 | No taint / taint only / taint + atm DM stack |
| `TestBiocomplexityAgeDM` | 9 | All 5 age brackets at boundary and midpoints |
| `TestBiocomplexitySpecialCases` | 6 | Floor ≥ 1, biomass cap, cap invariance, DM stack, high-bio max, 50-seed sweep |

### JSON schema fix

`biocomplexity_rating` was missing from `traveller_world_schema.json` since Session 63 despite being emitted by `World.to_dict()`. Added alongside the new `native_sophont` and `extinct_sophont` fields:

```json
"biocomplexity_rating": { "type": "integer", "minimum": 1 }
"native_sophont":       { "type": "boolean" }
"extinct_sophont":      { "type": "boolean" }
```

---

## Bug Fix — Tidal Seismic Stress for GG Satellite Mainworlds (Session 64, issue #74)

When the mainworld is a moon of a gas giant, the tidal seismic stress formula
previously used the host star's mass and the world's stellar orbit — missing the
dominant tidal driver (the gas giant itself).

`_apply_seismic_stress()` gains two new optional parameters:
- `gg_mass_earth: float = 0.0` — gas giant mass in Earth masses
- `gg_satellite_moon: Optional[Moon] = None` — the `Moon` record for the mainworld's
  orbit around the gas giant (provides `orbit_km`, `orbit_period_hours`,
  `orbit_eccentricity`)

When both are present and `gg_satellite_moon.orbit_km` is set, a second
`_compute_tidal_ss()` call adds the gas giant's tidal contribution to the running
total; the gas giant's tidal amplitude contribution is also added to
`tidal_amplitude_m`. Both call sites (`gen-ui/app.py` and `function_app.py`) were
updated to supply these parameters.

---

## Bug Fix — Biomass Temperature DMs (Session 64, WBH p.127)

### Missing "High temperature" DM rows

`generate_biomass_rating()` was only applying three of the five WBH temperature DM rows. The table has two independent sections:

| Row | Condition | DM | Was applied |
|---|---|---|---|
| 1 | High temperature > 353K | −2 | **No** |
| 2 | High temperature < 273K | −4 | **No** |
| 3 | Mean temperature > 353K | −4 | Yes |
| 4 | Mean temperature < 273K | −2 | Yes |
| 5 | Mean temperature 279–303K | +2 | Yes |

Rows 1 and 2 apply in addition to rows 3–5. Using `mean_temperature_k` as the proxy for both measures (accurate for non-tidal-locked worlds):

- `mean_temp_k > 353` → DM−2 (row 1) + DM−4 (row 3) = **DM−6** (was DM−4)
- `mean_temp_k < 273` → DM−4 (row 2) + DM−2 (row 4) = **DM−6** (was DM−2)

The combined DM now matches the footnote simplified values: boiling/frozen worlds receive the expected −6 temperature penalty regardless of which path is used. The simplified zone path (when `mean_temp_k` is not available) was already correct and is unchanged.

7 existing `TestTemperatureKPath` tests updated; 3 new boundary/equivalence tests added.

---

## Biocomplexity Rating (Session 63, WBH pp.127–131)

Worlds and moons with non-zero biomass now receive a biocomplexity rating describing the most advanced organisms possible.

**Formula:** 2D − 7 + min(biomass, 9) + DMs. DMs: atmosphere not 4–9 → DM−2; low-oxygen taint → DM−2; age ≤ 1 Gyr → DM−10; ≤ 2 Gyr → DM−8; ≤ 3 Gyr → DM−4; ≤ 4 Gyr → DM−2. Worst DM used at exact age boundaries. Minimum result 1.

**Data structures:** `World.biocomplexity_rating: Optional[int]` and `WorldDetail.biocomplexity_rating: Optional[int]` — set by `_apply_biomass()` (after biomass is determined); `None` when biomass = 0 or not computed. `BIOCOMPLEXITY_DESC` added to `tables.py`.

**Display:**
- System card orbit table: new **Biosphere** column shows `B, C` (biomass eHex, biocomplexity eHex) for any terrestrial world or moon with biomass > 0.
- System card mainworld section: new **Native life** inner-card shows Biomass and Biocomplexity rows when biomass > 0.
- World card Physical characteristics: Biomass and Biocomplexity rows appear when biomass > 0.

**Rare Earth Variant** (WBH p.130): deferred — see `context/deferred-features.md`.

---

## Moon Orbit Eccentricity and Inclination (Session 62, WBH p.76)

Significant moons with orbital positions now have eccentricity and inclination rolled, reusing the world-orbit tables (WBH pp.27–28).

**Eccentricity:** `roll_eccentricity()` (previously `_roll_eccentricity`, now public) with no world-specific DMs — the base table only. Results in [0.0, 0.999].

**Inclination:** `roll_inclination()` (previously `_roll_inclination`, now public). Same table as world orbits; inclination > 90° implies retrograde. Results in [0.0, 180.0°].

Both are rolled only when orbit data is provided (i.e., `orbit_au` and `star_mass_solar` supplied). Rings are excluded. Fields default to `0.0` when orbit placement is skipped. The old `orbit_retrograde: bool` field is replaced by `orbit_inclination: float` — retrograde is now implicit from the angle.

**Display:** The "Ecc/Incl" column in the system orbit table moon sub-rows now shows `{ecc:.3f}/{incl:.1f}°` in the same format as world orbits.

**JSON:** `orbit_eccentricity` (4 d.p.) and `orbit_inclination` (2 d.p.) emitted inside each moon's dict when > 0.

**Seed impact:** Any system generated with System detail enabled will see shifted results for all dice following a moon eccentricity/inclination roll. The rolls are appended at the end of orbit placement inside `generate_moons()`.

**Tests:** 9 new tests in `TestMoonEccentricityInclination` in `tests/test_moon_gen.py`.

---

## Native Life — Biomass Rating (Session 61, WBH pp.127–131)

Biomass ratings are now generated for all terrestrial worlds and moons in a system.

**Generation:** `generate_biomass_rating()` rolls 2D with DMs from atmosphere, hydrographics, system age, and temperature (simplified zone or mean K when available). Combined DM is clamped to [−12, +4]. Roll ≤ 0 → no native life. Special Case 1 (biologic taint + rolled 0 → biomass 1) is implemented but dormant pending biologic taint generation. Special Case 2 (inhospitable atmospheres 0, 1, A, B, C, F+ → biomass adjusted upward) is active. The optional rule (oxygenated atmospheres minimum biomass 1) is implemented off by default — see **Optional rule** below.

**RNG placement:** All biomass rolls are appended at the end of `attach_detail()` via `_apply_biomass()`, preserving all existing seed outputs for other fields.

**Mainworld requirement:** Mainworld biomass is only computed when Mainworld Detail is enabled (`WorldPhysical` set). Secondary worlds and their moons always receive biomass ratings when System Detail is enabled.

**Data structures:**
- `World.biomass_rating: Optional[int]` — mainworld biomass (set by `_apply_biomass()`)
- `WorldDetail.biomass_rating: Optional[int]` — secondary world and moon biomass

**Display:**
- System card orbit table Notes column: "Biomass N" for any terrestrial world or moon with biomass > 0
- Mainworld physical card (World Body): always shows biomass rating when Mainworld Detail is enabled
- JSON output: `biomass_rating` field added to World schema (optional integer, min 0)

**Optional rule — "Oxygen requires biomass":** When enabled (`optional_biomass_rule=True` in `attach_detail()`), any world with an oxygenated atmosphere (codes 2–9, D, E) that rolls biomass 0 is raised to 1. In gen-ui, controlled by the **"Oxygen requires biomass"** checkbox (enabled only when System detail is active; cleared when System detail is disabled). No seed disruption when disabled. Rare earth variant remains deferred.

**Tests:** 72 new tests in `tests/test_biomass.py` covering all DM table entries, DM clamping, Special Cases 1 and 2, temperature paths, age DM cumulative application, and the optional oxygen rule.

---

## Optional Runaway Greenhouse Rule (Session 68, WBH p.79)

Physics-based optional rule: worlds with Atm 2–F and mean temperature > 303 K roll 2D + DMs for runaway; on 12+ the atmosphere converts and hydrographics are recalculated.

**Trigger:** `atmosphere` in 2–15 (codes 2–F) AND `advanced_mean_temperature_k > 303`. Requires Advanced temperature to be enabled.

**Roll:** 2D + ⌈age_gyr⌉ + `(temp_k − 303) // 10` ≥ 12 → runaway occurred.

**Outcome — Case A (Atm already A/B/C/F+, codes 10–12/15–17):** atmosphere code unchanged; world treated as Boiling for hydrographic recalculation.

**Outcome — Case B (Atm 2–9/D/E):** roll 1D (DM: size 2–5 → −2; tainted Atm 2/4/7/9 → +1) to select new code: ≤ 1 → A (10), 2–4 → B (11), ≥ 5 → C (12). Hydrographics recalculated with new code and "Boiling".

**Post-runaway:** `world.temperature` set to `"Boiling"`; `generate_hydrographics()` re-called; `generate_advanced_mean_temperature()` re-run with new atmosphere code (reflects corrosive/insidious greenhouse multiplier — does not trigger a second runaway check).

**New `WorldPhysical` field:** `runaway_greenhouse: Optional[bool]` — set `True` when runaway triggers; absent otherwise. Emitted in JSON and displayed as "Runaway greenhouse: Yes" in world card and system card.

**New function:** `check_runaway_greenhouse(atmosphere, temp_k, age_gyr, size) → Optional[RunawayGreenhouseResult]` in `traveller_world_physical.py`. Pure function; caller applies mutations.

**gen-ui:** "Runaway greenhouse" checkbox added under "Advanced temperature" (enabled only when Full detail + Advanced temperature are active; cleared when either is disabled). Controlled by `_maybe_apply_runaway_greenhouse()` extracted from `_finish_system_generation()` to keep pylint limits.

**Tests:** 20 new tests in `TestCheckRunawayGreenhouse` covering trigger conditions, DM calculations, roll threshold, Case A/B branching, new atmosphere code selection (die 1/3/6), size DM, tainted DM, and `to_dict()` integration.

---

## Hydrographic Fluid Type (Session 67, WBH pp.91–92, issue #20)

`HydrographicDetail` gains a `fluid_type: Optional[str]` field identifying the dominant surface liquid based on temperature zone.

| Temperature zone | Fluid type |
|---|---|
| Boiling | Sulfuric Acid |
| Hot / Temperate | Water |
| Cold | Ammonia |
| Frozen | Liquid Hydrocarbons |

Desert worlds (Hydrographics 0) and Gas/Hydrogen atmosphere worlds (codes 16–17) carry `fluid_type = None` — no free liquid surface.

**Display:** "Fluid type" row appears after "Surface liquid" in the hydrographic detail inner-card in all four output surfaces.

**JSON:** `fluid_type` emitted inside `hydrographics.detail` when present; added to `traveller_world_schema.json`.

---

## Stellar Day / Sidereal Day Correction (Session 66, WBH p.106)

`WorldPhysical` gains `stellar_day_hours: Optional[float]` — the solar day length (time between successive sunrises) computed from the sidereal rotation period and orbital period.

**Formula:** For prograde worlds: `1 / (1/day − 1/year_hours)`. For retrograde: `1 / (1/day + 1/year_hours)`. 3:2 resonance: `stellar_day = 2 × orbital_period_yr × 8766`. 1:1 lock: field omitted (star stationary in sky). Only set when orbital data is available.

**Display:** "Stellar day" row shown below "Day length" in World Body card when available. Tidally locked worlds show no stellar day row.

**JSON:** `stellar_day_hours` emitted in `WorldPhysical.to_dict()` when set; added to schema.

---

## gen-ui: System Tab HTML Rendering (Issue #86)

The System tab (formerly built from native Qt `QGroupBox` / `QLabel` widgets via `_build_stellar_card()` and `_build_orbits_card()`) now renders `system.to_html()` in a `QWebEngineView`.

- `_build_stellar_card()`, `_build_orbits_card()`, `_WORLD_TYPE_LABEL`, `_orbit_profile()`, `_fmt_period()` removed (~273 lines).
- The tab is populated by a single `setHtml()` call on the `QWebEngineView`, identical to the save-as-HTML output.
- Net result: `gen-ui/app.py` reduced by ~273 lines (1283 → 1010); the System tab now includes all columns, styling, and detail the HTML template provides, including moon sub-rows, biosphere data, and anomaly notes.

---

## PyInstaller Binary Builds (issue #65)

Cross-platform standalone executables can now be built using PyInstaller.

**New files:**
- `traveller_gen_ui.spec` — PyInstaller spec that bundles `gen-ui/app.py` as a one-file executable, collecting all template files, system data, and PySide6 Qt plugins. Template path resolved at runtime via `sys._MEIPASS` when frozen.
- `.github/workflows/build-binaries.yml` — GitHub Actions workflow that builds signed executables for Windows, macOS (Intel + Apple Silicon), and Linux on every push to `main`. Artefacts published as GitHub release assets.
- `docs/BUILD.md` — build instructions for local PyInstaller builds and CI workflow usage.

---

## World Physical Detail

### Tidal Stress Factor (Session 60, issue #67, WBH p.126)

`WorldPhysical` gains `tidal_stress_factor: Optional[int]` — the seismic stress
contribution from surface tidal forces.

**Formula:** `floor(tidal_amplitude_m / 10)` where `tidal_amplitude_m` is the
combined surface tidal amplitude (star + moons, computed by the Session 58 pipeline).

**Example:** A world with 30.6 m of moon tidal effect + 0.24 m star effect gives
tidal_amplitude_m = 30.84 → TSF = 3.

**Integration:** `total_seismic_stress` is now the sum of all three components:
Residual Seismic Stress + Tidal Seismic Stress + Tidal Stress Factor. Both
`tidal_amplitude_m` and `tidal_stress_factor` are set together inside
`_apply_seismic_stress()` via `_compute_tidal_amplitude()`.

Displayed in gen-ui World Body card, `world_card.html`, and `render_system_json.py`
in the order: Tidal Seismic Stress → Tidal Stress Factor → Residual → Total.
`tidal_stress_factor` is emitted to JSON and schema only when > 0.

6 new tests in `TestTidalStressFactor`.

---

### Surface Tidal Amplitude (Session 58, issue #68, WBH pp.107–108)

`WorldPhysical` gains `tidal_amplitude_m: Optional[float]` — the combined surface tidal
amplitude in metres from the primary star and all significant moons.

**Star effect:** `(star_mass_solar × size) / (32 × AU³)`. Sol acting on Terra ≈ 0.25 m.

**Moon effect per moon:** `(moon_mass_earth × size) / (3.2 × (orbit_km / 10⁶)³)`. Moon mass
estimated from size using Terran density: `(size × 1600 / 12742)³` M⊕ (same method used in
`WorldPhysical.mass`). Rings and moons without `orbit_km` are excluded.

**Pipeline:** `generate_world_physical()` stores a star-only preliminary value in
`tidal_amplitude_m`; `apply_moon_tidal_effects()` adds all moon contributions and updates
the field in-place.

**Display:** "Tidal amplitude: X.XX m" row appears after the Tidal status row in all four
output surfaces — gen-ui World Body card, `world_card.html` Jinja2 template,
`render_system_json.py`, and the JSON schema (`tidal_amplitude_m` added to the
`WorldPhysical` branch).

21 new tests across `TestStarTidalEffectM`, `TestMoonMassEarth`, `TestMoonTidalEffectM`,
`TestComputeTidalAmplitude`, `TestTidalAmplitudeIntegration`.

Also in this session: the pre-existing `_ZONE_OBJECT_NAME → ZONE_CSS_CLASS` name typo in
`gen-ui/app.py` was fixed, and `test_moon_lock_occurs_when_dm_high_enough` was patched to
be fully deterministic (the broken-lock check was a source of intermittent test flap).

---

### Seismic Stress (Session 56, WBH pp.125–128)

Seismic stress is now calculated for every mainworld with physical detail. Four fields
are added to `WorldPhysical`; all are `Optional[int]`.

**Residual Seismic Stress (RSS):** `floor(Size − Age_Gyr + DMs)²`. DMs: `is_moon` +1;
density > 1.0 +2; density < 0.5 −1; sum of significant moon sizes (Size 1+, non-ring),
capped at +12. Values < 0 before squaring yield 0.

**Tidal Seismic Stress (TSS):** `PrimaryMass⊕² × (diam/1600)⁵ × e² /
(3000 × dist_Mkm⁵ × period_days × WorldMass⊕)`. Rounded down; stored as 0 when < 1
(omitted from `to_dict()` when 0).

**Total Seismic Stress:** RSS + TSS (+ Tidal Stress Factor once Session 60 runs).

**Seismic Temperature:** `⁴√(mean_temp_k⁴ + TSS⁴)`. Set only when the result rounds
to a value different from `mean_temperature_k`; omitted otherwise.

**Display:** World Body card, `world_card.html`, and `render_system_json.py` all show
the seismic fields. `apply_moon_tidal_effects()` sets `is_moon=True` for gas-giant
satellite mainworlds and always runs `_apply_seismic_stress()` even when the moon list
is empty.

22 new tests in `TestResidualSeismicStress`, `TestTidalSeismicStress`, `TestApplySeismicStress`, `TestSeismicTemperature`.

---

## Bug Fixes

### Mainworld-as-moon row not bold in orbit table (Session 61)

When the mainworld is a satellite of a gas giant it appears as a moon sub-row in the system orbit table. It was rendered with the `table-moon` CSS class instead of `table-mw`, so the row was not displayed in bold like other mainworld rows. Fixed: `moon_css` is now `"table-mw"` when `is_mw and mi == 1 and orbit.world_type == "gas_giant"`.

---

### BeltPhysical crash in `apply_moon_tidal_effects()` (Session 59)

`apply_moon_tidal_effects()` was called for belt mainworlds (Size 0), passing a
`BeltPhysical` object where `WorldPhysical` was expected. Both the tidal lock
re-run and `_apply_seismic_stress()` access attributes (`density`, `axial_tilt`,
`tidal_status`, etc.) that exist only on `WorldPhysical`, raising `AttributeError`.

Fix: `apply_moon_tidal_effects()` now returns immediately when `physical` is not
a `WorldPhysical` instance. Belt worlds have no tidal lock or seismic stress fields,
so the early return is semantically correct, not just defensive.

---

## Maintenance

### gen-ui: eccentricity and inclination always calculated (issue #58)

The "Orbital Eccentricity" and "Orbital Inclination" checkboxes have been removed
from the desktop UI. Both flags are now always passed as `True` when "System detail"
is enabled, so the Ecc/Incl column is always populated.

---

### Rename: `tidal_heating_factor` → `tidal_seismic_stress` (Session 59)

The WBH term for the orbital tidal contribution to seismic stress is "Tidal Seismic
Stress", not "Tidal Heating Factor". Renamed throughout:

- `WorldPhysical.tidal_heating_factor` field → `tidal_seismic_stress`
- `_compute_thf()` → `_compute_tidal_ss()`
- JSON key `"tidal_heating_factor"` → `"tidal_seismic_stress"`
- JSON schema property and description updated
- Display label in gen-ui, `world_card.html`, and `render_system_json.py`
- Tests updated (`TestComputeThf` → `TestComputeTidalSS`)

Formula and logic unchanged. Total Seismic Stress = Residual Seismic Stress +
Tidal Seismic Stress.

---

### Static typing — enum types (issue #38)

Five `StrEnum` / `IntEnum` types added to a new `world_codes.py` module, compatible with all existing `str` / `int` comparisons and JSON serialisation.

| Enum | Values |
|---|---|
| `StarportCode` (`StrEnum`) | `A B C D E X` |
| `TemperatureCategory` (`StrEnum`) | `Frozen Cold Temperate Hot Boiling` |
| `TradeCode` (`StrEnum`) | all 18 codes (`Ag As Ba De Fl Ga Hi Ht Ic In Lo Lt Na Ni Po Ri Va Wa`) |
| `TravelZone` (`StrEnum`) | `Green Amber Red` |
| `AtmosphereCode` (`IntEnum`) | codes 0–17 |

**`parse_uwp()` validation (`traveller_map_fetch.py`):** The UWP parser now raises `ValueError` (with chained exception context via `from exc`) for any of: wrong length, missing `-` separator at position 7, unrecognised starport letter, or non-hex digit in code positions. Previously it silently substituted defaults for malformed input.

**`World._validate_world_codes()` (`traveller_world_gen.py`):** New static method called at the top of `World.from_dict()`. Validates starport, atmosphere, temperature, trade codes, travel zone, and all integer range fields against the enum types and schema constraints. All validation failures raise `ValueError` with a descriptive message and chained exception context.

**Pyright CI:** `.github/workflows/typecheck.yml` added — runs `pyright` on every push/PR to `main`. `pyrightconfig.json` updated (`typeCheckingMode: "basic"`, explicit `exclude` list re-specifying all default patterns). `requirements-dev.txt` gains `pyright>=1.1.0`. Eight pre-existing Pyright errors in `traveller_world_gen.py`, `traveller_world_physical.py`, and `traveller_world_detail.py` were fixed: stored-boolean narrowing replaced with inline `isinstance()`, `Moon` forward reference resolved via `TYPE_CHECKING` guard, `hasattr()` narrowing replaced with `isinstance()`.

---

### Centralised display tables (issue #39)

Seven display-layer lookup tables previously duplicated across two to three files have been consolidated into a new `tables.py` module — a single definition is now the canonical source for each label set.

| Table | Previously defined in |
|---|---|
| Size → diameter label | `traveller_world_gen.py` ×2 |
| Size → gravity label | `traveller_world_gen.py` ×2 |
| Population → range label | `traveller_world_gen.py` ×2 |
| Trade code full names | `traveller_world_gen.py`, `gen-ui/app.py` |
| Base facility labels | `traveller_world_gen.py`, `gen-ui/app.py`, `render_system_json.py` |
| Travel zone → CSS class | `traveller_world_gen.py`, `gen-ui/app.py`, `render_system_json.py` |
| Tidal lock status labels | `traveller_world_physical.py`, `render_system_json.py` |

All five consumer files (`traveller_world_gen.py`, `traveller_system_gen.py`, `render_system_json.py`, `gen-ui/app.py`, `tests/test_world_physical.py`) now import from `tables`. No display output was changed.

---

### Pylint

`.pylintrc` restored after accidental deletion in commit f9f6ca1. The `[MESSAGES CONTROL]` block suppresses two structural false positives with inline documentation:

- `duplicate-code` — identical pipeline boilerplate exists across five entry-point files; several data-table copies are intentional to break circular imports. Tracked for future refactoring.
- `cyclic-import` — pre-existing `traveller_system_gen` → `traveller_world_detail` cycle resolved at runtime via `TYPE_CHECKING` guard. Tracked for cleanup.

Pylint 10.00/10 maintained across all core generation modules.

---

# Release Notes — v1.2.0

**Branch:** `feature/updates` → `main`
**Sessions:** 36–54
**Tests:** 1146

---

## Maintenance

### Static type-checking (Pyright / Pylance)

`pyrightconfig.json` added to the project root so Pylance resolves imports from
the project root (`extraPaths: ["."]`) consistent with the runtime `sys.path` that
`conftest.py` establishes for pytest.

All six test files made fully Pyright-clean (0 errors, 0 warnings):

| File | Issues fixed |
|------|-------------|
| `test_belt_physical.py` | 2 unguarded `system.mainworld` accesses |
| `test_function_app.py` | Azure stub used direct attribute assignment on `ModuleType` (→ `setattr()`); 4 unguarded `err` accesses |
| `test_hydro_detail.py` | 4 unguarded `generate_hydrographic_detail()` return accesses |
| `test_moon_gen.py` | `list[float | None]` not narrowed through intermediate comprehension |
| `test_traveller_world_gen.py` | Two pairs of shadowed class names; `Optional` attribute guards; `comp.orbit_number` arithmetic guards |
| `test_world_physical.py` | `_World` stub now inherits from `World`; mixed-type `**kwargs` dicts annotated `dict[str, Any]` |

**Notable bug found:** `TestWorldToDict` and `TestWorldToJson` were each declared
twice in `test_traveller_world_gen.py`. Python's namespace rules mean the second
definition silently replaced the first, so the first class's tests **never ran**.
The first instances are renamed `TestWorldToDictValues` and `TestWorldToJsonBasic`;
61 previously-invisible tests now execute.

**Source fix:** `World.to_json(indent: int = 2)` signature corrected to
`indent: Optional[int] = 2`, matching the docstring ("Pass `None` for compact
single-line output") and the `json.dumps` behaviour already in use.

**1146 tests** pass (1085 previously confirmed + 61 now un-shadowed).

---

## Improvements

### Basic Mean Temperature (Session 54, WBH p.47)

`WorldPhysical` gains `mean_temperature_k: Optional[int]` — the Basic Mean Temperature
in Kelvin computed from orbital position and atmosphere code.

**Formula:** modified roll = 7 (base/HZCO) + orbital DM + atmosphere DM.
Orbital DMs: `+4 +1 per 0.5 Orbit# below HZCO-1`; `−4 −1 per 0.5 Orbit# above HZCO+1`.
Atmosphere DMs are the same HZ Regions table DMs used for temperature categories.
Table lookup covers rolls 0–12 (178K–388K); extrapolates below 0 (−5K/step) and
above 12 (+50K/step); minimum 3K.

**Call sites:** `generate_world_physical()` gains `hz_deviation: Optional[float] = None`
parameter; `function_app._attach_mainworld_physical()` and `gen-ui/app.py` both pass
`mw_orbit.hz_deviation`. Value is absent when hz_deviation is not available (e.g., simple
standalone world generation without orbit context).

**Display:** all four HTML templates gain a "Mean temperature" row after "Day length";
`render_system_json.py._phys_rows()` and `traveller_world_schema.json` updated.

17 new tests in `TestOrbitDmForMeanTemp` (7) and `TestComputeMeanTemperature` (10);
**1085 tests** pass.

### HTML Template Refactor (Session 53, issue #40)

`World.to_html()` and `TravellerSystem.to_html()` now use Jinja2 templates
instead of hand-built f-strings. This eliminates doubled braces in CSS blocks,
makes the HTML structure directly editable without touching Python, and enables
Jinja2's built-in autoescaping (replaces the custom `esc()` helper).

**New files:**
- `html_render.py` — thin rendering module with a module-level `jinja2.Environment`
- `templates/world_card.html` — single world card
- `templates/world_list.html` — multi-world list (used by `--html` with multiple worlds)
- `templates/system_card.html` — full system card

**`requirements.txt`** gains `Jinja2>=3.1.0`.

The multi-world CLI `--html` output was previously stitched together with a fragile
regex that re-parsed each card's HTML. It now uses `world_list.html` directly.

---

## New Features

### Moon Tidal Lock DMs and Planet-to-Moon Lock (Session 52, WBH pp.106–107, issue #11)

Moon orbital positions (added in Session 51) unlock two previously deferred tidal effects.

**Moon-size DM in star-lock (WBH p.106):** `_tidal_lock_dm()` now subtracts the total size of all significant moons (Size 1+, non-ring) from the tidal lock DM when evaluating planet-to-star lock.

**Multi-star DM (WBH p.106):** `_tidal_lock_dm()` subtracts the number of stars orbited when > 1. Currently simplified to `num_stars_orbited=1` (full multi-star support deferred); the parameter is wired through the full call chain.

**Planet-to-moon lock (WBH p.107):** New `_planet_moon_lock_dm(moon, all_moons)` implements the WBH p.107 DM table: base −10, +Moon Size (Size 1+), PD-range DMs (orbit PD < 5: `+5 + ceil((5−PD)×5)`, 5–10: +4, 10–20: +2, 20–40: +1, 40–60: no DM, > 60: −6), −2 per moon beyond the first.

**Lock candidate ordering:** `_roll_tidal_lock_status()` now assembles all candidates (star + each qualifying moon), sorts by highest DM (moon before star on tie), and cascades until a lock result is found or all candidates are exhausted.

**Circular dependency resolution:** `WorldPhysical` needs moon data for DMs, but moons need `WorldPhysical` (diameter/mass) for Hill sphere. A new public `apply_moon_tidal_effects(physical, moons, ...)` function resolves this via a three-phase pipeline: `generate_world_physical()` runs first (no moon DMs), moons are generated using actual planet mass/diameter, then `apply_moon_tidal_effects()` re-runs tidal lock with full moon data and mutates `WorldPhysical` in-place.

New helpers in `_get_mainworld_moons()` and `_apply_mainworld_moon_tidal()` in `function_app.py` handle both GG satellite (moons at `orbit.detail.moons[0].detail.moons`) and non-GG (moons at `orbit.detail.moons`) cases. `gen-ui/app.py` `_finish_system_generation()` calls `apply_moon_tidal_effects()` after detail attachment.

24 new tests across `TestTidalLockDmMoon` (8), `TestPlanetMoonLockDm` (10), `TestRollTidalLockStatusMoons` (3), `TestApplyMoonTidalEffects` (3); **1068 tests** pass.

---

### Moon Quantity Adjacency DMs (Session 52, WBH p.56, issue #14)

Three of the four WBH p.56 moon quantity DM conditions that were previously deferred (blocked on moon orbital positions) are now implemented.

`_moon_quantity()` in `traveller_moon_gen.py` gains three new optional parameters, applied as `DM−1 per dice` when any condition is met (only one DM applies per world):

| Condition | Parameter |
|-----------|-----------|
| Planet orbit within companion star exclusion zone (±1 to +3 of companion orbit#) | `companion_exclusion_zones: list[tuple]` |
| Planet orbit adjacent to host star MAO boundary (±1.0) | `star_mao: float` |
| Planet orbit adjacent to outermost Far-star slot (±1.0) | `is_adjacent_outermost_far: bool` |

The fourth condition (`orbit_number < 1.0`) was already implemented. `generate_moons()` passes through the three new parameters.

`_moon_adjacency_context()` in `traveller_world_detail.py` computes these values from the system context (iterating `stellar_system.stars` for companions and Far stars, reading `system_orbits.star_mao`). The context dict is passed to `_moons_for()` and forwarded to both `generate_moons()` call sites in `generate_system_detail()` and `attach_detail()`.

8 new tests in `TestMoonQuantityAdjacencyDMs`; **1044 tests** after this feature (1068 after both features in Session 52).

---

### Moon Orbit Placement (Session 51, WBH pp.74–77, issue #16)

Moons now have orbital positions. `generate_moons()` accepts five new optional parameters (`orbit_au`, `star_mass_solar`, `planet_ecc`, `planet_diameter_km`, `planet_mass_earth`); when `orbit_au > 0` and `star_mass_solar > 0` the full orbit placement pipeline runs.

**Hill sphere** caps the outer moon limit: `Hill_AU = orbit_au × (1 − ecc) × ∛(mass_earth × 3e-6 / (3 × star_mass_solar))`, converted to PD by dividing by planet diameter. The practical moon limit is `floor(Hill_PD / 2)`.

**Moon removal:** if the moon limit is < 1 PD, no moons or rings survive; if 1 PD, significant moons are converted to a ring.

**Moon Orbit Range** = `Moon Limit − 2` (capped at `200 + n_moons`). Each moon rolls independently on the Inner/Middle/Outer table (DM+1 when MOR < 60), PDs are sorted ascending (closest-first), and adjacent collisions are resolved by bumping the outer moon out 1 PD.

**Orbital period** in hours: `√(orbit_km³ / mass_earth) / 361730`.

**Ring placement:** centre = `0.4 + roll(2)/8` PD, span = `roll(3)/100 + 0.07` PD; inner edge clamped ≥ 0.55 PD.

For secondary worlds (no `WorldPhysical`), mass and diameter are estimated from size code. For the mainworld, `WorldPhysical.diameter_km` and `WorldPhysical.mass` are used directly. `attach_detail()` and `_moons_for()` automatically pass orbit data to `generate_moons()`.

Moon orbit eccentricity and retrograde direction (WBH p.76) are deferred; the fields exist on `Moon` but default to 0.0/False.

22 new tests in `tests/test_moon_gen.py`; **1036 tests** pass.

---

### Tidal Lock Eccentricity DM (Session 50, WBH p.105)

The eccentricity DM for the Tidal Lock Status table is now applied. WBH p.105 specifies this as a general DM for all cases: when `eccentricity > 0.1`, apply `DM − floor(eccentricity × 10)`. Examples: e=0.25 → DM−2; e=0.50 → DM−5; e=0.999 → DM−9.

`_tidal_lock_dm()` gains `orbit_eccentricity: float = 0.0` as a new parameter; threaded through `_roll_tidal_lock_status()` and into `generate_world_physical()` (which already accepted `orbit_eccentricity` since Session 44). No seed disruption when `orbital_eccentricity=False` (default) — the parameter defaults to 0.0 and applies no DM. When the flag is True, tidal lock outcomes for worlds with `eccentricity > 0.1` will shift (fewer locks for eccentric orbits).

The stale "Orbital eccentricity" entry has been removed from `context/deferred-features.md` — that feature was fully implemented across Sessions 43 (orbital eccentricity rolls) and 48 (anomalous orbit DMs).

6 new tests in `TestTidalLockEccentricityDm`; **1014 tests** pass.

---

### System JSON HTML Renderer (Session 49)

New standalone script `render_system_json.py` reads any system JSON file produced by `TravellerSystem.to_dict()` and renders it as a rich, self-contained HTML document. No project module imports are required — the script uses Python stdlib only (`json`, `sys`, `html`, `pathlib`).

**Usage:**
```bash
python render_system_json.py system.json [output.html]
```
Output defaults to `<input-stem>.html` in the same directory.

**Rendered sections:**
- System header (name, age, star count, seed, mainworld UWP)
- Stars table (designation, type, mass, temperature, diameter, luminosity, orbit, period)
- Habitable zones summary (per star: HZ range, MAO, temperature zone)
- World count chips (gas giants, belts, terrestrials, total, empty)
- Orbital survey table — 11 columns: Star, #, Orbit#, AU, Period, Ecc/Incl, Type, Profile, Codes, Zone, Notes; moon sub-rows when `attach_detail()` has been called
- Mainworld panel: 11-cell stats grid, trade code badges, World Body card (WorldPhysical or BeltPhysical), atmosphere detail card (profile, pressure, O₂, scale height, taints, gas mix, altitude bands), hydrographic detail card, notes
- Raw JSON collapsible `<details>` block

Distinguishes `WorldPhysical` vs `BeltPhysical` by checking for `"composition"` key. CSS matches the existing `to_html()` design: CSS variables, dark mode, colour-coded temperature zones, trade code badges. Pylint 10.00/10.

Sample output: `examples/system_seed42.html` (seed=42, 3-star system named Aramis, mainworld UWP D200000-0, full eccentricity + inclination).

---

### Orbital Inclination (Session 46, issue #59)

WBH p.28 orbital inclination is now implemented as an optional gated feature using the same pattern as orbital eccentricity.

**`_roll_inclination()`** uses a 6-row severity table (2D ≤ 6 = Very Low through 2D = 11 = Extreme), each with a different degree formula, plus a recursive retrograde case (2D = 12 → `180 − re-roll`). Anomalous orbits already typed as `"inclined"` are skipped (their angle is stored in `notes`).

**New fields:**
- `OrbitSlot.inclination: float = 0.0` — `to_dict()` emits `"inclination"` (2 d.p.) when > 0
- `Star.orbit_inclination: float = 0.0` — `to_dict()` emits `"orbit_inclination"` when > 0
- `TravellerSystem.orbital_inclination: bool = False`

**API:** `parse_orbital_inclination()` added to `shared/helpers.py`; wired through all 5 system endpoints.

**Display:** The "Ecc" column is renamed **"Ecc/Incl"** in both gen-ui and HTML. When both are set, the cell shows `0.123/45.0°`; when only one is set, the other shows `—`; when neither is set, the cell shows just `—`.

**gen-ui:** "Orbital Inclination" checkbox added (enabled only when "System detail" is checked). When False (default), no dice fire — no seed disruption.

---

### Orbital Eccentricity Display Column (Session 44 cont.)

The inline `(e=X.XXX)` text formerly embedded in the AU cell of both the gen-ui System Orbits card and the `to_html()` orbit table has been replaced with a dedicated right-aligned **Ecc** column inserted after **AU**.

- Shows `0.350` (3 d.p.) when `OrbitSlot.eccentricity > 0`; `—` otherwise
- gen-ui detail_attached variant: 11 columns — `Star | Orbit# | AU | Ecc | Type | Profile | Codes | HZ | Zone | Period | Notes`; `right_cols={1,2,3,9}`
- gen-ui non-attached variant: 9 columns — `Star | Orbit# | AU | Ecc | Type | HZ | Zone | Period | Notes`; `right_cols={1,2,3,7}`
- HTML table: `<th>Ecc</th>` added after `<th>AU</th>`; moon sub-row `colspan` widened from 3 → 4
- System map SVG retains the inline `(e=0.35)` in the AU text column (no SVG layout change)

A missing **"Orbital Eccentricity"** checkbox was also added to the gen-ui toolbar row (alongside "NHZ Atmospheres", enabled only when "System detail" is checked). Without this checkbox, `generate_full_system()` was always called with `orbital_eccentricity=False`, leaving every `OrbitSlot.eccentricity` at 0.0 and the Ecc column always showing `—`.

---

### 1:1 Tidal Lock Axial Tilt & Eccentricity (Session 44, issue #10)

WBH p.77 Rules 3 and 4 for 1:1 tidal lock interactions are now implemented.

**Rule 3 — Axial tilt recomputed with 1D on Axial Tilt table.** Previously the 1:1 lock path used `(2D-2)/10` with a `> 3.0` guard (incorrect). New helper `_roll_axial_tilt_1d()` rolls 1D to select the outer band of the Axial Tilt table (the same 6 rows as `_roll_axial_tilt()`), then 1D within the band. The recompute is unconditional — any initial axial tilt is replaced.

**Rule 4 — Eccentricity reduction.** `generate_world_physical()` gains an `orbit_eccentricity: float = 0.0` parameter. When a world reaches 1:1 lock and `orbit_eccentricity > 0.1`, `_reroll_eccentricity_tidal()` re-rolls with DM-2 (using `_ECC_TABLE_PHYS`, an inline copy of the eccentricity table to avoid circular imports). The lower value is stored in new `WorldPhysical.eccentricity_adjusted` (`Optional[float]`, `init=False`). `_attach_mainworld_physical()` in `function_app.py` reads this field and writes it back to the orbit slot, updating the eccentricity that appears in JSON output and system maps.

**Seed impact:** The axial tilt change is seed-breaking for 1:1 locked worlds (same dice count, different interpretation). Eccentricity path only fires for locked worlds with `eccentricity > 0.1` when the orbital eccentricity feature flag is enabled.

---

### Orbital Eccentricity (Session 43, issue #57)

WBH p.27 orbital eccentricity is now implemented as an optional feature gated on `orbital_eccentricity=False`.

**Roll mechanic:** Two dice rolls per orbit. A first `2D+DM` selects a row in the six-row Eccentricity Values table; a second `1D` or `2D` roll divided by a row-specific divisor gives the fractional part. Final value is clamped to [0.000, 0.999].

**DMs (first roll only):**

| Condition | DM |
|---|---|
| Star eccentricities | +2 |
| Each close/near/far star with orbit# < slot (primary slots) | +1 per star |
| Orbit# < 1.0 and system age > 1 Gyr | −1 |
| Belt slot | +1 |

**Min/Max separation:** `AU × (1 − eccentricity)` and `AU × (1 + eccentricity)`

**New fields:**
- `OrbitSlot.eccentricity: float` — `field(default=0.0, init=False)`; `to_dict()` emits `"eccentricity"`, `"orbit_au_min"`, `"orbit_au_max"` when non-zero
- `Star.orbit_eccentricity: float = 0.0` — set for secondary stars by `generate_orbits()`; `to_dict()` emits when non-zero

**Flag plumbing:** `orbital_eccentricity` parameter added to `generate_orbits()`, `generate_full_system()`, `generate_system_from_world()`, and all relevant API endpoints. New `parse_orbital_eccentricity()` helper in `shared/helpers.py` reads the query parameter.

**Display:** System map AU text shows `1.234 (e=0.35)` inline when eccentricity > 0. gen-ui System Orbits card and `to_html()` orbit table each have a dedicated `Ecc` column (see above).

**Seed impact:** Flag False (default) → no new dice, no seed disruption. Flag True → seed-breaking (2 rolls per non-empty slot + 2 per secondary star).

---

### Orbit Notes Column (Session 41 cont.)

`OrbitSlot.notes` is now surfaced in every output that displays the orbit table:

- **gen-ui** — System Orbits card gains a trailing `Notes` column in both header variants: 10 columns (detail attached: `Star | Orbit# | AU | Type | Profile | Codes | HZ | Zone | Period | Notes`) and 8 columns (no detail: `Star | Orbit# | AU | Type | HZ | Zone | Period | Notes`).
- **`TravellerSystem.to_html()`** — orbit table notes cell now uses a `note_parts` list that combines the `"← mainworld"` marker with `OrbitSlot.notes`, showing all notes unconditionally for every orbit row (HZ placement notes, anomaly type notes, etc.).

---

### Anomalous Orbits (Session 41, issue #12)

WBH Step 7 (pp.49-50) is now implemented. After normal orbit placement, `generate_orbits()` rolls for anomalous orbit count (2D: ≤9 = 0, 10 = 1, 11 = 2, 12 = 3) and type.

**Anomaly types:**

| Type | Frequency | Effect |
|------|-----------|--------|
| Random | 2D ≤ 7 | Orbit placed anywhere in the star's valid zone |
| Eccentric | 2D = 8 | As random (eccentricity DM deferred) |
| Inclined | 2D = 9 | Inclination rolled (1D+2)×10° + d10; stored in notes |
| Retrograde | 2D = 10–11 | "Retrograde" noted |
| Trojan | 2D = 12 | Co-orbital with an existing non-empty world; 1D ≤ 3 → leading (L4), ≥ 4 → trailing (L5) |

Each anomalous orbit adds one terrestrial (or belt when the maximum of 13 terrestrials has been reached). In multi-star systems the star is chosen randomly from those with available orbit space.

Anomalous orbit positions respect companion exclusion bands (the same valid zone bounds used for normal placement, with ±0.01 clearance from each boundary to avoid landing exactly on the band edge).

**New field:** `OrbitSlot.anomaly_type: str` — one of `""`, `"random"`, `"eccentric"`, `"inclined"`, `"retrograde"`, `"trojan_leading"`, `"trojan_trailing"`. Included in `to_dict()` when non-empty.

**Display:**
- `system_map.py` — anomaly indicator appended to the type column: `"terr *"`, `"terr ~"`, `"terr /"`, `"terr R"`, `"terr L4"`, `"terr L5"`; belts use analogous `"belt ..."` labels
- `TravellerSystem.to_html()` orbit table — anomaly notes shown in the notes column (e.g., `[Inclined 45°]`, `[Trojan leading (L4)]`)
- `SystemOrbits.summary()` text output — same notes shown inline

**Seed impact:** The new `roll(2)` for anomalous count fires for every system — all seeds shift from Session 41 onwards.

---

### Orbital Periods (Session 40)

Kepler orbital periods are now computed and displayed for every star and world in a generated system.

**Stellar periods (`Star.orbit_period_yr`)**

`generate_stellar_data()` computes `P = √(AU³ / (M_central + m))` for every non-primary star after all dice rolls are complete (no seed disruption). Central mass rules follow WBH:
- Companion stars (e.g. Ab orbiting A): M_central = parent mass only
- Secondary stars (e.g. B, C): M_central = combined mass of all stars with effective system orbit# < this star's orbit#

`_eff_sysorn()` ensures that a companion to a secondary (e.g. Ba) uses its parent's orbit# when computing central mass for farther secondaries (so Ca's M_central correctly includes Ba). Periods are included in `Star.to_dict()` and `StarSystem.summary()`.

**World periods (`OrbitSlot.orbit_period_yr`)**

`generate_orbits()` computes `P = √(AU³ / M_central)` for every non-empty orbit slot after placement. M_central = designated star mass plus any companions whose `orbit_au < world.orbit_au` (WBH: worlds outside a tight companion include it in the central mass). Planet mass correction (`mE × 0.000003`) is omitted as negligible. Periods are emitted in `OrbitSlot.to_dict()`.

**Display — `system_map.py` and gen-ui**

- New `Period` column (x=490) in the orbit table of every system map, populated for both star rows and world rows
- `_fmt_period()` module-level helper auto-scales: `< 1 day → Xh`, `1–365 days → Xd`, `≥ 365 days → Xy`
- gen-ui System Orbits card gains a `Period` column in both detail-attached and non-attached variants
- gen-ui Stellar card gains a `Period` column (7 columns total, right-aligned)

---

### System Map — Column Label Sub-header Row (Session 39)

The orbit table in every system map now displays a column label row (`#  Orbit#  AU  Type  Profile  Codes  Zone ♦`) between the star header and the first world row. `Zone ♦` makes explicit that the last column shows both the temperature zone and moon count. `_TBL_ROW0_OFF` bumped from 38 to 50 px to accommodate the new row.

---

### Primary Star Outer Zone Placement (Session 39)

Primary stars in binary systems now populate the outer zone `[companion + 3.0, 17.0]` as well as the inner zone `[MAO, companion − 1.0]`. Previously all primary worlds were placed in the inner zone; the outer zone was unused.

A `star_outer` dict tracks the outer zone bounds. `_avail_range()` includes the outer range in proportional world allocation across stars. The placement loop wraps in a `for zone in zones` iterator that runs once per zone (inner, then outer), keeping the existing baseline → spread → slot logic unchanged within each pass.

Seed-breaking for any primary star that has a close/near/far companion with a valid inner zone.

---

### NHZ Atmosphere Generation (Session 38)

Out-of-habitable-zone worlds now roll NHZ atmosphere codes when the `nhz_atmospheres` flag is set. Two new atmosphere codes are added: code 16 (Gas, Helium / G) and code 17 (Gas, Hydrogen / H).

Four NHZ tables cover the four deviation bands (HZCO ≤ −2.01, −2.0 to −1.01, +1.01 to +3.0, ≥ +3.01). Each table result carries an atmosphere code, an optional exotic subtype key, and display markers. NHZ worlds with an exotic subtype bypass the standard `_roll_exotic_subtype()` roll.

NHZ generation is applied to mainworlds, secondary worlds, and moons:
- `generate_full_system()` and `generate_mainworld_at_orbit()` accept `nhz_atmospheres: bool = False`
- `TravellerSystem` stores `nhz_atmospheres` and threads it through `attach_detail()` to all secondary-world and moon paths
- gen-ui: "NHZ Atmospheres" checkbox added (enabled only when System detail is checked)
- CLI: `--nhz-atmospheres` flag added
- JSON Schema: `atmosphere.code.maximum` updated from 15 to 17

---

### Hydrographic Detail (Session 37)

New module `traveller_hydro_detail.py` implements WBH p.93 surface liquid percentages.

`HydrographicDetail` dataclass carries `surface_liquid_pct` (a flat random value within the WBH code range). `generate_hydrographic_detail()` is called from the shared section of `traveller_system_gen.py` and all API handlers. Exposed in:
- **JSON** — `hydrographics.detail.surface_liquid_pct`
- **HTML** — Hydrographic Detail inner-card in `World.to_html()`, `TravellerSystem.to_html()`, and `World.summary()`
- **gen-ui** — `_build_hydrographic_card()`

---

## Bug Fixes

### JSON Schema Missing `eccentricity_adjusted` Property (Session 49)

`WorldPhysical.to_dict()` emits `eccentricity_adjusted` when `tidal_status == "1:1_lock"` and
`orbit_eccentricity > 0.1` (WBH p.77 Rule 4), but the property was absent from the
`WorldPhysical` branch of `traveller_world_schema.json`. Validation with `jsonschema.validate()`
failed for any such world with the error "is not valid under any of the given schemas ['size_detail']"
(due to `"additionalProperties": false`).

Fix: `eccentricity_adjusted` added as an optional `number` property (`minimum: 0`, `maximum: 0.999`)
to `size_detail.oneOf[0].properties` (the `WorldPhysical` branch). No code change — the schema was
the only gap. The case is rare (requires 1:1 lock **and** `eccentricity > 0.1`), which is why it
was not caught by the existing 200-seed validation sweep in the test suite.

---

### Anomalous Orbit Eccentricity DMs Not Applied (Session 48, issue #64)

WBH pp.49-50 specifies DMs on the Eccentricity Values table for anomalous orbit types.
These DMs were silently ignored — all anomalous orbits used the base table.

| Anomaly type | WBH DM | Was applied |
|---|---|---|
| Random | +2 | No |
| Eccentric | +5 | No |
| Inclined | +2 | No |
| Retrograde | +2 | No |

Fix: added `_ANOM_ECC_DM` lookup dict and `anomaly_dm: int = 0` parameter to
`_roll_eccentricity()`. The eccentricity pass in `generate_orbits()` now passes
`anomaly_dm=_ANOM_ECC_DM.get(o.anomaly_type, 0)` for each orbit slot. No seed
disruption for systems without anomalous orbits. 6 regression tests added
(`TestAnomalyEccentricityDMs`); 1008 tests pass.

---

### Orbital Flags Not Wired Through TravellerMap Endpoints (Session 47, issue #63)

`orbital_eccentricity` and `orbital_inclination` parameters were silently ignored on both `/api/map/system` and `/api/map/system/{name}`. Three layers all missed the flags:

1. `generate_system_from_map()` called `generate_orbits(stellar)` with no keyword arguments and did not accept the flags at all.
2. The shared `_map_system_response()` helper had no `want_ecc` / `want_incl` parameters.
3. Neither endpoint handler called `parse_orbital_eccentricity()` or `parse_orbital_inclination()`.

A fourth gap in gen-ui was also found: `_do_travellermap_generation()` and both its call sites were not forwarding checkbox state.

Fix: flags added to `generate_system_from_map()` signature and threaded into `generate_orbits()` and the `TravellerSystem` constructor. Both `_map_system_response()` and the two endpoint handlers updated to parse and forward the flags. gen-ui call sites updated. 4 regression tests added (`TestGenerateSystemFromMapOrbitalFlags`); 1002 tests pass.

---

### JSON Unicode Error on Windows (Session 45, issue #60)

`open(schema_path)` in `tests/test_traveller_world_gen.py` was called without `encoding="utf-8"`. On Windows, Python defaults to the system codepage (cp1252), which cannot decode the non-ASCII characters in `traveller_world_schema.json` (e.g. `–` U+2013, `…` U+2026). Fixed to `open(schema_path, encoding="utf-8")`, matching the pattern used elsewhere in the test file.

---

### Virtual Environment Consolidated (Session 45, issues #61 and #62)

The dual-environment setup (`.venv` for Azure Functions, `.venv-1` for PySide6/gen-ui) has been replaced by a single `.venv` that contains all dependencies.

- `requirements-dev.txt` added for pytest and pylint
- Install scripts (`install.sh`, `install.ps1`, `install.bat`) now install all three requirements files in one pass and activate the venv at the end
- All `.vscode/settings.json`, `docs/VSCODE.md`, `docs/developer-guide.md`, `docs/uat-plan.md`, and `gen-ui/README.md` updated from `.venv-1` to `.venv`

---

### Incorrect Belt Counts for Fetched Mainworlds (Session 42, issue #52)

Two bugs in `traveller_map_fetch.py` caused the belt count shown in the orbit table to differ from the canonical PBG value on TravellerMap.

**Bug 1 — Pool truncation always dropped belts.** `_reconcile_orbit_types()` built the redistribution pool as `["gas_giant"] * canonical_gg + ["belt"] * canonical_belt` and truncated with `pool[:n]` before shuffling. Because gas giants are at the front of the pool, all GGs were preserved and only belts were dropped when there were too few available orbit slots. Fix: when `canonical_gg + canonical_belt > n`, empty orbit slots are now promoted to world slots before distribution, ensuring the canonical counts are always honoured.

**Bug 2 — Mainworld belt double-counted.** The WBH PBG convention (confirmed at `generate_belt_count()` line 2611) includes the mainworld in the belt count when the mainworld is Size 0. `_reconcile_orbit_types()` was distributing the full `canonical_belt` count among non-mainworld slots, and Step 6 then separately set the mainworld slot to `"belt"`, producing `canonical_belt + 1` total belts. Fix: `generate_system_from_map()` now subtracts 1 from `canonical_belt` before calling `_reconcile_orbit_types()` when `world.size == 0`.

---

### Companion Star Exclusion Zone (Session 39)

When a companion orbit# was less than 1.0, `excl = companion_orbit − 1.0` was ≤ 0 and never triggered the `max_o` cap, allowing primary worlds inside the WBH exclusion band `[companion − 1, companion + 3]`. Fixed: an `else` branch now pushes `mao = max(mao, companion_orbit + 3.0)` and syncs `star_mao[designation]` in-place.

`system_map.py` extended to render companion star rows inside the primary star's orbit-table section, sorted by orbit number.

---

### H/L Oxygen Taint Validation (Session 37, issue #55)

`_roll_single_taint()` now accepts `ppo: Optional[float]` and rerolls High Oxygen (H) results unless `ppo > 0.5 bar`, and Low Oxygen (L) results unless `ppo < 0.1 bar`. The `ppo` computation was moved before the taint block in `generate_atmosphere_detail()` so it is available at taint time. Seed-breaking for tainted atmosphere codes.

---

### System HTML Missing Mainworld Detail (Session 36, issue #51)

`TravellerSystem.to_html()` was omitting the `WorldPhysical` and atmosphere detail inner-cards from the mainworld panel — only `BeltPhysical` was handled. Added `.inner-card`, `.inner-lbl`, `.drow`, `.dlbl` CSS; `drow()` helper; and imports for `WorldPhysical`, `TIDAL_STATUS_LABELS`, and `format_atmosphere_profile()`.

### TravellerMap Fetch Incomplete Atmosphere Pipeline (Session 36, issue #51)

`generate_system_from_map()` was not calling `generate_gas_mix()` or `generate_unusual_subtype()` after `generate_atmosphere_detail()`, leaving gas composition and unusual subtypes absent for TravellerMap-fetched worlds. Also threaded `hz_deviation` into `generate_atmosphere_detail()` for orbit-position DMs. Both calls now follow the same pipeline as procedurally generated worlds.

---

## Test Coverage

| Scope | Tests added |
|---|---|
| `traveller_hydro_detail.py` — surface liquid percentages | +29 |
| H/L oxygen taint ppo validation | +6 |
| NHZ atmosphere generation (mainworld) | +33 |
| NHZ atmosphere generation (secondary worlds and moons) | +5 |
| Companion star exclusion zone fix | +2 |
| Primary star outer zone placement | +4 |
| Anomalous orbits (Step 7) | +6 |
| Incorrect belt counts for fetched mainworlds (issue #52) | +4 |
| Orbital eccentricity (issue #57) | +6 |
| Orbital inclination (issue #59) | +8 |
| TravellerMap orbital flag wiring (issue #63) | +4 |
| Anomalous orbit eccentricity DMs (issue #64) | +6 |
| Moon orbit placement (issue #16) | +22 |
| Moon quantity adjacency DMs (issue #14) | +8 |
| Moon tidal lock DMs and planet-to-moon lock (issue #11) | +24 |
| **Total new tests** | **+167** |
| **Suite total** | **1068** |

All 1068 tests pass. Pylint 10.00/10 on all core generation modules.

---

# Release Notes — v1.1.0

**Branch:** `feature/updates` → `main`
**Sessions:** 23–35
**Tests:** 890 (up from 523 in v1.0)

---

## New Features

### World Physical Detail

A new module `traveller_world_physical.py` implements the WBH physical world generation rules, producing a `WorldPhysical` record for every non-belt world that has physical detail requested.

**Fields generated:**
- Composition (silicate/ferric/icy/rocky) and density (g/cm³)
- Diameter (km), mass (M⊕), surface gravity (G), escape velocity (km/s)
- Axial tilt, including the full WBH p.77 extreme-tilt sub-table (6-band 1D table producing 20°–179° results)
- Rotation period (day length in hours)
- **Tidal lock status** (WBH pp. 105–107): 11-outcome table covering no-effect, tidal braking (×1.5–×5), prograde/retrograde spin, 3:2 resonance, and 1:1 lock; includes broken-lock check and axial tilt reroll for locked worlds

Physical detail is exposed in all output formats:
- **JSON** — `size_detail` object in world output
- **Text** — `World body` section in `summary()`
- **HTML** — `World body` inner-card in `to_html()`; Size stat box now shows actual rolled diameter and gravity rather than look-up table approximations
- **gen-ui** — new `Physical detail` checkbox (active only when `Full system` is checked); stellar card displays system age; `_build_physical_card()` renders the full physical card below trade codes

---

### Belt Physical Detail

A new module `traveller_belt_physical.py` implements WBH pp. 131–133 for asteroid belts, producing a `BeltPhysical` record for every belt orbit slot — whether a secondary world or the mainworld.

**Fields generated:**
- Belt span (inner and outer AU boundaries)
- Composition percentages: m-type (metallic), s-type (silicate), c-type (carbonaceous), and other
- Belt bulk (2D+2+DMs, minimum 1)
- Resource rating (2–12), with exploitation reduction for Industrial TL 8+ mainworlds
- Significant body counts: Size 1 planetoids and Size S planetoids (with optional outermost-orbit variance)

Belt physical detail is exposed in all output formats:
- **JSON** — `physical` object in `WorldDetail.to_dict()` for every belt slot
- **HTML** — `Belt body` block in the system mainworld panel
- **gen-ui** — `_build_physical_card()` dispatches on `BeltPhysical` to render span, composition, bulk, resource rating, and significant body counts

---

### Atmosphere Detail (WBH pp. 78–93)

Five phases of WBH atmosphere detail have been fully implemented, adding quantitative atmosphere data to every mainworld. All data is exposed in JSON, HTML, text summary, and the gen-ui atmosphere card.

**Phase 1 — Pressure, O₂, and scale height (WBH pp. 78–82)**

A new `AtmosphereDetail` dataclass and `generate_atmosphere_detail()` function compute:
- Surface pressure (bar), sampled from the WBH pressure span table with (2D−7)/100 variance
- Oxygen partial pressure, with DM+1 for systems older than 4 Gyr
- Atmospheric scale height (km), approximated as 8.5 / surface gravity
- WBH p.82 profile string: `{code}-{pressure_bar:.3f}-{ppo:.3f}`, e.g. `6-1.013-0.212` for Terra

**Phase 2 — Atmosphere taints (WBH pp. 82–85)**

Taint generation for tainted atmosphere codes (2, 4, 7, 9), with each taint carrying:
- Subtype (Radioactivity, Particulates, Low Oxygen, High CO₂, etc.)
- Severity (scale 1–9, labelled from "Minor irritant" to "Inevitably lethal")
- Persistence (scale 2–9, from "Constant" to "Rare, brief event")
- Cascade mechanic: Particulates result triggers a second taint roll

Taint suffix appended to profile string as `-T.S.P` per taint.

**Phase 3 — Exotic and corrosive/insidious subtypes (WBH pp. 85–87)**

Subtype rolls for Exotic (code 10/A), Corrosive (code 11/B), and Insidious (code 12/C) atmospheres, with:
- Orbit-position DMs on both subtype tables
- 14-entry Exotic subtype table; 14-entry Corrosive/Insidious subtype table
- Insidious hazards: up to 3 hazard rolls per world, each with optional additional gas
- Unbound pressure subtypes (C/D/E) represented as `None` in the model; displayed as `> 10.0 bar`

**Phase 4 — Gas composition (WBH pp. 87–95)**

Full gas mix generation for Exotic/Corrosive/Insidious atmospheres:
- 7 temperature-banded gas tables (Boiling-VH, Boiling-H, Hot, Temperate, Cold, Frozen-M, Frozen-D)
- 24 named gases, each with an eHex percentage
- CO* substitution: CO → CO₂ when not frozen with water; CO → N₂ when frozen with water
- Gas codes appended to profile string as `:code-##` tokens

**Phase 5 — Altitude bands and Unusual subtypes (WBH pp. 90–93)**

Altitude band computation for Very Dense (code 13/D) and Low (code 14/E) atmospheres:
- Minimum safe altitude above baseline (code 13) or maximum safe depth below baseline (code 14), derived from the WBH Bad Ratio formula: `altitude = ln(bad_ratio) × scale_height`
- `no_safe_altitude = True` when no breathable level exists
- Optional taint roll (1D ≥ 4) for codes 13 and 14

D26 subtype generation for Unusual (code 15/F) atmospheres:
- 12-entry D26 table (11–26) covering Dense subtypes, Ellipsoid, High Radiation, Layered, Panthalassic, Steam, Variable Pressure, Variable Composition, Combination, and Other
- Prerequisite checks: Layered requires size ≥ 9 (gravity > 1.2 G); Panthalassic requires hydro = 10; Steam requires hydro ≥ 5
- Combination result (D26 = 25) produces two independent non-Combination subtypes
- Profile string format: `F-S{code}` or `F-S{code1}.{code2}`, e.g. `F-S7` or `F-S3.A`

---

## Bug Fixes

### Gas Giant Mainworld Orbit Display (issue #22)

When the mainworld was a satellite of a gas giant, the orbit table showed the satellite's UWP profile (e.g. `A689521-B`) instead of the gas giant's profile (e.g. `GM7`). A secondary symptom caused the satellite to disappear entirely when the gas giant had no additional moons.

Fixed across three layers: `attach_detail()` now uses `orbit.gg_sah` for gas giant mainworld orbits and inserts the satellite as `moons[0]`; `_orbit_profile()` in gen-ui returns `gg_sah` first; `to_html()` in `TravellerSystem` uses `gg_sah` for CSS class and profile display in both detail-attached and no-detail paths.

### Belt Mainworld Display Crash in gen-ui (Session 30)

When generating a belt mainworld with physical detail enabled, `_build_stat_row()` attempted to access `physical.diameter_km` and `physical.gravity` — attributes present on `WorldPhysical` but not on `BeltPhysical`. The uncaught exception left only the header bar visible and silently discarded the scroll area. Fixed with an `isinstance(physical, BeltPhysical)` guard.

### Belt Span Formula Correction (issue #27, Session 30)

Belt span was computed using the AU range of the entire system (`max_au − min_au`) instead of the correct WBH p.131 "system orbit spread" — the per-slot orbital generation step `(max Orbit# − MAO) / n_orbits`. This produced wildly oversized spans (e.g. 0–11.97 AU for a belt at 0.35 AU). After correction, spans are physically plausible (e.g. 0.034–0.662 AU for the same belt). The fix applies to both secondary belts (`generate_system_detail()`) and mainworld belts (`attach_detail()`), with the spread computed per-star.

### Belt Bulk Formula Correction (Session 30)

Belt bulk was computed as 2×D2+DMs (range 2–4 before DMs), inconsistent with WBH p.132 which specifies 2D+2+DMs. Updated to `_roll(2, 2 + dm)` (range 4–14 before DMs).

---

## Test Coverage

| Scope | Tests added |
|---|---|
| `traveller_world_physical.py` — physical detail + tidal lock | +91 |
| `traveller_belt_physical.py` — belt span, composition, bulk, rating, bodies | +45 |
| Belt mainworld `attach_detail()` integration | +4 |
| Atmosphere Phase 1 — pressure, O₂, scale height | +52 |
| Atmosphere Phase 2 — taints (subtype, severity, persistence, cascade) | +42 |
| Atmosphere Phase 3 — exotic/CI subtypes, insidious hazards | +33 |
| Atmosphere Phase 4 — gas composition (7 tables, CO* substitution, profile) | +62 |
| Atmosphere Phase 5 — altitude bands, unusual subtypes, display | +58 |
| API and display regression tests | +8 |
| **Total new tests** | **+367** |
| **Suite total** | **890** |

All 890 tests pass. Pylint 10.00/10 on all core generation modules.
