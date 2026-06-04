"""
traveller_world_physical.py
===========================
Physical world characteristics derived from the UWP size and atmosphere
codes, following the World Builder's Handbook (WBH pp. 74-78, 103-107).

Scope
-----
Applies to terrestrial worlds with integer size codes 1-A only.
Size 0 (asteroid belts), Size S (small worldlets), and rings are
excluded and will be handled separately.

Rules implemented
-----------------
Diameter (WBH p.74):
  Size 1-A : base = size × 1,600 km; variation = (2D-7) × 200 km

Terrestrial Composition (WBH p.75):
  Roll 2D on the Terrestrial Composition Table, with DMs from size.
  Result gives one of five composition categories.

Terrestrial Density (WBH p.75-76):
  Roll 1D on the Terrestrial Density Table for the composition category.
  Result gives density in g/cm³.

Derived properties (WBH p.76-77):
  Relative diameter D* = diameter_km / 12,742
  Relative density  d* = density_g_cm3 / 5.515
  Mass (Earth = 1)    = D*³ × d*
  Surface gravity (G) = D* × d*
  Escape velocity (km/s) = 11.186 × √(gravity × D*)

Axial Tilt (WBH p.77):
  Roll 2D to select a tilt band; roll 1D within that band for degrees.
  On a 2D result of 10+, roll 1D on the Extreme Axial Tilt sub-table,
  which can produce retrograde tilts up to 180°.

Basic Rotation Rate (WBH p.103):
  Terrestrial worlds: (2D-2) × 4 + 2 + 1D + DMs  (hours)
  DM: +1 per 2 full Gyrs of system age (round down).

Tidal Lock Status (WBH pp. 105-107):
  After basic rotation, roll 2D + DM on the Tidal Lock Status table.
  Requires orbital distance (AU), orbit number, and host-star mass.
  DMs come from three sources: general DMs (p.105), star-lock DMs (p.106),
  and moon-lock DMs (p.107; deferred — requires moon orbital positions).
  Outcomes range from a simple multiplier on day length through prograde/
  retrograde slow rotation to 3:2 or 1:1 tidal lock.
  Deferred: moon-size DM, planet-locked-to-moon check.

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
# pylint: disable=locally-disabled,suppressed-message,too-many-lines

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

_rng: random.Random = random  # type: ignore[assignment]

if TYPE_CHECKING:
    from traveller_world_gen import World
    from traveller_moon_gen import Moon


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    """Return the sum of n d6 rolls plus dm, minimum 0."""
    return max(0, sum(_rng.randint(1, 6) for _ in range(n)) + dm)


# ---------------------------------------------------------------------------
# Terrestrial Composition Table (WBH p.75)
# ---------------------------------------------------------------------------

# Each entry: (upper_bound_inclusive, composition_label)
# Roll 2D + size DM; first entry whose bound >= roll is the result.
_COMPOSITION_THRESHOLDS: list[tuple[int, str]] = [
    (3,  "Heavy Iron Core"),   # 2-3
    (5,  "Dense Core"),        # 4-5
    (8,  "Standard"),          # 6-8
    (10, "Low Density"),       # 9-10
    (99, "Icy"),               # 11+
]

# Size DM for the Terrestrial Composition Table roll (WBH p.75).
# Larger worlds retain heavy elements more effectively.
_COMPOSITION_SIZE_DM: dict[int, int] = {
    1: -2, 2: -2,
    3: -1, 4: -1,
    5:  0, 6:  0,
    7:  1, 8:  1,
    9:  2, 10: 2,
}


def _composition_dm(size: int) -> int:
    """Return the size DM for the Terrestrial Composition Table roll."""
    return _COMPOSITION_SIZE_DM.get(size, 0)


def _roll_composition(size: int) -> str:
    """Roll on the Terrestrial Composition Table and return category name."""
    result = _roll(2, _composition_dm(size))
    for bound, label in _COMPOSITION_THRESHOLDS:
        if result <= bound:
            return label
    return "Icy"


# ---------------------------------------------------------------------------
# Terrestrial Density Table (WBH p.75-76)
# ---------------------------------------------------------------------------

# Per-composition density parameters: (base_g_cm3, dice_multiplier)
# Density = base + 1D × multiplier  (g/cm³)
_DENSITY_PARAMS: dict[str, tuple[float, float]] = {
    "Heavy Iron Core": (6.5, 0.4),   # 6.9 – 9.0  g/cm³
    "Dense Core":      (4.8, 0.3),   # 5.1 – 6.6  g/cm³
    "Standard":        (3.4, 0.3),   # 3.7 – 5.2  g/cm³
    "Low Density":     (2.2, 0.2),   # 2.4 – 3.4  g/cm³
    "Icy":             (0.6, 0.2),   # 0.8 – 1.8  g/cm³
}


def _roll_density(composition: str) -> float:
    """Roll on the Terrestrial Density Table and return density in g/cm³."""
    base, mult = _DENSITY_PARAMS.get(composition, (3.4, 0.3))
    return round(base + _rng.randint(1, 6) * mult, 2)


# ---------------------------------------------------------------------------
# Diameter (WBH p.74)
# ---------------------------------------------------------------------------

# Base diameter in km for each integer size code 1-A.
_DIAMETER_BASE_KM: dict[int, int] = {
    1: 1600, 2: 3200,  3: 4800,  4: 6400,  5: 8000,
    6: 9600, 7: 11200, 8: 12800, 9: 14400, 10: 16000,
}


def _roll_diameter(size: int) -> int:
    """Roll actual diameter in km for the given size code (1-A)."""
    base = _DIAMETER_BASE_KM[size]
    variation = (_roll(2) - 7) * 200   # (2D-7) × 200 km, range ±1000 km
    return max(100, base + variation)


# ---------------------------------------------------------------------------
# Axial Tilt Table (WBH p.77)
# ---------------------------------------------------------------------------

def _roll_extreme_axial_tilt() -> float:
    """Roll on the Extreme Axial Tilt sub-table (WBH p.77).

    1D selects the band:
      1–2 : 10 + 1D × 10  →  20–70°   (high axial tilt)
      3   : 30 + 1D × 10  →  40–90°   (extreme axial tilt)
      4   : 90 + 1D × 1D  →  91–126°  (retrograde rotation)
      5   : 180 - 1D × 1D →  144–179° (extreme retrograde)
      6   : 120 + 1D × 10 →  130–180° (extreme retrograde, high variance)
    Result clamped to [0, 180].
    """
    band = _rng.randint(1, 6)
    if band <= 2:
        return float(10 + _rng.randint(1, 6) * 10)
    if band == 3:
        return float(30 + _rng.randint(1, 6) * 10)
    if band == 4:
        return min(float(90 + _rng.randint(1, 6) * _rng.randint(1, 6)), 180.0)
    if band == 5:
        return max(float(180 - _rng.randint(1, 6) * _rng.randint(1, 6)), 0.0)
    # band == 6
    return min(float(120 + _rng.randint(1, 6) * 10), 180.0)


def _roll_axial_tilt() -> float:
    """Roll axial tilt in degrees from the Axial Tilt Table (WBH p.77).

    2D selects the band; the per-band formula gives the result in degrees.
    Bands and formulas (WBH p.77):
      2-4  : (1D-1) / 50        →  0.00 – 0.10°
      5    : 1D / 5             →  0.20 – 1.20°
      6    : 1D                 →  1 – 6°
      7    : 6 + 1D             →  7 – 12°
      8-9  : 5 + (1D × 5)      →  10 – 35°
      ≥10  : extreme axial tilt table
    """
    result = _roll(2)
    if result <= 4:
        return round((_rng.randint(1, 6) - 1) / 50, 2)
    if result == 5:
        return round(_rng.randint(1, 6) / 5, 1)
    if result == 6:
        return float(_rng.randint(1, 6))
    if result == 7:
        return float(6 + _rng.randint(1, 6))
    if result <= 9:
        return float(5 + _rng.randint(1, 6) * 5)
    return _roll_extreme_axial_tilt()


def _roll_axial_tilt_1d() -> float:
    """Recompute axial tilt for 1:1 lock: 1D selects band on Axial Tilt table (WBH p.77 Rule 3)."""
    band = _rng.randint(1, 6)
    if band == 1:
        return round((_rng.randint(1, 6) - 1) / 50, 2)
    if band == 2:
        return round(_rng.randint(1, 6) / 5, 1)
    if band == 3:
        return float(_rng.randint(1, 6))
    if band == 4:
        return float(6 + _rng.randint(1, 6))
    if band == 5:
        return float(5 + _rng.randint(1, 6) * 5)
    return _roll_extreme_axial_tilt()  # band == 6


# ---------------------------------------------------------------------------
# Basic Rotation Rate (WBH p.103)
# ---------------------------------------------------------------------------

def _age_dm(age_gyr: float) -> int:
    """Return the age DM for the Basic Rotation Rate roll (WBH p.103).

    DM+1 per 2 full Gyrs of system age, rounded down.
    """
    return int(age_gyr // 2)


def _roll_day_length(age_gyr: float = 0.0) -> float:
    """Roll basic rotation period in hours for a terrestrial world (WBH p.103).

    Formula: (2D-2) × 4 + 2 + 1D + DMs
    DM: +1 per 2 full Gyrs of system age (round down).
    """
    dm = _age_dm(age_gyr)
    hours = (_roll(2) - 2) * 4 + 2 + _rng.randint(1, 6) + dm
    return round(float(max(1, hours)), 1)



def _orbital_period_hours(orbit_au: float, star_mass: float) -> float:
    """Orbital period in standard hours. P_years = sqrt(AU³ / M_star)."""
    return math.sqrt(orbit_au ** 3 / star_mass) * 8766.0


def _compute_stellar_day(
        sidereal_h: float,
        orbital_period_h: float,
        tidal_status: str,
) -> Optional[float]:
    """Stellar (solar) day in hours from sidereal day and orbital period (WBH p.106).

    The stellar day is what inhabitants experience as 'a day'. It differs from
    the sidereal day because the planet moves along its orbit while rotating.
    Returns None for 1:1 tidally locked worlds (star is stationary in the sky).
    """
    if tidal_status == "1:1_lock":
        return None
    if tidal_status == "retrograde":
        return round((sidereal_h * orbital_period_h) / (orbital_period_h + sidereal_h), 1)
    denom = orbital_period_h - sidereal_h
    if denom <= 0:
        return None
    return round((sidereal_h * orbital_period_h) / denom, 1)


def _reroll_axial_tilt_for_lock() -> float:
    """Reroll axial tilt for 3:2 lock: (2D-2) ÷ 10 degrees (WBH p.105)."""
    return round((_roll(2) - 2) / 10.0, 1)


# Inline copy of _ECC_TABLE from traveller_orbit_gen.py — avoids circular import
_ECC_TABLE_PHYS = [
    (5,  -0.001, 1, 1000),
    (7,   0.000, 1,  200),
    (9,   0.030, 1,  100),
    (10,  0.050, 1,   20),
    (11,  0.050, 2,   20),
    (99,  0.300, 2,   20),
]


def _reroll_eccentricity_tidal(orbit_number: float, age_gyr: float) -> float:
    """Re-roll eccentricity with DM-2 for 1:1 tidal lock (WBH p.77 Rule 4)."""
    dm = -2
    if orbit_number < 1.0 < age_gyr:
        dm -= 1
    first = _rng.randint(1, 6) + _rng.randint(1, 6) + dm
    for max_roll, base, n_dice, divisor in _ECC_TABLE_PHYS:
        if first <= max_roll:
            frac = sum(_rng.randint(1, 6) for _ in range(n_dice)) / divisor
            return min(0.999, max(0.0, base + frac))
    return 0.0


def _tidal_lock_dm(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
        size: int,
        axial_tilt: float,
        atmosphere: int,
        age_gyr: float,
        orbit_number: float,
        star_mass: float,
        orbit_eccentricity: float = 0.0,
        moons: list | None = None,
        num_stars_orbited: int = 1,
) -> int:
    """Compute total DM for the planet-to-star Tidal Lock Status roll.

    Combines general DMs (WBH p.105) and star-lock DMs (WBH p.106).
    At boundary values, uses the DM closer to 0 per WBH edge-condition rule.
    """
    dm = -4  # base DM for star lock (WBH p.106)

    # --- General DMs (WBH p.105) ---
    if size >= 1:
        dm += math.ceil(size / 3)

    if orbit_eccentricity > 0.1:
        dm -= int(orbit_eccentricity * 10)

    # Axial tilt DMs are additive (WBH p.105 note)
    if axial_tilt > 30:
        dm -= 2
    if 60 <= axial_tilt <= 120:
        dm -= 4
    if 80 <= axial_tilt <= 100:
        dm -= 4

    # Atmospheric pressure > 2.5 bar: atmosphere code 8+ is a sufficient proxy
    if atmosphere >= 8:
        dm -= 2

    if age_gyr < 1:
        dm -= 2
    elif age_gyr > 10:
        dm += 4
    elif age_gyr >= 5:
        dm += 2

    # --- Star-lock DMs (WBH p.106) ---
    if orbit_number < 1:
        dm += 4 + int(10 * (1 - orbit_number))
    elif orbit_number < 2:
        dm += 4
    elif orbit_number <= 3:
        dm += 1
    else:
        dm -= int(orbit_number) * 2

    if star_mass < 0.5:
        dm -= 2
    elif star_mass < 1.0:
        dm -= 1
    elif star_mass > 5:
        dm += 2
    elif star_mass > 2:
        dm += 1

    # Moon DM: DM-Total Size of all significant moons Size 1+ (WBH p.106)
    if moons:
        total_moon_sz = sum(
            int(m.size_code) for m in moons
            if not m.is_ring and m.size_code not in (0, "S")
            and int(m.size_code) >= 1
        )
        dm -= total_moon_sz

    # Multi-star DM: DM-Total number of stars orbited (WBH p.106)
    if num_stars_orbited > 1:
        dm -= num_stars_orbited

    return dm


def _planet_moon_lock_dm(moon: "Moon", all_moons: list) -> int:
    """DM for a planet's lock to a specific moon (WBH p.107 left column).

    Base DM is -10; only moons with orbit_pd data can contribute orbit DMs.
    """
    dm = -10  # base

    # Moon size DM: DM+Moon Size if Size 1+
    if moon.size_code not in (0, "S") and int(moon.size_code) >= 1:
        dm += int(moon.size_code)

    # Moon orbit PD DMs
    if moon.orbit_pd is not None:
        pd = moon.orbit_pd
        if pd < 5:
            dm += 5 + math.ceil((5 - pd) * 5)   # DM+5+(5-PD)×5 round up
        elif pd <= 10:
            dm += 4
        elif pd <= 20:
            dm += 2
        elif pd <= 40:
            dm += 1
        elif pd > 60:
            dm -= 6
        # 40–60 PD: no DM

    # Multiple significant moons: DM-2 per moon beyond the first
    sig = [m for m in all_moons
           if not m.is_ring and m.size_code not in (0, "S")
           and int(m.size_code) >= 1]
    extra = len(sig) - 1
    if extra > 0:
        dm -= 2 * extra

    return dm


def _apply_tidal_lock_result(  # pylint: disable=too-many-return-statements
        result: int,
        basic_day_h: float,
        axial_tilt: float,
        period_h: float,
        allow_broken_check: bool = True,
) -> tuple[float, float, str]:
    """Apply one row of the Tidal Lock Status table (WBH p.105).

    Returns (day_hours, axial_tilt, tidal_status).
    allow_broken_check=False suppresses the 1:1 re-roll (used on the reroll itself).
    """
    if result <= 2:
        return basic_day_h, axial_tilt, "none"
    if result == 3:
        return round(basic_day_h * 1.5, 1), axial_tilt, "braking"
    if result == 4:
        return round(basic_day_h * 2.0, 1), axial_tilt, "braking"
    if result == 5:
        return round(basic_day_h * 3.0, 1), axial_tilt, "braking"
    if result == 6:
        return round(basic_day_h * 5.0, 1), axial_tilt, "braking"
    if result == 7:
        day = float(_rng.randint(1, 6) * 5 * 24)
        return day, axial_tilt, "prograde"
    if result == 8:
        day = float(_rng.randint(1, 6) * 20 * 24)
        return day, axial_tilt, "prograde"
    if result == 9:
        day = float(_rng.randint(1, 6) * 10 * 24)
        new_tilt = (180.0 - axial_tilt) if axial_tilt < 90.0 else axial_tilt
        return day, new_tilt, "retrograde"
    if result == 10:
        day = float(_rng.randint(1, 6) * 50 * 24)
        new_tilt = (180.0 - axial_tilt) if axial_tilt < 90.0 else axial_tilt
        return day, new_tilt, "retrograde"
    if result == 11:
        day = round(period_h * 2.0 / 3.0, 1)
        new_tilt = _reroll_axial_tilt_for_lock() if axial_tilt > 3.0 else axial_tilt
        return day, new_tilt, "3:2_lock"
    # result >= 12: 1:1 tidal lock
    if allow_broken_check and (_rng.randint(1, 6) + _rng.randint(1, 6)) == 12:
        # Broken tidal lock: reroll on the table with no DMs (WBH p.105 footnote)
        reroll = _rng.randint(1, 6) + _rng.randint(1, 6)
        return _apply_tidal_lock_result(
            reroll, basic_day_h, axial_tilt, period_h, allow_broken_check=False
        )
    day = round(period_h, 1)
    new_tilt = _roll_axial_tilt_1d()  # WBH p.77 Rule 3: 1D on Axial Tilt table, unconditional
    return day, new_tilt, "1:1_lock"


def _roll_one_lock_case(dm: int, basic_day_h: float, axial_tilt: float,
                        period_h: float) -> tuple[float, float, str]:
    """Roll 2D+DM for one tidal lock case and apply the result."""
    if dm <= -10:
        return basic_day_h, axial_tilt, "none"
    roll = 12 if dm >= 10 else _roll(2) + dm
    return _apply_tidal_lock_result(roll, basic_day_h, axial_tilt, period_h)


def _roll_tidal_lock_status(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        size: int,
        axial_tilt: float,
        atmosphere: int,
        age_gyr: float,
        orbit_number: float,
        orbit_au: float,
        star_mass: float,
        basic_day_h: float,
        orbit_eccentricity: float = 0.0,
        moons: list | None = None,
        num_stars_orbited: int = 1,
) -> tuple[float, float, str]:
    """Roll and apply the Tidal Lock Status table (WBH pp.105-107).

    Handles planet-to-star and planet-to-moon cases in WBH priority order:
    roll for the highest DM case first; cascade to next if no lock occurs.
    Returns (day_hours, axial_tilt, tidal_status).
    """
    period_h = _orbital_period_hours(orbit_au, star_mass)

    star_dm = _tidal_lock_dm(size, axial_tilt, atmosphere, age_gyr,
                              orbit_number, star_mass, orbit_eccentricity,
                              moons=moons, num_stars_orbited=num_stars_orbited)

    # Build candidate list: (dm, lock_type, moon_or_None)
    # Moon candidates require orbit_pd and Size 1+ (WBH p.107)
    candidates: list[tuple[str, int, Moon | None]] = [("star", star_dm, None)]
    if moons:
        for moon in moons:
            if (not moon.is_ring and moon.orbit_pd is not None
                    and moon.size_code not in (0, "S")
                    and int(moon.size_code) >= 1):
                m_dm = _planet_moon_lock_dm(moon, moons)
                candidates.append(("moon", m_dm, moon))

    # Highest DM first; ties: moon before star (WBH p.107)
    candidates.sort(key=lambda c: (-c[1], 0 if c[0] == "moon" else 1))

    for lock_type, dm, moon in candidates:
        if lock_type == "moon":
            assert moon is not None
            moon_period_h = moon.orbit_period_hours or period_h
            day_h, tilt, status = _roll_one_lock_case(
                dm, basic_day_h, axial_tilt, moon_period_h)
        else:
            day_h, tilt, status = _roll_one_lock_case(
                dm, basic_day_h, axial_tilt, period_h)
        if status != "none":
            return day_h, tilt, status

    return basic_day_h, axial_tilt, "none"


# ---------------------------------------------------------------------------
# Seismic Stress (WBH Seismology section, ~pp. 125-128)
# ---------------------------------------------------------------------------

# Solar-to-Earth mass conversion (1 M☉ = 333,000 M⊕, approximate)
_SOLAR_TO_EARTH_MASS = 333_000.0

# AU to millions of km (1 AU = 149.5978707 Mkm)
_AU_TO_MKM = 149.597_870_7


def _compute_rss(
        size: int,
        density: float,
        age_gyr: float,
        moons: list | None = None,
        is_moon: bool = False,
) -> int:
    """Compute Residual Seismic Stress (WBH p.125).

    Formula: floor(Size - Age_Gyr + DMs)², treating floor values < 1 as 0.
    DMs: is_moon +1; density > 1.0 +2; density < 0.5 -1;
         significant moon sizes summed (Size 1+), capped at +12.
    """
    dm = 0
    if is_moon:
        dm += 1
    if density > 1.0:
        dm += 2
    elif density < 0.5:
        dm -= 1
    if moons:
        total_moon_sz = sum(
            int(m.size_code) for m in moons
            if not m.is_ring
            and m.size_code not in (0, "S")
            and int(m.size_code) >= 1
        )
        dm += min(12, total_moon_sz)
    raw = size - age_gyr + dm
    floor_val = math.floor(raw)
    if floor_val < 1:
        return 0
    return floor_val * floor_val


def _compute_tidal_ss(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        diameter_km: float,
        world_mass_earth: float,
        star_mass_solar: float,
        orbit_au: float,
        orbit_eccentricity: float,
        orbit_period_hours: float,
) -> int:
    """Compute Tidal Seismic Stress for a world around its primary (WBH p.127).

    Formula: (PrimaryMass⊕)² × (diameter_km/1600)⁵ × e² /
             (3000 × DistanceMkm⁵ × PeriodDays × WorldMass⊕)
    Values < 1 are treated as 0 (ignored per WBH rule).
    """
    if orbit_eccentricity <= 0.0 or world_mass_earth <= 0.0:
        return 0
    star_mass_earth = star_mass_solar * _SOLAR_TO_EARTH_MASS
    size_factor = diameter_km / 1600.0
    distance_mkm = orbit_au * _AU_TO_MKM
    period_days = orbit_period_hours / 24.0
    if distance_mkm <= 0.0 or period_days <= 0.0:
        return 0
    thf = (
        star_mass_earth ** 2
        * size_factor ** 5
        * orbit_eccentricity ** 2
    ) / (
        3_000.0
        * distance_mkm ** 5
        * period_days
        * world_mass_earth
    )
    return max(0, int(thf))


# ---------------------------------------------------------------------------
# Surface Tidal Amplitude (WBH pp.107-108)
# ---------------------------------------------------------------------------

def _moon_mass_earth(moon: "Moon") -> float:
    """Estimate moon mass in Earth masses using the same diameter³ method as WorldPhysical.

    Assumes Terran density (density/5.515 = 1.0): mass = (diameter_km / 12742)³.
    Size S → 800 km base diameter. Rings and size 0 return 0.
    """
    if moon.is_ring or moon.size_code == 0:
        return 0.0
    if moon.size_code == "S":
        diam = 800.0
    else:
        sz = int(moon.size_code)
        if sz < 1:
            return 0.0
        diam = sz * 1600.0
    return (diam / _EARTH_DIAMETER_KM) ** 3


def _star_tidal_effect_m(star_mass_solar: float, world_size: int, orbit_au: float) -> float:
    """Star tidal effect on a planet in metres (WBH p.107).

    Formula: (Star Mass [solar] × Planet Size) / (32 × AU³)
    Sol on Terra (size 8, 1 AU) = 0.25 m.
    """
    if world_size <= 0 or orbit_au <= 0.0:
        return 0.0
    return (star_mass_solar * world_size) / (32.0 * orbit_au ** 3)


def _moon_tidal_effect_m(moon: "Moon", world_size: int) -> float:
    """Moon tidal effect on its parent planet in metres (WBH p.108).

    Formula: (Moon Mass [Earth] × Planet Size) / (3.2 × (orbit_km / 1,000,000)³)
    Luna (0.0123 ME, 384 400 km) on Terra (size 8) ≈ 0.54 m.
    Rings, moons without orbit_km, and moons with zero mass return 0.
    """
    if moon.is_ring or moon.orbit_km is None or moon.orbit_km <= 0.0:
        return 0.0
    mass = _moon_mass_earth(moon)
    if mass <= 0.0:
        return 0.0
    dist_mkm = moon.orbit_km / 1_000_000.0
    if dist_mkm <= 0.0:
        return 0.0
    return (mass * world_size) / (3.2 * dist_mkm ** 3)


def _compute_tidal_amplitude(
        world_size: int,
        star_mass_solar: float,
        orbit_au: float,
        moons: list | None = None,
) -> float:
    """Total surface tidal amplitude in metres (WBH pp.107-108).

    Sum of star tidal effect plus each qualifying moon's tidal effect.
    Planet-to-moon and moon-to-moon effects are deferred (optional per WBH).
    """
    total = _star_tidal_effect_m(star_mass_solar, world_size, orbit_au)
    if moons:
        for moon in moons:
            total += _moon_tidal_effect_m(moon, world_size)
    return round(total, 4)


def _apply_seismic_stress(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        physical: "WorldPhysical",
        world_size: int,
        age_gyr: float,
        star_mass_solar: float,
        orbit_au: float,
        orbit_eccentricity: float,
        orbit_period_hours: float,
        moons: list | None = None,
        is_moon: bool = False,
        gg_mass_earth: float = 0.0,
        gg_satellite_moon: Optional["Moon"] = None,
) -> None:
    """Compute and set all seismic stress fields on WorldPhysical (WBH ~pp. 125-128).

    Sets residual_seismic_stress, tidal_seismic_stress, total_seismic_stress,
    and seismic_temperature_k (only when it differs from mean_temperature_k).
    Also updates advanced_mean_temperature_k, high_temperature_k, and
    low_temperature_k in-place using ⁴√(T⁴ + TSS⁴) when those fields are set
    and the rounded value changes.
    When gg_mass_earth > 0 and gg_satellite_moon has orbit data, also adds the
    gas giant primary's tidal contribution (for GG satellite mainworlds).
    Mutates physical in-place.
    """
    rss = _compute_rss(world_size, physical.density, age_gyr, moons, is_moon)
    tidal_ss = _compute_tidal_ss(
        physical.diameter_km, physical.mass, star_mass_solar,
        orbit_au, orbit_eccentricity, orbit_period_hours,
    )
    tidal_amp = _compute_tidal_amplitude(world_size, star_mass_solar, orbit_au, moons)

    # Gas giant primary tidal amplitude (for mainworld-as-GG-satellite, WBH p.127)
    # Note: _compute_tidal_ss is NOT applied here — that formula is calibrated for
    # star→planet distances (AU scale) and produces nonsensical values at moon
    # distances (~0.1–0.8 Mkm). The amplitude contribution below correctly captures
    # the GG tidal effect; it flows through TSF into the seismic stress total.
    if gg_mass_earth > 0.0 and gg_satellite_moon is not None and gg_satellite_moon.orbit_km:
        dist_mkm = gg_satellite_moon.orbit_km / 1_000_000.0
        if dist_mkm > 0.0:
            tidal_amp += (gg_mass_earth * world_size) / (3.2 * dist_mkm ** 3)

    tsf = min(math.floor(tidal_amp / 10), 500)
    tss = rss + tidal_ss + tsf
    physical.residual_seismic_stress = rss
    physical.tidal_seismic_stress = tidal_ss
    physical.tidal_stress_factor = tsf
    physical.tidal_amplitude_m = tidal_amp
    physical.total_seismic_stress = tss
    if physical.mean_temperature_k is not None and tss > 0:
        old_t = physical.mean_temperature_k
        adj = round((old_t ** 4 + tss ** 4) ** 0.25)
        if adj != old_t:
            physical.seismic_temperature_k = max(old_t, adj)
    if physical.advanced_mean_temperature_k is not None and tss > 0:
        adv_t = physical.advanced_mean_temperature_k
        adv_adj = round((adv_t ** 4 + tss ** 4) ** 0.25)
        if adv_adj != adv_t:
            physical.advanced_mean_temperature_k = max(adv_t, adv_adj)
            for attr in ("high_temperature_k", "low_temperature_k"):
                t = getattr(physical, attr)
                if t is not None:
                    setattr(physical, attr, max(t, round((t ** 4 + tss ** 4) ** 0.25)))


# ---------------------------------------------------------------------------
# WorldPhysical dataclass
# ---------------------------------------------------------------------------

_EARTH_DIAMETER_KM = 12_742
_EARTH_DENSITY_G_CM3 = 5.515


@dataclass
class WorldPhysical:  # pylint: disable=too-many-instance-attributes
    """Physical characteristics for a Size 1-A terrestrial world."""

    composition: str        # Terrestrial Composition Table result
    diameter_km: int        # Actual diameter in km
    density: float          # g/cm³
    mass: float             # Relative to Earth
    gravity: float          # Surface gravity in G
    escape_velocity: float  # km/s
    axial_tilt: float       # Degrees (0–180; >90° = retrograde; post-tidal final value)
    day_length: float       # Rotation period in standard hours (post-tidal final value)
    tidal_status: str       # "none"|"braking"|"prograde"|"retrograde"|"3:2_lock"|"1:1_lock"
    eccentricity_adjusted: Optional[float] = field(default=None, init=False)
    mean_temperature_k: Optional[int] = field(default=None, init=False)
    residual_seismic_stress: Optional[int] = field(default=None, init=False)
    tidal_seismic_stress: Optional[int] = field(default=None, init=False)
    tidal_stress_factor: Optional[int] = field(default=None, init=False)
    total_seismic_stress: Optional[int] = field(default=None, init=False)
    seismic_temperature_k: Optional[int] = field(default=None, init=False)
    tidal_amplitude_m: Optional[float] = field(default=None, init=False)
    albedo: Optional[float] = field(default=None, init=False)
    greenhouse_factor: Optional[float] = field(default=None, init=False)
    advanced_mean_temperature_k: Optional[int] = field(default=None, init=False)
    high_temperature_k: Optional[int] = field(default=None, init=False)
    low_temperature_k: Optional[int] = field(default=None, init=False)
    stellar_day_hours: Optional[float] = field(default=None, init=False)
    runaway_greenhouse: Optional[bool] = field(default=None, init=False)
    resource_rating:    Optional[int]  = field(default=None, init=False)

    @classmethod
    def from_dict(cls, d: dict) -> "WorldPhysical":
        """Reconstruct a WorldPhysical from a dict produced by to_dict()."""
        obj = cls(
            composition=str(d.get("composition", "Rock")),
            diameter_km=int(d.get("diameter_km", 0)),
            density=float(d.get("density_g_cm3", 0.0)),
            mass=float(d.get("mass_earth", 0.0)),
            gravity=float(d.get("gravity_g", 0.0)),
            escape_velocity=float(d.get("escape_velocity_km_s", 0.0)),
            axial_tilt=float(d.get("axial_tilt_deg", 0.0)),
            day_length=float(d.get("day_length_hours", 0.0)),
            tidal_status=str(d.get("tidal_status", "none")),
        )
        def _fi(k):
            return float(d[k]) if d.get(k) is not None else None
        def _ii(k):
            return int(d[k]) if d.get(k) is not None else None
        obj.eccentricity_adjusted         = _fi("eccentricity_adjusted")
        obj.mean_temperature_k            = _ii("mean_temperature_k")
        obj.residual_seismic_stress       = _ii("residual_seismic_stress")
        obj.tidal_seismic_stress          = _ii("tidal_seismic_stress")
        obj.tidal_stress_factor           = _ii("tidal_stress_factor")
        obj.total_seismic_stress          = _ii("total_seismic_stress")
        obj.seismic_temperature_k              = _ii("seismic_temperature_k")
        obj.tidal_amplitude_m                 = _fi("tidal_amplitude_m")
        obj.albedo                        = _fi("albedo")
        obj.greenhouse_factor             = _fi("greenhouse_factor")
        obj.advanced_mean_temperature_k   = _ii("advanced_mean_temperature_k")
        obj.high_temperature_k            = _ii("high_temperature_k")
        obj.low_temperature_k             = _ii("low_temperature_k")
        obj.stellar_day_hours             = _fi("stellar_day_hours")
        obj.runaway_greenhouse = (
            bool(d["runaway_greenhouse"]) if d.get("runaway_greenhouse") is not None else None
        )
        obj.resource_rating = _ii("resource_rating")
        return obj

    def to_dict(self) -> dict:  # pylint: disable=too-many-branches
        """Return physical characteristics as a JSON-compatible dict."""
        d = {
            "composition":          self.composition,
            "diameter_km":          self.diameter_km,
            "density_g_cm3":        self.density,
            "mass_earth":           self.mass,
            "gravity_g":            self.gravity,
            "escape_velocity_km_s": self.escape_velocity,
            "axial_tilt_deg":       self.axial_tilt,
            "day_length_hours":     self.day_length,
            "tidal_status":         self.tidal_status,
        }
        if self.eccentricity_adjusted is not None:
            d["eccentricity_adjusted"] = round(self.eccentricity_adjusted, 4)
        if self.mean_temperature_k is not None:
            d["mean_temperature_k"] = self.mean_temperature_k
        if self.residual_seismic_stress is not None:
            d["residual_seismic_stress"] = self.residual_seismic_stress
        if self.tidal_seismic_stress:
            d["tidal_seismic_stress"] = self.tidal_seismic_stress
        if self.tidal_stress_factor:
            d["tidal_stress_factor"] = self.tidal_stress_factor
        if self.total_seismic_stress is not None:
            d["total_seismic_stress"] = self.total_seismic_stress
        if self.seismic_temperature_k is not None:
            d["seismic_temperature_k"] = self.seismic_temperature_k
        if self.tidal_amplitude_m is not None:
            d["tidal_amplitude_m"] = round(self.tidal_amplitude_m, 4)
        if self.albedo is not None:
            d["albedo"] = round(self.albedo, 4)
        if self.greenhouse_factor is not None:
            d["greenhouse_factor"] = round(self.greenhouse_factor, 4)
        if self.advanced_mean_temperature_k is not None:
            d["advanced_mean_temperature_k"] = self.advanced_mean_temperature_k
        if self.high_temperature_k is not None:
            d["high_temperature_k"] = self.high_temperature_k
        if self.low_temperature_k is not None:
            d["low_temperature_k"] = self.low_temperature_k
        if self.stellar_day_hours is not None:
            d["stellar_day_hours"] = self.stellar_day_hours
        if self.runaway_greenhouse is not None:
            d["runaway_greenhouse"] = self.runaway_greenhouse
        if self.resource_rating is not None:
            d["resource_rating"] = self.resource_rating
        return d


# ---------------------------------------------------------------------------
# Resource rating helpers (WBH p.131)
# ---------------------------------------------------------------------------

def _density_resource_dm(density: float) -> int:
    """Return the density DM for the terrestrial resource rating roll."""
    if density > 1.12:
        return 2
    if density < 0.5:
        return -2
    return 0


def apply_biological_resource_dms(
    resource_rating: int,
    biomass: Optional[int],
    biodiversity: Optional[int],
    compatibility: Optional[int],
) -> int:
    """Apply biological DMs to a base resource rating and re-clamp to [2, 12].

    Called from attach_detail() after biomass/biodiversity/compatibility are
    known.  No dice are rolled; all adjustments are deterministic.
    """
    rr = resource_rating
    bio = biomass or 0
    if bio >= 3:
        rr += 2
    if biodiversity is not None:
        if biodiversity >= 11:      # B+
            rr += 2
        elif biodiversity >= 8:     # 8–A
            rr += 1
    if compatibility is not None:
        if compatibility >= 8:
            rr += 2
        elif compatibility <= 3 and bio >= 1:
            rr -= 1
    return max(2, min(12, rr))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_world_physical(  # pylint: disable=too-many-positional-arguments,too-many-arguments,too-many-locals
        world: "World",
        age_gyr: float = 0.0,
        orbit_number: Optional[float] = None,
        orbit_au: Optional[float] = None,
        star_mass: Optional[float] = None,
        orbit_eccentricity: float = 0.0,
        hz_deviation: Optional[float] = None,
        rng: Optional[random.Random] = None,
) -> Optional[WorldPhysical]:
    """Generate physical characteristics for a mainworld.

    Implements WBH pp. 74-77, 103-107: diameter, composition, density, mass,
    surface gravity, escape velocity, axial tilt, basic rotation rate, and
    tidal lock status. Also applies 1:1 lock eccentricity reduction (WBH p.77).

    Returns None for Size 0 (belt), Size S, and ring worlds; these
    body types are out of scope and will be handled separately.

    Parameters
    ----------
    world : World
        The mainworld whose size code drives generation.
    age_gyr : float
        System age in Gyr, used for the rotation rate age DM and tidal DMs.
        Defaults to 0.0 (no DM) when age is unavailable.
    orbit_number : float, optional
        WBH Orbit# of the world's orbit, used for tidal lock DMs.
    orbit_au : float, optional
        Orbital distance in AU, used for the orbital period calculation.
    star_mass : float, optional
        Host star mass in solar masses, used for tidal lock DMs and period.
    orbit_eccentricity : float
        Current orbital eccentricity; applies DM−floor(e×10) to the tidal
        lock roll when > 0.1 (WBH p.105); also triggers eccentricity
        reduction on 1:1 lock when > 0.1 (WBH p.77 Rule 4).

    All three of orbit_number, orbit_au, and star_mass must be provided for
    the tidal lock check to run. If any is None, tidal_status is "none".

    Returns
    -------
    WorldPhysical or None
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if world.size == 0:
        return None

    composition = _roll_composition(world.size)
    diameter_km = _roll_diameter(world.size)
    density = _roll_density(composition)
    axial_tilt = _roll_axial_tilt()
    day_length = _roll_day_length(age_gyr)

    rel_d = diameter_km / _EARTH_DIAMETER_KM
    rel_rho = density / _EARTH_DENSITY_G_CM3

    mass = round(rel_d ** 3 * rel_rho, 4)
    gravity = round(rel_d * rel_rho, 3)
    escape_velocity = round(11.186 * math.sqrt(gravity * rel_d), 2)

    tidal_status = "none"
    if orbit_number is not None and orbit_au is not None and star_mass is not None:
        day_length, axial_tilt, tidal_status = _roll_tidal_lock_status(
            size=world.size,
            axial_tilt=axial_tilt,
            atmosphere=world.atmosphere,
            age_gyr=age_gyr,
            orbit_number=orbit_number,
            orbit_au=orbit_au,
            star_mass=star_mass,
            basic_day_h=day_length,
            orbit_eccentricity=orbit_eccentricity,
        )

    wp = WorldPhysical(
        composition=composition,
        diameter_km=diameter_km,
        density=density,
        mass=mass,
        gravity=gravity,
        escape_velocity=escape_velocity,
        axial_tilt=axial_tilt,
        day_length=day_length,
        tidal_status=tidal_status,
    )
    if tidal_status == "1:1_lock" and orbit_eccentricity > 0.1:
        new_ecc = _reroll_eccentricity_tidal(orbit_number or 0.0, age_gyr)
        wp.eccentricity_adjusted = min(orbit_eccentricity, new_ecc)
    if hz_deviation is not None:
        from traveller_world_atmosphere_detail import _compute_mean_temperature  # pylint: disable=import-outside-toplevel
        wp.mean_temperature_k = _compute_mean_temperature(hz_deviation, world.atmosphere)
    if orbit_au is not None and star_mass is not None and world.size > 0:
        wp.tidal_amplitude_m = _compute_tidal_amplitude(world.size, star_mass, orbit_au)
    if orbit_au is not None and star_mass is not None:
        period_h = _orbital_period_hours(orbit_au, star_mass)
        wp.stellar_day_hours = _compute_stellar_day(wp.day_length, period_h, wp.tidal_status)
    wp.resource_rating = max(2, min(12,
        _roll(2, -7 + world.size + _density_resource_dm(density))
    ))
    return wp


def apply_moon_tidal_effects(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        physical: "WorldPhysical",
        moons: list,
        world_size: int,
        world_atmosphere: int,
        age_gyr: float,
        orbit_number: float,
        orbit_au: float,
        star_mass: float,
        orbit_eccentricity: float = 0.0,
        num_stars_orbited: int = 1,
        is_moon: bool = False,
        gg_mass_earth: float = 0.0,
        gg_satellite_moon: Optional["Moon"] = None,
) -> None:
    """Re-run the tidal lock check with moon data and compute seismic stress.

    Called after moon generation completes (WBH pp.106-107, ~pp.125-128).
    Mutates physical in-place. Tidal lock re-run is skipped when moons is
    empty, but seismic stress is always computed.
    Size 0 (belt) worlds are skipped — BeltPhysical has no tidal or seismic fields.
    When gg_mass_earth > 0 and gg_satellite_moon has orbit data, the gas giant
    primary's tidal contribution is included in the seismic stress calculation.
    """
    if not isinstance(physical, WorldPhysical):
        return
    if moons:
        day_h, tilt, status = _roll_tidal_lock_status(
            size=world_size,
            axial_tilt=physical.axial_tilt,
            atmosphere=world_atmosphere,
            age_gyr=age_gyr,
            orbit_number=orbit_number,
            orbit_au=orbit_au,
            star_mass=star_mass,
            basic_day_h=physical.day_length,
            orbit_eccentricity=orbit_eccentricity,
            moons=moons,
            num_stars_orbited=num_stars_orbited,
        )
        physical.day_length = day_h
        physical.axial_tilt = tilt
        physical.tidal_status = status
        if status == "1:1_lock" and orbit_eccentricity > 0.1:
            new_ecc = _reroll_eccentricity_tidal(orbit_number, age_gyr)
            physical.eccentricity_adjusted = min(orbit_eccentricity, new_ecc)

    period_h = _orbital_period_hours(orbit_au, star_mass) if star_mass > 0 else 0.0
    _apply_seismic_stress(
        physical,
        world_size=world_size,
        age_gyr=age_gyr,
        star_mass_solar=star_mass,
        orbit_au=orbit_au,
        orbit_eccentricity=orbit_eccentricity,
        orbit_period_hours=period_h,
        moons=moons,
        is_moon=is_moon,
        gg_mass_earth=gg_mass_earth,
        gg_satellite_moon=gg_satellite_moon,
    )
    if period_h > 0:
        physical.stellar_day_hours = _compute_stellar_day(
            physical.day_length, period_h, physical.tidal_status
        )
