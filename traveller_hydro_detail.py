"""
traveller_hydro_detail.py
=========================
Hydrographic detail for Traveller mainworlds, following the World Builder's
Handbook (WBH pp. 91-95).

Phase 1 (Session 37): surface liquid percentage to the nearest 1%, derived
from the integer Hydrographics code using a flat random distribution over each
code's defined percentage range (WBH Hydrographics Ranges table, p.93).

Phase 2 (Session 67): fluid type — the primary liquid covering the world
surface, determined by temperature zone (WBH pp.91-92).

Licence
-------
MIT Licence -- see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""

import random
from dataclasses import dataclass, field
from typing import Optional


# WBH p.93 Hydrographics Ranges table: code -> (low_pct, high_pct)
_HYDRO_PCT_RANGE: dict[int, tuple[int, int]] = {
    0:  (0,   5),
    1:  (6,  15),
    2:  (16, 25),
    3:  (26, 35),
    4:  (36, 45),
    5:  (46, 55),
    6:  (56, 65),
    7:  (66, 75),
    8:  (76, 85),
    9:  (86, 95),
    10: (96, 100),
}

# WBH pp.91-92 — primary fluid type by temperature zone.
_FLUID_TYPE_BY_TEMP: dict[str, str] = {
    "Boiling":   "Sulfuric Acid",
    "Hot":       "Water",
    "Temperate": "Water",
    "Cold":      "Ammonia",
    "Frozen":    "Liquid Hydrocarbons",
}

# Atmosphere codes with no surface liquid (gas giant / hydrogen atmospheres).
_NO_SURFACE_LIQUID_ATMS: frozenset[int] = frozenset({16, 17})


def _fluid_type(atmosphere: int, temperature: str) -> Optional[str]:
    """Return the primary fluid type (WBH pp.91-92) or None for dry/gas worlds."""
    if atmosphere in _NO_SURFACE_LIQUID_ATMS:
        return None
    return _FLUID_TYPE_BY_TEMP.get(temperature)


@dataclass
class HydrographicDetail:
    """Detailed hydrographic characteristics for a mainworld."""

    surface_liquid_pct: int            # 0-100 %, to nearest 1 % (Phase 1)
    fluid_type: Optional[str] = field(default=None)  # primary surface fluid (Phase 2)

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        d: dict = {"surface_liquid_pct": self.surface_liquid_pct}
        if self.fluid_type is not None:
            d["fluid_type"] = self.fluid_type
        return d


def generate_hydrographic_detail(
    hydrographics: int,
    size: int,
    *,
    atmosphere: int = 0,
    temperature: str = "Temperate",
) -> Optional[HydrographicDetail]:
    """Return hydrographic detail for a mainworld.

    Returns None for size 0 (belts, which carry no hydrographic detail).

    Worlds with Size > 9 and Hydrographics A (10) are always 100% liquid
    (WBH p.93: worlds above Size code 9 with Hydrographics code A are always
    treated as 100% liquid).

    For all other cases the surface liquid percentage is drawn from a flat
    uniform distribution over the code's defined range (WBH p.93 table).

    Fluid type (WBH pp.91-92) is determined by temperature zone; desert worlds
    (hydrographics 0) and gas-atmosphere worlds (codes 16-17) produce no fluid
    type.

    Args:
        hydrographics: integer hydro code 0-10.
        size: integer UWP size code.
        atmosphere: integer atmosphere code (keyword-only).
        temperature: temperature category string — "Boiling", "Hot",
            "Temperate", "Cold", or "Frozen" (keyword-only).

    Returns:
        HydrographicDetail or None.
    """
    if size == 0:
        return None
    if hydrographics < 0 or hydrographics > 10:
        return None

    if hydrographics == 10 and size > 9:
        pct = 100
    else:
        low, high = _HYDRO_PCT_RANGE[hydrographics]
        pct = random.randint(low, high)

    fluid = _fluid_type(atmosphere, temperature) if hydrographics > 0 else None

    return HydrographicDetail(surface_liquid_pct=pct, fluid_type=fluid)
