"""
traveller_world_atmosphere_detail.py
=====================================
Atmosphere-derived physical characteristics for Traveller worlds, following
the World Builder's Handbook (WBH pp. 47-50, 79).

Scope
-----
Basic Mean Temperature (WBH p.47):
  Converts orbital HZ deviation and atmosphere code to a mean temperature in K
  using the Basic Mean Temperature table and DM rules.

Advanced Mean Temperature (WBH pp.47-50):
  Physics-based calculation: T = 279 × ⁴√(L × (1-A) × (1+G) / AU²).
  Also computes High and Low temperature bounds via Steps 1-9 (axial tilt,
  rotation, geographic, and luminosity variance factors).

Runaway Greenhouse (WBH p.79):
  Optional check that may convert a world's atmosphere to Exotic/Corrosive/
  Insidious when advanced temperature exceeds 303 K.

These procedures depend on atmosphere code, hydrographics, orbital position,
and stellar luminosity — not on the physical body tables — and are therefore
separate from traveller_world_physical.py.

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

import math
import random
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

_rng: random.Random = random  # type: ignore[assignment]

if TYPE_CHECKING:
    from traveller_world_physical import WorldPhysical


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    """Return the sum of n d6 rolls plus dm, minimum 0."""
    return max(0, sum(_rng.randint(1, 6) for _ in range(n)) + dm)


def _orbital_period_hours(orbit_au: float, star_mass: float) -> float:
    """Orbital period in standard hours. P_years = sqrt(AU³ / M_star).

    Private copy to avoid a circular import with traveller_world_physical.
    """
    return math.sqrt(orbit_au ** 3 / star_mass) * 8766.0


# ---------------------------------------------------------------------------
# Atmosphere groupings — Albedo (WBH pp.47-48)
# ---------------------------------------------------------------------------

_ATM_THIN   = {1, 2, 3, 14}          # Trace / Very Thin / Low
_ATM_MID    = {4, 5, 6, 7, 8, 9}     # Thin through Dense
_ATM_VDENSE = {13}                    # Very Dense
_ATM_HEAVY  = {10, 11, 12, 15, 16, 17}  # Exotic, Corrosive, Insidious, Unusual+


# ---------------------------------------------------------------------------
# Atmosphere groupings — Greenhouse Factor (WBH p.48)
# ---------------------------------------------------------------------------

_ATM_GH_STANDARD = {1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14}
_ATM_GH_EXOTIC   = {10, 15}
_ATM_GH_EXTREME  = {11, 12, 16, 17}


# ---------------------------------------------------------------------------
# Albedo roll (WBH pp.47-48)
# ---------------------------------------------------------------------------

def _roll_albedo(  # pylint: disable=too-many-branches
        atmosphere: int,
        hydrographics: int,
        density: float,
        hz_deviation: float,
) -> float:
    """Roll surface albedo (WBH pp.47-48).

    World type (rocky/icy/icy-far) sets the base; atmosphere and hydrographic
    modifiers are added; result clamped to [0.02, 0.98].
    """
    if density > 0.5:
        albedo = 0.04 + (_roll(2) - 2) * 0.02
    elif hz_deviation <= 2.0:
        albedo = 0.20 + (_roll(2) - 3) * 0.05
    else:
        albedo = 0.25 + (_roll(2) - 2) * 0.07
        if albedo <= 0.40:
            albedo -= max(0, _rng.randint(1, 6) - 1) * 0.05

    if atmosphere in _ATM_THIN:
        albedo += (_roll(2) - 3) * 0.01
    elif atmosphere in _ATM_MID:
        albedo += _roll(2) * 0.01
    elif atmosphere in _ATM_VDENSE:
        albedo += _roll(2) * 0.03
    elif atmosphere in _ATM_HEAVY:
        albedo += (_roll(2) - 2) * 0.05

    if 2 <= hydrographics <= 5:
        albedo += (_roll(2) - 2) * 0.02
    elif hydrographics >= 6:
        albedo += (_roll(2) - 4) * 0.03

    return max(0.02, min(0.98, round(albedo, 4)))


# ---------------------------------------------------------------------------
# Greenhouse factor roll (WBH p.48)
# ---------------------------------------------------------------------------

def _roll_greenhouse_factor(atmosphere: int, pressure_bar: float) -> float:
    """Roll greenhouse factor G (WBH p.48).

    Initial = 0.5 × √bar; then atmosphere-type modifier applied.
    Returns 0.0 for vacuum (atmosphere 0).
    """
    if atmosphere == 0:
        return 0.0
    initial = 0.5 * math.sqrt(pressure_bar)
    if atmosphere in _ATM_GH_STANDARD:
        return round(initial + _roll(3) * 0.01, 4)
    if atmosphere in _ATM_GH_EXOTIC:
        return round(initial * max(0.5, _rng.randint(1, 6) - 1), 4)
    if atmosphere in _ATM_GH_EXTREME:
        die = _rng.randint(1, 6)
        multiplier = float(die) if die <= 5 else float(_roll(3))
        return round(initial * multiplier, 4)
    return round(initial + _roll(3) * 0.01, 4)


# ---------------------------------------------------------------------------
# Basic Mean Temperature (WBH p.47)
# ---------------------------------------------------------------------------

# K values for modified rolls 0-12. Below 0: -5K/step. Above 12: +50K/step.
# Minimum temperature is 3K. K values are authoritative; the °C column in the
# book has a typo at roll 0 (shows -85°C; correct value for 178K is -95°C).
_MEAN_TEMP_TABLE_K: dict[int, int] = {
    0: 178, 1: 198, 2: 218, 3: 238, 4: 263,
    5: 278, 6: 283, 7: 288, 8: 293, 9: 298,
    10: 313, 11: 338, 12: 388,
}

# Atmosphere DMs for the Basic Mean Temperature roll (HZ Regions table, p.47).
# Inline copy of TEMPERATURE_DM from traveller_world_gen.py — avoids circular import.
_MEAN_TEMP_ATM_DM: dict[int, int] = {
    0:  0,  1:  0,
    2: -2,  3: -2,
    4: -1,  5: -1,  14: -1,
    6:  0,  7:  0,
    8:  1,  9:  1,
    10: 2,  13: 2,  15: 2,
    11: 6,  12: 6,
    16: 0,  17: 0,
}


def _orbit_dm_for_mean_temp(hz_deviation: float) -> int:
    """Return the orbital position DM for the Basic Mean Temperature roll.

    If Orbit# < HZCO-1: DM+4 +1 per 0.5 Orbit# below HZCO-1 (round to nearest).
    If Orbit# > HZCO+1: DM-4 -1 per 0.5 Orbit# above HZCO+1 (round to nearest).
    In the habitable zone (|hz_deviation| <= 1): DM 0.
    """
    if hz_deviation < -1.0:
        return 4 + round((-hz_deviation - 1.0) * 2)
    if hz_deviation > 1.0:
        return -4 - round((hz_deviation - 1.0) * 2)
    return 0


def _compute_mean_temperature(hz_deviation: float, atmosphere: int) -> int:
    """Compute Basic Mean Temperature in K (WBH p.47).

    Modified roll = 7 + orbital_DM + atmosphere_DM, then table lookup.
    Extrapolates below roll 0 (-5K/step) and above roll 12 (+50K/step).
    Result is clamped to a minimum of 3K.
    When the extrapolated value would fall below 10K (modified roll < -33),
    the result is instead 1D+5 per the WBH footnote.
    """
    orbit_dm = _orbit_dm_for_mean_temp(hz_deviation)
    atm_dm = _MEAN_TEMP_ATM_DM.get(atmosphere, 0)
    modified_roll = 7 + orbit_dm + atm_dm
    if modified_roll in _MEAN_TEMP_TABLE_K:
        return max(3, _MEAN_TEMP_TABLE_K[modified_roll])
    if modified_roll < 0:
        t = 178 + modified_roll * 5
        if t < 10:
            return _rng.randint(1, 6) + 5
        return max(3, t)
    return max(3, 388 + (modified_roll - 12) * 50)


# ---------------------------------------------------------------------------
# High/Low temperature variance factors (WBH pp.48-50)
# ---------------------------------------------------------------------------

def _axial_tilt_factor(axial_tilt: float, orbital_period_hours: float) -> float:
    """Axial Tilt Factor (WBH p.48, Step 1).

    sin(effective_tilt), where effective tilt is clamped to [0, 90°] by
    reflecting values above 90° back from 180°. Halved for very short years
    (< 0.1 standard years); increased by 0.01×yr for long years (> 2.0
    standard years), capped at min(factor + 0.25, 1.0).
    """
    tilt = axial_tilt if axial_tilt <= 90.0 else 180.0 - axial_tilt
    factor = math.sin(math.radians(tilt))
    orbital_years = orbital_period_hours / 8766.0
    if orbital_years < 0.1:
        factor *= 0.5
    elif orbital_years > 2.0:
        factor = min(1.0, factor + min(0.25, 0.01 * orbital_years))
    return factor


def _rotation_factor(day_length: float, tidal_status: str) -> float:
    """Rotation Factor (WBH p.49, Step 2).

    √(|day_hours|) / 50, capped at 1.0.
    Worlds in 1:1 solar tidal lock always return 1.0.
    """
    if tidal_status == "1:1_lock":
        return 1.0
    return min(1.0, math.sqrt(abs(day_length)) / 50.0)


def _geographic_factor(hydrographics: int) -> float:
    """Geographic Factor (WBH p.49, Step 3).

    (10 - HYD) / 20. Surface Distribution modifier (WBH p.100) is not yet
    implemented; the factor is used without it.
    """
    return (10 - hydrographics) / 20.0


# ---------------------------------------------------------------------------
# Public API — Advanced Mean Temperature (WBH pp.47-50)
# ---------------------------------------------------------------------------

def generate_advanced_mean_temperature(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        physical: "WorldPhysical",
        atmosphere: int,
        hydrographics: int,
        pressure_bar: Optional[float],
        luminosity: float,
        orbit_au: float,
        hz_deviation: float,
        orbit_eccentricity: float = 0.0,
        star_mass: float = 1.0,
        rng: Optional[random.Random] = None,
) -> None:
    """Compute advanced mean temperature plus high/low bounds (WBH pp.47-50).

    Mean formula: T(K) = 279 × ⁴√(L × (1-A) × (1+G) / AU²)
    High/Low use the same formula with luminosity adjusted by the variance
    factor and AU adjusted by orbital eccentricity (Steps 1-9, WBH pp.48-50).

    Mutates physical in-place, setting albedo, greenhouse_factor,
    advanced_mean_temperature_k, high_temperature_k, and low_temperature_k.
    All temperatures are clamped to a minimum of 3K.
    When pressure_bar is None (unbound-pressure subtypes), 10.0 bar is used
    as a minimum estimate for the greenhouse factor roll.
    BeltPhysical guard: returns immediately when physical lacks a density field.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if not hasattr(physical, "density"):
        return
    eff_pressure = pressure_bar if pressure_bar is not None else 10.0
    albedo = _roll_albedo(atmosphere, hydrographics, physical.density, hz_deviation)
    greenhouse = _roll_greenhouse_factor(atmosphere, eff_pressure)

    temp_k = 3
    if orbit_au > 0.0 and luminosity > 0.0:
        interior = luminosity * (1.0 - albedo) * (1.0 + greenhouse)
        if interior > 0.0:
            temp_k = max(3, round(279.0 * (interior / orbit_au ** 2) ** 0.25))

    physical.albedo = albedo
    physical.greenhouse_factor = greenhouse
    physical.advanced_mean_temperature_k = temp_k

    orbital_period_h = (
        _orbital_period_hours(orbit_au, star_mass)
        if orbit_au > 0.0 and star_mass > 0.0 else 0.0
    )
    variance = max(0.0, min(1.0,
        _axial_tilt_factor(physical.axial_tilt, orbital_period_h)
        + _rotation_factor(physical.day_length, physical.tidal_status)
        + _geographic_factor(hydrographics)
    ))
    lum_modifier = variance / (1.0 + eff_pressure)

    high_lum = luminosity * (1.0 + lum_modifier)
    low_lum  = luminosity * (1.0 - lum_modifier)
    near_au  = max(1e-9, orbit_au * (1.0 - orbit_eccentricity))
    far_au   = max(1e-9, orbit_au * (1.0 + orbit_eccentricity))
    common   = (1.0 - albedo) * (1.0 + greenhouse)

    def _temp(lum: float, au: float) -> int:
        if lum <= 0.0 or common <= 0.0 or au <= 0.0:
            return 3
        return max(3, round(279.0 * (lum * common / au ** 2) ** 0.25))

    physical.high_temperature_k = _temp(high_lum, near_au)
    physical.low_temperature_k  = _temp(low_lum,  far_au)


# ---------------------------------------------------------------------------
# Public API — Runaway Greenhouse Check (WBH p.79)
# ---------------------------------------------------------------------------

@dataclass
class RunawayGreenhouseResult:
    """Produced by check_runaway_greenhouse() when a runaway occurred."""
    new_atmosphere: Optional[int]  # None if world already had Atm A/B/C/F+


def check_runaway_greenhouse(
        atmosphere: int,
        temp_k: int,
        age_gyr: float,
        size: int,
        rng: Optional[random.Random] = None,
) -> Optional[RunawayGreenhouseResult]:
    """Roll for runaway greenhouse (WBH p.79).

    Returns RunawayGreenhouseResult when runaway occurs, None otherwise.
    The caller is responsible for mutating world.atmosphere,
    world.temperature, world.hydrographics, and re-running
    generate_advanced_mean_temperature() with the new atmosphere code.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if not 2 <= atmosphere <= 15:
        return None
    if temp_k <= 303:
        return None

    dm_age  = math.ceil(age_gyr)
    dm_temp = (temp_k - 303) // 10
    if _roll(2) + dm_age + dm_temp < 12:
        return None

    if atmosphere in (10, 11, 12, 15, 16, 17):
        return RunawayGreenhouseResult(new_atmosphere=None)

    tainted  = atmosphere in (2, 4, 7, 9)
    dm_size  = -2 if 2 <= size <= 5 else 0
    dm_taint =  1 if tainted else 0
    die = _rng.randint(1, 6) + dm_size + dm_taint
    if die <= 1:
        new_atm = 10   # A — Exotic
    elif die <= 4:
        new_atm = 11   # B — Corrosive
    else:
        new_atm = 12   # C — Insidious
    return RunawayGreenhouseResult(new_atmosphere=new_atm)
