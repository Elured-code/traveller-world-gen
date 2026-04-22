"""
traveller_moon_gen.py
=====================
Generates significant moons and rings for every world in a star system,
following the World Builder's Handbook (WBH pp.55-57, 74-77).

Rules implemented
-----------------
Quantity (WBH p.56):
  Planet Size 1-2  : 1D-5
  Planet Size 3-9  : 2D-8
  Planet Size A-F  : 2D-6
  Small GG (GS#)   : 3D-7
  Medium/Large GG  : 4D-6
  DM-1 per dice if orbit# < 1.0 (only condition relevant without
  eccentricity data; other adjacency conditions require star/spread
  context and are omitted as out of scope)
  Negative result  : 0 moons
  Exactly 0        : 1 significant ring (R)

Sizing (WBH p.57):
  Each moon: 1D roll picks a range, second roll gives size
    1-3 → S  (size S, ~600km)
    4-5 → D3-1  (0 = ring R, 1, or 2)
    6   → Terrestrial: Size-1 - 1D  (may give R or S)
          Gas giant: special table below
  Gas Giant Special Moon Sizing (1D):
    1-3 → 1D   (size 1-6)
    4-5 → 2D-2 (size 0-A; 0 = ring R)
    6   → 2D+4 (size 6-G; G = small gas giant)

  Rings: multiple rings on a single planet are collapsed to one
  R0# notation (e.g. R03 = three significant rings).

Output
------
A Moon dataclass holds (size_code, is_ring).
size_code is an integer for numeric sizes, or the string "S" for
size S moons.  Rings are stored as (size_code=0, is_ring=True).

The main entry point `generate_moons(world_detail, orbit_number)`
returns a list of Moon objects sorted: rings first, then S moons,
then numeric sizes ascending.

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
import random
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from traveller_world_detail import WorldDetail


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    return max(0, sum(random.randint(1, 6) for _ in range(n)) + dm)

def _d3() -> int:
    return (random.randint(1, 6) + 1) // 2

_EHEX = "0123456789ABCDEFG"
def _ehex(n: int) -> str:
    n = max(0, min(n, len(_EHEX) - 1))
    return _EHEX[n]


# ---------------------------------------------------------------------------
# Moon dataclass
# ---------------------------------------------------------------------------

@dataclass
class Moon:
    """A single significant moon or ring."""
    size_code: int | str   # int for numeric sizes, "S" for size S, 0 for ring
    is_ring: bool = False
    is_gas_giant_moon: bool = False  # True if moon is itself a small GG
    detail: Optional["WorldDetail"] = None  # full SAH+social, populated later
    _ring_count: int = field(default=1, init=False, repr=False)  # collapsed ring count

    @property
    def size_str(self) -> str:
        if self.is_ring:
            return "R"
        if self.size_code == "S":
            return "S"
        return _ehex(int(self.size_code))

    def __repr__(self) -> str:
        if self.is_ring:
            return "Ring"
        return f"Size {self.size_str}"

    def to_dict(self) -> dict:
        """Serialise this moon to a JSON-compatible dict.
        The 'detail' field (WorldDetail) is serialised inline if present.
        """
        d: dict = {
            "size":             self.size_str,
            "is_ring":          self.is_ring,
            "is_gas_giant_moon": self.is_gas_giant_moon,
        }
        if self.is_ring:
            d["ring_count"] = getattr(self, "_ring_count", 1)
        if self.detail is not None:
            d["detail"] = self.detail.to_dict()
        return d


# ---------------------------------------------------------------------------
# Moon quantity (WBH p.56)
# ---------------------------------------------------------------------------

def _moon_quantity(size_code: int | str, orbit_number: float,
                   is_gas_giant: bool, gg_category: str) -> int:
    """
    Roll for number of significant moons.
    Returns the raw result (negative = 0 moons, 0 = 1 ring).
    """
    # Orbit# < 1.0 → DM-1 per dice
    dm = -1 if orbit_number < 1.0 else 0

    if is_gas_giant:
        if gg_category == "S":
            result = _roll(3, dm * 3) - 7   # 3D-7
        else:
            result = _roll(4, dm * 4) - 6   # 4D-6
    else:
        sz = int(size_code) if size_code != "S" else 1
        if sz <= 2:
            result = random.randint(1, 6) + dm - 5     # 1D-5
        elif sz <= 9:
            result = _roll(2, dm * 2) - 8              # 2D-8
        else:
            result = _roll(2, dm * 2) - 6              # 2D-6

    return result


# ---------------------------------------------------------------------------
# Moon sizing (WBH p.57)
# ---------------------------------------------------------------------------

def _size_terrestrial_moon(parent_size: int) -> Moon:
    """
    Size one moon for a terrestrial parent (WBH p.57).

    WBH rule: "Moons may range in size from S to the Size of the parent planet."
    The clamp at the end of each branch enforces this — any roll that would
    exceed the parent size is clamped down to the parent size (twin world).
    The Size 1 planet special case falls out naturally: D3-1 can give 2 which
    would exceed parent_size=1 and is clamped to 1 (twin).

    r=6 branch WBH: "a negative result indicates a Size S moon, a 0 indicates
    a ring." The formula is (parent_size - 1) - 1D. For parent_size=1 the
    result is always ≤ 0 (ring or S). For larger parents it can be positive.
    """
    r = random.randint(1, 6)
    if r <= 3:
        return Moon(size_code="S")
    elif r <= 5:
        sz = _d3() - 1            # D3-1: 0, 1, or 2
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        # Clamp: moon cannot exceed parent size (WBH p.57)
        sz = min(sz, parent_size)
        return Moon(size_code=sz)
    else:
        # Size = (parent_size - 1) - 1D; negative → S, zero → ring (WBH p.57)
        sz = (parent_size - 1) - random.randint(1, 6)
        if sz < 0:
            return Moon(size_code="S")
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        return Moon(size_code=sz)


def _size_gg_moon(gg_diameter: int) -> Moon:
    """Size one moon for a gas giant parent."""
    r = random.randint(1, 6)
    if r <= 3:
        return Moon(size_code="S")
    elif r <= 5:
        sz = _d3() - 1
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        return Moon(size_code=sz)
    else:
        # Gas Giant Special Moon Sizing
        r2 = random.randint(1, 6)
        if r2 <= 3:
            sz = random.randint(1, 6)             # 1D → 1-6
        elif r2 <= 5:
            sz = max(0, _roll(2) - 2)             # 2D-2 → 0-A
        else:
            sz = _roll(2, 4)                      # 2D+4 → 6-G
            if sz >= 16:
                # Size G = this moon is a small gas giant
                gg_sz = _d3() + _d3()             # D3+D3 for GS diameter
                return Moon(size_code=gg_sz, is_gas_giant_moon=True)
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        # Clamp moon to be smaller than parent
        sz = min(sz, gg_diameter - 1)
        return Moon(size_code=max(1, sz))


# ---------------------------------------------------------------------------
# Twin/near-twin check (WBH p.57)
# ---------------------------------------------------------------------------

def _twin_check(moon: Moon, parent_size: int) -> Moon:
    """
    If a terrestrial moon's size is exactly parent_size - 2, roll 2D:
      2  → size becomes parent_size - 1
      12 → size becomes parent_size (twin world)
      else → unchanged
    """
    if moon.is_ring or moon.size_code == "S":
        return moon
    sz = int(moon.size_code)
    if sz == parent_size - 2:
        r = _roll(2)
        if r == 2:
            return Moon(size_code=parent_size - 1)
        elif r == 12:
            return Moon(size_code=parent_size)
    return moon


# ---------------------------------------------------------------------------
# Ring consolidation
# ---------------------------------------------------------------------------

def _consolidate(moons: List[Moon]) -> List[Moon]:
    """
    Collapse multiple rings into a single R0# entry.
    Returns list with at most one ring entry (R0N).
    """
    rings = [m for m in moons if m.is_ring]
    others = [m for m in moons if not m.is_ring]
    if not rings:
        return others
    # Represent all rings as a single Moon with ring_count attribute
    ring_entry = Moon(size_code=0, is_ring=True)
    ring_entry._ring_count = len(rings)
    return [ring_entry] + others


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_moons(
    size_code: int | str,
    orbit_number: float,
    is_gas_giant: bool = False,
    gg_category: str = "M",   # "S", "M", or "L"
    gg_diameter: int = 8,
) -> List[Moon]:
    """
    Generate all significant moons for a world.

    Parameters
    ----------
    size_code     : planet size (int 1-F, or "S" for size S terrestrial)
    orbit_number  : orbital Orbit# (used for DM check)
    is_gas_giant  : True if this is a gas giant
    gg_category   : "S", "M", or "L" — gas giant size category
    gg_diameter   : gas giant diameter in Terran diameters (for clamping)

    Returns
    -------
    List of Moon objects, rings first then by size.
    """
    # Belts (size 0) are diffuse debris fields, not solid bodies.
    # The WBH moon rules apply to planets (solid bodies ≥ size S).
    # A belt cannot gravitationally retain significant moons.
    if not is_gas_giant and size_code != "S" and int(size_code) == 0:
        return []

    raw = _moon_quantity(size_code, orbit_number, is_gas_giant, gg_category)

    if raw < 0:
        return []
    if raw == 0:
        ring = Moon(size_code=0, is_ring=True)
        ring._ring_count = 1
        return [ring]

    moons: List[Moon] = []
    for _ in range(raw):
        if is_gas_giant:
            m = _size_gg_moon(gg_diameter)
        else:
            sz = int(size_code) if size_code != "S" else 1
            m = _size_terrestrial_moon(sz)
            m = _twin_check(m, sz)
        moons.append(m)

    moons = _consolidate(moons)

    # Sort: rings first, then S, then numeric ascending
    def sort_key(m: Moon):
        if m.is_ring: return (0, 0)
        if m.size_code == "S": return (1, 0)
        return (2, int(m.size_code))

    return sorted(moons, key=sort_key)


def moons_str(moons: List[Moon]) -> str:
    """Compact string representation of a moon list, e.g. 'R03, S, S, 2, 5'."""
    if not moons:
        return "—"
    parts = []
    for m in moons:
        if m.is_ring:
            count = getattr(m, "_ring_count", 1)
            parts.append(f"R{count:02d}")
        elif m.is_gas_giant_moon:
            parts.append(f"GS{_ehex(int(m.size_code))}")
        elif m.size_code == "S":
            parts.append("S")
        else:
            parts.append(_ehex(int(m.size_code)))
    return ", ".join(parts)
