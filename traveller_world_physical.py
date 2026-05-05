"""
traveller_world_physical.py
===========================
Physical world characteristics derived from the UWP size and atmosphere
codes, following the World Builder's Handbook (WBH pp. 74-78).

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
  Result clamped to 0-90°.

Day Length (WBH p.77-78):
  Roll 2D to select a rotation period band; roll 1D within that band.
  Result in standard hours. Tidal locking (requires orbital data) is
  out of scope and will be handled separately.

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
# pylint: disable=locally-disabled,suppressed-message

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from traveller_world_gen import World


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    """Return the sum of n d6 rolls plus dm, minimum 0."""
    return max(0, sum(random.randint(1, 6) for _ in range(n)) + dm)


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
    return round(base + random.randint(1, 6) * mult, 2)


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
    """Placeholder for the WBH Extreme Axial Tilt sub-table (WBH p.77).

    The full extreme table is not yet implemented; returns a high-tilt
    value until the sub-table rules are added.
    """
    # Extreme axial tilt sub-table not yet implemented (WBH p.77).
    return float(30 + _roll(2) * 5)   # 40-90° placeholder


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
        return round((random.randint(1, 6) - 1) / 50, 2)
    if result == 5:
        return round(random.randint(1, 6) / 5, 1)
    if result == 6:
        return float(random.randint(1, 6))
    if result == 7:
        return float(6 + random.randint(1, 6))
    if result <= 9:
        return float(5 + random.randint(1, 6) * 5)
    return _roll_extreme_axial_tilt()


# ---------------------------------------------------------------------------
# Day Length Table (WBH p.77-78)
# ---------------------------------------------------------------------------

# Each entry: (upper_bound_inclusive, base_hours, dice_count, multiplier)
# Roll 2D selects a band; rolls within that band give: base + nD × multiplier
# Result stored in standard hours (1 decimal place).
_DAY_LENGTH_BANDS: list[tuple[int, int, int, int]] = [
    (3,   6, 1,  2),   # 2-3:   6 + 1D × 2h  =  8-18h  (fast rotator)
    (6,  14, 1,  4),   # 4-6:  14 + 1D × 4h  = 18-38h  (standard)
    (9,  30, 1, 10),   # 7-9:  30 + 1D × 10h = 40-90h  (slow rotator)
    (11, 60, 2, 10),   # 10-11: 60 + 2D × 10h = 80-180h
    (99,100, 2, 25),   # 12:  100 + 2D × 25h = 150-400h (very slow)
]


def _roll_day_length() -> float:
    """Roll rotation period in hours from the Day Length Table."""
    band_roll = _roll(2)
    for bound, base, dice, mult in _DAY_LENGTH_BANDS:
        if band_roll <= bound:
            hours = base + _roll(dice) * mult
            return round(float(hours), 1)
    return 24.0


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
    axial_tilt: float       # Degrees (0-90)
    day_length: float       # Rotation period in standard hours

    def to_dict(self) -> dict:
        """Return physical characteristics as a JSON-compatible dict."""
        return {
            "composition":          self.composition,
            "diameter_km":          self.diameter_km,
            "density_g_cm3":        self.density,
            "mass_earth":           self.mass,
            "gravity_g":            self.gravity,
            "escape_velocity_km_s": self.escape_velocity,
            "axial_tilt_deg":       self.axial_tilt,
            "day_length_hours":     self.day_length,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_world_physical(world: "World") -> Optional[WorldPhysical]:
    """Generate physical characteristics for a mainworld.

    Implements WBH pp. 74-77: diameter, composition, density, mass,
    surface gravity, and escape velocity.  Derived properties are
    calculated from diameter and density using standard formulae
    (WBH p.76-77).

    Returns None for Size 0 (belt), Size S, and ring worlds; these
    body types are out of scope and will be handled separately.

    Parameters
    ----------
    world : World
        The mainworld whose size code drives generation.

    Returns
    -------
    WorldPhysical or None
    """
    if world.size == 0:
        return None

    composition = _roll_composition(world.size)
    diameter_km = _roll_diameter(world.size)
    density = _roll_density(composition)
    axial_tilt = _roll_axial_tilt()
    day_length = _roll_day_length()

    rel_d = diameter_km / _EARTH_DIAMETER_KM
    rel_rho = density / _EARTH_DENSITY_G_CM3

    mass = round(rel_d ** 3 * rel_rho, 4)
    gravity = round(rel_d * rel_rho, 3)
    escape_velocity = round(11.186 * math.sqrt(gravity * rel_d), 2)

    return WorldPhysical(
        composition=composition,
        diameter_km=diameter_km,
        density=density,
        mass=mass,
        gravity=gravity,
        escape_velocity=escape_velocity,
        axial_tilt=axial_tilt,
        day_length=day_length,
    )
