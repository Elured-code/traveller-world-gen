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

# pylint: disable=too-many-lines
import json
import random
import secrets
from dataclasses import dataclass
from typing import Optional

from traveller_stellar_gen import StarSystem, generate_stellar_data
from traveller_orbit_gen import SystemOrbits, OrbitSlot, generate_orbits
from traveller_belt_physical import BeltPhysical
from traveller_world_physical import TIDAL_STATUS_LABELS, WorldPhysical
from traveller_hydro_detail import generate_hydrographic_detail
from html_render import render
from traveller_world_gen import (
    World,
    generate_size,
    generate_atmosphere,
    generate_nhz_atmosphere,
    generate_atmosphere_detail,
    generate_gas_mix,
    generate_unusual_subtype,
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
    to_hex,
    ATMOSPHERE_MIN_TL,
    ATMOSPHERE_NAMES,
    GOVERNMENT_NAMES,
    HYDROGRAPHIC_NAMES,
    STARPORT_QUALITY_LABEL,
    TEMPERATURE_DM,
    format_atmosphere_profile,
)


# ---------------------------------------------------------------------------
# HZ deviation → raw temperature roll  (WBH p.46-47)
# ---------------------------------------------------------------------------

def hz_deviation_to_raw_roll(  # pylint: disable=unused-argument
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
    Negative deviation (closer = hotter) raises the raw roll toward Boiling.
    Positive deviation (further = colder) lowers the raw roll toward Frozen.

    The hzco and orbit parameters are retained for API compatibility but are
    no longer used; the WBH HZ Regions table (p.46) is applied directly to
    the unscaled orbit# deviation.  Sub-Orbit#1 scaling was removed because
    it conflicts with is_habitable_zone (which uses the unscaled deviation) and
    produces absurd results for dim stars (HZCO ≈ 0 amplified 50×).

    Returns an int in range 2-12 (clamped).
    """
    # Map deviation to raw roll via the HZ Regions table (WBH p.46)
    # HZCO = raw roll 7 (deviation 0)
    # Each 0.1 Orbit# away from HZCO shifts the raw roll by ~1
    eff_dev = hz_deviation

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
    nhz_atmospheres: bool = False
    orbital_eccentricity: bool = False
    orbital_inclination: bool = False

    def to_dict(self) -> dict:
        """Serialise this system to a JSON-compatible dict."""
        d = self.stellar_system.to_dict()
        d["orbits"] = self.system_orbits.to_dict()
        d["mainworld"] = self.mainworld.to_dict() if self.mainworld else None
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialise this system to a JSON string."""
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
            from traveller_world_detail import system_body_table  # pylint: disable=import-outside-toplevel
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

    def to_html(self, detail_attached: bool = False) -> str:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Return a self-contained HTML system card.

        Suitable for saving as a standalone .html file or serving directly
        from the API /api/system/{name}/card endpoint.

        Parameters
        ----------
        detail_attached : bool
            Pass True when attach_detail() has already been called so the
            card includes secondary world profiles and satellite data.
        """
        mw = self.mainworld

        # ── Star rows ─────────────────────────────────────────────────────
        star_rows = []
        for star in self.stellar_system.stars:
            orb = (f"Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)"
                   if star.orbit_number else "")
            star_rows.append({
                "designation": star.designation,
                "classification": star.classification(),
                "mass": f"{star.mass:.2f}",
                "temperature": f"{star.temperature:,}",
                "luminosity": f"{star.luminosity:.3g}",
                "orbit": orb,
            })

        # ── Orbital rows ──────────────────────────────────────────────────
        orbit_rows = []
        for o in self.system_orbits.orbits:
            detail = getattr(o, "detail", None)
            if o.world_type == "empty":
                profile = "—"
                type_cls = "type-empty"
            elif o.canonical_profile:
                # Canonical mainworld: always show the fetched UWP verbatim.
                profile = o.canonical_profile
                type_cls = ("type-belt" if o.world_type == "belt"
                            else "type-inh" if mw and mw.population > 0
                            else "type-terr")
            elif detail is not None:
                # Gas giant orbits: use gg_sah as profile (gg_sah is always
                # the gas giant profile; detail.profile may be a satellite UWP).
                if o.world_type == "gas_giant":
                    profile = o.gg_sah or detail.profile
                    type_cls = "type-gg"
                else:
                    profile = detail.profile
                    type_cls = ("type-belt" if o.world_type == "belt"
                                else "type-inh" if detail.inhabited
                                else "type-terr")
            else:
                if o.world_type == "gas_giant" and o.gg_sah:
                    profile = o.gg_sah
                    type_cls = "type-gg"
                else:
                    profile = ""
                    type_cls = "type-terr"

            note_parts = []
            if o.is_mainworld_candidate:
                note_parts.append("← mainworld")
            if o.notes:
                note_parts.append(o.notes)

            if o.is_mainworld_candidate and mw:
                orbit_codes = list(mw.trade_codes)
            elif detail is not None and not detail.is_gas_giant:
                orbit_codes = list(detail.trade_codes)
            else:
                orbit_codes = []

            ecc_incl = (
                f"{o.eccentricity:.3f}/{o.inclination:.1f}°"
                if (o.eccentricity > 0 or o.inclination > 0)
                else "—"
            )

            moons = []
            if detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):
                    if moon.is_ring:
                        moon_profile = f"R{moon.ring_count:02d}"
                        moon_codes = []
                    elif moon.detail is not None:
                        moon_profile = moon.detail.profile
                        moon_codes = list(moon.detail.trade_codes)
                    else:
                        moon_profile = f"size {moon.size_str}"
                        moon_codes = []
                    moons.append({
                        "idx": mi,
                        "pd_str": (f"{moon.orbit_pd:.1f} PD"
                                   if moon.orbit_pd is not None else ""),
                        "km_str": (f"{moon.orbit_km:,.0f} km"
                                   if moon.orbit_km is not None else ""),
                        "type_str": ("ring" if moon.is_ring
                                     else f"size {moon.size_str}"),
                        "profile": moon_profile,
                        "codes": moon_codes,
                        "range_str": (moon.orbit_range.capitalize()
                                      if moon.orbit_range else ""),
                    })

            orbit_rows.append({
                "star_desig": o.star_designation,
                "slot_index": o.slot_index,
                "orbit_num": f"{o.orbit_number:.2f}",
                "orbit_au": f"{o.orbit_au:.3f}",
                "ecc_incl": ecc_incl,
                "world_type": o.world_type,
                "type_cls": type_cls,
                "profile": profile,
                "codes": orbit_codes,
                "temp_zone": o.temperature_zone,
                "mw_mark": "  ".join(note_parts),
                "row_cls": "mw-row" if o.is_mainworld_candidate else "",
                "moons": moons,
            })

        # ── Mainworld panel data ──────────────────────────────────────────
        mw_data = None
        if mw:
            mw_atm_profile = ""
            mw_gas_parts = ""
            if mw.atmosphere_detail is not None:
                mw_atm_profile = format_atmosphere_profile(
                    mw.atmosphere, mw.atmosphere_detail)
                if mw.atmosphere_detail.gas_mix:
                    mw_gas_parts = " · ".join(
                        f"{c.gas_name} ({c.gas_code})"
                        + (f" {c.percentage}%" if c.percentage is not None else "")
                        for c in mw.atmosphere_detail.gas_mix
                    )

            phys_data = None
            if isinstance(mw.size_detail, BeltPhysical):
                phys_data = {"type": "belt", "data": mw.size_detail}
            elif isinstance(mw.size_detail, WorldPhysical):
                p = mw.size_detail
                tidal_label = (TIDAL_STATUS_LABELS[p.tidal_status]
                               if p.tidal_status != "none" else "")
                phys_data = {"type": "world", "data": p,
                             "tidal_label": tidal_label}

            mw_data = {
                "world": mw,
                "uwp": mw.uwp(),
                "zone_cls": {
                    "Green": "zone-green",
                    "Amber": "zone-amber",
                    "Red": "zone-red",
                }.get(mw.travel_zone, "zone-green"),
                "trade_codes": list(mw.trade_codes),
                "starport_quality": STARPORT_QUALITY_LABEL.get(mw.starport, "?"),
                "size_hex": to_hex(mw.size),
                "size_str": str(mw.size * 1600) + " km" if mw.size else "Belt",
                "atm_hex": to_hex(mw.atmosphere),
                "atm_name": ATMOSPHERE_NAMES.get(mw.atmosphere, "?"),
                "hydro_hex": to_hex(mw.hydrographics),
                "hydro_name": HYDROGRAPHIC_NAMES.get(mw.hydrographics, "?"),
                "pop_hex": to_hex(mw.population),
                "tl_hex": to_hex(mw.tech_level),
                "gov_hex": to_hex(mw.government),
                "gov_name": GOVERNMENT_NAMES.get(mw.government, "?"),
                "law_hex": to_hex(mw.law_level),
                "phys_data": phys_data,
                "atm_detail": mw.atmosphere_detail,
                "atm_profile": mw_atm_profile,
                "gas_parts": mw_gas_parts,
                "hydro_detail": mw.hydrographic_detail,
                "notes": list(mw.notes),
            }

        return render("system_card.html",
            title=(mw.name if mw else "Unknown") + " system",
            star_classes=" + ".join(
                s.classification() for s in self.stellar_system.stars),
            age=(f"{self.stellar_system.age_gyr:.2f} Gyr"
                 if self.stellar_system.age_gyr else "?"),
            nw=self.system_orbits.total_worlds,
            star_rows=star_rows,
            orbit_rows=orbit_rows,
            detail_attached=detail_attached,
            mw_data=mw_data,
            json_str=self.to_json(),
        )


_GG_EHEX = "0123456789ABCDEFGHIJ"


def _gg_diameter(gg_sah: str) -> int:
    """Return the numeric diameter from a gas giant SAH string (e.g. 'GM9' → 9)."""
    if len(gg_sah) >= 3 and gg_sah[2].upper() in _GG_EHEX:
        return _GG_EHEX.index(gg_sah[2].upper())
    return 8  # fallback: mid-range GM diameter


def generate_mainworld_at_orbit(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-statements
    name: str,
    orbit: OrbitSlot,
    hzco: float,
    gas_giant_count: int,
    belt_count: int,
    system_age_gyr: Optional[float] = None,
    nhz_atmospheres: bool = False,
) -> World:
    """
    Generate a mainworld whose temperature is constrained by its orbital
    position, following the WBH Habitable Zones Regions table (p.46-47).

    All steps follow the CRB generation procedure (pp.248-261) except:
    - Temperature uses the orbital HZ deviation instead of a random roll
    - gas_giant_count, belt_count, and population_multiplier come from
      the orbit generation rather than being re-rolled independently
    - WBH atmosphere detail (pressure, ppo, scale height) is attached
      via ``generate_atmosphere_detail()``; *system_age_gyr* feeds the
      WBH p.80 DM+1 to oxygen fraction for systems older than 4 Gyr.
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
    elif orbit.world_type == "gas_giant":
        # The mainworld is a satellite of the gas giant, not the giant itself.
        # Size is constrained: at least 1, at most gg_diameter-1 (WBH p.57).
        gg_sah = getattr(orbit, "gg_sah", "")
        gg_diam = _gg_diameter(gg_sah)
        world.size = min(max(generate_size(), 1), gg_diam - 1)
        _nhz = (nhz_atmospheres
                and orbit.hz_deviation is not None
                and abs(orbit.hz_deviation) > 1.0)
        if _nhz:
            world.atmosphere, _nhz_key = generate_nhz_atmosphere(
                world.size, orbit.hz_deviation
            )
        else:
            world.atmosphere = generate_atmosphere(world.size)
            _nhz_key = None
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=orbit.hz_deviation,
            hzco=hzco,
            orbit=orbit.orbit_number,
        )
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, system_age_gyr, world.temperature,
            hz_deviation=orbit.hz_deviation,
            exotic_key_override=_nhz_key,
        )
        world.hydrographics = generate_hydrographics(
            world.size, world.atmosphere, world.temperature
        )
        if world.atmosphere_detail is not None:
            generate_gas_mix(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, orbit.hz_deviation, world.hydrographics,
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )
        world.notes.append(
            f"Mainworld is a satellite of gas giant {gg_sah or '?'} "
            f"at Orbit# {orbit.orbit_number:.2f} ({orbit.orbit_au:.2f} AU)"
        )
    else:
        # Steps 1-2: Size and Atmosphere (random as normal, or NHZ override)
        world.size = generate_size()
        _nhz = (nhz_atmospheres
                and orbit.hz_deviation is not None
                and abs(orbit.hz_deviation) > 1.0)
        if _nhz:
            world.atmosphere, _nhz_key = generate_nhz_atmosphere(
                world.size, orbit.hz_deviation
            )
        else:
            world.atmosphere = generate_atmosphere(world.size)
            _nhz_key = None

        # Step 3: Temperature — derived from orbital position (WBH p.46-47)
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=orbit.hz_deviation,
            hzco=hzco,
            orbit=orbit.orbit_number,
        )

        # Atmosphere detail needs temperature to characterise exotic/corrosive subtypes
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, system_age_gyr, world.temperature,
            hz_deviation=orbit.hz_deviation,
            exotic_key_override=_nhz_key,
        )

        # Step 4: Hydrographics (uses orbital-constrained temperature)
        world.hydrographics = generate_hydrographics(
            world.size, world.atmosphere, world.temperature
        )
        if world.atmosphere_detail is not None:
            generate_gas_mix(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, orbit.hz_deviation, world.hydrographics,
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )

    # Hydrographic detail — precise surface-liquid percentage (WBH p.93)
    world.hydrographic_detail = generate_hydrographic_detail(
        world.hydrographics, world.size
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
        world.atmosphere, world.government, world.law_level, world.starport
    )

    # Record orbital context in notes
    world.notes.append(
        f"Orbits Star {orbit.star_designation} at Orbit# {orbit.orbit_number:.2f}"
        f" ({orbit.orbit_au:.3f} AU). HZ deviation {orbit.hz_deviation:+.2f}."
    )

    return world


def generate_full_system(
    name: str = "Unknown",
    seed: Optional[int] = None,
    nhz_atmospheres: bool = False,
    orbital_eccentricity: bool = False,
    orbital_inclination: bool = False,
) -> TravellerSystem:
    """
    Generate a complete Traveller star system with stellar data, orbital
    structure, and a fully characterised mainworld.

    Args:
        name:                 Mainworld name.
        seed:                 Optional RNG seed for reproducible results.
        nhz_atmospheres:      When True, worlds outside the habitable zone use
                              WBH Non-Habitable Zone atmosphere tables.
        orbital_eccentricity: When True, roll orbital eccentricity for all
                              worlds and companion stars (WBH p.27).
        orbital_inclination:  When True, roll orbital inclination for all
                              worlds and companion stars (WBH p.28).

    Returns:
        A TravellerSystem containing stellar data, orbits, and mainworld.
    """
    if seed is None:
        seed = secrets.randbelow(2 ** 31)
    random.seed(seed)

    # Step 1: Stars
    stellar = generate_stellar_data()

    # Step 2: Orbits and mainworld orbit selection
    orbits = generate_orbits(stellar, orbital_eccentricity=orbital_eccentricity,
                             orbital_inclination=orbital_inclination)

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
            system_age_gyr=stellar.age_gyr,
            nhz_atmospheres=nhz_atmospheres,
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=mainworld,
        mainworld_orbit=mw_orbit,
        nhz_atmospheres=nhz_atmospheres,
        orbital_eccentricity=orbital_eccentricity,
        orbital_inclination=orbital_inclination,
    )


def generate_system_from_world(
    world: World,
    seed: Optional[int] = None,
    orbital_eccentricity: bool = False,
    orbital_inclination: bool = False,
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
    orbits = generate_orbits(stellar, orbital_eccentricity=orbital_eccentricity,
                             orbital_inclination=orbital_inclination)

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

    world.atmosphere_detail = generate_atmosphere_detail(
        world.atmosphere,
        world.size,
        stellar.age_gyr,
        world.temperature,
        hz_deviation=mw_orbit.hz_deviation if mw_orbit is not None else None,
    )
    if world.atmosphere_detail is not None:
        generate_gas_mix(
            world.atmosphere_detail, world.atmosphere, world.size,
            world.temperature,
            mw_orbit.hz_deviation if mw_orbit is not None else None,
            world.hydrographics,
        )
        generate_unusual_subtype(
            world.atmosphere_detail, world.atmosphere,
            world.size, world.hydrographics,
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=world,
        mainworld_orbit=mw_orbit,
        orbital_eccentricity=orbital_eccentricity,
        orbital_inclination=orbital_inclination,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate a Traveller star system and print it to stdout."""
    import argparse  # pylint: disable=import-outside-toplevel
    import sys as _sys  # pylint: disable=import-outside-toplevel

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
    parser.add_argument("--nhz-atmospheres", action="store_true",
                        help="Use WBH Non-Habitable Zone atmosphere tables for out-of-HZ worlds")
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

    from traveller_world_detail import attach_detail  # pylint: disable=import-outside-toplevel

    for i in range(args.count):
        system = generate_full_system(
            name=args.name if args.count == 1 else f"{args.name}-{i+1}",
            seed=args.seed if i == 0 else None,
            nhz_atmospheres=args.nhz_atmospheres,
        )

        if want_detail:
            attach_detail(system)

        if out_format == "json":
            print(system.to_json())
        elif out_format == "html":
            if args.count > 1:
                _sys.stderr.write(
                    "Warning: --html with --count > 1 outputs multiple HTML documents.\n"
                )
            print(system.to_html(detail_attached=want_detail))
        else:
            if args.count > 1:
                print(f"\n{'='*60}\nSystem {i+1}\n{'='*60}")
            print(system.summary())


if __name__ == "__main__":
    main()
