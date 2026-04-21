"""
traveller_stellar_gen.py
========================
Stellar data generation for the Traveller RPG (2022 Core Rulebook /
World Builder's Handbook, Sept 2023 edition).

Implements the expanded star system generation procedure described in the
World Builder's Handbook (WBH), covering:

  • Primary star type and class determination (WBH p.14-15)
  • Star subtype (p.16)
  • Star mass, temperature, and diameter (p.17-19) with interpolation
  • Luminosity via the Stefan-Boltzmann formula (p.20)
  • System age (p.20-22)
  • Multiple stars — Close, Near, Far, and Companion presence (p.23)
  • Stellar Orbit# ranges for secondary stars (p.27)
  • Non-primary star type determination (p.29) — Random, Lesser, Sibling, Twin

Out of scope (Special Circumstances chapter, p.219+):
  • Full post-stellar object generation (white dwarfs, neutron stars,
    black holes, pulsars) — these are detected and labelled but not
    physically characterised
  • Protostar and primordial system special rules
  • Star cluster and nebula handling
  • Eccentricity calculation for stellar orbits
  • Habitable zone orbit placement (requires full system generation)

All dice are simulated using Python's random module, matching the Traveller
2D convention: 2D = sum of two fair six-sided dice.

Usage
-----
    from traveller_stellar_gen import generate_stellar_data, StarSystem

    system = generate_stellar_data()
    print(system.summary())
    data = system.to_dict()

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
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def roll(n: int, dm: int = 0) -> int:
    """Roll n six-sided dice and add dm. Minimum result is 0."""
    return max(0, sum(random.randint(1, 6) for _ in range(n)) + dm)


def d3() -> int:
    """Simulate a D3 as ceil(1D / 2)."""
    return (random.randint(1, 6) + 1) // 2


def d10() -> int:
    """Roll a d10 (1-10)."""
    return random.randint(1, 10)


# ---------------------------------------------------------------------------
# Lookup tables — all taken directly from WBH source pages
# ---------------------------------------------------------------------------

# Star Type Determination table (WBH p.14-15)
# Maps 2D result to primary type result.
# Roll 12+ → consult Hot column (second 2D roll).
# Roll 2 → Special (not main sequence).
STAR_TYPE_TABLE = {
    2:  "Special",
    3:  "M",
    4:  "M",
    5:  "M",
    6:  "M",
    7:  "K",
    8:  "K",
    9:  "G",
    10: "G",
    11: "F",
    # 12+ → Hot column
}

# Hot column (WBH p.14-15): consulted on a 2D re-roll when primary gives 12+
HOT_COLUMN = {
    2:  "A",   # Class VI (Special re-roll with DM+1)
    3:  "A",
    4:  "A",
    5:  "A",
    6:  "A",
    7:  "A",
    8:  "A",
    9:  "A",
    10: "B",
    11: "B",
    # 12+ → O
}

# Special column — consulted on primary roll of 2 (WBH p.14-15)
SPECIAL_COLUMN = {
    2:  "Class VI",   # requires a second type roll with DM+1
    3:  "Class VI",
    4:  "Class VI",
    5:  "Class VI",
    6:  "Class IV",
    7:  "Class IV",
    8:  "Class IV",
    9:  "Class III",
    10: "Class III",
    11: "Giants",     # requires Giants column roll
    # 12+ → Giants
}

# Giants column — for "Giants" results (WBH p.14-15)
GIANTS_COLUMN = {
    2:  "III",
    3:  "III",
    4:  "III",
    5:  "III",
    6:  "III",
    7:  "III",
    8:  "III",
    9:  "II",
    10: "II",
    11: "Ib",
    # 12+ → Ia
}

# Star Subtype table (WBH p.16)
# 2D → numeric subtype (for non-M primary stars) or M-type subtype
SUBTYPE_NUMERIC = {
    2: 0, 3: 1, 4: 3, 5: 5, 6: 7, 7: 9, 8: 8, 9: 6, 10: 4, 11: 2, 12: 0
}
SUBTYPE_M_PRIMARY = {
    2: 8, 3: 6, 4: 5, 5: 4, 6: 0, 7: 2, 8: 1, 9: 3, 10: 5, 11: 7, 12: 9
}

# Star Mass and Temperature by Class (WBH p.17)
# Keys are (spectral_type, subtype_anchor) where subtype_anchor is 0, 5, or 9.
# Values are (mass, temperature_K).
STAR_MASS_TEMP: dict[tuple[str, int], tuple[float, int]] = {
    # Class V (main sequence) — mass in solar masses, temp in K
    ("O", 0): (90.0,  50000),
    ("O", 5): (60.0,  40000),
    ("B", 0): (18.0,  30000),
    ("B", 5): (5.0,   15000),
    ("A", 0): (2.2,   10000),
    ("A", 5): (1.8,    8000),
    ("F", 0): (1.5,    7500),
    ("F", 5): (1.3,    6500),
    ("G", 0): (1.1,    6000),
    ("G", 5): (0.9,    5600),
    ("K", 0): (0.8,    5200),
    ("K", 5): (0.7,    4400),
    ("M", 0): (0.5,    3700),
    ("M", 5): (0.16,   3000),
    ("M", 9): (0.08,   2400),
}

# Star Diameter by Class (WBH p.18-19)
# Keys (spectral_type, subtype_anchor, luminosity_class)
# Values: diameter in solar diameters. None = class not applicable.
STAR_DIAMETER: dict[tuple[str, int, str], Optional[float]] = {
    # (type, subtype, class) → diameter
    # --- O ---
    ("O", 0, "Ia"): 25.0,  ("O", 5, "Ia"): 22.0,
    ("O", 0, "Ib"): 24.0,  ("O", 5, "Ib"): 20.0,
    ("O", 0, "II"): 22.0,  ("O", 5, "II"): 18.0,
    ("O", 0, "III"):21.0,  ("O", 5, "III"):15.0,
    ("O", 0, "V"):  20.0,  ("O", 5, "V"):  12.0,
    ("O", 0, "VI"):  0.18, ("O", 5, "VI"):  0.18,
    # --- B ---
    ("B", 0, "Ia"): 20.0,  ("B", 5, "Ia"): 60.0,
    ("B", 0, "Ib"): 14.0,  ("B", 5, "Ib"): 25.0,
    ("B", 0, "II"): 12.0,  ("B", 5, "II"): 14.0,
    ("B", 0, "III"):10.0,  ("B", 5, "III"): 6.0,
    ("B", 0, "IV"):  8.0,  ("B", 5, "IV"):  5.0,
    ("B", 0, "V"):   7.0,  ("B", 5, "V"):   3.5,
    ("B", 0, "VI"):  0.2,  ("B", 5, "VI"):  0.5,
    # --- A ---
    ("A", 0, "Ia"):120.0,  ("A", 5, "Ia"):180.0,
    ("A", 0, "Ib"): 50.0,  ("A", 5, "Ib"): 75.0,
    ("A", 0, "II"): 30.0,  ("A", 5, "II"): 45.0,
    ("A", 0, "III"): 5.0,  ("A", 5, "III"): 5.0,
    ("A", 0, "IV"):  4.0,  ("A", 5, "IV"):  3.0,
    ("A", 0, "V"):   2.2,  ("A", 5, "V"):   2.0,
    # --- F ---
    ("F", 0, "Ia"):210.0,  ("F", 5, "Ia"):280.0,
    ("F", 0, "Ib"): 85.0,  ("F", 5, "Ib"):115.0,
    ("F", 0, "II"): 50.0,  ("F", 5, "II"): 66.0,
    ("F", 0, "III"): 5.0,  ("F", 5, "III"): 5.0,
    ("F", 0, "IV"):  3.0,  ("F", 5, "IV"):  2.0,
    ("F", 0, "V"):   1.7,  ("F", 5, "V"):   1.5,
    # --- G ---
    ("G", 0, "Ia"):330.0,  ("G", 5, "Ia"):360.0,
    ("G", 0, "Ib"):135.0,  ("G", 5, "Ib"):150.0,
    ("G", 0, "II"): 77.0,  ("G", 5, "II"): 90.0,
    ("G", 0, "III"):10.0,  ("G", 5, "III"):15.0,
    ("G", 0, "IV"):  3.0,  ("G", 5, "IV"):  4.0,
    ("G", 0, "V"):   1.1,  ("G", 5, "V"):   0.95,
    ("G", 0, "VI"):  0.8,  ("G", 5, "VI"):  0.7,
    # --- K ---
    ("K", 0, "Ia"):420.0,  ("K", 5, "Ia"):600.0,
    ("K", 0, "Ib"):180.0,  ("K", 5, "Ib"):260.0,
    ("K", 0, "II"):110.0,  ("K", 5, "II"):160.0,
    ("K", 0, "III"):20.0,  ("K", 5, "III"):40.0,
    ("K", 0, "IV"):  6.0,
    ("K", 0, "V"):   0.9,  ("K", 5, "V"):   0.8,
    ("K", 0, "VI"):  0.6,  ("K", 5, "VI"):  0.5,
    # --- M ---
    ("M", 0, "Ia"):900.0,  ("M", 5, "Ia"):1200.0, ("M", 9, "Ia"):1800.0,
    ("M", 0, "Ib"):380.0,  ("M", 5, "Ib"): 600.0, ("M", 9, "Ib"): 800.0,
    ("M", 0, "II"):230.0,  ("M", 5, "II"): 350.0, ("M", 9, "II"): 500.0,
    ("M", 0, "III"):60.0,  ("M", 5, "III"):100.0, ("M", 9, "III"):200.0,
    ("M", 0, "V"):   0.7,  ("M", 5, "V"):   0.2,  ("M", 9, "V"):   0.1,
    ("M", 0, "VI"):  0.4,  ("M", 5, "VI"):  0.1,  ("M", 9, "VI"):  0.08,
}

# Spectral type ordering for Lesser/Sibling logic
SPECTRAL_ORDER = ["O", "B", "A", "F", "G", "K", "M"]

# Colour descriptions per spectral type (WBH p.17)
SPECTRAL_COLOUR = {
    "O": "Blue",
    "B": "Blue-White",
    "A": "White",
    "F": "Yellow-White",
    "G": "Yellow",
    "K": "Light Orange",
    "M": "Orange-Red",
    "D": "White (degenerate)",
    "BD": "Brown",
}

# Type order hottest→coolest (for 'hotter than primary' check in Random)
TYPE_HEAT_ORDER = {"O": 0, "B": 1, "A": 2, "F": 3, "G": 4, "K": 5, "M": 6}


# ---------------------------------------------------------------------------
# Interpolation helpers
# ---------------------------------------------------------------------------

def _interpolate(
    spectral: str,
    subtype: int,
    lum_class: str,
    table: dict,
) -> Optional[float]:
    """
    Linearly interpolate a value from STAR_MASS_TEMP or STAR_DIAMETER
    for an arbitrary subtype between the anchored reference subtypes (0, 5, 9).

    Returns None if the requested class is not defined for this spectral type.
    """
    # Determine anchor brackets
    if spectral == "M":
        anchors = [0, 5, 9]
    else:
        anchors = [0, 5]

    # Build the key depending on which table this is
    def get_val(anchor: int) -> Optional[float]:
        if table is STAR_MASS_TEMP:
            return table.get((spectral, anchor), (None, None))[0]
        else:
            return table.get((spectral, anchor, lum_class))

    # Find the bracket containing our subtype
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i + 1]
        if lo <= subtype <= hi:
            v_lo = get_val(lo)
            v_hi = get_val(hi)
            if v_lo is None or v_hi is None:
                return None
            fraction = (subtype - lo) / (hi - lo)
            return v_lo + (v_hi - v_lo) * fraction

    # Subtype beyond highest anchor — return highest value
    return get_val(anchors[-1])


def _interp_temp(spectral: str, subtype: int) -> Optional[int]:
    """Interpolate surface temperature for a Class V star."""
    if spectral == "M":
        anchors = [(0, 3700), (5, 3000), (9, 2400)]
    elif spectral == "K":
        anchors = [(0, 5200), (5, 4400)]
    elif spectral == "G":
        anchors = [(0, 6000), (5, 5600)]
    elif spectral == "F":
        anchors = [(0, 7500), (5, 6500)]
    elif spectral == "A":
        anchors = [(0, 10000), (5, 8000)]
    elif spectral == "B":
        anchors = [(0, 30000), (5, 15000)]
    elif spectral == "O":
        anchors = [(0, 50000), (5, 40000)]
    else:
        return None

    for i in range(len(anchors) - 1):
        lo, t_lo = anchors[i]
        hi, t_hi = anchors[i + 1]
        if lo <= subtype <= hi:
            frac = (subtype - lo) / (hi - lo)
            return round(t_lo + (t_hi - t_lo) * frac)
    return anchors[-1][1]


# ---------------------------------------------------------------------------
# Star dataclass
# ---------------------------------------------------------------------------

@dataclass
class Star:
    """Represents one star in a system."""

    designation: str            # e.g. "Aa", "Ab", "B", "Ca"
    role: str                   # "primary", "companion", "close", "near", "far"
    spectral_type: str          # "G", "K", "M", "O", "B", "A", "F", "D", "BD"
    subtype: Optional[int]      # 0-9 for main sequence; None for D/BD
    lum_class: str              # "Ia","Ib","II","III","IV","V","VI","D","BD"
    mass: float                 # Solar masses
    temperature: int            # Surface temperature in Kelvin
    diameter: float             # Solar diameters
    luminosity: float           # Solar luminosity (L☉)
    orbit_number: Optional[float] = None   # Orbit# relative to parent
    orbit_au: Optional[float] = None       # Approximate AU
    age_gyr: Optional[float] = None        # System age in Gyr (primary only)
    ms_lifespan_gyr: Optional[float] = None  # Main sequence lifespan
    special_notes: str = ""     # e.g. "protostar", "post-stellar"

    def classification(self) -> str:
        """Return the standard Traveller star classification string."""
        if self.spectral_type == "D":
            return "D"
        if self.spectral_type == "BD":
            return "BD"
        sub = str(self.subtype) if self.subtype is not None else ""
        return f"{self.spectral_type}{sub} {self.lum_class}"

    def colour(self) -> str:
        return SPECTRAL_COLOUR.get(self.spectral_type, "Unknown")

    def to_dict(self) -> dict:
        return {
            "designation": self.designation,
            "role": self.role,
            "classification": self.classification(),
            "spectral_type": self.spectral_type,
            "subtype": self.subtype,
            "luminosity_class": self.lum_class,
            "mass_solar": round(self.mass, 3),
            "temperature_k": self.temperature,
            "diameter_solar": round(self.diameter, 3),
            "luminosity_solar": round(self.luminosity, 4),
            "orbit_number": round(self.orbit_number, 2) if self.orbit_number is not None else None,
            "orbit_au": round(self.orbit_au, 3) if self.orbit_au is not None else None,
            "age_gyr": round(self.age_gyr, 3) if self.age_gyr is not None else None,
            "ms_lifespan_gyr": round(self.ms_lifespan_gyr, 2) if self.ms_lifespan_gyr is not None else None,
            "colour": self.colour(),
            "special_notes": self.special_notes,
        }


# ---------------------------------------------------------------------------
# StarSystem dataclass
# ---------------------------------------------------------------------------

@dataclass
class StarSystem:
    """Holds all generated stellar data for one system."""

    stars: List[Star] = field(default_factory=list)

    @property
    def primary(self) -> Star:
        return self.stars[0]

    @property
    def age_gyr(self) -> Optional[float]:
        return self.primary.age_gyr

    def to_dict(self) -> dict:
        return {
            "star_count": len(self.stars),
            "age_gyr": round(self.age_gyr, 3) if self.age_gyr is not None else None,
            "stars": [s.to_dict() for s in self.stars],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            f"  Star system  —  {len(self.stars)} star(s)",
            f"  System age   :  {self.age_gyr:.2f} Gyr" if self.age_gyr else "  System age   :  Unknown",
            "=" * 60,
        ]
        for star in self.stars:
            orbit_str = ""
            if star.orbit_number is not None:
                orbit_str = f"  Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)"
            lines.append(
                f"  {star.designation:<4}  {star.classification():<12}  "
                f"Mass {star.mass:.2f}☉  T {star.temperature:,}K  "
                f"L {star.luminosity:.3g}☉{orbit_str}"
            )
            if star.special_notes:
                lines.append(f"       Note: {star.special_notes}")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Physical property derivation
# ---------------------------------------------------------------------------

def _compute_luminosity(diameter: float, temperature: int) -> float:
    """
    Luminosity formula from WBH p.20:
        L = (diameter / 1)^2 × (temperature / 5772)^4
    Diameter is in solar units. Sol temperature ≈ 5,772 K.
    """
    return (diameter ** 2) * ((temperature / 5772) ** 4)


def _main_sequence_lifespan(mass: float) -> float:
    """
    WBH p.20: Lifespan (Gyr) = 10 / mass^2.5
    """
    if mass <= 0:
        return float("inf")
    return 10.0 / (mass ** 2.5)


def _star_properties(
    spectral: str,
    subtype: Optional[int],
    lum_class: str,
) -> Tuple[float, int, float, float]:
    """
    Derive (mass, temperature, diameter, luminosity) for a star.
    Returns approximate values via linear interpolation from WBH tables.
    """
    if spectral == "D":
        # White dwarf: approximate values
        return (0.6, 25000, 0.013, _compute_luminosity(0.013, 25000))
    if spectral == "BD":
        # Brown dwarf: approximate values
        return (0.05, 1500, 0.1, _compute_luminosity(0.1, 1500))

    st = subtype if subtype is not None else 0

    # Mass (from Class V table regardless of actual class, then scale)
    mass_v = _interpolate(spectral, st, "V", STAR_MASS_TEMP)
    if mass_v is None:
        mass_v = 1.0
    # Giant classes are more massive — apply approximate scale factors
    mass_scale = {"Ia": 3.0, "Ib": 2.5, "II": 2.0, "III": 1.5,
                  "IV": 1.1, "V": 1.0, "VI": 0.85}.get(lum_class, 1.0)
    mass = mass_v * mass_scale

    # Temperature (interpolated for V, adjusted slightly for other classes)
    temp_v = _interp_temp(spectral, st)
    if temp_v is None:
        temp_v = 5000
    temp_scale = {
        "Ia": 0.85, "Ib": 0.88, "II": 0.92, "III": 0.90,
        "IV": 0.97, "V": 1.0, "VI": 0.95,
    }.get(lum_class, 1.0)
    temperature = round(temp_v * temp_scale)

    # Diameter (from the specific class table)
    diameter = _interpolate(spectral, st, lum_class, STAR_DIAMETER)
    if diameter is None:
        # Fall back to class V if no entry
        diameter = _interpolate(spectral, st, "V", STAR_DIAMETER) or 1.0

    luminosity = _compute_luminosity(diameter, temperature)

    return (mass, temperature, diameter, luminosity)


# ---------------------------------------------------------------------------
# Subtype generation
# ---------------------------------------------------------------------------

def _roll_subtype(spectral: str, use_m_column: bool = False) -> int:
    """
    Roll for numeric subtype using the Star Subtype table (WBH p.16).
    use_m_column=True for primary M-type stars.
    """
    r = roll(2)
    if use_m_column:
        return SUBTYPE_M_PRIMARY.get(r, r % 10)
    return SUBTYPE_NUMERIC.get(r, r % 10)


def _apply_class_iv_subtype_limit(subtype: int) -> int:
    """
    Class IV is limited to types B0–K4.
    For K-type Class IV: subtract 5 from any subtype result above 4.
    """
    return max(0, subtype - 5) if subtype > 4 else subtype


# ---------------------------------------------------------------------------
# Orbit# to AU conversion
# ---------------------------------------------------------------------------

# WBH Orbit# to AU lookup — standard Traveller Orbit# table
ORBIT_AU = {
    0: 0.2,   0.5: 0.2,   1: 0.4,   2: 0.7,   3: 1.0,   4: 1.6,
    5: 2.8,   6: 5.2,     7: 10.0,  8: 20.0,  9: 40.0,  10: 77.0,
    11: 154.0, 12: 266.0, 13: 532.0, 14: 1064.0, 15: 2128.0,
    16: 4256.0, 17: 8512.0,
}


def _orbit_to_au(orbit_num: float) -> float:
    """
    Convert a fractional Orbit# to AU using linear interpolation
    between the standard Traveller Orbit# table entries.
    """
    keys = sorted(ORBIT_AU.keys())
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= orbit_num <= hi:
            frac = (orbit_num - lo) / (hi - lo)
            return ORBIT_AU[lo] + (ORBIT_AU[hi] - ORBIT_AU[lo]) * frac
    # Beyond table range
    if orbit_num < keys[0]:
        return ORBIT_AU[keys[0]]
    return ORBIT_AU[keys[-1]]


# ---------------------------------------------------------------------------
# Primary star generation (WBH p.14-16)
# ---------------------------------------------------------------------------

def _generate_primary_star_type() -> Tuple[str, str]:
    """
    Roll on the Star Type Determination table (WBH p.14-15).
    Returns (spectral_type, lum_class).
    lum_class will be "V" for all standard results unless special/hot columns
    indicate otherwise.
    """
    r = roll(2)

    if r <= 2:
        # Special column
        r2 = roll(2)
        result = SPECIAL_COLUMN.get(r2, "Giants" if r2 >= 12 else "Class III")
        if result.startswith("Class"):
            cls_num = result.split()[-1]
            lum_map = {"VI": "VI", "IV": "IV", "III": "III"}
            lum_class = lum_map.get(cls_num, "V")
            # Re-roll for actual type on Type column with DM+1
            r3 = roll(2, 1)
            spectral = STAR_TYPE_TABLE.get(min(r3, 11), "M")
            if spectral == "Special" or spectral not in TYPE_HEAT_ORDER:
                spectral = "M"
            # Apply class limits
            if lum_class == "IV":
                # Class IV limited to B0–K4 only
                if spectral not in ("O", "B", "A", "F", "G", "K"):
                    spectral = "K"
            if lum_class == "VI":
                # Class VI: treat F as G, A as B
                if spectral == "F":
                    spectral = "G"
                if spectral == "A":
                    spectral = "B"
            return spectral, lum_class

        elif result == "Giants":
            # Roll on Giants column
            r4 = roll(2)
            lum_class = GIANTS_COLUMN.get(r4, "Ia" if r4 >= 12 else "III")
            r5 = roll(2, 1)
            spectral = STAR_TYPE_TABLE.get(min(r5, 11), "G")
            if spectral in ("Special",):
                spectral = "G"
            return spectral, lum_class

        else:
            return "M", "V"

    if r == 12:
        # Hot column
        r2 = roll(2)
        if r2 >= 12:
            spectral = "O"
        else:
            spectral = HOT_COLUMN.get(r2, "A")
        # On roll of 12+ in hot column, and 11+ means Giants
        if r2 >= 11:
            # Bright hot star — roll Giants column for class
            r3 = roll(2)
            lum_class = GIANTS_COLUMN.get(r3, "Ia" if r3 >= 12 else "III")
            return spectral, lum_class
        return spectral, "V"

    spectral = STAR_TYPE_TABLE.get(r, "M")
    return spectral, "V"


def generate_primary_star(designation: str = "A") -> Star:
    """
    Generate the primary star of a system (WBH pp.14-20).
    Includes type, subtype, physical properties, and system age.
    """
    spectral, lum_class = _generate_primary_star_type()

    # Handle special/post-stellar types
    if spectral in ("D",):
        mass, temperature, diameter, luminosity = _star_properties("D", None, "D")
        age = _small_star_age()
        return Star(
            designation=designation, role="primary",
            spectral_type="D", subtype=None, lum_class="D",
            mass=mass, temperature=temperature,
            diameter=diameter, luminosity=luminosity,
            age_gyr=age, ms_lifespan_gyr=None,
            special_notes="White dwarf (post-stellar)",
        )
    if spectral in ("BD",):
        mass, temperature, diameter, luminosity = _star_properties("BD", None, "BD")
        age = _small_star_age()
        return Star(
            designation=designation, role="primary",
            spectral_type="BD", subtype=None, lum_class="BD",
            mass=mass, temperature=temperature,
            diameter=diameter, luminosity=luminosity,
            age_gyr=age, ms_lifespan_gyr=None,
            special_notes="Brown dwarf (sub-stellar)",
        )

    # Subtype
    use_m_col = (spectral == "M")
    subtype = _roll_subtype(spectral, use_m_column=use_m_col)

    # Class IV special limits
    if lum_class == "IV":
        if spectral == "K":
            subtype = _apply_class_iv_subtype_limit(subtype)
        if spectral == "O":
            spectral = "B"

    # Class VI: F→G, A→B
    if lum_class == "VI":
        if spectral == "F":
            spectral = "G"
        if spectral == "A":
            spectral = "B"

    mass, temperature, diameter, luminosity = _star_properties(
        spectral, subtype, lum_class
    )
    ms_lifespan = _main_sequence_lifespan(mass)
    age = _generate_system_age(mass, ms_lifespan)

    notes = ""
    if age < 0.1:
        notes = "Primordial system (age < 0.1 Gyr)"
    elif age < 0.01:
        notes = "Protostar (age < 0.01 Gyr)"

    return Star(
        designation=designation, role="primary",
        spectral_type=spectral, subtype=subtype, lum_class=lum_class,
        mass=mass, temperature=temperature,
        diameter=diameter, luminosity=luminosity,
        age_gyr=age, ms_lifespan_gyr=ms_lifespan,
        special_notes=notes,
    )


# ---------------------------------------------------------------------------
# System age (WBH p.20-22)
# ---------------------------------------------------------------------------

def _small_star_age() -> float:
    """
    Age for stars with mass < 0.9 (WBH p.20-21).
    Roll 1D × 2, add D3-1, optionally add d10 fractional digit.
    """
    age = random.randint(1, 6) * 2 + (d3() - 1)
    # Add one fractional digit via d10 (subtract 1 from integer part)
    frac = d10() / 10.0
    age = max(0.1, (age - 1) + frac)
    return round(age, 2)


def _generate_system_age(mass: float, ms_lifespan: float) -> float:
    """
    Generate system age (Gyr) based on primary star mass (WBH p.20-22).
    """
    if mass <= 0:
        return _small_star_age()

    if mass < 0.9:
        return _small_star_age()

    # Larger stars — age is a random fraction of their main sequence lifespan
    # Use linear variance: age = ms_lifespan × (random fraction 0–1)
    fraction = random.random()
    age = ms_lifespan * fraction
    # Minimum age check
    if mass < 4.7:
        age = max(0.01, age)
    age = min(age, 13.8)  # universe age cap
    return round(age, 3)


# ---------------------------------------------------------------------------
# Habitable zone centre orbit (WBH p.246 formula approximation)
# ---------------------------------------------------------------------------

def habitable_zone_au(luminosity: float) -> float:
    """
    Approximate habitable zone centre distance in AU.
    Distance ≈ sqrt(luminosity)  (WBH p.246 checklist formula approximation)
    """
    return math.sqrt(max(luminosity, 1e-10))


# ---------------------------------------------------------------------------
# Multiple stars (WBH p.23-29)
# ---------------------------------------------------------------------------

def _multiple_star_dm(primary: Star) -> int:
    """Return the DM for the Multiple Stars Presence roll (WBH p.23)."""
    lc = primary.lum_class
    sp = primary.spectral_type

    if lc in ("Ia", "Ib", "II", "III", "IV"):
        return +1
    if lc in ("V", "VI") and sp in ("O", "B", "A", "F"):
        return +1
    if lc in ("V", "VI") and sp == "M":
        return -1
    if sp in ("D", "BD"):
        return -1
    return 0


def _determine_non_primary_type(
    parent: Star,
    role: str,
    designation: str,
    _depth: int = 0,
) -> Star:
    """
    Determine the type of a non-primary star using the
    Non-Primary Star Determination table (WBH p.29).

    role must be one of: "companion", "close", "near", "far"

    The WBH states the primary star is always the most massive.  After
    all result paths are resolved a final mass check is applied: if the
    generated star still exceeds the parent's mass (possible when the
    parent is a subdwarf or when same-letter subtypes vary widely) the
    star is replaced with a brown dwarf, which is always sub-stellar.
    The _depth guard prevents infinite recursion on "other" results.
    """
    dm = 0
    if parent.lum_class in ("III", "IV"):
        dm = -1

    r = roll(2, dm)

    # Determine result category from table
    if role == "companion":
        # Companion column
        if r <= 1:
            result = "other"
        elif r <= 3:
            result = "other"
        elif r <= 5:
            result = "random"
        elif r <= 6:
            result = "random"
        elif r <= 7:
            result = "lesser"
        elif r == 8:
            result = "sibling"
        elif r == 9:
            result = "sibling"
        elif r == 10:
            result = "twin"
        else:
            result = "twin"
    else:
        # Secondary column (close, near, far)
        if r <= 1:
            result = "other"
        elif r <= 3:
            result = "other"
        elif r <= 5:
            result = "random"
        elif r == 6:
            result = "random"
        elif r <= 7:
            result = "lesser"
        elif r == 8:
            result = "lesser"
        elif r == 9:
            result = "sibling"
        elif r == 10:
            result = "sibling"
        else:
            result = "twin"

    # Resolve result
    if result == "other":
        # Roll again on same column recursively (with depth limit)
        if _depth >= 8:
            return _build_star("BD", "BD", designation, role)
        return _determine_non_primary_type(parent, role, designation, _depth + 1)

    if result == "random":
        # Roll on main type table; if the result would be more massive than
        # the parent, treat as lesser instead (WBH: primary is most massive).
        # We check actual computed mass, not just spectral letter, because
        # within the same letter a lower subtype (e.g. M0 vs M7) can be
        # significantly more massive.
        spectral, lum_class = _generate_primary_star_type()
        candidate = _build_star(spectral, lum_class, designation, role)
        if candidate.mass > parent.mass * 1.001:
            result = "lesser"
        else:
            return candidate

    if result == "lesser":
        # Same class, one spectral type cooler; reroll subtype
        sp_idx = SPECTRAL_ORDER.index(parent.spectral_type) if parent.spectral_type in SPECTRAL_ORDER else -1
        if sp_idx >= len(SPECTRAL_ORDER) - 1:
            # M-type lesser → M-type.
            # The lesser must be dimmer (higher subtype number) than the parent.
            # If the roll produces a lower subtype (heavier star), promote to BD.
            new_sub = _roll_subtype("M")
            if parent.subtype is not None and new_sub <= parent.subtype:
                # Rolled equal-or-hotter within M → use BD instead
                return _build_star("BD", "BD", designation, role)
            return _build_star("M", parent.lum_class, designation, role,
                               forced_subtype=new_sub)
        new_spectral = SPECTRAL_ORDER[sp_idx + 1]
        # If Class IV lesser becomes too cool for Class IV → Class V
        lum_class = parent.lum_class
        if lum_class == "IV" and new_spectral not in ("B", "A", "F", "G", "K"):
            lum_class = "V"
        star = _build_star(new_spectral, lum_class, designation, role)
        if star.mass > parent.mass * 1.001:
            return _build_star("BD", "BD", designation, role)
        return star

    if result == "sibling":
        # Same type; subtract 1D from subtype
        if parent.subtype is None:
            return _build_star(parent.spectral_type, parent.lum_class,
                               designation, role)
        sub_reduction = random.randint(1, 6)
        new_sub = parent.subtype + sub_reduction  # higher number = dimmer
        # Wrap to next cooler type if needed
        sp_idx = SPECTRAL_ORDER.index(parent.spectral_type) if parent.spectral_type in SPECTRAL_ORDER else -1
        if new_sub > 9:
            if sp_idx >= len(SPECTRAL_ORDER) - 1:
                return _build_star("BD", "BD", designation, role)
            new_sub = new_sub - 10
            new_spectral = SPECTRAL_ORDER[sp_idx + 1]
        else:
            new_spectral = parent.spectral_type
        star = _build_star(new_spectral, parent.lum_class, designation, role,
                           forced_subtype=new_sub)
        if star.mass > parent.mass * 1.001:
            return _build_star("BD", "BD", designation, role)
        return star

    # twin
    star = _build_star(parent.spectral_type, parent.lum_class, designation,
                       role, forced_subtype=parent.subtype)
    # Final safety net: the WBH requires the primary to be the most massive
    # star in the system.  If any result path still produces a star heavier
    # than the parent (e.g. Class VI parent whose Class V equivalent is
    # heavier), replace it with a brown dwarf.
    if star.mass > parent.mass * 1.001:
        return _build_star("BD", "BD", designation, role)
    return star


def _build_star(
    spectral: str,
    lum_class: str,
    designation: str,
    role: str,
    forced_subtype: Optional[int] = None,
) -> Star:
    """Construct a Star object from type/class, rolling subtype if needed."""
    if spectral in ("D",):
        mass, temp, diam, lum = _star_properties("D", None, "D")
        return Star(
            designation=designation, role=role,
            spectral_type="D", subtype=None, lum_class="D",
            mass=mass, temperature=temp, diameter=diam, luminosity=lum,
            special_notes="White dwarf",
        )
    if spectral in ("BD",):
        mass, temp, diam, lum = _star_properties("BD", None, "BD")
        return Star(
            designation=designation, role=role,
            spectral_type="BD", subtype=None, lum_class="BD",
            mass=mass, temperature=temp, diameter=diam, luminosity=lum,
            special_notes="Brown dwarf",
        )

    subtype = forced_subtype if forced_subtype is not None else _roll_subtype(
        spectral, use_m_column=False
    )
    # Clamp subtype to 0-9
    subtype = max(0, min(9, subtype))

    # Apply class limits
    if lum_class == "IV" and spectral == "K":
        subtype = _apply_class_iv_subtype_limit(subtype)
    if lum_class == "VI":
        if spectral == "F":
            spectral = "G"
        if spectral == "A":
            spectral = "B"

    mass, temp, diam, lum = _star_properties(spectral, subtype, lum_class)
    ms_life = _main_sequence_lifespan(mass)

    return Star(
        designation=designation, role=role,
        spectral_type=spectral, subtype=subtype, lum_class=lum_class,
        mass=mass, temperature=temp, diameter=diam, luminosity=lum,
        ms_lifespan_gyr=ms_life,
    )


def _companion_orbit() -> Tuple[float, float]:
    """
    Companion star Orbit# (WBH p.27):
    Orbit# = 1D÷10 + (2D-7)÷100  → range ~0.05–0.65
    """
    orbit_num = random.randint(1, 6) / 10.0 + (roll(2) - 7) / 100.0
    orbit_num = max(0.05, min(0.65, orbit_num))
    return round(orbit_num, 2), _orbit_to_au(orbit_num)


def _secondary_orbit(slot: str) -> Tuple[float, float]:
    """
    Secondary star Orbit# ranges (WBH p.27):
      Close  = 1D-1 (0=0.5); range 0.5–5
      Near   = 1D+5; range 6–11
      Far    = 1D+11; range 12–17
    """
    if slot == "close":
        base = random.randint(1, 6) - 1
        orbit_num = max(0.5, float(base))
    elif slot == "near":
        orbit_num = float(random.randint(1, 6) + 5)
    else:  # far
        orbit_num = float(random.randint(1, 6) + 11)
    # Add optional fractional variance
    frac = random.randint(0, 9) / 10.0
    orbit_num = round(orbit_num + frac, 1)
    return orbit_num, _orbit_to_au(orbit_num)


# ---------------------------------------------------------------------------
# Top-level system generation
# ---------------------------------------------------------------------------

def generate_stellar_data() -> StarSystem:
    """
    Generate complete stellar data for a star system.

    Procedure (WBH pp.14-29):
      1. Primary star — type, class, subtype, physical properties, age
      2. Multiple stars presence — Close, Near, Far, Companion (each 2D ≥ 10)
      3. For each secondary that exists, determine type via Non-Primary table
      4. For each of the above (including primary), check for a companion

    Returns a StarSystem with all stars populated.
    """
    system = StarSystem()

    # Step 1: Primary star
    primary = generate_primary_star("A")
    primary.orbit_number = 0.0
    primary.orbit_au = 0.0
    system.stars.append(primary)

    multi_dm = _multiple_star_dm(primary)

    # Giant primaries cannot have Close secondaries
    can_have_close = primary.lum_class not in ("Ia", "Ib", "II", "III")

    # Step 2: Check Close / Near / Far secondary presence
    slots = []
    if can_have_close and roll(2, multi_dm) >= 10:
        slots.append("close")
    if roll(2, multi_dm) >= 10:
        slots.append("near")
    if roll(2, multi_dm) >= 10:
        slots.append("far")

    # Step 3: Determine secondary stars and assign designations
    # Designation scheme: secondary letters B, C, D...
    # Stars with companions get suffix 'a'; companions get suffix 'b'
    # For simplicity we use A (primary), B (close/near/far), C, D, etc.
    secondary_letter = ord("B")
    secondary_stars: list[tuple[str, str]] = []  # (designation, slot)

    for slot in slots:
        desig = chr(secondary_letter)
        secondary_stars.append((desig, slot))
        secondary_letter += 1

    for desig, slot in secondary_stars:
        star = _determine_non_primary_type(primary, slot, desig)
        orbit_num, orbit_au = _secondary_orbit(slot)
        star.orbit_number = orbit_num
        star.orbit_au = orbit_au
        star.role = slot
        system.stars.append(star)

    # Step 4: Check companion for primary and each secondary
    all_current = list(system.stars)  # snapshot before adding companions
    companion_suffix = ord("a")

    for parent_star in all_current:
        if roll(2, multi_dm) >= 10:
            comp_desig = parent_star.designation + chr(companion_suffix)
            companion = _determine_non_primary_type(parent_star, "companion",
                                                    comp_desig)
            orbit_num, orbit_au = _companion_orbit()
            companion.orbit_number = orbit_num
            companion.orbit_au = orbit_au
            system.stars.append(companion)

    # Propagate system age from primary to all stars
    for star in system.stars:
        if star.age_gyr is None:
            star.age_gyr = primary.age_gyr

    return system


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Traveller (WBH) stellar data for a star system."
    )
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible results")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of systems to generate")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    systems = [generate_stellar_data() for _ in range(args.count)]

    if args.json:
        if args.count == 1:
            print(systems[0].to_json())
        else:
            print(json.dumps([s.to_dict() for s in systems], indent=2))
    else:
        for i, system in enumerate(systems):
            if args.seed is None and args.count > 1:
                print(f"System {i + 1}")
            print(system.summary())
            if i < len(systems) - 1:
                print()


if __name__ == "__main__":
    main()
