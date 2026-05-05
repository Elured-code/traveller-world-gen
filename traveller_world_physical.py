"""
traveller_world_physical.py
===========================
Physical world characteristics derived from the UWP size and atmosphere
codes, following the World Builder's Handbook (WBH pp. 74-77).

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
# WorldPhysical dataclass
# ---------------------------------------------------------------------------

_EARTH_DIAMETER_KM = 12_742
_EARTH_DENSITY_G_CM3 = 5.515


@dataclass
class WorldPhysical:
    """Physical characteristics for a Size 1-A terrestrial world."""

    composition: str        # Terrestrial Composition Table result
    diameter_km: int        # Actual diameter in km
    density: float          # g/cm³
    mass: float             # Relative to Earth
    gravity: float          # Surface gravity in G
    escape_velocity: float  # km/s

    def to_dict(self) -> dict:
        """Return physical characteristics as a JSON-compatible dict."""
        return {
            "composition":          self.composition,
            "diameter_km":          self.diameter_km,
            "density_g_cm3":        self.density,
            "mass_earth":           self.mass,
            "gravity_g":            self.gravity,
            "escape_velocity_km_s": self.escape_velocity,
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
    )
