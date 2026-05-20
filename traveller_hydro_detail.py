"""
traveller_hydro_detail.py
=========================
Hydrographic detail for Traveller mainworlds, following the World Builder's
Handbook (WBH pp. 93-96).

Phase 1 (this module): surface liquid percentage to the nearest 1%, derived
from the integer Hydrographics code using a flat random distribution over each
code's defined percentage range (WBH Hydrographics Ranges table, p.93).

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
from dataclasses import dataclass
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


@dataclass
class HydrographicDetail:
    """Detailed hydrographic characteristics for a mainworld."""

    surface_liquid_pct: int  # 0-100 %, to nearest 1 %

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {"surface_liquid_pct": self.surface_liquid_pct}


def generate_hydrographic_detail(
    hydrographics: int,
    size: int,
) -> Optional[HydrographicDetail]:
    """Return hydrographic detail for a mainworld.

    Returns None for size 0 (belts, which carry no hydrographic detail).

    Worlds with Size > 9 and Hydrographics A (10) are always 100% liquid
    (WBH p.93: worlds above Size code 9 with Hydrographics code A are always
    treated as 100% liquid).

    For all other cases the surface liquid percentage is drawn from a flat
    uniform distribution over the code's defined range (WBH p.93 table).

    Args:
        hydrographics: integer hydro code 0-10.
        size: integer UWP size code.

    Returns:
        HydrographicDetail or None.
    """
    if size == 0:
        return None
    if hydrographics < 0 or hydrographics > 10:
        return None

    if hydrographics == 10 and size > 9:
        return HydrographicDetail(surface_liquid_pct=100)

    low, high = _HYDRO_PCT_RANGE[hydrographics]
    return HydrographicDetail(surface_liquid_pct=random.randint(low, high))
