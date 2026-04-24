"""
traveller_system_gen.py
=======================
Full system generation for the Traveller RPG, integrating:
  - Stellar generation  (traveller_stellar_gen.py  — WBH pp.14-29)
  - Orbit placement     (traveller_orbit_gen.py     — WBH pp.36-51)
  - Mainworld generation (traveller_world_gen.py    — CRB pp.248-261)

The key integration point is the Habitable Zones Regions table (WBH p.46-47),
which maps an orbit's HZ deviation to the raw 2D roll used for the CRB
temperature table (p.251).  Rather than rolling temperature randomly,
the orbit's position in the HZ is used to derive the raw roll, ensuring
the mainworld's temperature is consistent with its orbital distance from
the parent star(s).

Habitable Zones Regions table (WBH p.46):
  Raw roll  |  HZCO deviation  |  Temperature zone
  ------    |  ---------------  |  ----------------
  2-        |  +1.1 or more    |  Frozen
  3         |  +1.00           |  Cold
  4         |  +0.50           |  Cold
  5         |  +0.20           |  Temperate
  6         |  +0.10           |  Temperate
  7         |  +0.00           |  Temperate (HZCO)
  8         |  -0.10           |  Temperate
  9         |  -0.20           |  Temperate
  10        |  -0.50           |  Hot
  11        |  -1.00           |  Hot
  12+       |  -1.1 or less    |  Boiling

The raw roll is then fed into the CRB temperature procedure as the
pre-determined 2D result (before atmosphere DMs are added).

World Builder's Handbook and the gas giant/belt counts from the orbit
generation are passed through to the World dataclass, replacing the
independently-rolled values that generate_world() would normally produce.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""

from __future__ import annotations

import json
import random
import secrets
from dataclasses import dataclass
from typing import Optional

from traveller_stellar_gen import StarSystem, generate_stellar_data
from traveller_orbit_gen import SystemOrbits, OrbitSlot, generate_orbits
from traveller_world_gen import (
    World,
    generate_size,
    generate_atmosphere,
    temperature_category,
    generate_hydrographics,
    generate_population,
    generate_government,
    generate_law_level,
    generate_starport,
    generate_tech_level,
    generate_bases,
    generate_population_multiplier,
    assign_trade_codes,
    assign_travel_zone,
    ATMOSPHERE_MIN_TL,
    ATMOSPHERE_NAMES,
    TEMPERATURE_DM,
)


# ---------------------------------------------------------------------------
# HZ deviation → raw temperature roll  (WBH p.46-47)
# ---------------------------------------------------------------------------

def hz_deviation_to_raw_roll(
    hz_deviation: float,
    hzco: float,
    orbit: float,
) -> int:
    """
    Convert an orbit's HZ deviation to the raw 2D temperature roll
    used in the CRB temperature table (p.251), via the WBH Habitable
    Zones Regions table (p.46).

    The raw roll is the 2D result BEFORE atmosphere DMs are applied.
    A raw roll of 7 corresponds to the HZCO itself (deviation 0).
    Negative deviation (closer = hotter) lowers the raw roll.
    Positive deviation (further = colder) raises the raw roll.

    For sub-Orbit#1 positions (WBH p.42) the effective deviation is
    scaled by dividing by the smaller of HZCO or the world's Orbit#.

    Returns an int in range 2-12 (clamped).
    """
    # Scale deviation for sub-Orbit#1 positions
    if hzco < 1.0 or orbit < 1.0:
        denom = max(min(hzco, orbit), 0.01)
        eff_dev = hz_deviation / denom
    else:
        eff_dev = hz_deviation

    # Map deviation to raw roll via the HZ Regions table
    # HZCO = raw roll 7 (deviation 0)
    # Each 0.1 Orbit# away from HZCO shifts the raw roll by ~1
    # Exact boundaries from WBH table:
    if eff_dev >= 1.1:
        raw = 2        # Frozen
    elif eff_dev >= 1.0:
        raw = 3        # Cold
    elif eff_dev >= 0.5:
        raw = 4        # Cold
    elif eff_dev >= 0.2:
        raw = 5        # Temperate (cool)
    elif eff_dev >= 0.1:
        raw = 6        # Temperate
    elif eff_dev >= 0.0:
        raw = 7        # Temperate (HZCO)
    elif eff_dev >= -0.1:
        raw = 8        # Temperate (warm)
    elif eff_dev >= -0.2:
        raw = 9        # Temperate (warm)
    elif eff_dev >= -0.5:
        raw = 10       # Hot
    elif eff_dev >= -1.0:
        raw = 11       # Hot
    else:
        raw = 12       # Boiling

    return max(2, min(12, raw))


def generate_temperature_from_orbit(
    atmosphere: int,
    hz_deviation: float,
    hzco: float,
    orbit: float,
) -> str:
    """
    Determine temperature using orbital position rather than a random roll.

    The raw roll from hz_deviation_to_raw_roll() is used as the 2D result,
    then the atmosphere DM is added exactly as the CRB specifies (p.251).
    This ensures the world's temperature is consistent with its orbit.
    """
    raw_roll = hz_deviation_to_raw_roll(hz_deviation, hzco, orbit)
    atm_dm = TEMPERATURE_DM.get(atmosphere, 0)
    modified_roll = raw_roll + atm_dm
    return temperature_category(modified_roll)


# ---------------------------------------------------------------------------
# Main integration: generate a complete system
# ---------------------------------------------------------------------------

@dataclass
class TravellerSystem:
    """A fully generated Traveller star system with mainworld."""

    stellar_system: StarSystem
    system_orbits: SystemOrbits
    mainworld: Optional[World]
    mainworld_orbit: Optional[OrbitSlot]

    def to_dict(self) -> dict:
        d = self.stellar_system.to_dict()
        d["orbits"] = self.system_orbits.to_dict()
        d["mainworld"] = self.mainworld.to_dict() if self.mainworld else None
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def summary(self) -> str:
        """
        Human-readable full system summary.

        If attach_detail() has been called, the orbital section uses
        system_body_table() which shows secondary world profiles and
        significant moon sub-rows.  Without detail attached it falls
        back to SystemOrbits.summary() which shows type and zone only.
        """
        # Check whether detail has been attached to any non-empty orbit
        detail_attached = any(
            getattr(o, "detail", None) is not None
            for o in self.system_orbits.orbits
            if o.world_type != "empty"
        )

        if detail_attached:
            from traveller_world_detail import system_body_table
            orbital_section = system_body_table(self)
        else:
            orbital_section = self.system_orbits.summary()

        lines = [self.stellar_system.summary(), "", orbital_section]

        if self.mainworld and self.mainworld_orbit:
            mw = self.mainworld
            mo = self.mainworld_orbit
            lines.append("")
            lines.append("=" * 60)
            lines.append(f"  Mainworld  —  {mw.name}  {mw.uwp()}")
            lines.append(
                f"  Star {mo.star_designation}  Orbit# {mo.orbit_number:.2f}"
                f"  ({mo.orbit_au:.3f} AU)  HZ dev {mo.hz_deviation:+.2f}"
            )
            lines.append("=" * 60)
            lines.append(mw.summary())
        return "\n".join(lines)

    def to_html(self, detail_attached: bool = False) -> str:
        """Return a self-contained HTML system card.

        Suitable for saving as a standalone .html file or serving directly
        from the API /api/system/{name}/card endpoint.  Mirrors the inline
        Claude display style used by World.to_html().

        Parameters
        ----------
        detail_attached : bool
            Pass True when attach_detail() has already been called so the
            card includes secondary world profiles and satellite data.
        """
        from traveller_world_detail import system_body_table
        from traveller_world_gen import STARPORT_QUALITY, to_hex

        mw  = self.mainworld
        mwo = self.mainworld_orbit
        st  = self.stellar_system.primary

        def esc(s: str) -> str:
            return (str(s).replace("&","&amp;").replace("<","&lt;")
                         .replace(">","&gt;").replace('"',"&quot;"))

        # ── Stellar summary ───────────────────────────────────────────────
        star_rows = ""
        for star in self.stellar_system.stars:
            orb = (f"  Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)"
                   if star.orbit_number else "")
            star_rows += (
                f'<tr><td class="mono">{esc(star.designation)}</td>'
                f'<td>{esc(star.classification())}</td>'
                f'<td class="mono">{esc(f"{star.mass:.2f}")} M☉</td>'
                f'<td class="mono">{esc(f"{star.temperature:,}")} K</td>'
                f'<td class="mono">{esc(f"{star.luminosity:.3g}")} L☉</td>'
                f'<td>{esc(orb)}</td></tr>'
            )

        # ── Orbital table ─────────────────────────────────────────────────
        # Build rows from the orbit list; include detail when attached
        orbit_rows = ""
        for o in self.system_orbits.orbits:
            detail = getattr(o, "detail", None)
            if o.world_type == "empty":
                profile = "—"
                type_cls = "type-empty"
            elif o.canonical_profile:
                # Canonical mainworld: always show the fetched UWP verbatim,
                # even if detail has been attached (detail.profile renders
                # uninhabited worlds as Y{sah}000-0 which is wrong for a
                # canonical mainworld with pop=0).
                profile = esc(o.canonical_profile)
                type_cls = ("type-belt" if o.world_type == "belt"
                            else "type-inh" if mw and mw.population > 0
                            else "type-terr")
            elif detail is not None:
                profile = esc(detail.profile)
                type_cls = ("type-gg" if detail.is_gas_giant
                            else "type-belt" if o.world_type == "belt"
                            else "type-inh" if detail.inhabited
                            else "type-terr")
            else:
                profile = ""
                type_cls = "type-terr"

            mw_mark = " ← mainworld" if o.is_mainworld_candidate else ""
            row_cls  = "mw-row" if o.is_mainworld_candidate else ""
            if o.is_mainworld_candidate and mw:
                orbit_codes = mw.trade_codes
            elif detail is not None and not detail.is_gas_giant:
                orbit_codes = detail.trade_codes
            else:
                orbit_codes = []
            codes_html = "".join(
                f'<span class="badge trade">{esc(tc)}</span>'
                for tc in orbit_codes
            )
            orbit_rows += (
                f'<tr class="{row_cls}">'
                f'<td class="mono">{esc(o.star_designation)}</td>'
                f'<td class="mono">{o.slot_index}</td>'
                f'<td class="mono">{o.orbit_number:.2f}</td>'
                f'<td class="mono">{o.orbit_au:.3f}</td>'
                f'<td class="{type_cls}">{esc(o.world_type)}</td>'
                f'<td class="mono profile">{profile}</td>'
                f'<td class="codes-cell">{codes_html}</td>'
                f'<td class="zone-{o.temperature_zone}">{esc(o.temperature_zone)}</td>'
                f'<td class="mw-note">{esc(mw_mark)}</td>'
                f'</tr>'
            )
            # Moon sub-rows when detail is attached
            if detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):
                    if moon.is_ring:
                        rc = getattr(moon, "_ring_count", 1)
                        mp = f"R{rc:02d}"
                        moon_codes_html = ""
                    elif moon.detail is not None:
                        mp = esc(moon.detail.profile)
                        moon_codes_html = "".join(
                            f'<span class="badge trade">{esc(tc)}</span>'
                            for tc in moon.detail.trade_codes
                        )
                    else:
                        mp = f"size {esc(moon.size_str)}"
                        moon_codes_html = ""
                    orbit_rows += (
                        f'<tr class="moon-row">'
                        f'<td></td><td class="mono moon-idx">↳ m{mi}</td>'
                        f'<td colspan="3" class="moon-type">moon {mi} — '
                        f'{"ring" if moon.is_ring else "size " + esc(moon.size_str)}</td>'
                        f'<td class="mono profile">{mp}</td>'
                        f'<td class="codes-cell">{moon_codes_html}</td>'
                        f'<td></td><td></td></tr>'
                    )

        # ── Mainworld panel ───────────────────────────────────────────────
        if mw:
            from traveller_world_gen import (
                ATMOSPHERE_NAMES, GOVERNMENT_NAMES,
                HYDROGRAPHIC_NAMES, STARPORT_QUALITY_LABEL,
            )
            trade_badges = "".join(
                f'<span class="badge trade">{esc(tc)}</span>'
                for tc in mw.trade_codes
            ) or '<span class="no-val">None</span>'
            zone_cls = {"Green":"zone-green","Amber":"zone-amber","Red":"zone-red"}.get(
                mw.travel_zone, "zone-green")
            mw_panel = f"""
  <div class="section-title">Mainworld — {esc(mw.name)}</div>
  <div class="mw-grid">
    <div class="stat"><p class="sl">UWP</p>
      <p class="sv mono">{esc(mw.uwp())}</p>
      <p class="ss"><span class="badge {zone_cls}">{esc(mw.travel_zone)} zone</span></p></div>
    <div class="stat"><p class="sl">Starport {esc(mw.starport)}</p>
      <p class="sv">{esc(STARPORT_QUALITY_LABEL.get(mw.starport, "?"))}</p></div>
    <div class="stat"><p class="sl">Size {esc(to_hex(mw.size))}</p>
      <p class="sv">{esc(str(mw.size * 1600) + " km" if mw.size else "Belt")}</p></div>
    <div class="stat"><p class="sl">Atmosphere {esc(to_hex(mw.atmosphere))}</p>
      <p class="sv">{esc(ATMOSPHERE_NAMES.get(mw.atmosphere, "?"))}</p></div>
    <div class="stat"><p class="sl">Temperature</p>
      <p class="sv">{esc(mw.temperature)}</p></div>
    <div class="stat"><p class="sl">Hydrographics {esc(to_hex(mw.hydrographics))}</p>
      <p class="sv">{esc(HYDROGRAPHIC_NAMES.get(mw.hydrographics, "?"))}</p></div>
    <div class="stat"><p class="sl">Population {esc(to_hex(mw.population))}</p>
      <p class="sv">TL {esc(to_hex(mw.tech_level))}</p></div>
    <div class="stat"><p class="sl">Government {esc(to_hex(mw.government))}</p>
      <p class="sv">{esc(GOVERNMENT_NAMES.get(mw.government, "?"))}</p></div>
    <div class="stat"><p class="sl">Law Level</p>
      <p class="sv">{esc(to_hex(mw.law_level))}</p></div>
  </div>
  <div class="trade-row"><span class="trade-lbl">Trade codes</span>{trade_badges}</div>"""
        else:
            mw_panel = '<p class="no-val">No mainworld determined.</p>'

        title       = esc(mw.name if mw else "Unknown") + " system"
        age         = f"{self.stellar_system.age_gyr:.2f} Gyr" if self.stellar_system.age_gyr else "?"
        nw          = self.system_orbits.total_worlds
        star_classes = " + ".join(esc(s.classification()) for s in self.stellar_system.stars)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
:root{{
  --bg1:#ffffff;--bg2:#f5f5f3;--bg3:#eeede8;
  --txt1:#1a1a19;--txt2:#6b6a65;--txt3:#b0aea7;
  --bdr:rgba(0,0,0,0.12);--r8:8px;--r12:12px;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
}}
@media(prefers-color-scheme:dark){{:root{{
  --bg1:#1e1e1c;--bg2:#2a2a28;--bg3:#323230;
  --txt1:#e8e6de;--txt2:#9c9a92;--txt3:#6b6a65;
  --bdr:rgba(255,255,255,0.10);
}}}}
body{{background:var(--bg3);margin:0;padding:1.5rem;color:var(--txt1)}}
.card{{background:var(--bg1);border:0.5px solid var(--bdr);border-radius:var(--r12);
  padding:1rem 1.25rem;max-width:900px;margin:0 auto 1rem}}
.header{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}}
h1{{font-size:22px;font-weight:500;margin:0}}
.sub{{font-size:14px;color:var(--txt2);margin:0}}
.badge{{display:inline-block;font-size:11px;font-weight:500;padding:2px 9px;
  border-radius:var(--r8);margin:2px 2px 2px 0}}
.zone-green{{background:#e1f5ee;color:#085041}}
.zone-amber{{background:#faeeda;color:#633806}}
.zone-red{{background:#fcebeb;color:#791f1f}}
.trade{{background:#faece7;color:#712b13}}
.b-gray{{background:#f1efe8;color:#444441}}
.section-title{{font-size:13px;font-weight:500;color:var(--txt2);
  margin:16px 0 8px;text-transform:uppercase;letter-spacing:0.05em}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;padding:4px 6px;color:var(--txt2);font-weight:500;
  border-bottom:1px solid var(--bdr)}}
td{{padding:3px 6px;border-bottom:0.5px solid var(--bdr);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.mono{{font-family:ui-monospace,"Cascadia Code","Fira Mono",monospace}}
.profile{{color:var(--txt1)}}
.type-gg{{color:#1a5fa8}}
.type-inh{{color:#085041;font-weight:500}}
.type-terr{{color:var(--txt2)}}
.type-belt{{color:var(--txt3)}}
.type-empty{{color:var(--txt3)}}
.mw-row td{{background:var(--bg2);font-weight:500}}
.mw-note{{font-size:11px;color:#085041}}
.moon-row td{{color:var(--txt2);font-size:11px;background:var(--bg1)}}
.moon-type{{padding-left:24px}}
.moon-idx{{color:var(--txt3)}}
.zone-boiling{{color:#791f1f;font-weight:500}}
.zone-hot{{color:#633806;font-weight:500}}
.zone-temperate{{color:#085041;font-weight:500}}
.zone-cold{{color:#0c447c}}
.zone-frozen{{color:var(--txt3)}}
.mw-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}}
@media(max-width:600px){{.mw-grid{{grid-template-columns:repeat(2,1fr)}}}}
.stat{{background:var(--bg2);border-radius:var(--r8);padding:10px 12px}}
.sl{{font-size:11px;color:var(--txt2);margin:0 0 2px}}
.sv{{font-size:14px;font-weight:500;margin:0}}
.ss{{font-size:11px;color:var(--txt2);margin:2px 0 0}}
.trade-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}}
.codes-cell{{white-space:nowrap}}
.trade-lbl{{font-size:12px;color:var(--txt2)}}
.no-val{{font-size:13px;color:var(--txt2);margin:0}}
details summary{{font-size:12px;color:var(--txt2);cursor:pointer;padding:4px 0;margin-top:12px}}
pre{{font-family:ui-monospace,monospace;font-size:11px;color:var(--txt2);
  white-space:pre-wrap;line-height:1.6;margin:8px 0 0}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>{title}</h1>
    <p class="sub mono">{star_classes}</p>
    <span class="badge b-gray">{esc(age)}</span>
    <span class="badge b-gray">{nw} worlds</span>
  </div>

  <div class="section-title">Stars</div>
  <table>
    <thead><tr><th>Desig</th><th>Class</th><th>Mass</th>
    <th>Temp</th><th>Lum</th><th>Orbit</th></tr></thead>
    <tbody>{star_rows}</tbody>
  </table>

  <div class="section-title">Orbital survey{"  ·  detail included" if detail_attached else ""}</div>
  <table>
    <thead><tr><th>Star</th><th>#</th><th>Orbit#</th><th>AU</th>
    <th>Type</th><th>Profile</th><th>Codes</th><th>Zone</th><th></th></tr></thead>
    <tbody>{orbit_rows}</tbody>
  </table>

  {mw_panel}

  <details>
    <summary>Raw JSON</summary>
    <pre>{esc(self.to_json())}</pre>
  </details>
</div>
</body>
</html>"""


def generate_mainworld_at_orbit(
    name: str,
    orbit: OrbitSlot,
    hzco: float,
    gas_giant_count: int,
    belt_count: int,
) -> World:
    """
    Generate a mainworld whose temperature is constrained by its orbital
    position, following the WBH Habitable Zones Regions table (p.46-47).

    All steps follow the CRB generation procedure (pp.248-261) except:
    - Temperature uses the orbital HZ deviation instead of a random roll
    - gas_giant_count, belt_count, and population_multiplier come from
      the orbit generation rather than being re-rolled independently
    """
    world = World(name=name)

    # If the mainworld orbit is a belt, the physical characteristics are
    # fixed: size=0, atmosphere=0, hydrographics=0 (WBH p.53 — "Size 0 world
    # is a special case… a belt of planetoids").  Social codes (population,
    # government, law, starport, TL) are still rolled normally, and the
    # Asteroid (As) trade code will be assigned automatically.
    # Temperature is set to the orbital zone value but has no physical meaning
    # for a diffuse belt.
    if orbit.world_type == "belt":
        world.size = 0
        world.atmosphere = 0
        world.hydrographics = 0
        world.temperature = generate_temperature_from_orbit(
            atmosphere=0,
            hz_deviation=orbit.hz_deviation,
            hzco=hzco,
            orbit=orbit.orbit_number,
        )
    else:
        # Steps 1-2: Size and Atmosphere (random as normal)
        world.size = generate_size()
        world.atmosphere = generate_atmosphere(world.size)

        # Step 3: Temperature — derived from orbital position (WBH p.46-47)
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=orbit.hz_deviation,
            hzco=hzco,
            orbit=orbit.orbit_number,
        )

        # Step 4: Hydrographics (uses orbital-constrained temperature)
        world.hydrographics = generate_hydrographics(
            world.size, world.atmosphere, world.temperature
        )

    # Steps 5-7: Population, Government, Law Level
    world.population = generate_population()
    world.government = generate_government(world.population)
    world.law_level = (
        0 if world.population == 0
        else generate_law_level(world.government)
    )

    # Step 8: Starport
    world.starport = generate_starport(world.population)

    # Step 9: Tech Level
    world.tech_level = (
        0 if world.population == 0
        else generate_tech_level(
            world.starport, world.size, world.atmosphere,
            world.hydrographics, world.population, world.government,
        )
    )

    # Step 9 supplementary: minimum TL note
    min_tl = ATMOSPHERE_MIN_TL.get(world.atmosphere, 0)
    if world.population > 0 and world.tech_level < min_tl:
        world.notes.append(
            f"TL {world.tech_level} is below the minimum TL {min_tl} "
            f"needed to maintain Atmosphere {world.atmosphere} "
            f"({ATMOSPHERE_NAMES.get(world.atmosphere, '?')}). "
            "Population may be doomed."
        )

    # Step 10: Bases
    world.bases = generate_bases(
        world.starport, world.tech_level, world.population, world.law_level
    )

    # Step 11: Gas giants and belts — use orbit generation counts
    world.has_gas_giant = gas_giant_count > 0
    world.gas_giant_count = gas_giant_count
    world.belt_count = belt_count
    world.population_multiplier = generate_population_multiplier(world.population)

    # Step 12: Trade Codes
    world.trade_codes = assign_trade_codes(
        world.size, world.atmosphere, world.hydrographics,
        world.population, world.government, world.law_level,
        world.tech_level,
    )

    # Step 13: Travel Zone
    world.travel_zone = assign_travel_zone(
        world.atmosphere, world.government, world.law_level
    )

    # Record orbital context in notes
    world.notes.append(
        f"Orbits Star {orbit.star_designation} at Orbit# {orbit.orbit_number:.2f}"
        f" ({orbit.orbit_au:.3f} AU). "
        f"HZ deviation {orbit.hz_deviation:+.2f} → "
        f"base temperature raw roll "
        f"{hz_deviation_to_raw_roll(orbit.hz_deviation, hzco, orbit.orbit_number)}."
    )

    return world


def generate_full_system(
    name: str = "Unknown",
    seed: Optional[int] = None,
) -> TravellerSystem:
    """
    Generate a complete Traveller star system with stellar data, orbital
    structure, and a fully characterised mainworld.

    Args:
        name:  Mainworld name.
        seed:  Optional RNG seed for reproducible results.

    Returns:
        A TravellerSystem containing stellar data, orbits, and mainworld.
    """
    if seed is None:
        seed = secrets.randbelow(2 ** 31)
    random.seed(seed)

    # Step 1: Stars
    stellar = generate_stellar_data()

    # Step 2: Orbits and mainworld orbit selection
    orbits = generate_orbits(stellar)

    mw_orbit = orbits.mainworld_orbit
    mainworld = None

    if mw_orbit is not None:
        # Retrieve HZCO for the mainworld's host star
        hzco = orbits.star_hzco.get(mw_orbit.star_designation, 1.0)

        mainworld = generate_mainworld_at_orbit(
            name=name,
            orbit=mw_orbit,
            hzco=hzco,
            gas_giant_count=orbits.gas_giant_count,
            belt_count=orbits.belt_count,
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=mainworld,
        mainworld_orbit=mw_orbit,
    )


def generate_system_from_world(
    world: World,
    seed: Optional[int] = None,
) -> TravellerSystem:
    """
    Generate a complete Traveller star system around an existing mainworld.

    The world's UWP, bases, trade codes, and PBG values are preserved
    exactly. New stellar data and orbital structure are generated
    procedurally. The mainworld's temperature is recalculated from its
    assigned orbital position to remain consistent with the host star's
    habitable zone.

    The canonical UWP is stamped on the mainworld orbit slot so the
    HTML/JSON output always shows the correct profile, following the same
    pattern used for TravellerMap canonical systems.

    Args:
        world: An existing World object (e.g. from World.from_dict()).
        seed:  Optional RNG seed for reproducible stellar/orbital generation.

    Returns:
        A TravellerSystem with the supplied world placed as the mainworld.
    """
    if seed is None:
        seed = secrets.randbelow(2 ** 31)
    random.seed(seed)

    stellar = generate_stellar_data()
    orbits = generate_orbits(stellar)

    # Reconcile PBG: honour the world's canonical gas giant and belt counts
    # rather than the freshly generated orbit counts.
    orbits.gas_giant_count = world.gas_giant_count
    orbits.belt_count = world.belt_count

    mw_orbit = orbits.mainworld_orbit

    if mw_orbit is not None:
        # Stamp canonical UWP on the orbit slot (mirrors TravellerMap path).
        mw_orbit.canonical_profile = world.uwp()

        # Recalculate temperature from orbital position ("orbital temperature,
        # not random" design rule — the JSON value is discarded).
        hzco = orbits.star_hzco.get(mw_orbit.star_designation, 1.0)
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=mw_orbit.hz_deviation,
            hzco=hzco,
            orbit=mw_orbit.orbit_number,
        )
        world.notes.append(
            f"System generated from existing mainworld UWP {world.uwp()}. "
            f"Placed at Star {mw_orbit.star_designation} Orbit# "
            f"{mw_orbit.orbit_number:.2f} ({mw_orbit.orbit_au:.3f} AU), "
            f"HZ deviation {mw_orbit.hz_deviation:+.2f}; "
            f"temperature recalculated as {world.temperature}."
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=world,
        mainworld_orbit=mw_orbit,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    import sys as _sys

    parser = argparse.ArgumentParser(
        description=(
            "Generate a complete Traveller star system with mainworld. "
            "Use --detail to include all secondary world and moon profiles. "
            "Use --format to select output: text (default), json, or html."
        )
    )
    parser.add_argument("--name",   default="Unknown",
                        help="Mainworld name")
    parser.add_argument("--seed",   type=int, default=None,
                        help="RNG seed for reproducible results")
    parser.add_argument("--count",  type=int, default=1,
                        help="Number of systems to generate")
    parser.add_argument("--detail", action="store_true",
                        help="Attach all secondary world SAH/social profiles and moon data")
    # --format supersedes the legacy --json flag; --json kept for back-compat
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument("--format", choices=["text", "json", "html"],
                           default=None,
                           help="Output format: text (default), json, or html")
    fmt_group.add_argument("--json",   action="store_true",
                           help="Output as JSON (shorthand for --format json)")
    fmt_group.add_argument("--html",   action="store_true",
                           help="Output as self-contained HTML card (implies --detail)")
    args = parser.parse_args()

    # Resolve final format and detail flag
    if args.html:
        out_format = "html"
        want_detail = True
    elif args.json:
        out_format = "json"
        want_detail = args.detail
    elif args.format:
        out_format = args.format
        want_detail = args.detail or (args.format == "html")
    else:
        out_format = "text"
        want_detail = args.detail

    from traveller_world_detail import attach_detail

    for i in range(args.count):
        system = generate_full_system(
            name=args.name if args.count == 1 else f"{args.name}-{i+1}",
            seed=args.seed if i == 0 else None,
        )

        if want_detail:
            attach_detail(system)

        if out_format == "json":
            print(system.to_json())
        elif out_format == "html":
            if args.count > 1:
                _sys.stderr.write(
                    f"Warning: --html with --count > 1 outputs multiple HTML documents.\n"
                )
            print(system.to_html(detail_attached=want_detail))
        else:
            if args.count > 1:
                print(f"\n{'='*60}\nSystem {i+1}\n{'='*60}")
            print(system.summary())


if __name__ == "__main__":
    main()
