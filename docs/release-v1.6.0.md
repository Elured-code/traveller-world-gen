# Traveller World Generator — v1.6.0 Release Notes

**3023 tests pass. Pylint 10.00/10.**

Sessions 104–177. This is the largest release since the project's founding: the
generation pipeline was unified so CLI, desktop, and web all produce the same
world for the same seed; the WBH social characteristics chain grew to cover
culture, economics, world importance, starports, and travel zones; a native
FastAPI web server matured into a fully-featured application with survey forms
and an in-app help system; the system map gained a full 3-D perspective
renderer and an A3 poster export; and Novelty Tech Level and the runaway
greenhouse rule were extended to their full WBH scope. Alongside the features,
this release closes a long tail of seed-reproducibility and cross-platform
consistency bugs, and moves the codebase to an installable `src/` package
layout with a hardened, Flex-Consumption FastAPI deployment.

---

## Mainworld Selection, Pipeline Unification & Cross-Platform Consistency

### Same Seed, Same World (Sessions 116, 119)

For a long time, the CLI, the desktop app, and the FastAPI web server could
each produce a *different* mainworld from the *same* seed, because each entry
point threaded (or failed to thread) the seeded `random.Random` instance
differently. FastAPI's physical-detail step was quietly advancing the global
`random` module instead of the shared RNG object, leaving the web server's
population/government/tech-level rolls out of sync with gen-ui's. The CLI was
missing the social-generation step entirely, so command-line mainworlds never
got past placeholder starport `X` and all-zero social codes. Both are fixed:
every generation path now threads one `random.Random(seed)` through the whole
pipeline, and the CLI gained `--orbital-eccentricity` / `--orbital-inclination`
flags to match the other two front ends.

### `system_pipeline.py`: One Pipeline for All Three Entry Points (Session 120)

The post-generation orchestration — attach physical detail, attach world
detail, name bodies, apply tidal effects, optionally select a mainworld,
apply social detail, optionally attach population/government/law/tech detail —
was previously duplicated (with small drifts) across the CLI, gen-ui, and
FastAPI. A new `system_pipeline.py` module and its `PipelineOptions` dataclass
now run that exact ordered sequence once, called identically from all three
places. This removed roughly 130 lines of near-duplicate pipeline code and
closes off an entire class of "it works in the desktop app but not on the
web" bugs. Advanced Mean Temperature is now always computed as part of this
pipeline, rather than being an opt-in checkbox.

### Reproducibility Fixes (Sessions 116, 177)

Two related reproducibility bugs were found and fixed: FastAPI was making two
separate API calls per generation (one for the system, one for the mainworld
card) that could diverge from each other, now merged into a single
`include_mw_card` response so both come from one generation pass; and a
TravellerMap-sourced system could show its mainworld orbiting a different star
depending on which part of the app was asked, because secondary star
positions and system age weren't actually keyed to the seed in that code path.
The seed-position bug also touched mainworld selection, occasionally promoting
the wrong world to mainworld. All are now fully deterministic for a given
seed.

### Orbit Numbering & Missing Secondary Star (Session 167)

In systems where a companion star's exclusion zone splits a star's own worlds
into an inner and an outer placement zone, the Orbital survey table's `#`
column used to restart numbering at 1 for the outer zone — which, worse, could
cause `attach_detail()` to attribute a world's generated detail to the wrong
orbit. Numbering is now continuous. A close/near/far secondary star with no
orbit slots of its own (all its worlds ended up orbiting the primary instead)
used to be invisible in the table entirely; it now appears as a row under the
primary, positioned by orbital radius.

---

## Social, Economic & Cultural Characteristics

This release completes most of the WBH Social Characteristics checklist begun
in v1.5.0, adding culture, economics, world importance, starport traffic, and
extended travel zone determination on top of the existing population,
government, and law level detail.

### World Importance & Culture (Sessions 127–130, 132)

Every inhabited world now gets a deterministic **World Importance** score
(−3 to +6) from eight CRB modifiers — starport class, population, tech level,
Ag/In/Ri trade codes, base presence, and X-Boat waystations — displayed on the
world card and bolded when notably high. Alongside it, the full eight-trait
**Culture Detail** system (Diversity, Xenophilia, Uniqueness, Symbology,
Cohesion, Progressiveness, Expansionism, Militancy) was rolled out, producing
a compact `DXUS-CPEM` cultural profile string for every inhabited world. When
a mainworld is fetched from TravellerMap, its T5 Cultural Extension (Cx) field
— four eHex characters for Heterogeneity/Acceptance/Strangeness/Symbols — is
now converted into the first four cultural traits using WBH's clamping rules
instead of being rolled from scratch, and the reverse (rolled traits →
forward-computed Cx) is likewise now displayed for every inhabited world
(Session 135, issue #141).

### Economic Characteristics (Session 133)

`WorldImportance` gained a full economic profile: Labour Factor, Infrastructure
Factor, and a die-rolled Efficiency Factor combine into Resource Units, which
in turn feed GWP Base Value, GWP per capita, and Total GWP (in MCr). A new
Resource Factor field on `WorldPhysical` adjusts the world's raw resource
rating for tech level and trade codes. A Development Score and a compact
economics profile string (e.g. `765+2`) round out the picture, and the world
card's former single "Culture Detail" section was split into separate Culture
and Economic Detail cards to keep the two concepts distinct.

### Inequality Rating & World Trade Number (Session 136, issue #100)

**Inequality Rating** (0–100, 50 = perfectly equal) is rolled per world from
government, law level, PCR, and infrastructure DMs, and now feeds directly
into the Development Score formula that had been using a placeholder value
of 0. **World Trade Number** is computed deterministically from population,
tech level, and starport class via the standard 8×6 WTN lookup table and
displayed as an eHex digit.

### Starport Detail (Session 137, issue #101)

A new `traveller_world_starport_detail.py` module implements WBH §8 starport
traffic and capacity: expected weekly ship arrivals from traffic importance,
highport/downport docking capacities and largest-pad size by starport class,
and shipyard build capacity (Class A/B/C only) with tech-level and trade-code
modifiers. The result is displayed as a compact `C-HX:DX:±#` starport profile
at the top of the Social card. Secondary-world spaceports remain deferred to
a future release.

### Extended Travel Zone (Session 138, issue #103)

Beyond the basic CRB Amber/Red assignment, travel zone can now be determined
by the full WBH §10 procedure: two independent 2D rolls (Red takes priority
over Amber) with modifiers for stellar hazards (magnetars, pulsars,
protostars), high seismic stress, primordial atmospheres, extreme temperature
or pressure, government and law-level extremes, low xenophilia, high
militancy, factional uprisings, and ongoing war. Starport X is always Red;
Green remains the default otherwise.

### Sub-Tech Level Corrections (Session 121)

All nine WBH §5 Quality-of-Life and Transportation sub-tech-level categories
(Energy, Electronics, Manufacturing, Medical, Environmental, Land/Sea/Air/Space
Transport) had been using the world's overall High Tech Level as both their
base and their bounds. Each now uses its correct WBH-specified base and bound
formula and the correct set of population/trade/atmosphere/hydrographic DMs.
Personal and Heavy Military sub-TLs received matching corrections, replacing
an incorrect "Law Level 0 forces military TL to 0" rule with the WBH-correct
floor-raising behaviour.

---

## Novelty Tech Level (Sessions 175–176, issue #137)

A world's **Novelty Tech Level** — the cutting-edge technology reachable
through imports, prototypes, or local industry, beyond its own common Tech
Level — had been a flat placeholder equal to the world's own TL since it was
introduced. It is now the full WBH §5 procedure, taking the highest of four
factors: the highest Tech Level among nearby Rich, Industrial, or
Class-A-starport worlds within 6 parsecs (TravellerMap-fetched worlds only,
via TravellerMap's `jumpworlds` API); the highest of a world's own eleven
technology subcategory levels, since locally-produced prototypes can outpace a
world's common-use TL; an optional, off-by-default house rule for
previous-culture relic technology (the WBH source gives no dice mechanic for
this, only narrative guidance); and a "survivable prototype" floor for worlds
whose common Tech Level falls short of what their environment requires — a
Tech Level 2 vacuum world, for example, is now assumed to have at least
prototype Tech Level 6 life support explaining its survival, per the WBH
example. This now applies to every world, generated or TravellerMap-fetched.

---

## Runaway Greenhouse Extended to Secondary Worlds and Moons (Session 146)

The WBH p.79 runaway greenhouse check — previously mainworld-only — now
applies to every eligible secondary world and moon (never to gas giants
themselves, though rocky/icy moons orbiting a gas giant are still checked).
Secondary worlds and moons don't carry a full `WorldPhysical` body, so their
temperature for the check is derived via the lighter "Basic Mean Temperature"
table instead. The existing "Runaway greenhouse" option now covers the whole
system rather than just the mainworld, and the CLI gained a
`--runaway-greenhouse` flag so it can reach the feature for the first time.

---

## Body Naming Overhaul (Sessions 168–170, 173)

Stars, worlds, and moons are named more systematically. Stars now follow
`<systemname> <designation>` (e.g. "Unknown A", "Unknown Ba") — companion
stars, previously left unnamed, now get names too. Worlds and belts follow
`<systemname> <designation>-<n>`, numbered per star in orbital-radius order,
with belts now sharing the same numbering sequence as worlds instead of a
separate counter. The mainworld keeps the plain system name with no suffix.
Moons use `<parentname> <satellite>` with phonetic letter names (ay, bee,
cee, … zed) in place of the previous Greek-letter scheme.

---

## FastAPI Web Server & Web UI

### TravellerMap Endpoints and SVG Maps (Sessions 114, 115)

Two new endpoints round out TravellerMap support: `GET/POST
/api/map/system/full` runs the complete detail pipeline against a
TravellerMap-fetched system (secondary worlds, moons, physical detail, tidal
effects, social detail) while preserving the canonical UWP rather than
re-rolling it, and `GET /api/map/system/svg` renders a system map SVG that
respects TravellerMap's canonical world/belt/gas-giant counts instead of a
fresh procedural roll. The CLI's `system_map.py` gained matching `--sector`
and `--hex` flags. A routing bug where `/api/system/svg` was being matched as
a world named "svg" was also fixed by re-ordering route registration.

### Security Hardening (Sessions 115, 144, 145, 160, 161)

A security pass across the FastAPI layer fixed an XSS hole in the client-side
status display (user-supplied text was being injected via `innerHTML`
instead of `textContent`), added a `Content-Security-Policy` and standard
security headers to every response, sandboxed all iframes, validated SVG
content-type before rendering fetched maps, and allowlisted values read back
from `localStorage`. This was followed by defense-in-depth against
oversized requests: a streaming ASGI body-size limit (16 KB default, issue
#167), a platform-level 1 MB backstop after migrating the Azure Functions app
to Flex Consumption (issue #168), and fine-grained JSON schema validation
rejecting overlong strings, oversized lists, or excessive nesting anywhere in
a submitted world payload (issue #169). Azure Monitor alerts on exception and
restart frequency (issue #170) close out the monitoring side. The Flex
Consumption migration itself required a validate-then-cutover approach after
an in-place migration failed against the live app; a related identity
misconfiguration found during the cutover was remediated the same session,
including rotating an exposed storage account key.

### Survey Forms (Sessions 123, 139, 140)

The FastAPI web app and desktop app can now render three of the IISS's paper
survey forms as styled, theme-aware HTML: **Class 0/I** (stellar data —
component, spectral class, mass, temperature, orbit, eccentricity, period),
**Class II/III**, and **Class IV Part C** (population, government, law level,
technology, culture, economics, starport, and military — the full social
detail checklist in one document). In gen-ui, a Survey Form button and type
dropdown open the chosen form in its own window; in the web app it's a tab
alongside System and Mainworld.

### Help System (Sessions 138, 141, 142)

Both the desktop and web apps gained in-app help: gen-ui's **Help > User
Guide** menu item and the web app's "?" button both render
`docs/Traveller World Generator User Guide.md` as themed HTML (a small
Markdown-to-HTML converter handles headings, code blocks, tables, and lists),
and a **Help > About** dialog / in-page About button on the world card
display app credits, licensing, and WBH/CRB attribution. Getting the web
version working end-to-end required several follow-up fixes: relaxing
`X-Frame-Options` so the same-origin help iframe could actually render, fixing
a lazy-load guard that never fired, and copying `docs/` into the Azure and
Docker deployment images (found via a real deployment showing "User guide not
available").

### Theme, Icon, and UI Polish (Sessions 117, 118, 122, 139)

The web app was retheme to match the tabletop source material — an amber
accent on near-black in dark mode, a warm parchment palette in light mode —
and gained a proper favicon and app icon (also used for the desktop app's
`.icns`/`.ico`/`.png` bundle icons). A Mongoose Publishing copyright footer
was added to every rendered page. Smaller fixes: the system map now matches
the page background instead of pure white in light mode, a redundant
per-card copyright line was removed, moon sub-rows in the orbital table were
misaligned by one column, and a call-order bug meant that a runaway
greenhouse conversion could leave a mainworld's orbit-slot data
(atmosphere/hydrographics) out of sync with the mainworld object itself
across seven endpoints (issue #138) — all fixed.

---

## System Map: Perspective Overhaul & Poster Export

### 3-D Perspective Rendering (Sessions 104–113)

The system map's perspective mode went from a flat schematic to a genuinely
three-dimensional rendering over a run of ten sessions: an isometric floor
grid, a translucent orbital-plane disc, near/far arc splitting with dashed
"behind the plane" segments for inclined orbits, drop lines connecting a body
to its plane projection, radial-gradient sphere shading on every star and
world glyph, foreshortened 3-D ring systems for ringed gas giants, and
perspective-correct filled bands for asteroid belts (replacing a flat stroke
or rectangle marker). Along the way, several projection bugs were fixed —
retrograde-inclination orbits drawing off-center, eccentric orbits floating
away from their star, and near-equatorial orbits triggering an imperceptible
near/far split. In gen-ui, the map is now rendered via `QWebEngineView`
(Chromium) rather than Qt's native SVG renderer, which was found to silently
corrupt maps containing blur filters.

### World Icon Textures (Session 143)

Terrestrial and gas-giant map icons carry real visual texture now instead of
a flat inhabited/uninhabited colour scheme. Eight terrestrial archetypes
(garden, ocean, desert, barren, ice, volcanic, hostile, tundra) are derived
from a world's SAH codes and temperature zone, each with its own gradient;
gas giants get cloud-banding coloured by size class. The map legend was
updated to match.

### Companion Star Placement Fixes (Sessions 163–166)

A cluster of related fixes brought companion-star display in line with
worlds: the Stars table gained a **Primary** column showing which star each
row orbits; the Orbital survey table now lists companion stars as rows under
their own parent star's worlds, in true orbital-radius order, rather than as
a separate disconnected block; and the system map now draws a secondary
star's own companion in the correct zone (previously it could be drawn
next to the primary by mistake) as well as nested next to its parent
wherever that parent appears as dashed context.

### A3 Poster Export (Sessions 148–159)

A new **File > Export A3 Poster…** action in gen-ui produces a self-contained,
print-ready two-page HTML document: a full-bleed perspective system map with
floating Stars/Mainworld/Notable-bodies cards on page 1, and the complete
system card (stars + full orbital survey table) on page 2, sized to fit a
single A3 page. The feature was refined over several sessions — light-mode
map rendering, smaller semi-transparent cards, a condensed system-card
summary added to page 1, a centered title card, and eventually a direct
PDF export option (no browser print step required) with card shadows removed
because they didn't survive the PDF conversion cleanly.

---

## Desktop App (gen-ui) Improvements

- **File > New / New with New Seed** (Session 162) — Ctrl+N regenerates with
  the currently displayed seed and options (something the plain Generate
  button can't do once a seed has auto-filled); Ctrl+Shift+N always rolls a
  fresh seed while keeping the current options.
- **Keyboard focus fix** (Session 172) — the `Name:` field could stop
  accepting keyboard input entirely after a generation, due to a
  PySide6/QtWebEngine focus-stealing quirk in the read-only result views.
  Those views are now explicitly excluded from keyboard focus.
- **System Map window persistence** (Session 149) — the Light/Dark theme and
  Perspective/Top-down toggles now persist across newly opened map windows,
  instead of resetting every time.
- **pytest-qt GUI test suite** (Session 124) — 121 automated GUI tests now
  cover the desktop app's window, options dialog, system map window, and
  survey form window, using in-memory stubs for `QSettings` and
  `QWebEngineView` so the suite runs headless and fast.

---

## Infrastructure & Packaging

### Package Migration to `src/traveller_gen/` (Session 134, issues #155, #156)

All 22 generation modules moved from the project root into an installable
`src/traveller_gen/` package, with `pyproject.toml` and `pip install -e .`
replacing `sys.path` hacks for local development. CLI entry points
(`traveller-world`, `traveller-mapfetch`) are now registered properly, and
Azure deployment is simplified to a single `pip install --target azure-api/`
step instead of a maintained file-by-file copy list.

### Azure Flex Consumption & Monitoring (Sessions 126, 145, 161)

The Azure Functions deployment migrated from classic to Flex Consumption,
required to set a platform-level request body-size backstop underneath the
FastAPI-level limit. Application Insights integration adds per-request
tracing and dependency tracking when deployed; a daily execution quota and a
monthly cost-management budget with email alerts guard against runaway
spend; and Azure Monitor alerts now fire on abnormal exception or restart
frequency.

### Stale Build Artifact Fix (Session 174, issue #172)

A leftover, gitignored `azure-api/traveller_gen/` mirror — created by
previously running the Azure deploy-prep script locally — could silently
shadow the real `src/traveller_gen` package for the rest of a local pytest
session, since `conftest.py` put `azure-api/` at the front of `sys.path`.
Tests would pass, but against stale code, with new edits invisible until the
mirror was manually deleted. Not a CI issue (the mirror never exists on a
fresh checkout), but a real local-development hazard — fixed by appending
rather than prepending that path, plus a `conftest.py` assertion that guards
against any future recurrence.

---

## Bug Fixes

- Vacuum worlds (atmosphere 0) showed near-zero temperature variance in
  advanced high/low temperature due to a missing pressure-table entry
  (Session 125, issue #144).
- Secondary worlds with NHZ Gas/Helium or Gas/Hydrogen atmospheres were
  incorrectly treated as colonisable at any tech level (Session 119).
- Computing a secondary world's tech level from an EHEX atmosphere digit
  above `F` (codes 16/17) raised a `ValueError` instead of parsing correctly
  (Session 119).
- Moon sub-rows in the orbital survey table were misaligned by one column
  against the header (Sessions 119, 122).
- A runaway-greenhouse atmosphere conversion could leave a mainworld's
  orbit-slot data out of sync with the mainworld object across seven FastAPI
  endpoints (Session 117, issue #138).
- The system map's Content-Security-Policy blocked the `blob:` URLs used to
  render fetched SVG maps (Session 117).
- FastAPI could return a different mainworld UWP than gen-ui for the same
  seed, because two separate API calls used different RNG paths (Session
  116).
- A companion star belonging to a *secondary* star was drawn in the
  *primary* star's system-map zone instead of its own parent's zone (Session
  164, issue #171).
- The Orbital survey table's `#` column restarted at 1 for a star's outer
  placement zone, and could misattribute a world's detail to the wrong orbit
  as a result (Session 167).
- The System Map window reset its theme and perspective toggle every time a
  new window was opened, ignoring the last-used setting (Session 149).
- A TravellerMap-fetched system's mainworld could appear to orbit a
  different star depending on which part of the app generated it, because
  system age and secondary star position weren't seeded in that code path
  (Session 177).
- A stale, gitignored build artifact could silently shadow the real source
  package during local test runs, making tests pass against outdated code
  (Session 174, issue #172).
- The `Name:` field in gen-ui could stop accepting keyboard input after a
  generation, due to a Qt focus-stealing interaction with read-only result
  views (Session 172).

---

## Tests

3023 tests pass; pylint 10.00/10.
