"""
traveller_world_gen.py
======================
Generates a Traveller (2022 Core Rulebook) mainworld using the standard
Universe Creation rules (pp. 248-261).

Each characteristic is generated in rulebook order, with each step feeding
into the next exactly as the rules describe.  The final output is a full
Universal World Profile (UWP) string plus a human-readable summary.

Usage:
    python traveller_world_gen.py                # generates one random world
    python traveller_world_gen.py --name Cogri   # give the world a name
    python traveller_world_gen.py --count 5      # generate five worlds
    python traveller_world_gen.py --seed 42      # reproducible result

All dice notation used here:
    2D   = sum of two six-sided dice  (range 2-12)
    1D   = one six-sided die          (range 1-6)

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
# pylint: disable=too-many-lines

import json
import math
import random
_rng: random.Random = random  # type: ignore[assignment]
import argparse
from dataclasses import dataclass, field
from typing import List, Optional, Union, TYPE_CHECKING

from traveller_belt_physical import BeltPhysical
from traveller_hydro_detail import HydrographicDetail
from html_render import render
from world_codes import (
    APP_VERSION, AtmosphereCode, StarportCode, TemperatureCategory, TradeCode, TravelZone,
)
from tables import (
    SIZE_DIAMETER_LABEL, SIZE_GRAVITY_LABEL, POPULATION_RANGE,
    TRADE_CODE_FULL, BASE_FULL, ZONE_CSS_CLASS, TIDAL_STATUS_LABELS,
    BIOCOMPLEXITY_DESC, habitability_description,
)

if TYPE_CHECKING:
    from traveller_world_physical import WorldPhysical
    from traveller_world_population_detail import PopulationDetail
    from traveller_world_government_detail import GovernmentDetail
    from traveller_world_law_detail import LawDetail
    from traveller_world_tech_detail import TechDetail


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def roll(num_dice: int, modifier: int = 0) -> int:
    """Roll *num_dice* six-sided dice and add *modifier*.

    The result is clamped to a minimum of 0 because many Traveller tables
    treat negative totals as zero (e.g. Atmosphere, Hydrographics).
    """
    total = sum(_rng.randint(1, 6) for _ in range(num_dice))
    return max(0, total + modifier)


# ---------------------------------------------------------------------------
# Hexadecimal helper
# ---------------------------------------------------------------------------

# Traveller eHex: 0–9 then A=10 … G=16, H=17, I=18 … Z=35 (covers max TL 28)
_HEX_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def to_hex(value: int) -> str:
    """Convert an integer to a single Traveller eHex character."""
    value = max(0, min(value, len(_HEX_DIGITS) - 1))
    return _HEX_DIGITS[value]


# ---------------------------------------------------------------------------
# Lookup tables  (all directly from the 2022 Core Rulebook)
# ---------------------------------------------------------------------------

# Atmosphere descriptions (p.250 + WBH NHZ), indexed by atmosphere code 0-17
ATMOSPHERE_NAMES = {
    0:  "None",
    1:  "Trace",
    2:  "Very Thin, Tainted",
    3:  "Very Thin",
    4:  "Thin, Tainted",
    5:  "Thin",
    6:  "Standard",
    7:  "Standard, Tainted",
    8:  "Dense",
    9:  "Dense, Tainted",
    10: "Exotic",
    11: "Corrosive",
    12: "Insidious",
    13: "Very Dense",
    14: "Low",
    15: "Unusual",
    16: "Gas, Helium",
    17: "Gas, Hydrogen",
}

# Survival gear required by atmosphere (p.250)
ATMOSPHERE_GEAR = {
    0:  "Vacc Suit",
    1:  "Vacc Suit",
    2:  "Respirator, Filter",
    3:  "Respirator",
    4:  "Filter",
    5:  "None",
    6:  "None",
    7:  "Filter",
    8:  "None",
    9:  "Filter",
    10: "Air Supply",
    11: "Vacc Suit",
    12: "Vacc Suit",
    13: "None",   # Very Dense: may be habitable at altitude
    14: "None",   # Low: breathable in lowlands
    15: "Varies",
    16: "Vacc Suit",
    17: "Vacc Suit",
}

# Hydrographic descriptions (p.251), indexed by code 0-10
HYDROGRAPHIC_NAMES = {
    0:  "Desert world (0-5%)",
    1:  "Dry world (6-15%)",
    2:  "A few small seas (16-25%)",
    3:  "Small seas and oceans (26-35%)",
    4:  "Wet world (36-45%)",
    5:  "A large ocean (46-55%)",
    6:  "Large oceans (56-65%)",
    7:  "Earth-like world (66-75%)",
    8:  "Only a few islands and archipelagos (76-85%)",
    9:  "Almost entirely water (86-95%)",
    10: "Waterworld (96-100%)",
}

# Government type descriptions (p.252), indexed by code 0-15
GOVERNMENT_NAMES = {
    0:  "None",
    1:  "Company/Corporation",
    2:  "Participating Democracy",
    3:  "Self-Perpetuating Oligarchy",
    4:  "Representative Democracy",
    5:  "Feudal Technocracy",
    6:  "Captive Government",
    7:  "Balkanisation",
    8:  "Civil Service Bureaucracy",
    9:  "Impersonal Bureaucracy",
    10: "Charismatic Dictator",
    11: "Non-Charismatic Leader",
    12: "Charismatic Oligarchy",
    13: "Religious Dictatorship",
    14: "Religious Autocracy",
    15: "Totalitarian Oligarchy",
}

# Minimum Tech Level required to maintain the atmosphere (p.259)
# A world CAN have a lower TL but its population cannot sustain life support.
ATMOSPHERE_MIN_TL = {
    0:  8,
    1:  8,
    2:  5,
    3:  5,
    4:  3,
    5:  0,   # no special requirement
    6:  0,
    7:  3,
    8:  0,
    9:  3,
    10: 8,
    11: 9,
    12: 10,
    13: 5,
    14: 5,
    15: 8,
}

# Starport class table (p.257): roll 2D + population DM → class letter
# Indexed by the modified 2D roll result (clamped to 2-11+).
def starport_class_from_roll(modified_roll: int) -> str:
    """Return the starport class letter for a given modified 2D roll."""
    if modified_roll <= 2:
        return "X"
    if modified_roll <= 4:
        return "E"
    if modified_roll <= 6:
        return "D"
    if modified_roll <= 8:
        return "C"
    if modified_roll <= 10:
        return "B"
    return "A"

# Starport quality labels (p.257) — the Quality column value
STARPORT_QUALITY_LABEL = {
    "A": "Excellent",
    "B": "Good",
    "C": "Routine",
    "D": "Poor",
    "E": "Frontier",
    "X": "No Starport",
}

# Starport facility details (p.257) — fuel type and key facilities
STARPORT_FACILITY_DETAIL = {
    "A": "Refined fuel, full shipyard, repair",
    "B": "Refined fuel, spacecraft shipyard, repair",
    "C": "Unrefined fuel, small craft shipyard, repair",
    "D": "Unrefined fuel, limited repair",
    "E": "No fuel, no facilities",
    "X": "No facilities",
}

# Combined description for use in summary() and to_dict()
STARPORT_QUALITY = {
    code: f"{label} ({STARPORT_FACILITY_DETAIL[code]})"
    for code, label in STARPORT_QUALITY_LABEL.items()
}

# Tech Level DMs from various characteristics (p.258-259)
# Starport DMs
STARPORT_TL_DM = {"A": 6, "B": 4, "C": 2, "D": 1, "E": 1, "X": -4}

# Size DMs for TL
SIZE_TL_DM = {0: 2, 1: 2, 2: 1, 3: 1, 4: 1}   # codes ≥5 give +0

# Atmosphere DMs for TL
ATMOSPHERE_TL_DM = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1,
                    14: 1, 15: 1}  # codes 6-13 give +0

# Hydrographics DMs for TL
HYDROGRAPHICS_TL_DM = {9: 1, 10: 2}    # codes 0-8 give +0

# Population DMs for TL
POPULATION_TL_DM = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1,
                    8: 1, 9: 2, 10: 4}  # others give +0

# Government DMs for TL
GOVERNMENT_TL_DM = {0: 1, 5: 1, 13: -2, 14: -2}  # others give +0

# Temperature DMs by Atmosphere code (p.251)
TEMPERATURE_DM = {
    0:  0,  1:  0,                       # no modifier (but extreme swings)
    2: -2,  3: -2,
    4: -1,  5: -1,  14: -1,
    6:  0,  7:  0,
    8:  1,  9:  1,
    10: 2,  13: 2,  15: 2,
    11: 6,  12: 6,
    16: 0,  17: 0,
}

def temperature_category(modified_roll: int) -> str:
    """Return temperature category string from modified 2D roll (p.251)."""
    if modified_roll <= 2:
        return "Frozen"
    if modified_roll <= 4:
        return "Cold"
    if modified_roll <= 9:
        return "Temperate"
    if modified_roll <= 11:
        return "Hot"
    return "Boiling"


# ---------------------------------------------------------------------------
# WBH atmosphere detail (pp. 78-82)
# ---------------------------------------------------------------------------
#
# The Core Rulebook atmosphere code is a single digit (0-15).  The
# World Builder's Handbook expands each code with quantitative
# characteristics: pressure in bar, oxygen partial pressure, and
# atmospheric scale height.  This block adds those derived values
# without disturbing the canonical UWP code.

# Pressure spans (WBH p.79 "Atmosphere Codes" table).  Each entry is
# (minimum_bar, span_bar); actual pressure is minimum + span * variance
# where variance is a linear 0..1 value.  Codes without a defined span
# (0, A=10, B=11, C=12, F=15, G=16, H=17) are intentionally absent —
# vacuum, exotic, corrosive, insidious, unusual and gas-dwarf
# atmospheres do not have a single representative pressure.
ATMOSPHERE_PRESSURE_SPAN_BAR = {
    1:  (0.001, 0.089),  # Trace
    2:  (0.10,  0.32),   # Very Thin, Tainted
    3:  (0.10,  0.32),   # Very Thin
    4:  (0.43,  0.27),   # Thin, Tainted
    5:  (0.43,  0.27),   # Thin
    6:  (0.70,  0.79),   # Standard
    7:  (0.70,  0.79),   # Standard, Tainted
    8:  (1.50,  0.99),   # Dense
    9:  (1.50,  0.99),   # Dense, Tainted
    13: (2.50,  7.50),   # Very Dense
    14: (0.10,  0.32),   # Low
}

# Atmosphere codes for which oxygen partial pressure is meaningful
# (nitrogen-oxygen mixes per WBH p.80).  Trace (1) has a pressure but
# no defined oxygen content, so it is excluded.
_PPO_CODES = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 13, 14})

# Surface gravity in G by Size code, matching the dict already used
# in World.to_dict().  Used by the scale-height approximation.
SIZE_GRAVITY_G = {
    0:  0.00,
    1:  0.05,
    2:  0.15,
    3:  0.25,
    4:  0.35,
    5:  0.45,
    6:  0.70,
    7:  0.90,
    8:  1.00,
    9:  1.25,
    10: 1.40,
}


def _dice(num: int) -> int:
    """Sum *num* d6 rolls without clamping.

    ``roll()`` clamps negative results to zero, which is wrong for
    WBH formulas where a negative variance term is legitimate
    (e.g. the (2D-7)/100 term in the oxygen-fraction formula).
    """
    return sum(_rng.randint(1, 6) for _ in range(num))


def _atmosphere_pressure_bar(code: int) -> Optional[float]:
    """Return total atmospheric pressure in bar (WBH p.79).

    Rolls a linear variance across the code's defined span using
    ``((1D-1)*5 + (1D-1)) / 30`` per the WBH formula.  Returns ``None``
    for codes without a defined pressure span.
    """
    span = ATMOSPHERE_PRESSURE_SPAN_BAR.get(code)
    if span is None:
        return None
    minimum, width = span
    variance = (
        (_rng.randint(1, 6) - 1) * 5 + (_rng.randint(1, 6) - 1)
    ) / 30
    return round(minimum + width * variance, 3)


def _subtype_pressure_bar(
    min_bar: float,
    span_bar: Optional[float],
) -> Optional[float]:
    """Roll pressure within a subtype's defined range (WBH pp.85-86).

    Uses the same WBH variance formula as ``_atmosphere_pressure_bar()``.
    Returns ``None`` when ``span_bar`` is ``None`` (unbound pressure ≥ 10.0 bar).
    """
    if span_bar is None:
        return None
    variance = (
        (_rng.randint(1, 6) - 1) * 5 + (_rng.randint(1, 6) - 1)
    ) / 30
    return round(max(0.0, min_bar + span_bar * variance), 3)


def _oxygen_partial_pressure(
    code: int,
    total_pressure_bar: Optional[float],
    system_age_gyr: Optional[float] = None,
) -> Optional[float]:
    """Return oxygen partial pressure in bar (WBH p.80).

    Only meaningful for nitrogen-oxygen atmospheres (codes 2-9, D, E).
    The WBH oxygen-fraction formula is ``(1D + DMs)/20 + (2D-7)/100``
    with DM+1 when system age exceeds 4 Gyr.  If the rolled fraction
    is zero or negative it is rerolled as ``1D * 0.01`` per WBH.
    Returns ``None`` if the code is not breathable or pressure is
    unknown.
    """
    if code not in _PPO_CODES or total_pressure_bar is None:
        return None
    dm = 1 if (system_age_gyr is not None and system_age_gyr > 4.0) else 0
    fraction = (_rng.randint(1, 6) + dm) / 20 + (_dice(2) - 7) / 100
    if fraction <= 0:
        fraction = _rng.randint(1, 6) * 0.01
    return round(fraction * total_pressure_bar, 3)


def _scale_height_km(size: int, code: int) -> Optional[float]:
    """Return atmospheric scale height in km (WBH p.81).

    Uses the simple approximation ``8.5 / gravity`` from p.81, which
    assumes near-Terran temperature and gas mix.  Returns ``None`` for
    code 0 (no atmosphere) or sizes whose gravity is effectively zero.
    """
    if code == 0:
        return None
    gravity = SIZE_GRAVITY_G.get(size)
    if not gravity:
        return None
    return round(8.5 / gravity, 2)


# ---------------------------------------------------------------------------
# Exotic / Corrosive / Insidious atmosphere tables (WBH pp.85-87)
# ---------------------------------------------------------------------------

_EXOTIC_CODES = frozenset({10})
_CI_CODES     = frozenset({11, 12})   # Corrosive (B) and Insidious (C)

# Exotic Atmosphere Subtype table (WBH p.85).
# 2D+DM → (subtype_code, type_name, pressure_min_bar, pressure_span_bar)
# pressure_span_bar=None means pressure is unbound (≥ 10.0 bar).
_EXOTIC_SUBTYPE_TABLE: dict = {
    2:  ("2", "Very Thin, Irritant",                   0.10, 0.32),
    3:  ("3", "Very Thin",                              0.10, 0.32),
    4:  ("4", "Thin, Irritant",                         0.43, 0.27),
    5:  ("5", "Thin",                                   0.43, 0.27),
    6:  ("6", "Standard",                               0.70, 0.79),
    7:  ("7", "Standard, Irritant",                     0.70, 0.79),
    8:  ("8", "Dense",                                  1.50, 0.99),
    9:  ("9", "Dense, Irritant",                        1.50, 0.99),
    10: ("A", "Very Dense",                             2.50, 7.50),
    11: ("B", "Very Dense, Irritant",                   2.50, 7.50),
    12: ("C", "Very Dense, Occasionally Corrosive",     2.50, 7.50),
    13: ("A", "Very Dense",                             2.50, 7.50),
    14: ("B", "Very Dense, Irritant",                   2.50, 7.50),
}

# Corrosive and Insidious Atmosphere Subtype table (WBH p.86).
# 2D+DM → (subtype_code, type_name, pressure_min_bar, pressure_span_bar)
_CI_SUBTYPE_TABLE: dict = {
    1:  ("1", "Very Thin, Temperature 50K or less",            0.10, 0.32),
    2:  ("2", "Very Thin, Irritant",                           0.10, 0.32),
    3:  ("3", "Very Thin",                                     0.10, 0.32),
    4:  ("4", "Thin, Irritant",                                0.43, 0.27),
    5:  ("5", "Thin",                                          0.43, 0.27),
    6:  ("6", "Standard",                                      0.70, 0.79),
    7:  ("7", "Standard, Irritant",                            0.70, 0.79),
    8:  ("8", "Dense",                                         1.50, 0.99),
    9:  ("9", "Dense, Irritant",                               1.50, 0.99),
    10: ("A", "Very Dense",                                    2.50, 7.50),
    11: ("B", "Very Dense, Irritant",                          2.50, 7.50),
    12: ("C", "Extremely Dense",                              10.00, None),
    13: ("D", "Extremely Dense, Temperature 500K+",           10.00, None),
    14: ("E", "Extremely Dense, Temperature 500K+, Irritant", 10.00, None),
}

# ---------------------------------------------------------------------------
# Non-Habitable Zone (NHZ) Atmosphere tables (WBH pp.78-79)
# ---------------------------------------------------------------------------
# Each entry: (atm_code, base_exotic_key, irritant_exotic_key, star, dagger)
#   atm_code          — UWP atmosphere code result
#   base_exotic_key   — _EXOTIC_SUBTYPE_TABLE key when no irritant (code 10 only)
#   irritant_exotic_key — key used when irritant roll succeeds (code 10 only)
#   star              — True: roll 1D ≥4 to apply irritant_exotic_key
#   dagger            — True: DM+1 to irritant roll when hz_deviation ≤ -3.0
# Keys are 2D-7+Size roll results (clamped to 0; max reachable is 15).
# Entries 16–17 exist for theoretical completeness only.

_NHZ_HOT_A: dict = {   # HZCO ≤ -2.01
     0: ( 0, None, None, False, False),
     1: ( 0, None, None, False, False),
     2: ( 1, None, None, False, False),
     3: ( 1, None, None, False, False),
     4: (10,    3,    2,  True, False),
     5: (10,    5,    4,  True, False),
     6: (10,    6,    7,  True, False),
     7: (10,    8,    9,  True,  True),
     8: (10,   10,   11,  True,  True),
     9: (11, None, None, False, False),
    10: (11, None, None, False, False),
    11: (11, None, None, False, False),
    12: (12, None, None, False, False),
    13: (11, None, None, False, False),
    14: (12, None, None, False, False),
    15: (15, None, None, False, False),
    16: (16, None, None, False, False),
    17: (17, None, None, False, False),
}

_NHZ_HOT_B: dict = {   # HZCO -1.01 to -2.0
     0: ( 0, None, None, False, False),
     1: ( 1, None, None, False, False),
     2: (10,    2, None, False, False),
     3: (10,    3, None, False, False),
     4: (10,    4, None, False, False),
     5: (10,    5, None, False, False),
     6: (10,    6, None, False, False),
     7: (10,    7, None, False, False),
     8: (10,    8, None, False, False),
     9: (10,    9, None, False, False),
    10: (10,   10,   11,  True, False),
    11: (11, None, None, False, False),
    12: (12, None, None, False, False),
    13: (11, None, None, False, False),
    14: (12, None, None, False, False),
    15: (15, None, None, False, False),
    16: (16, None, None, False, False),
    17: (17, None, None, False, False),
}

_NHZ_COLD_A: dict = {   # HZCO +1.01 to +3.0
     0: ( 0, None, None, False, False),
     1: ( 1, None, None, False, False),
     2: ( 1, None, None, False, False),
     3: (10,    3,    2,  True, False),
     4: (10,    4, None, False, False),
     5: (10,    5, None, False, False),
     6: (10,    6, None, False, False),
     7: (10,    7, None, False, False),
     8: (10,    8, None, False, False),
     9: (10,    9, None, False, False),
    10: (10,   10,   11,  True, False),
    11: (11, None, None, False, False),
    12: (12, None, None, False, False),
    13: (13, None, None, False, False),
    14: (14, None, None, False, False),
    15: (15, None, None, False, False),
    16: (16, None, None, False, False),
    17: (17, None, None, False, False),
}

_NHZ_COLD_B: dict = {   # HZCO ≥ +3.01 — same as Cold A except 13→Gas Helium, 14→Gas Hydrogen
     0: ( 0, None, None, False, False),
     1: ( 1, None, None, False, False),
     2: ( 1, None, None, False, False),
     3: (10,    3,    2,  True, False),
     4: (10,    4, None, False, False),
     5: (10,    5, None, False, False),
     6: (10,    6, None, False, False),
     7: (10,    7, None, False, False),
     8: (10,    8, None, False, False),
     9: (10,    9, None, False, False),
    10: (10,   10,   11,  True, False),
    11: (11, None, None, False, False),
    12: (12, None, None, False, False),
    13: (16, None, None, False, False),
    14: (17, None, None, False, False),
    15: (15, None, None, False, False),
    16: (16, None, None, False, False),
    17: (17, None, None, False, False),
}

# Insidious Atmosphere Hazard table (WBH p.87).
# 2D+DM → (hazard_code, hazard_name)
_INSIDIOUS_HAZARD_TABLE: dict = {
    4:  ("B", "Biologic"),
    5:  ("R", "Radioactivity"),
    6:  ("G", "Gas Mix"),
    7:  ("G", "Gas Mix"),
    8:  ("T", "Temperature"),
    9:  ("G", "Gas Mix"),
    10: ("T", "Temperature"),
    11: ("R", "Radioactivity"),
    12: ("T", "Temperature"),
}

# Hazardous atmospheric gases (Taint=Y) from the Atmospheric Gas Composition
# table (WBH pp.88-89). Used when rolling a Gas Mix hazard.
_HAZARDOUS_GASES = [
    "Methane (CH₄)",
    "Ammonia (NH₃)",
    "Hydrofluoric Acid (HF)",
    "Sodium (Na)",
    "Carbon Monoxide (CO)",
    "Hydrogen Cyanide (HCN)",
    "Ethane (C₂H₆)",
    "Hydrochloric Acid (HCl)",
    "Fluorine (F₂)",
    "Carbon Dioxide (CO₂)",
    "Formamide (CH₃NO)",
    "Formic Acid (CH₂O₂)",
    "Sulphur Dioxide (SO₂)",
    "Chlorine (Cl₂)",
    "Sulphuric Acid (H₂SO₄)",
]

# ---------------------------------------------------------------------------
# Atmosphere Gas Mix tables (WBH pp.95+)
# ---------------------------------------------------------------------------

# Gas name → chemical code (from Atmospheric Gas Composition table, WBH p.87).
# "Silicates" and "Metal Vapours" are not in the p.87 table; codes are assigned.
_GAS_CODES: dict = {
    "Silicates":          "SO",
    "Metal Vapours":      "MV",
    "Hydrogen":           "H₂",
    "Helium":             "He",
    "Methane":            "CH₄",
    "Ammonia":            "NH₃",
    "Water Vapour":       "H₂O",
    "Hydrofluoric Acid":  "HF",
    "Neon":               "Ne",
    "Sodium":             "Na",
    "Nitrogen":           "N₂",
    "Carbon Monoxide":    "CO",
    "Hydrogen Cyanide":   "HCN",
    "Ethane":             "C₂H₆",
    "Hydrochloric Acid":  "HCl",
    "Fluorine":           "F₂",
    "Argon":              "Ar",
    "Carbon Dioxide":     "CO₂",
    "Formamide":          "CH₃NO",
    "Formic Acid":        "CH₂O₂",
    "Sulphur Dioxide":    "SO₂",
    "Chlorine":           "Cl₂",
    "Krypton":            "Kr",
    "Sulphuric Acid":     "H₂SO₄",
}

# Each table maps a 2D+DM result to {A: gas_name, B: gas_name, C: gas_name}
# where A=Exotic, B=Corrosive, C=Insidious.  Carbon Monoxide entries
# (CO*) are replaced by _roll_single_gas() per the CO* footnote.

# Boiling Atmosphere Gas Mix — HZCO ≤ -2.01 (453 K+)
_GAS_MIX_BOILING_VH: dict = {
    -2: {"A": "Silicates",       "B": "Silicates",       "C": "Metal Vapours"},
    -1: {"A": "Sodium",          "B": "Sodium",          "C": "Silicates"},
     0: {"A": "Krypton",         "B": "Krypton",         "C": "Sodium"},
     1: {"A": "Argon",           "B": "Argon",           "C": "Sulphuric Acid"},
     2: {"A": "Sulphur Dioxide", "B": "Sulphur Dioxide", "C": "Hydrochloric Acid"},
     3: {"A": "Carbon Monoxide", "B": "Hydrogen Cyanide","C": "Chlorine"},
     4: {"A": "Carbon Dioxide",  "B": "Formamide",       "C": "Fluorine"},
     5: {"A": "Nitrogen",        "B": "Carbon Dioxide",  "C": "Formic Acid"},
     6: {"A": "Carbon Dioxide",  "B": "Nitrogen",        "C": "Water Vapour"},
     7: {"A": "Nitrogen",        "B": "Carbon Dioxide",  "C": "Nitrogen"},
     8: {"A": "Water Vapour",    "B": "Sulphur Dioxide", "C": "Carbon Dioxide"},
     9: {"A": "Sulphur Dioxide", "B": "Water Vapour",    "C": "Sulphur Dioxide"},
    10: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Hydrogen Cyanide"},
    11: {"A": "Methane",         "B": "Ammonia",         "C": "Ammonia"},
    12: {"A": "Water Vapour",    "B": "Ammonia",         "C": "Hydrofluoric Acid"},
    13: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
}

# Boiling Atmosphere Gas Mix — HZCO -1.01 to -2.0 (353-453 K)
_GAS_MIX_BOILING_H: dict = {
     1: {"A": "Krypton",         "B": "Argon",           "C": "Hydrochloric Acid"},
     2: {"A": "Argon",           "B": "Sulphur Dioxide", "C": "Chlorine"},
     3: {"A": "Sulphur Dioxide", "B": "Hydrogen Cyanide","C": "Fluorine"},
     4: {"A": "Ethane",          "B": "Ethane",          "C": "Formic Acid"},
     5: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Water Vapour"},
     6: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     7: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Carbon Dioxide"},
     8: {"A": "Nitrogen",        "B": "Sulphur Dioxide", "C": "Sulphur Dioxide"},
     9: {"A": "Water Vapour",    "B": "Water Vapour",    "C": "Hydrogen Cyanide"},
    10: {"A": "Sulphur Dioxide", "B": "Nitrogen",        "C": "Ammonia"},
    11: {"A": "Methane",         "B": "Ammonia",         "C": "Methane"},
    12: {"A": "Neon",            "B": "Ammonia",         "C": "Hydrofluoric Acid"},
    13: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
}

# Hot Atmosphere Gas Mix (303-353 K)
_GAS_MIX_HOT: dict = {
     1: {"A": "Krypton",         "B": "Argon",           "C": "Hydrochloric Acid"},
     2: {"A": "Argon",           "B": "Sulphur Dioxide", "C": "Chlorine"},
     3: {"A": "Sulphur Dioxide", "B": "Hydrogen Cyanide","C": "Fluorine"},
     4: {"A": "Ethane",          "B": "Ethane",          "C": "Sulphur Dioxide"},
     5: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Carbon Monoxide"},
     6: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     7: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Carbon Dioxide"},
     8: {"A": "Nitrogen",        "B": "Sulphur Dioxide", "C": "Ethane"},
     9: {"A": "Carbon Monoxide", "B": "Carbon Monoxide", "C": "Hydrogen Cyanide"},
    10: {"A": "Sulphur Dioxide", "B": "Nitrogen",        "C": "Ammonia"},
    11: {"A": "Methane",         "B": "Ammonia",         "C": "Methane"},
    12: {"A": "Neon",            "B": "Ammonia",         "C": "Hydrofluoric Acid"},
    13: {"A": "Methane",         "B": "Methane",         "C": "Helium"},
}

# Temperate Atmosphere Gas Mix (273-303 K)
_GAS_MIX_TEMPERATE: dict = {
     1: {"A": "Krypton",         "B": "Krypton",         "C": "Argon"},
     2: {"A": "Argon",           "B": "Chlorine",        "C": "Chlorine"},
     3: {"A": "Sulphur Dioxide", "B": "Argon",           "C": "Fluorine"},
     4: {"A": "Nitrogen",        "B": "Sulphur Dioxide", "C": "Sulphur Dioxide"},
     5: {"A": "Carbon Monoxide", "B": "Carbon Monoxide", "C": "Carbon Monoxide"},
     6: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     7: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Carbon Dioxide"},
     8: {"A": "Ethane",          "B": "Ethane",          "C": "Ethane"},
     9: {"A": "Nitrogen",        "B": "Ammonia",         "C": "Ammonia"},
    10: {"A": "Neon",            "B": "Ammonia",         "C": "Ammonia"},
    11: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
    12: {"A": "Methane",         "B": "Helium",          "C": "Helium"},
    13: {"A": "Helium",          "B": "Hydrogen",        "C": "Hydrogen"},
}

# Cold Atmosphere Gas Mix (223-273 K)
_GAS_MIX_COLD: dict = {
     1: {"A": "Krypton",         "B": "Krypton",         "C": "Argon"},
     2: {"A": "Argon",           "B": "Chlorine",        "C": "Chlorine"},
     3: {"A": "Ethane",          "B": "Argon",           "C": "Fluorine"},
     4: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Ethane"},
     5: {"A": "Carbon Monoxide", "B": "Carbon Monoxide", "C": "Carbon Monoxide"},
     6: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     7: {"A": "Carbon Dioxide",  "B": "Carbon Dioxide",  "C": "Carbon Dioxide"},
     8: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     9: {"A": "Ethane",          "B": "Ethane",          "C": "Ethane"},
    10: {"A": "Methane",         "B": "Ammonia",         "C": "Ammonia"},
    11: {"A": "Neon",            "B": "Methane",         "C": "Methane"},
    12: {"A": "Methane",         "B": "Helium",          "C": "Helium"},
    13: {"A": "Helium",          "B": "Hydrogen",        "C": "Hydrogen"},
}

# Frozen Atmosphere Gas Mix — HZCO +1.01 to +3.0 (123-223 K)
_GAS_MIX_FROZEN_M: dict = {
     1: {"A": "Krypton",         "B": "Krypton",         "C": "Krypton"},
     2: {"A": "Argon",           "B": "Argon",           "C": "Argon"},
     3: {"A": "Argon",           "B": "Argon",           "C": "Fluorine"},
     4: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     5: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     6: {"A": "Carbon Monoxide", "B": "Carbon Monoxide", "C": "Carbon Monoxide"},
     7: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     8: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
     9: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
    10: {"A": "Methane",         "B": "Neon",            "C": "Neon"},
    11: {"A": "Neon",            "B": "Methane",         "C": "Helium"},
    12: {"A": "Methane",         "B": "Helium",          "C": "Hydrogen"},
    13: {"A": "Helium",          "B": "Hydrogen",        "C": "Hydrogen"},
}

# Frozen Atmosphere Gas Mix — HZCO +3.01+ (below 123 K)
_GAS_MIX_FROZEN_D: dict = {
     1: {"A": "Krypton",         "B": "Krypton",         "C": "Krypton"},
     2: {"A": "Argon",           "B": "Argon",           "C": "Argon"},
     3: {"A": "Argon",           "B": "Argon",           "C": "Fluorine"},
     4: {"A": "Methane",         "B": "Methane",         "C": "Methane"},
     5: {"A": "Carbon Monoxide", "B": "Carbon Monoxide", "C": "Carbon Monoxide"},
     6: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     7: {"A": "Nitrogen",        "B": "Nitrogen",        "C": "Nitrogen"},
     8: {"A": "Neon",            "B": "Neon",            "C": "Neon"},
     9: {"A": "Helium",          "B": "Helium",          "C": "Helium"},
    10: {"A": "Helium",          "B": "Helium",          "C": "Helium"},
    11: {"A": "Hydrogen",        "B": "Hydrogen",        "C": "Hydrogen"},
    12: {"A": "Hydrogen",        "B": "Hydrogen",        "C": "Hydrogen"},
    13: {"A": "Hydrogen",        "B": "Hydrogen",        "C": "Hydrogen"},
}

# ---------------------------------------------------------------------------
# Atmosphere taint tables (WBH pp.82-85)
# ---------------------------------------------------------------------------

# Atmosphere codes that always carry a taint (per UWP definition).
_TAINTED_CODES = frozenset({2, 4, 7, 9})

# Single-char profile codes that identify O2-driven subtypes.
_O2_TAINT_CODES = frozenset({"L", "H"})

# DM applied to the subtype 2D roll by atmosphere code (others: 0).
_TAINT_SUBTYPE_DM = {4: -2, 9: 2}

# 2D+DM → (subtype name, single-char profile code).
# Result 10: Particulates + roll again (needs_second_roll = True).
# Biologic (B): forces biomass_rating ≥ 1 via generate_biomass_rating() (issue #28).
_TAINT_SUBTYPE_TABLE = {
    2:  ("Low Oxygen",        "L"),
    3:  ("Radioactivity",     "R"),
    4:  ("Biologic",          "B"),
    5:  ("Gas Mix",           "G"),
    6:  ("Particulates",      "P"),
    7:  ("Gas Mix",           "G"),
    8:  ("Sulphur Compounds", "S"),
    9:  ("Biologic",          "B"),
    10: ("Particulates",      "P"),   # result 10: Particulates + roll again
    11: ("Radioactivity",     "R"),
    12: ("High Oxygen",       "H"),
}

# Severity code (1-9) → descriptive name (WBH p.83).
_TAINT_SEVERITY_TABLE = {
    1: "Trivial irritant",
    2: "Surmountable irritant",
    3: "Minor irritant",
    4: "Major irritant",
    5: "Serious irritant",
    6: "Hazardous irritant",
    7: "Long term lethal: DM-2 to aging rolls",
    8: "Inevitably lethal: death within 1D days",
    9: "Rapidly lethal: death within 1D minutes",
}

# Persistence code (2-9) → descriptive name (WBH p.83).
_TAINT_PERSISTENCE_TABLE = {
    2: "Occasional and brief",
    3: "Occasional and lingering",
    4: "Irregular",
    5: "Fluctuating",
    6: "Varying: 2D daily on 6-, reduce severity 1D h",
    7: "Varying: 2D daily on 4-, reduce severity 1D h",
    8: "Varying: 2D daily on 2, reduce severity 1D h",
    9: "Constant",
}


def _taint_severity_code(raw: int) -> int:
    """Map a raw 2D+DM roll to a severity code 1–9 (WBH p.83)."""
    return max(1, min(9, raw - 3))


def _taint_persistence_code(raw: int) -> int:
    """Map a raw 2D+DM roll to a persistence code 2–9 (WBH p.83)."""
    return max(2, min(9, raw))


def _roll_single_taint(atm_code: int, ppo: Optional[float] = None) -> tuple:
    """Roll one taint for a tainted atmosphere (WBH pp.82-83).

    Returns ``(Taint, needs_second_roll)``.  ``needs_second_roll`` is
    ``True`` only when the subtype roll is 10 (Particulates and roll again).

    ``ppo`` constrains H/L subtypes to physically valid ranges (issue #55):
    High Oxygen (H) is only accepted when ppo > 0.5 bar; Low Oxygen (L)
    is only accepted when ppo < 0.1 bar.  When ``ppo`` is ``None`` the
    constraint is not applied (backwards-compatible default).

    Severity and persistence DMs:
    - L/H subtypes: +4 to severity, +4 to persistence (or +6 if
      severity code ≥ 8).
    """
    dm = _TAINT_SUBTYPE_DM.get(atm_code, 0)
    while True:
        raw_sub = max(2, min(12, roll(2) + dm))
        subtype_name, subtype_code = _TAINT_SUBTYPE_TABLE[raw_sub]
        if subtype_code == "H" and ppo is not None and ppo <= 0.5:
            continue
        if subtype_code == "L" and ppo is not None and ppo >= 0.1:
            continue
        break
    needs_second = raw_sub == 10

    sev_dm = 4 if subtype_code in _O2_TAINT_CODES else 0
    sev_code = _taint_severity_code(roll(2) + sev_dm)

    per_dm = (6 if sev_code >= 8 else 4) if subtype_code in _O2_TAINT_CODES else 0
    per_code = _taint_persistence_code(roll(2) + per_dm)

    return Taint(
        subtype=subtype_name,
        subtype_code=subtype_code,
        severity_code=sev_code,
        severity=_TAINT_SEVERITY_TABLE[sev_code],
        persistence_code=per_code,
        persistence=_TAINT_PERSISTENCE_TABLE[per_code],
    ), needs_second


@dataclass
class Taint:
    """One atmosphere taint (WBH pp.82-85).

    Stores both the human-readable names and the compact profile codes
    used in the WBH p.82 atmosphere profile string.
    """
    subtype:          str   # descriptive name, e.g. "Particulates"
    subtype_code:     str   # single-char profile code, e.g. "P"
    severity_code:    int   # 1–9
    severity:         str   # e.g. "Major irritant"
    persistence_code: int   # 2–9
    persistence:      str   # e.g. "Irregular"

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict."""
        return {
            "subtype":          self.subtype,
            "subtype_code":     self.subtype_code,
            "severity_code":    self.severity_code,
            "severity":         self.severity,
            "persistence_code": self.persistence_code,
            "persistence":      self.persistence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Taint":
        """Reconstruct a Taint from a dict produced by to_dict()."""
        return cls(
            subtype=str(d["subtype"]),
            subtype_code=str(d.get("subtype_code", "")),
            severity_code=int(d["severity_code"]),
            severity=str(d["severity"]),
            persistence_code=int(d["persistence_code"]),
            persistence=str(d["persistence"]),
        )


@dataclass
class InsidiousHazard:
    """One hazard present in an insidious atmosphere (WBH p.87).

    ``gases`` is populated only for Gas Mix hazards; it lists randomly-
    selected hazardous atmospheric components from the Atmospheric Gas
    Composition table (WBH pp.88-89).
    """
    hazard_code: str
    hazard:      str
    gases:       list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict.  ``gases`` is omitted when empty."""
        d: dict = {"hazard_code": self.hazard_code, "hazard": self.hazard}
        if self.gases:
            d["gases"] = self.gases
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "InsidiousHazard":
        """Reconstruct an InsidiousHazard from a dict produced by to_dict()."""
        return cls(
            hazard_code=str(d["hazard_code"]),
            hazard=str(d["hazard"]),
            gases=list(d.get("gases", [])),
        )


def _roll_exotic_subtype(
    size: int,
    hz_deviation: Optional[float],
) -> tuple:
    """Roll and look up an Exotic Atmosphere subtype (WBH p.85).

    Returns ``(subtype_code, subtype_name, pressure_bar_or_None)``.
    DMs: Size 2–4 = DM-2; Orbit < HZCO-1 (hz_deviation < -1.0) = DM-2;
    Orbit > HZCO+2 (hz_deviation > +2.0) = DM+2.
    """
    dm = 0
    if 2 <= size <= 4:
        dm -= 2
    if hz_deviation is not None:
        if hz_deviation < -1.0:
            dm -= 2
        elif hz_deviation > 2.0:
            dm += 2
    raw = max(2, min(14, _dice(2) + dm))
    s_code, s_name, min_bar, span_bar = _EXOTIC_SUBTYPE_TABLE[raw]
    return s_code, s_name, _subtype_pressure_bar(min_bar, span_bar)


def _roll_ci_subtype(
    atm_code: int,
    size: int,
    hz_deviation: Optional[float],
) -> tuple:
    """Roll and look up a Corrosive/Insidious Atmosphere subtype (WBH p.86).

    Returns ``(subtype_code, subtype_name, pressure_bar_or_None)``.
    DMs: Size 2–4 = DM-3; Size 8+ = DM+2; Orbit < HZCO-1 = DM+4;
    Orbit > HZCO+2 = DM-2; Insidious (code 12) = DM+2.
    """
    dm = 0
    if 2 <= size <= 4:
        dm -= 3
    elif size >= 8:
        dm += 2
    if hz_deviation is not None:
        if hz_deviation < -1.0:
            dm += 4
        elif hz_deviation > 2.0:
            dm -= 2
    if atm_code == 12:
        dm += 2
    raw = max(1, min(14, _dice(2) + dm))
    s_code, s_name, min_bar, span_bar = _CI_SUBTYPE_TABLE[raw]
    return s_code, s_name, _subtype_pressure_bar(min_bar, span_bar)


def _roll_insidious_hazard(subtype_code: str) -> list:
    """Roll the Insidious Atmosphere Hazard table (WBH p.87).

    Returns a list of ``InsidiousHazard`` objects.  Subtype D or E
    automatically adds a Temperature hazard before the table roll.
    Subtype C/D/E applies DM+2 to the hazard roll.  Gas Mix hazards
    randomly select 1–3 components from ``_HAZARDOUS_GASES``.
    """
    hazards: list = []
    dm = 2 if subtype_code in ("C", "D", "E") else 0
    if subtype_code in ("D", "E"):
        hazards.append(InsidiousHazard(hazard_code="T", hazard="Temperature"))
    raw = max(4, min(12, _dice(2) + dm))
    h_code, h_name = _INSIDIOUS_HAZARD_TABLE[raw]
    gases: list = []
    if h_code == "G":
        n_roll = _dice(1)
        n = 1 if n_roll <= 2 else (2 if n_roll <= 4 else 3)
        gases = _rng.sample(_HAZARDOUS_GASES, n)
    hazards.append(InsidiousHazard(hazard_code=h_code, hazard=h_name, gases=gases))
    return hazards


@dataclass
class GasMixComponent:
    """One gas component in an atmosphere's gas mix (WBH pp.95+).

    ``percentage`` is the whole-number percentage of this gas in the
    atmosphere (e.g. 75 for 75%).  It is omitted when not determined.
    """
    gas_name:   str
    gas_code:   str
    percentage: Optional[int] = None

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict."""
        d: dict = {"gas_name": self.gas_name, "gas_code": self.gas_code}
        if self.percentage is not None:
            d["percentage"] = self.percentage
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GasMixComponent":
        """Reconstruct a GasMixComponent from a dict produced by to_dict()."""
        return cls(
            gas_name=str(d["gas_name"]),
            gas_code=str(d["gas_code"]),
            percentage=int(d["percentage"]) if d.get("percentage") is not None else None,
        )


@dataclass
class AtmosphereDetail:  # pylint: disable=too-many-instance-attributes
    """Quantitative atmosphere characteristics (WBH pp. 78-95+).

    Supplements the UWP single-digit atmosphere code with pressure,
    oxygen partial pressure, scale height, taint detail, and (for
    exotic/corrosive/insidious codes) the rolled subtype, hazards,
    and gas mix components.
    Each field is optional because the relevant rule does not apply
    to every code.
    """
    pressure_bar:            Optional[float] = None
    oxygen_partial_pressure: Optional[float] = None
    scale_height_km:         Optional[float] = None
    taints:                  list = field(default_factory=list)
    subtype_code:            Optional[str]   = None
    subtype_name:            Optional[str]   = None
    hazards:                 list = field(default_factory=list)
    gas_mix:                 list = field(default_factory=list)
    min_safe_altitude_km:    Optional[float] = None
    no_safe_altitude:        bool = field(default=False)
    unusual_subtypes:        list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the detail as a JSON-friendly dict.

        Numeric fields are omitted when ``None``; list fields are omitted
        when empty.  Both conventions keep the JSON compact for worlds
        where the rule does not apply.
        """
        out: dict = {}
        if self.subtype_code is not None:
            out["subtype_code"] = self.subtype_code
        if self.subtype_name is not None:
            out["subtype_name"] = self.subtype_name
        if self.pressure_bar is not None:
            out["pressure_bar"] = self.pressure_bar
        if self.oxygen_partial_pressure is not None:
            out["oxygen_partial_pressure_bar"] = self.oxygen_partial_pressure
        if self.scale_height_km is not None:
            out["scale_height_km"] = self.scale_height_km
        if self.taints:
            out["taints"] = [t.to_dict() for t in self.taints]
        if self.hazards:
            out["hazards"] = [h.to_dict() for h in self.hazards]
        if self.gas_mix:
            out["gas_mix"] = [c.to_dict() for c in self.gas_mix]
        if self.min_safe_altitude_km is not None:
            out["min_safe_altitude_km"] = self.min_safe_altitude_km
        if self.no_safe_altitude:
            out["no_safe_altitude"] = True
        if self.unusual_subtypes:
            out["unusual_subtypes"] = [s.to_dict() for s in self.unusual_subtypes]
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "AtmosphereDetail":
        """Reconstruct an AtmosphereDetail from a dict produced by to_dict()."""
        def _f(k):
            return float(d[k]) if d.get(k) is not None else None
        return cls(
            pressure_bar=_f("pressure_bar"),
            oxygen_partial_pressure=_f("oxygen_partial_pressure_bar"),
            scale_height_km=_f("scale_height_km"),
            taints=[Taint.from_dict(t) for t in d.get("taints", [])],
            subtype_code=d.get("subtype_code"),
            subtype_name=d.get("subtype_name"),
            hazards=[InsidiousHazard.from_dict(h) for h in d.get("hazards", [])],
            gas_mix=[GasMixComponent.from_dict(c) for c in d.get("gas_mix", [])],
            min_safe_altitude_km=_f("min_safe_altitude_km"),
            no_safe_altitude=bool(d.get("no_safe_altitude", False)),
            unusual_subtypes=[UnusualSubtype.from_dict(s) for s in d.get("unusual_subtypes", [])],
        )


def _select_gas_mix_table(  # pylint: disable=too-many-return-statements
    temperature: str,
    hz_deviation: Optional[float],
) -> tuple:
    """Select the gas mix table and generation parameters for an atmosphere.

    Returns ``(table, min_result, max_result, size_lo_dm, extra_dm, co_sub)``
    where ``size_lo_dm`` is the DM for size 1–7 (always DM+1 for size A+),
    ``extra_dm`` is a fixed additional DM (e.g. estimated temperature
    sub-range), and ``co_sub`` is the CO* substitute gas name when the
    world has water hydrographics.

    Boiling very-hot (~600 K estimated) falls below the 700 K threshold so
    no extra temperature DM is applied.  Frozen deep (~80 K estimated) is
    in the 70–100 K band so DM+3 is applied as a fixed estimate.  A GitHub
    issue tracks refining these DMs once mean temperature in K is available.
    """
    if temperature == "Boiling" and hz_deviation is not None and hz_deviation <= -2.01:
        return (_GAS_MIX_BOILING_VH, -2, 13, -1, 0, "Carbon Dioxide")
    if temperature == "Boiling":
        return (_GAS_MIX_BOILING_H, 1, 13, -1, 0, "Carbon Dioxide")
    if temperature == "Hot":
        return (_GAS_MIX_HOT, 1, 13, -1, 0, "Carbon Dioxide")
    if temperature == "Cold":
        return (_GAS_MIX_COLD, 1, 13, -1, 0, "Carbon Dioxide")
    if temperature == "Frozen" and hz_deviation is not None and hz_deviation >= 3.01:
        return (_GAS_MIX_FROZEN_D, 1, 13, -3, 3, "Nitrogen")
    if temperature == "Frozen":
        return (_GAS_MIX_FROZEN_M, 1, 13, -1, 0, "Nitrogen")
    return (_GAS_MIX_TEMPERATE, 1, 13, -1, 0, "Carbon Dioxide")


def _roll_single_gas(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    table: dict,
    col: str,
    min_result: int,
    max_result: int,
    size: int,
    size_lo_dm: int,
    extra_dm: int,
    hydro: int,
    co_sub: str,
) -> tuple:
    """Roll on one column of a gas mix table and return ``(gas_name, gas_code)``.

    Applies size DMs (``size_lo_dm`` for size 1–7, DM+1 for size A+) and
    ``extra_dm``, then clamps to ``[min_result, max_result]``.  Carbon
    Monoxide results are replaced with ``co_sub`` when ``hydro > 0``
    (WBH CO* footnote).
    """
    dm = extra_dm
    if 1 <= size <= 7:
        dm += size_lo_dm
    elif size >= 10:
        dm += 1
    result = max(min_result, min(max_result, _dice(2) + dm))
    gas_name = table[result][col]
    if gas_name == "Carbon Monoxide" and hydro > 0:
        gas_name = co_sub
    return gas_name, _GAS_CODES.get(gas_name, gas_name)


def _roll_gas_mix(  # pylint: disable=too-many-locals
    atm_code: int,
    size: int,
    temperature: str,
    hz_deviation: Optional[float],
    hydro: int,
) -> list:
    """Roll primary and secondary gas components for an A/B/C atmosphere.

    Returns a list of up to two ``GasMixComponent`` entries.  Primary
    percentage is ``(_dice(1) + 4) × 10``, capped at 100.  Secondary
    percentage is ``(_dice(1) + 4) × 10`` of the remainder.  When both
    rolls yield the same gas the percentages are summed into one entry.
    """
    col = {10: "A", 11: "B", 12: "C"}[atm_code]
    table, min_r, max_r, size_lo_dm, extra_dm, co_sub = _select_gas_mix_table(
        temperature, hz_deviation
    )
    prim_name, prim_code = _roll_single_gas(
        table, col, min_r, max_r, size, size_lo_dm, extra_dm, hydro, co_sub
    )
    prim_pct = min(100, (_dice(1) + 4) * 10)
    sec_name, sec_code = _roll_single_gas(
        table, col, min_r, max_r, size, size_lo_dm, extra_dm, hydro, co_sub
    )
    sec_pct = (_dice(1) + 4) * 10 * (100 - prim_pct) // 100
    if prim_name == sec_name:
        return [GasMixComponent(
            gas_name=prim_name, gas_code=prim_code,
            percentage=min(100, prim_pct + sec_pct),
        )]
    components: list = [GasMixComponent(
        gas_name=prim_name, gas_code=prim_code, percentage=prim_pct,
    )]
    if sec_pct > 0:
        components.append(GasMixComponent(
            gas_name=sec_name, gas_code=sec_code, percentage=sec_pct,
        ))
    return components


def _compute_very_dense_altitude(
    pressure_bar: float, ppo: float, scale_height_km: float,
) -> tuple:
    """Return ``(min_safe_altitude_km, no_safe_altitude)`` for a Very Dense (D) atmosphere.

    Habitable locations require N₂ < 2.0 bar AND O₂ < 0.5 bar.
    Bad ratio = max(ppo / 0.5, n2 / 2.0).  Min safe altitude = ln(bad_ratio) × H.
    If O₂ at that altitude < 0.1 bar no breathable level exists.
    """
    n2 = pressure_bar - ppo
    bad_ratio = max(ppo / 0.5, n2 / 2.0)
    if bad_ratio <= 1.0:
        return 0.0, False
    min_alt = math.log(bad_ratio) * scale_height_km
    if ppo / bad_ratio < 0.1:
        return None, True
    return round(min_alt, 1), False


def _compute_low_altitude(
    pressure_bar: float, ppo: float, scale_height_km: float,
) -> tuple:
    """Return ``(safe_depth_km as negative float, no_safe_altitude)`` for a Low (E) atmosphere.

    Surface O₂ < 0.1 bar; must descend into depressions.
    Low bad ratio = 0.1 / ppo.  Safe depth = ln(low_bad_ratio) × H, stored negative.
    If N₂ at that depth > 2.0 bar no breathable level exists.
    """
    if ppo <= 0:
        return None, True
    low_bad_ratio = 0.1 / ppo
    safe_depth = math.log(low_bad_ratio) * scale_height_km
    n2_at_depth = (pressure_bar - ppo) * low_bad_ratio
    if n2_at_depth > 2.0:
        return None, True
    return -round(safe_depth, 1), False


def generate_atmosphere_detail(  # pylint: disable=too-many-locals,too-many-branches,too-many-positional-arguments,too-many-arguments
    code: int,
    size: int,
    system_age_gyr: Optional[float] = None,
    temperature: Optional[str] = None,  # pylint: disable=unused-argument
    hz_deviation: Optional[float] = None,
    exotic_key_override: Optional[int] = None,
) -> AtmosphereDetail:
    """Generate quantitative atmosphere characteristics for a world.

    Combines the WBH pp.79-93 helpers into a single ``AtmosphereDetail``.
    Safe to call for any atmosphere code: fields that do not apply to
    the given code are left as ``None``.

    ``hz_deviation`` drives the orbit-position DMs on the exotic and
    corrosive/insidious subtype tables.  Pass ``orbit.hz_deviation`` from
    the orbit slot; standalone worlds with no orbit pass ``None``.
    ``temperature`` is reserved for gas composition (Phase 4).

    ``exotic_key_override`` bypasses the normal exotic subtype roll when
    set; the value is used as a direct key into ``_EXOTIC_SUBTYPE_TABLE``.
    Used by NHZ atmosphere generation to pass a pre-determined subtype.
    """
    if code in (16, 17):
        return AtmosphereDetail()

    subtype_code: Optional[str] = None
    subtype_name: Optional[str] = None
    hazards: list = []

    if code in _EXOTIC_CODES:
        if exotic_key_override is not None:
            s_code, s_name, min_bar, span_bar = _EXOTIC_SUBTYPE_TABLE[exotic_key_override]
            subtype_code, subtype_name = s_code, s_name
            pressure = _subtype_pressure_bar(min_bar, span_bar)
        else:
            subtype_code, subtype_name, pressure = _roll_exotic_subtype(
                size, hz_deviation
            )
    elif code in _CI_CODES:
        subtype_code, subtype_name, pressure = _roll_ci_subtype(
            code, size, hz_deviation
        )
        if code == 12 and subtype_code is not None:
            hazards = _roll_insidious_hazard(subtype_code)
    else:
        pressure = _atmosphere_pressure_bar(code)

    ppo = _oxygen_partial_pressure(code, pressure, system_age_gyr)

    taints: list = []
    if code in _TAINTED_CODES:
        taint, needs_second = _roll_single_taint(code, ppo)
        taints.append(taint)
        if needs_second:
            second, _ = _roll_single_taint(code, ppo)
            taints.append(second)
    if code in (13, 14) and _rng.randint(1, 6) >= 4:
        taint, needs_second = _roll_single_taint(code, ppo)
        taints.append(taint)
        if needs_second:
            second, _ = _roll_single_taint(code, ppo)
            taints.append(second)

    scale = _scale_height_km(size, code)

    min_safe_alt: Optional[float] = None
    no_safe_alt: bool = False
    if code == 13 and pressure is not None and ppo is not None and scale is not None:
        min_safe_alt, no_safe_alt = _compute_very_dense_altitude(pressure, ppo, scale)
    elif code == 14 and pressure is not None and ppo is not None and scale is not None:
        min_safe_alt, no_safe_alt = _compute_low_altitude(pressure, ppo, scale)

    return AtmosphereDetail(
        pressure_bar=pressure,
        oxygen_partial_pressure=ppo,
        scale_height_km=scale,
        taints=taints,
        subtype_code=subtype_code,
        subtype_name=subtype_name,
        hazards=hazards,
        min_safe_altitude_km=min_safe_alt,
        no_safe_altitude=no_safe_alt,
    )


def generate_gas_mix(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    detail: AtmosphereDetail,
    atm_code: int,
    size: int,
    temperature: str,
    hz_deviation: Optional[float],
    hydro: int,
) -> None:
    """Populate ``detail.gas_mix`` for Exotic/Corrosive/Insidious atmospheres.

    No-op for codes outside {10, 11, 12}.  Call this after
    ``generate_hydrographics()`` so the CO* substitution rule can check
    whether the world has water hydrographics.
    """
    if atm_code not in _EXOTIC_CODES | _CI_CODES:
        return
    detail.gas_mix = _roll_gas_mix(atm_code, size, temperature, hz_deviation, hydro)


# ---------------------------------------------------------------------------
# Unusual atmosphere subtype generation (WBH pp.92-93, code 15 / F)
# ---------------------------------------------------------------------------

@dataclass
class UnusualSubtype:
    """One subtype of an Unusual (F) atmosphere (WBH pp.92-93)."""
    subtype_code: str   # "1"–"9", "A", "F"; "" only for the Combination sentinel
    subtype_name: str
    description:  str

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict."""
        return {
            "subtype_code": self.subtype_code,
            "subtype_name": self.subtype_name,
            "description":  self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UnusualSubtype":
        """Reconstruct an UnusualSubtype from a dict produced by to_dict()."""
        return cls(
            subtype_code=str(d["subtype_code"]),
            subtype_name=str(d["subtype_name"]),
            description=str(d["description"]),
        )


# D26 table (roll _rng.randint(1,2)*10 + _rng.randint(1,6) → 11–26).
# Entries: (subtype_code, subtype_name, atmospheric_conditions_description)
_UNUSUAL_SUBTYPE_TABLE: dict = {
    11: ("1", "Dense, Extreme",
         "Density between 10 and 100 bar, possibly with free oxygen"),
    12: ("2", "Dense, Very Extreme",
         "Density between 100 and 1,000 bar, possibly with free oxygen"),
    13: ("3", "Dense, Crushing",
         "Density above 1,000 bar; surface may be unreachable or indistinct"),
    14: ("4", "Ellipsoid",
         "Tidal forces or fast rotation elongate one axis; "
         "pressure may range from near vacuum to very dense"),
    15: ("5", "High Radiation",
         "Internal or external factors bombard the world with constant high radiation"),
    16: ("6", "Layered",
         "Different altitudes have different gas compositions"),
    21: ("7", "Panthalassic",
         "A world ocean hundreds of km deep; pressure at least standard, often very dense"),
    22: ("8", "Steam",
         "Water vapor merges with oceans; very dense or above pressures"),
    23: ("9", "Variable Pressure",
         "Tides or storms cause large variations in atmospheric pressure"),
    24: ("A", "Variable Composition",
         "Composition varies with seasons, lifeform lifecycles, or other factors"),
    25: ("",  "Combination",          "Roll two compatible types"),
    26: ("F", "Other",                "Something else entirely"),
}


def _d26() -> int:
    """Roll D26 (1D2 × 10 + 1D6), giving results 11–26."""
    return _rng.randint(1, 2) * 10 + _rng.randint(1, 6)


def _roll_unusual_subtype(
    size: int,
    hydro: int,
    allow_combination: bool = True,
) -> UnusualSubtype:
    """Roll one Unusual atmosphere subtype, rerolling if prerequisites not met.

    Prerequisites (WBH pp.92-93):
    - Layered (D26=16):      SIZE_GRAVITY_G[size] > 1.2  →  size ≥ 9
    - Panthalassic (D26=21): hydro == 10
    - Steam (D26=22):        hydro >= 5
    Pressure prerequisites for Panthalassic/Steam are not checked here
    because code-15 worlds have no defined pressure span.
    """
    while True:
        result = _d26()
        code, name, desc = _UNUSUAL_SUBTYPE_TABLE[result]
        if code == "" and not allow_combination:
            continue
        if result == 16 and SIZE_GRAVITY_G.get(size, 0.0) <= 1.2:
            continue
        if result == 21 and hydro != 10:
            continue
        if result == 22 and hydro < 5:
            continue
        return UnusualSubtype(subtype_code=code, subtype_name=name, description=desc)


def generate_unusual_subtype(
    detail: AtmosphereDetail,
    atm_code: int,
    size: int,
    hydro: int,
) -> None:
    """Populate ``detail.unusual_subtypes`` for Unusual (F) atmospheres.

    No-op for codes other than 15.  Call this after
    ``generate_hydrographics()`` so Panthalassic/Steam prerequisites
    can be evaluated against actual hydro.
    """
    if atm_code != 15:
        return
    first = _roll_unusual_subtype(size, hydro, allow_combination=True)
    if first.subtype_code == "":
        sub1 = _roll_unusual_subtype(size, hydro, allow_combination=False)
        sub2 = _roll_unusual_subtype(size, hydro, allow_combination=False)
        detail.unusual_subtypes = [sub1, sub2]
    else:
        detail.unusual_subtypes = [first]


def format_atmosphere_profile(
    code: int, detail: Optional[AtmosphereDetail],
) -> str:
    """Return the WBH p.82/p.88/p.93 atmosphere profile string.

    Format is ``A-bar-ppo[-T.S.P...][:XX-##:YY-##]`` where A is the eHex
    atmosphere code, ``bar`` is the total pressure, ``ppo`` is the oxygen
    partial pressure, each ``T.S.P`` triplet encodes a taint (subtype code,
    severity code, persistence code), and ``:XX-##`` entries are gas-mix
    components (code and two-digit percentage).  Any field is dropped when
    not applicable.  For Unusual (F, code 15) the format is ``F-S#[.#]``
    per WBH p.93.  Examples::

        format_atmosphere_profile(6, detail)   # "6-1.013-0.212"
        format_atmosphere_profile(7, detail)   # "7-1.148-0.138-P.7.9"
        format_atmosphere_profile(0, None)     # "0"
        format_atmosphere_profile(10, detail)  # "A-St4-0.55:N₂-75:CO₂-20"
    """
    if detail is None:
        return to_hex(code)
    if code in (16, 17):
        return to_hex(code)
    if code == 15:
        if detail.unusual_subtypes:
            codes = ".".join(
                s.subtype_code for s in detail.unusual_subtypes if s.subtype_code
            )
            return f"F-S{codes}"
        return "F"
    parts = [to_hex(code)]
    if detail.pressure_bar is not None:
        parts.append(f"{detail.pressure_bar:g}")
    if detail.oxygen_partial_pressure is not None:
        parts.append(f"{detail.oxygen_partial_pressure:g}")
    for taint in detail.taints:
        parts.append(f"{taint.subtype_code}.{taint.severity_code}.{taint.persistence_code}")
    base = "-".join(parts)
    if detail.gas_mix:
        gas_tokens = "".join(
            f":{c.gas_code}-{c.percentage:02d}" if c.percentage is not None
            else f":{c.gas_code}"
            for c in detail.gas_mix
        )
        return base + gas_tokens
    return base


# ---------------------------------------------------------------------------
# World dataclass
# ---------------------------------------------------------------------------

@dataclass
class World:  # pylint: disable=too-many-instance-attributes
    """Holds all generated characteristics for one mainworld."""
    name:           str   = "Unknown"
    size:           int   = 0
    atmosphere:     int   = 0
    atmosphere_detail:    Optional[AtmosphereDetail]    = None
    temperature:          str   = "Temperate"
    hydrographics:        int   = 0
    hydrographic_detail:  Optional[HydrographicDetail]  = None
    population:     int   = 0
    government:     int   = 0
    law_level:      int   = 0
    starport:       str   = "X"
    tech_level:     int   = 0
    has_gas_giant:  bool  = False
    gas_giant_count:  int   = 0
    belt_count:       int   = 0
    population_multiplier: int = 0   # WBH "P" digit, 1-9 (0 if uninhabited)
    bases:          List[str] = field(default_factory=list)
    trade_codes:    List[str] = field(default_factory=list)
    travel_zone:    str   = "Green"
    notes:          List[str] = field(default_factory=list)
    seed:           Optional[int] = None
    size_detail:    Optional[Union["WorldPhysical", BeltPhysical]] = field(default=None, init=False)
    biomass_rating:        Optional[int] = field(default=None, init=False)
    biocomplexity_rating:  Optional[int] = field(default=None, init=False)
    native_sophont:  bool = field(default=False, init=False)
    extinct_sophont: bool = field(default=False, init=False)
    biodiversity_rating:  Optional[int] = field(default=None, init=False)
    compatibility_rating: Optional[int] = field(default=None, init=False)
    lifeform_profile:     Optional[str] = field(default=None, init=False)
    habitability_rating:  Optional[int] = field(default=None, init=False)
    population_detail: Optional["PopulationDetail"] = field(default=None, init=False)
    government_detail: Optional["GovernmentDetail"] = field(default=None, init=False)
    law_detail:        Optional["LawDetail"]         = field(default=None, init=False)
    tech_detail:       Optional["TechDetail"]        = field(default=None, init=False)
                                    # WBH Social Characteristics tech level profile.
                                    # Set by attach_tech_detail() (Session 116, issue #98).
                                    # None by default; only set when "Social detail" enabled.

    # ------------------------------------------------------------------
    # UWP string (e.g. "CA6A643-9")
    # ------------------------------------------------------------------
    def uwp(self) -> str:
        """Return the Universal World Profile string in standard format."""
        return (
            f"{self.starport}"
            f"{to_hex(self.size)}"
            f"{to_hex(self.atmosphere)}"
            f"{to_hex(self.hydrographics)}"
            f"{to_hex(self.population)}"
            f"{to_hex(self.government)}"
            f"{to_hex(self.law_level)}"
            f"-{to_hex(self.tech_level)}"
        )

    # ------------------------------------------------------------------
    # JSON output helpers
    # ------------------------------------------------------------------
    def _atmosphere_dict(self) -> dict:
        """Return the atmosphere block for ``to_dict()``.

        Always includes ``code``, ``name`` and ``survival_gear``.  When
        an ``AtmosphereDetail`` is attached, its non-None fields are
        nested under ``detail`` and a derived WBH profile string is
        added under ``profile``.
        """
        block: dict = {
            "code": self.atmosphere,
            "name": ATMOSPHERE_NAMES.get(self.atmosphere, "Unknown"),
            "survival_gear": ATMOSPHERE_GEAR.get(self.atmosphere, "Unknown"),
        }
        if self.atmosphere_detail is not None:
            detail = self.atmosphere_detail.to_dict()
            if detail:
                block["detail"] = detail
            block["profile"] = format_atmosphere_profile(
                self.atmosphere, self.atmosphere_detail
            )
        return block

    def to_dict(self) -> dict:
        """Return all world data as a plain Python dict.

        The dict is structured to match the JSON schema defined in
        traveller_world_schema.json.  Every field uses snake_case keys.
        Human-readable label strings (atmosphere name, government type,
        etc.) are included alongside the raw numeric/hex codes so that
        the document is useful without cross-referencing lookup tables.
        """
        return {
            "name": self.name,
            "uwp": self.uwp(),
            "starport": {
                "code": self.starport,
                "description": STARPORT_QUALITY.get(self.starport, "Unknown"),
            },
            "size": {
                "code": self.size,
                "diameter_km": SIZE_DIAMETER_LABEL.get(self.size, "Unknown"),
                "surface_gravity": SIZE_GRAVITY_LABEL.get(self.size, "Unknown"),
            },
            "atmosphere": self._atmosphere_dict(),
            "temperature": self.temperature,
            "hydrographics": {
                "code": self.hydrographics,
                "description": HYDROGRAPHIC_NAMES.get(
                    self.hydrographics, "Unknown"
                ),
                **({"detail": self.hydrographic_detail.to_dict()}
                   if self.hydrographic_detail is not None else {}),
            },
            "population": {
                "code": self.population,
                "range": POPULATION_RANGE.get(self.population, "Hundreds of billions+"),
            },
            "government": {
                "code": self.government,
                "name": GOVERNMENT_NAMES.get(self.government, "Unknown"),
            },
            "law_level": self.law_level,
            "tech_level": self.tech_level,
            "has_gas_giant": self.has_gas_giant,
            "gas_giant_count": self.gas_giant_count,
            "belt_count": self.belt_count,
            "population_multiplier": self.population_multiplier,
            "pbg": (
                f"{self.population_multiplier}"
                f"{self.belt_count}"
                f"{self.gas_giant_count}"
            ),
            "bases": self.bases,
            "trade_codes": self.trade_codes,
            "travel_zone": self.travel_zone,
            "notes": self.notes,
            **({"size_detail": self.size_detail.to_dict()} if self.size_detail else {}),
            **({"biomass_rating": self.biomass_rating} if self.biomass_rating is not None else {}),
            **({"biocomplexity_rating": self.biocomplexity_rating}
               if self.biocomplexity_rating is not None else {}),
            **({"native_sophont": True}  if self.native_sophont  else {}),
            **({"extinct_sophont": True} if self.extinct_sophont else {}),
            **({"biodiversity_rating": self.biodiversity_rating}
               if self.biodiversity_rating is not None else {}),
            **({"compatibility_rating": self.compatibility_rating}
               if self.compatibility_rating is not None else {}),
            **({"lifeform_profile": self.lifeform_profile}
               if self.lifeform_profile is not None else {}),
            **({"habitability_rating": self.habitability_rating}
               if self.habitability_rating is not None else {}),
            **({"seed": self.seed} if self.seed is not None else {}),
            **({"population_detail": self.population_detail.to_dict()}
               if self.population_detail is not None else {}),
            **({"government_detail": self.government_detail.to_dict()}
               if self.government_detail is not None else {}),
            **({"law_detail": self.law_detail.to_dict()}
               if self.law_detail is not None else {}),
            **({"tech_detail": self.tech_detail.to_dict()}
               if self.tech_detail is not None else {}),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialise the world to a JSON string.

        Args:
            indent: Number of spaces used for pretty-printing.
                    Pass ``None`` for compact single-line output.

        Returns:
            A UTF-8–safe JSON string conforming to
            traveller_world_schema.json.
        """
        d = {"_app_version": APP_VERSION}
        d.update(self.to_dict())
        return json.dumps(d, indent=indent, ensure_ascii=False)

    @staticmethod
    def _validate_world_codes(d: dict) -> None:  # pylint: disable=too-many-branches
        """Validate magic-code fields in a raw dict before constructing a World.

        Raises ValueError with a descriptive message on the first invalid value.
        Only validates fields that are present; missing fields receive defaults
        in from_dict() and are not checked here.
        """
        def _unwrap(val: object) -> object:
            return val.get("code") if isinstance(val, dict) else val  # type: ignore[union-attr]

        if "starport" in d:
            raw = str(_unwrap(d["starport"]) or "X")
            try:
                StarportCode(raw)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid starport code {raw!r}: expected one of {', '.join(StarportCode)}"
                ) from exc

        if "atmosphere" in d:
            try:
                AtmosphereCode(int(_unwrap(d["atmosphere"]) or 0))  # type: ignore[arg-type]
            except ValueError as exc:
                raise ValueError(
                    f"Invalid atmosphere code {_unwrap(d['atmosphere'])!r}: expected 0–17"
                ) from exc

        if "temperature" in d:
            temp = str(d["temperature"])
            try:
                TemperatureCategory(temp)
            except ValueError as exc:
                valid = ", ".join(t.value for t in TemperatureCategory)
                raise ValueError(f"Invalid temperature {temp!r}: expected one of {valid}") from exc

        if "trade_codes" in d:
            for code in d["trade_codes"]:
                try:
                    TradeCode(str(code))
                except ValueError as exc:
                    valid = ", ".join(t.value for t in TradeCode)
                    raise ValueError(
                        f"Unknown trade code {code!r}: expected one of {valid}"
                    ) from exc

        if "travel_zone" in d:
            zone = str(d["travel_zone"])
            try:
                TravelZone(zone)
            except ValueError as exc:
                valid = ", ".join(z.value for z in TravelZone)
                raise ValueError(
                    f"Invalid travel zone {zone!r}: expected one of {valid}"
                ) from exc

        for fname, lo, hi in (
            ("size",          0, 10),
            ("hydrographics", 0, 10),
            ("population",    0, 12),
            ("government",    0, 15),
            ("law_level",     0, 18),
        ):
            if fname in d:
                try:
                    val = int(_unwrap(d[fname]) or 0)  # type: ignore[arg-type]
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Field {fname!r} must be an integer, got {d[fname]!r}"
                    ) from exc
                if val < lo or val > hi:
                    raise ValueError(
                        f"Field {fname!r} value {val} is out of range [{lo}, {hi}]"
                    )

    @classmethod
    def from_dict(cls, d: dict) -> "World":  # pylint: disable=too-many-locals,too-many-branches
        """Reconstruct a World from a dict produced by to_dict().

        Handles both the nested form produced by to_dict() (where 'starport',
        'size', 'atmosphere', 'hydrographics', 'population', and 'government'
        are sub-objects with a 'code' key) and flat forms where the value is
        the code directly.  Missing fields receive safe defaults.

        All post-generation detail sub-objects (atmosphere_detail,
        hydrographic_detail, size_detail, biomass_rating,
        biocomplexity_rating, native_sophont, extinct_sophont) are restored
        when present in the dict.

        Raises ValueError if any present field contains an invalid code or is
        out of range.
        """
        cls._validate_world_codes(d)

        def _int(val: object, default: int = 0) -> int:
            try:
                return int(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        def _code(val: object) -> object:
            """Return val['code'] when val is a dict, else val itself."""
            return val.get("code") if isinstance(val, dict) else val  # type: ignore[union-attr]

        gas_giant_count = _int(_code(d.get("gas_giant_count", 0)))

        world = cls(
            name=str(d.get("name", "Unknown")),
            starport=str(_code(d.get("starport", "X")) or "X"),
            size=_int(_code(d.get("size", 0))),
            atmosphere=_int(_code(d.get("atmosphere", 0))),
            temperature=str(d.get("temperature", "Temperate")),
            hydrographics=_int(_code(d.get("hydrographics", 0))),
            population=_int(_code(d.get("population", 0))),
            government=_int(_code(d.get("government", 0))),
            law_level=_int(d.get("law_level", 0)),
            tech_level=_int(d.get("tech_level", 0)),
            has_gas_giant=bool(d.get("has_gas_giant", gas_giant_count > 0)),
            gas_giant_count=gas_giant_count,
            belt_count=_int(d.get("belt_count", 0)),
            population_multiplier=_int(d.get("population_multiplier", 0)),
            bases=list(d.get("bases", [])),
            trade_codes=list(d.get("trade_codes", [])),
            travel_zone=str(d.get("travel_zone", "Green")),
            notes=list(d.get("notes", [])),
        )

        atm_block = d.get("atmosphere", {})
        atm_detail_d = atm_block.get("detail") if isinstance(atm_block, dict) else None
        if atm_detail_d:
            world.atmosphere_detail = AtmosphereDetail.from_dict(atm_detail_d)

        hydro_block = d.get("hydrographics", {})
        hydro_detail_d = hydro_block.get("detail") if isinstance(hydro_block, dict) else None
        if hydro_detail_d:
            world.hydrographic_detail = HydrographicDetail.from_dict(hydro_detail_d)

        sd = d.get("size_detail")
        if sd:
            if "composition" in sd:
                from traveller_world_physical import WorldPhysical  # pylint: disable=import-outside-toplevel
                world.size_detail = WorldPhysical.from_dict(sd)
            else:
                world.size_detail = BeltPhysical.from_dict(sd)

        if d.get("biomass_rating") is not None:
            world.biomass_rating = int(d["biomass_rating"])
        if d.get("biocomplexity_rating") is not None:
            world.biocomplexity_rating = int(d["biocomplexity_rating"])
        world.native_sophont = bool(d.get("native_sophont", False))
        world.extinct_sophont = bool(d.get("extinct_sophont", False))
        if d.get("biodiversity_rating") is not None:
            world.biodiversity_rating = int(d["biodiversity_rating"])
        if d.get("compatibility_rating") is not None:
            world.compatibility_rating = int(d["compatibility_rating"])
        world.lifeform_profile = d.get("lifeform_profile")
        if d.get("habitability_rating") is not None:
            world.habitability_rating = int(d["habitability_rating"])
        if d.get("seed") is not None:
            world.seed = int(d["seed"])
        if d.get("population_detail") is not None:
            from traveller_world_population_detail import PopulationDetail as _PD  # pylint: disable=import-outside-toplevel
            world.population_detail = _PD.from_dict(d["population_detail"])
        if d.get("government_detail") is not None:
            from traveller_world_government_detail import GovernmentDetail as _GD  # pylint: disable=import-outside-toplevel
            world.government_detail = _GD.from_dict(d["government_detail"])
        if d.get("law_detail") is not None:
            from traveller_world_law_detail import LawDetail as _LD  # pylint: disable=import-outside-toplevel
            world.law_detail = _LD.from_dict(d["law_detail"])
        if d.get("tech_detail") is not None:
            from traveller_world_tech_detail import TechDetail as _TD  # pylint: disable=import-outside-toplevel
            world.tech_detail = _TD.from_dict(d["tech_detail"])

        return world

    # ------------------------------------------------------------------
    # HTML display card
    # ------------------------------------------------------------------
    @staticmethod
    def _tl_era(tl: int) -> str:
        """Return the canonical era name for a Tech Level (pp. 6-7).

        TL 0-3   → Primitive
        TL 4-6   → Industrial
        TL 7-9   → Pre-Stellar
        TL 10-11 → Early Stellar
        TL 12-14 → Average Stellar
        TL 15+   → High Stellar
        """
        if tl <= 3:
            return "Primitive"
        if tl <= 6:
            return "Industrial"
        if tl <= 9:
            return "Pre-Stellar"
        if tl <= 11:
            return "Early Stellar"
        if tl <= 14:
            return "Average Stellar"
        return "High Stellar"

    @staticmethod
    def _tl_era_css(tl: int) -> str:
        """Return a CSS class name matching the era colour used in the widget."""
        if tl <= 3:
            return "era-primitive"
        if tl <= 6:
            return "era-industrial"
        if tl <= 9:
            return "era-prestellar"
        if tl <= 11:
            return "era-earlystellar"
        if tl <= 14:
            return "era-avgstellar"
        return "era-highstellar"

    def to_html(self) -> str:
        """Return a self-contained HTML card representing this world.

        The output can be embedded in any HTML page, saved as a standalone
        .html file, or served directly from the Azure Functions API.

        Tech Level era labels (Traveller 2022 Core Rulebook pp. 6-7):
            TL 0-3 = Primitive, TL 4-6 = Industrial, TL 7-9 = Pre-Stellar,
            TL 10-11 = Early Stellar, TL 12-14 = Average Stellar, TL 15+ = High Stellar

        Returns:
            A UTF-8 HTML string with all CSS inlined; no external resources.
        """
        return render("world_card.html", ctx=_world_html_ctx(self))

    # ------------------------------------------------------------------
    # Human-readable summary
    # ------------------------------------------------------------------
    def summary(self) -> str:  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """Return a human-readable summary of this world's characteristics."""
        pop_range = POPULATION_RANGE
        size_km   = {k: f"{v} km" for k, v in SIZE_DIAMETER_LABEL.items()}
        gravity   = SIZE_GRAVITY_LABEL

        lines = [
            f"{'='*56}",
            f"  {self.name}  —  {self.uwp()}",
            f"{'='*56}",
            f"  Trade codes : {' '.join(self.trade_codes) or 'None'}",
            f"  Bases       : {' '.join(self.bases) or 'None'}",
            f"  Travel zone : {self.travel_zone}",
            f"  Gas giant   : {'Yes' if self.has_gas_giant else 'No'}"
                f"  (count: {self.gas_giant_count})",
            f"  Belts       : {self.belt_count}",
            f"  Pop. mult.  : {self.population_multiplier}  "
                f"(PBG: {self.population_multiplier}{self.belt_count}{self.gas_giant_count})",
            f"{'-'*56}",
            f"  Starport    : {self.starport}  ({STARPORT_QUALITY.get(self.starport, '?')})",
            f"  Size        : {to_hex(self.size)}  "
                f"({size_km.get(self.size, '?')}, {gravity.get(self.size, '?')})",
            f"  Atmosphere  : {to_hex(self.atmosphere)}  "
                f"({ATMOSPHERE_NAMES.get(self.atmosphere, '?')})",
            f"  Temperature : {self.temperature}",
            f"  Hydrograph. : {to_hex(self.hydrographics)}  "
                f"({HYDROGRAPHIC_NAMES.get(self.hydrographics, '?')})",
            f"  Population  : {to_hex(self.population)}  "
                f"({pop_range.get(self.population, 'Tens of billions+')})",
            f"  Government  : {to_hex(self.government)}  "
                f"({GOVERNMENT_NAMES.get(self.government, '?')})",
            f"  Law Level   : {to_hex(self.law_level)}",
            f"  Tech Level  : {to_hex(self.tech_level)}",
        ]

        if self.atmosphere_detail is not None:
            ad = self.atmosphere_detail
            lines.append(f"{'-'*56}")
            profile = format_atmosphere_profile(self.atmosphere, ad)
            lines.append(f"  {'Atm. profile':<12}: {profile}")
            if ad.subtype_name is not None:
                lines.append(f"  {'Subtype':<12}: {ad.subtype_name}")
            if ad.pressure_bar is not None:
                lines.append(f"  {'Pressure':<12}: {ad.pressure_bar:.3f} bar")
            elif ad.subtype_code in ("C", "D", "E"):
                lines.append(f"  {'Pressure':<12}: > 10.0 bar (extremely dense)")
            if ad.oxygen_partial_pressure is not None:
                lines.append(f"  {'O2 ppo':<12}: {ad.oxygen_partial_pressure:.3f} bar")
            if ad.scale_height_km is not None:
                lines.append(f"  {'Scale ht.':<12}: {ad.scale_height_km:.1f} km")
            if ad.no_safe_altitude:
                lines.append(f"  {'Safe alt.':<12}: None (no breathable level)")
            elif ad.min_safe_altitude_km is not None:
                if ad.min_safe_altitude_km >= 0:
                    lines.append(
                        f"  {'Min safe alt':<12}: {ad.min_safe_altitude_km:.1f} km above baseline"
                    )
                else:
                    depth = abs(ad.min_safe_altitude_km)
                    lines.append(
                        f"  {'Max safe dep':<12}: {depth:.1f} km below baseline"
                    )
            for sub in ad.unusual_subtypes:
                lines.append(f"  {'Subtype':<12}: {sub.subtype_name} ({sub.subtype_code})")
            for i, taint in enumerate(ad.taints):
                label = f"Taint {i + 1}" if len(ad.taints) > 1 else "Taint"
                lines.append(
                    f"  {label:<12}: {taint.subtype}"
                    f"  sev {taint.severity_code}  per {taint.persistence_code}"
                )
            for hazard in ad.hazards:
                lines.append(f"  {'Hazard':<12}: {hazard.hazard}")
                if hazard.gases:
                    lines.append(f"  {'  Gas mix':<12}: {', '.join(hazard.gases)}")
            if ad.gas_mix:
                gas_parts = ", ".join(
                    f"{c.gas_name} ({c.gas_code})"
                    + (f" {c.percentage}%" if c.percentage is not None else "")
                    for c in ad.gas_mix
                )
                lines.append(f"  {'Gas mix':<12}: {gas_parts}")

        if self.hydrographic_detail is not None:
            lines.append(f"{'-'*56}")
            lines.append(
                f"  {'Surface liq.':<12}: "
                f"{self.hydrographic_detail.surface_liquid_pct}%"
            )
            if self.hydrographic_detail.fluid_type is not None:
                lines.append(
                    f"  {'Fluid type':<12}: {self.hydrographic_detail.fluid_type}"
                )

        if self.size_detail:
            p = self.size_detail
            lines.append(f"{'-'*56}")
            if isinstance(p, BeltPhysical):
                lines.append("  Belt body")
                lines.append(f"  Belt span   : {p.inner_au} – {p.outer_au} AU")
                lines.append(
                    f"  Composition : M: {p.m_type_pct}% / S: {p.s_type_pct}%"
                    f" / C: {p.c_type_pct}% / Other: {p.other_pct}%"
                )
                lines.append(f"  Bulk        : {p.bulk}")
                lines.append(f"  Resource    : {p.resource_rating}")
                lines.append(
                    f"  Bodies      : {p.size_1_bodies} × Size 1,"
                    f" {p.size_s_bodies} × Size S"
                )
            else:
                lines.append("  World body")
                lines.append(f"  Composition : {p.composition}")
                lines.append(f"  Diameter    : {p.diameter_km:,} km")
                lines.append(f"  Density     : {p.density:.2f} g/cm³")
                lines.append(f"  Mass        : {p.mass:.4f} M⊕")
                lines.append(f"  Gravity     : {p.gravity:.3f} G")
                lines.append(f"  Esc. vel.   : {p.escape_velocity:.2f} km/s")
                if p.resource_rating is not None:
                    lines.append(f"  Resource    : {p.resource_rating}")
                lines.append(f"  Axial tilt  : {p.axial_tilt}°")
                lines.append(f"  Day length  : {p.day_length:.1f} h")
                if p.stellar_day_hours is not None:
                    lines.append(f"  Stellar day : {p.stellar_day_hours:.1f} h")
                if p.tidal_status != "none":
                    lines.append(f"  Tidal status: {TIDAL_STATUS_LABELS[p.tidal_status]}")

        if self.notes:
            lines.append(f"{'-'*56}")
            lines.append("  Notes:")
            for note in self.notes:
                lines.append(f"    * {note}")

        lines.append(f"{'='*56}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML context builder — shared by World.to_html() and the multi-world CLI
# ---------------------------------------------------------------------------

def _world_html_ctx(world: "World") -> dict:  # pylint: disable=too-many-locals,protected-access
    """Build the Jinja2 context dict for a world card template render."""
    d = world.to_dict()
    gear = d["atmosphere"]["survival_gear"]

    if world.size_detail and not isinstance(world.size_detail, BeltPhysical):
        size_km = f"{world.size_detail.diameter_km:,}"
        size_gravity = f"{world.size_detail.gravity:.2f}G"
    else:
        size_km = d["size"]["diameter_km"]
        size_gravity = d["size"]["surface_gravity"]

    atm_profile = ""
    gas_parts = ""
    if world.atmosphere_detail is not None:
        atm_profile = format_atmosphere_profile(world.atmosphere, world.atmosphere_detail)
        if world.atmosphere_detail.gas_mix:
            gas_parts = " · ".join(
                f"{c.gas_name} ({c.gas_code})"
                + (f" {c.percentage}%" if c.percentage is not None else "")
                for c in world.atmosphere_detail.gas_mix
            )

    tidal_label = ""
    if (world.size_detail is not None and not isinstance(world.size_detail, BeltPhysical)
            and world.size_detail.tidal_status != "none"):
        tidal_label = TIDAL_STATUS_LABELS[world.size_detail.tidal_status]

    return {
        "world": world,
        "uwp": world.uwp(),
        "zone_class": ZONE_CSS_CLASS.get(world.travel_zone, "zone-green"),
        "tl_era": world._tl_era(world.tech_level),  # pylint: disable=protected-access
        "tl_era_css": world._tl_era_css(world.tech_level),  # pylint: disable=protected-access
        "starport_label": STARPORT_QUALITY_LABEL.get(world.starport, "?"),
        "starport_detail": STARPORT_FACILITY_DETAIL.get(world.starport, ""),
        "size_hex": to_hex(world.size),
        "size_km": size_km,
        "size_gravity": size_gravity,
        "atm_hex": to_hex(world.atmosphere),
        "atm_name": d["atmosphere"]["name"],
        "atm_survival": gear,
        "atm_survival_danger": gear not in ("None", "Varies"),
        "hydro_hex": to_hex(world.hydrographics),
        "hydro_desc": d["hydrographics"]["description"].split(" (")[0],
        "pop_hex": to_hex(world.population),
        "pop_range": d["population"]["range"],
        "gov_hex": to_hex(world.government),
        "gov_name": d["government"]["name"],
        "law_hex": to_hex(world.law_level),
        "tl_hex": to_hex(world.tech_level),
        "bases_str": "  ".join(BASE_FULL.get(b, b) for b in world.bases) or "None",
        "trade_codes": [TRADE_CODE_FULL.get(tc, tc) for tc in world.trade_codes],
        "pbg": (f"{world.population_multiplier}"
                f"{world.belt_count}{world.gas_giant_count}"),
        "is_belt_phys": isinstance(world.size_detail, BeltPhysical),
        "atm_profile": atm_profile,
        "gas_parts": gas_parts,
        "tidal_label": tidal_label,
        "biomass_rating": world.biomass_rating,
        "biomass_str": (to_hex(world.biomass_rating)
                        if world.biomass_rating is not None else None),
        "biocomplexity_rating": world.biocomplexity_rating,
        "biocomplexity_str": (
            f"{to_hex(world.biocomplexity_rating)} — "
            + BIOCOMPLEXITY_DESC.get(
                world.biocomplexity_rating, "Ecosystem-wide superorganisms")
            if world.biocomplexity_rating is not None else None
        ),
        "native_sophont":  world.native_sophont,
        "extinct_sophont": world.extinct_sophont,
        "biodiversity_rating": world.biodiversity_rating,
        "biodiversity_str": (to_hex(world.biodiversity_rating)
                             if world.biodiversity_rating is not None else None),
        "compatibility_rating": world.compatibility_rating,
        "compatibility_str": (to_hex(world.compatibility_rating)
                              if world.compatibility_rating is not None else None),
        "lifeform_profile": world.lifeform_profile,
        "habitability_rating": world.habitability_rating,
        "habitability_str": (
            f"{world.habitability_rating} — "
            + habitability_description(world.habitability_rating)
            if world.habitability_rating is not None else None
        ),
        "json_str": world.to_json(),
        "pop_detail": world.population_detail,
        "pop_detail_total_str": (
            f"{world.population_detail.total_population:,}"
            if world.population_detail is not None else None),
        "pop_detail_urban_str": (
            f"{world.population_detail.urban_population:,}"
            if world.population_detail is not None else None),
        "pop_detail_major_total_str": (
            f"{world.population_detail.major_city_total_population:,}"
            if world.population_detail is not None else None),
        "pop_detail_cities": (
            [(i + 1, f"{c.population:,}")
             for i, c in enumerate(world.population_detail.cities)]
            if world.population_detail is not None else []),
        "gov_detail": world.government_detail,
        "law_detail": world.law_detail,
        "tech_detail": world.tech_detail,
    }


# ---------------------------------------------------------------------------
# Generation functions — one per step in the rulebook
# ---------------------------------------------------------------------------

def generate_size() -> int:
    """Step 1 — Size (p.249): roll 2D-2, range 0-10.

    Size 0 = asteroid/orbital complex; Size 8 = roughly Earth-sized.
    """
    return roll(2, -2)


def generate_atmosphere(size: int) -> int:
    """Step 2 — Atmosphere (p.249-250): roll 2D-7 + Size, minimum 0.

    Size 0 or 1 worlds cannot retain an atmosphere, so they are forced to 0.
    """
    if size <= 1:
        return 0
    return max(0, roll(2, -7 + size))


def generate_nhz_atmosphere(size: int, hz_deviation: float) -> tuple:
    """Generate atmosphere for a Non-Habitable Zone world (WBH pp.78-79).

    Rolls 2D-7+Size and looks up the result in the appropriate NHZ column
    based on ``hz_deviation``.  Returns ``(atm_code, exotic_key)`` where
    ``exotic_key`` is the ``_EXOTIC_SUBTYPE_TABLE`` key when
    ``atm_code == 10``; ``None`` otherwise.

    The caller is responsible for ensuring ``abs(hz_deviation) > 1.0``.
    Worlds with size ≤ 1 cannot retain an atmosphere and return ``(0, None)``.
    """
    if size <= 1:
        return 0, None

    result = max(0, roll(2, -7 + size))

    if hz_deviation <= -2.01:
        table = _NHZ_HOT_A
    elif hz_deviation <= -1.01:
        table = _NHZ_HOT_B
    elif hz_deviation <= 3.0:
        table = _NHZ_COLD_A
    else:
        table = _NHZ_COLD_B

    result = min(result, max(table))
    atm_code, base_key, irr_key, star, dagger = table[result]

    exotic_key: Optional[int] = None
    if atm_code == 10:
        if star:
            dm = 1 if (dagger and hz_deviation <= -3.0) else 0
            exotic_key = irr_key if _rng.randint(1, 6) + dm >= 4 else base_key
        else:
            exotic_key = base_key

    return atm_code, exotic_key


def generate_temperature(atmosphere: int) -> str:
    """Step 3 — Temperature (p.251): roll 2D + Atmosphere DM.

    Returns a descriptive category string (Frozen / Cold / Temperate /
    Hot / Boiling) that is used as a DM source for Hydrographics.
    """
    dm = TEMPERATURE_DM.get(atmosphere, 0)
    result = roll(2, dm)
    return temperature_category(result)


def generate_hydrographics(size: int, atmosphere: int, temperature: str) -> int:
    """Step 4 — Hydrographics (p.251): roll 2D-7 + Atmosphere + DMs.

    Several special cases apply:
      - Size 0/1 worlds have Hydrographics 0 (no gravity to hold liquid).
      - Atmosphere 0, 1, or 10-15 (A-F) imposes DM-4.
      - Hot temperature imposes DM-2 (liquids evaporate).
      - Boiling temperature imposes DM-6.
      - Atmosphere D (Very Dense) and Panthalassic F are exceptions that
        CAN retain liquid despite the extreme atmosphere; the rulebook
        notes they keep their hydrographics even when hot/boiling.
    """
    if size <= 1:
        return 0
    if atmosphere in (16, 17):
        return 0

    # Base roll: 2D-7 + Atmosphere code
    base = roll(2, -7 + atmosphere)

    dm = 0

    # Thin or exotic/corrosive atmospheres lose water easily
    if atmosphere in (0, 1) or atmosphere >= 10:
        dm -= 4

    # Temperature modifiers (only if atmosphere is NOT code D=13 or
    # panthalassic F=15, which are special liquid-retaining cases)
    if atmosphere not in (13, 15):
        if temperature == "Hot":
            dm -= 2
        elif temperature == "Boiling":
            dm -= 6

    return max(0, min(10, base + dm))


_SETTLEMENT_DMS: dict = {
    "standard":     {},
    "long_settled": {0: 1, 1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 2, 8: 3, 9: 2},
    "well_settled": {4: 1, 5: 2, 6: 2, 7: 1, 8: 2, 9: 1},
    "backwater":    {0: -3, 1: -3, 2: -3, 3: -3, 4: -1, 5: 1, 6: 1, 7: -1, 8: 1, 9: -1},
    "unsettled":    {4: -5, 5: -4, 6: -4, 7: -5, 8: -4, 9: -5},
}
_SETTLEMENT_DEFAULT_DM: dict = {
    "standard": 0, "long_settled": 0, "well_settled": -1, "backwater": -5, "unsettled": -7,
}


def _population_settlement_dm(settlement_type: str, atmosphere: int) -> int:
    """Return the population DM for the given settlement type and atmosphere."""
    return _SETTLEMENT_DMS.get(settlement_type, {}).get(
        atmosphere, _SETTLEMENT_DEFAULT_DM.get(settlement_type, 0)
    )


def generate_population(settlement_dm: int = 0) -> int:
    """Step 5 — Population (p.251-252): roll 2D-2, range 0-10.

    Population 0 = uninhabited.  The referee may optionally place very
    high-population worlds (11-12) but the dice do not produce these.
    An optional settlement_dm shifts the roll while keeping the 0–10 range.
    """
    return min(10, roll(2, -2 + settlement_dm))


def generate_government(population: int) -> int:
    """Step 6 — Government (p.252): roll 2D-7 + Population, minimum 0.

    If Population is 0 the world is uninhabited and has no government.
    """
    if population == 0:
        return 0
    return max(0, roll(2, -7 + population))


def generate_law_level(government: int) -> int:
    """Step 7 — Law Level (p.255): roll 2D-7 + Government, clamped to [0, 18].

    Law Level 0 = no restrictions; higher values ban progressively more.
    If Population is 0 (handled by caller), Law Level should also be 0.
    Maximum 18 (eHex 'I') matches the schema and WBH subcategory ceilings.
    """
    return min(18, max(0, roll(2, -7 + government)))


def generate_starport(population: int) -> str:
    """Step 8 — Starport (p.257): roll 2D + Population DMs.

    Population DMs:
      Pop 8-9  → DM+1
      Pop 10+  → DM+2
      Pop 3-4  → DM-1
      Pop ≤2   → DM-2
    """
    dm = 0
    if population >= 10:
        dm = +2
    elif population >= 8:
        dm = +1
    elif population <= 2:
        dm = -2
    elif population <= 4:
        dm = -1

    modified = roll(2, dm)
    return starport_class_from_roll(modified)


def generate_tech_level(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        starport: str, size: int, atmosphere: int,
        hydrographics: int, population: int,
        government: int) -> int:
    """Step 9 — Tech Level (p.258-259): roll 1D + multiple DMs.

    DMs come from Starport, Size, Atmosphere, Hydrographics,
    Population, and Government codes.  The minimum TL required by the
    Atmosphere is noted separately (as a world note) but is NOT forced
    here — a referee may keep a low-TL doomed colony.
    """
    dm = 0

    # Starport DM
    dm += STARPORT_TL_DM.get(starport, 0)

    # Size DMs (small worlds are easier to survey/supply; they get a boost)
    dm += SIZE_TL_DM.get(size, 0)

    # Atmosphere DMs (exotic/extreme atmospheres demand advanced tech)
    dm += ATMOSPHERE_TL_DM.get(atmosphere, 0)

    # Hydrographics DMs (very watery worlds need advanced water tech)
    dm += HYDROGRAPHICS_TL_DM.get(hydrographics, 0)

    # Population DMs (large populations drive technological development)
    dm += POPULATION_TL_DM.get(population, 0)

    # Government DMs (some governments accelerate or suppress technology)
    dm += GOVERNMENT_TL_DM.get(government, 0)

    return max(0, roll(1, dm))


# ---------------------------------------------------------------------------
# Base generation tables  (Starport Facilities table, p.257; Bases p.259)
# ---------------------------------------------------------------------------

# For each starport class, list the base types that may be present along
# with the minimum 2D roll required for that base to exist.
# A roll >= the threshold means the base IS present.
# Highport and Corsair have additional DMs applied before the roll is checked
# (see generate_bases below).
#
# Base code → description:
#   N  Naval Base
#   S  Scout Base / Way Station
#   M  Military Base
#   C  Corsair Base
#   H  Highport
BASE_THRESHOLDS: dict = {
    #          base  min_roll
    "A": [("N", 8), ("M", 8), ("S", 10), ("H", 6)],
    "B": [("N", 8), ("M", 8), ("S",  9), ("H", 8)],
    "C": [          ("M", 10), ("S",  9), ("H", 10)],
    "D": [                     ("S",  8), ("H", 12), ("C", 12)],
    "E": [                                           ("C", 10)],
    "X": [                                           ("C", 10)],
}

# Highport DMs (p.257):
#   DM+2 if TL 12+; DM+1 if TL 9-11; DM+1 if Pop 9+; DM-1 if Pop ≤6
def _highport_dm(tech_level: int, population: int) -> int:
    """Return the combined DM for the highport presence roll."""
    dm = 0
    if tech_level >= 12:
        dm += 2
    elif tech_level >= 9:
        dm += 1
    if population >= 9:
        dm += 1
    if population <= 6:
        dm -= 1
    return dm


# Corsair DMs (p.257):
#   DM+2 if Law Level 0; DM-2 if Law Level 2+
def _corsair_dm(law_level: int) -> int:
    """Return the DM for the corsair base presence roll."""
    if law_level == 0:
        return +2
    if law_level >= 2:
        return -2
    return 0   # Law Level 1: no modifier


def generate_bases(starport: str, tech_level: int,
                   population: int, law_level: int) -> List[str]:
    """Step 10 — Bases (p.257, p.259): roll 2D per candidate base type.

    For each base type available at the given starport class, roll 2D
    (plus any applicable DMs) and compare to the minimum threshold.
    The base is present if the roll meets or exceeds the threshold.

    Naval (N), Military (M), and Scout (S) bases use a plain 2D roll.
    Highport (H) and Corsair (C) apply additional DMs from world stats.

    Returns a sorted list of base code letters, e.g. ['N', 'S'].
    """
    present = []

    candidates = BASE_THRESHOLDS.get(starport, [])
    for base_code, threshold in candidates:
        # Determine any additional DM for this specific base type
        if base_code == "H":
            dm = _highport_dm(tech_level, population)
        elif base_code == "C":
            dm = _corsair_dm(law_level)
        else:
            dm = 0   # Naval, Scout, Military: straight 2D roll

        if roll(2, dm) >= threshold:
            present.append(base_code)

    return sorted(present)


def generate_population_multiplier(population: int) -> int:
    """WBH — Population P-digit (multiplier): two D3 rolls → value 1–9.

    Source: World Builder's Handbook, Population P Value table.

    The P digit refines the population code to one significant figure.
    A Population 6 world with P=3 has approximately 3,000,000 inhabitants.

    Procedure:
      First D3:  1→adds 0, 2→adds 3, 3→adds 6
      Second D3: 1→adds 1, 2→adds 2, 3→adds 3
      Combined result is always in the range 1–9.

    Population 0 worlds are uninhabited; P is defined as 0.
    """
    if population == 0:
        return 0
    # D3 is simulated as ceil(1D/2)
    def d3() -> int:
        return (_rng.randint(1, 6) + 1) // 2   # gives 1, 2 or 3

    first  = d3()   # maps 1→0, 2→3, 3→6
    second = d3()   # maps 1→1, 2→2, 3→3

    offset_map = {1: 0, 2: 3, 3: 6}
    return offset_map[first] + second


def generate_gas_giant_count() -> int:
    """WBH — Number of gas giants in the system (p.36).

    Called only when gas giants are already known to be present.
    Roll 2D on the Gas Giant Quantity table (no stellar DMs in a
    simple mainworld-only generation — those require full star system
    generation from the WBH Special Circumstances chapter).

      2D ≤ 4  → 1 gas giant
      5–6     → 2
      7–8     → 3
      9–11    → 4
      12      → 5
      13+     → 6
    """
    result = roll(2)
    if result <= 4:
        return 1
    if result <= 6:
        return 2
    if result <= 8:
        return 3
    if result <= 11:
        return 4
    if result == 12:
        return 5
    return 6


def generate_belt_count(has_gas_giant: bool, size: int) -> int:
    """WBH — Number of planetoid belts in the system (p.36).

    Procedure:
      1. Check existence: roll 2D; belt present on 8+.
      2. If present, roll 2D on Planetoid Belt Quantity table:
           2D ≤ 6   → 1 belt
           7–11     → 2 belts
           12+      → 3 belts
         DM+1 if one or more gas giants are present.
      3. Continuation method: if the mainworld is Size 0 (an asteroid
         belt itself), add 1 to the total belt count.

    Note: the WBH defines further DMs for protostars, post-stellar
    objects, and multiple-star systems. Those require full stellar
    generation and are not applied here.
    """
    belt_count = 0

    # Existence check: 2D ≥ 8
    if roll(2) >= 8:
        dm = 1 if has_gas_giant else 0
        result = roll(2, dm)
        if result <= 6:
            belt_count = 1
        elif result <= 11:
            belt_count = 2
        else:
            belt_count = 3

    # Continuation method: Size 0 mainworld is itself part of a belt
    if size == 0:
        belt_count += 1

    return belt_count


def generate_gas_giant() -> bool:
    """Step 11 — Gas Giant presence (p.246): roll 2D; on 10+ there is NO gas giant.

    Gas giants allow fuel skimming, making travel cheaper and easier.
    """
    return roll(2) <= 9  # 10+ means no gas giant


def assign_trade_codes(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
        size: int, atmosphere: int, hydrographics: int,
        population: int, government: int,
        law_level: int, tech_level: int) -> List[str]:
    """Step 12 — Trade Codes (p.260-261).

    Each code is awarded if ALL listed criteria are met.  Criteria are
    taken directly from the Trade Codes table on p.260.
    """
    codes = []

    # Agricultural (Ag): Atm 4-9, Hyd 4-8, Pop 5-7  (CRB p.260)
    if (4 <= atmosphere <= 9 and 4 <= hydrographics <= 8 and 5 <= population <= 7):
        codes.append("Ag")

    # Asteroid (As): tiny, airless, dry
    if size == 0 and atmosphere == 0 and hydrographics == 0:
        codes.append("As")

    # Barren (Ba): completely uninhabited, no government, no law
    if population == 0 and government == 0 and law_level == 0:
        codes.append("Ba")

    # Desert (De): some atmosphere but no surface water
    if 2 <= atmosphere <= 9 and hydrographics == 0:
        codes.append("De")

    # Fluid Oceans (Fl): liquid surface but not water (exotic atmospheres)
    if atmosphere >= 10 and hydrographics >= 1:
        codes.append("Fl")

    # Garden (Ga): Earth-like in the best ways
    if (6 <= size <= 8
            and atmosphere in (5, 6, 8)
            and 5 <= hydrographics <= 7):
        codes.append("Ga")

    # High Population (Hi)
    if population >= 9:
        codes.append("Hi")

    # High Tech (Ht)
    if tech_level >= 12:
        codes.append("Ht")

    # Ice-Capped (Ic): thin, near-frozen atmosphere with some water ice
    if atmosphere <= 1 <= hydrographics:
        codes.append("Ic")

    # Industrial (In): heavy industrial base
    if (atmosphere in (0, 1, 2, 4, 7, 9, 10, 11, 12)
            and population >= 9):
        codes.append("In")

    # Low Population (Lo)
    if 1 <= population <= 3:
        codes.append("Lo")

    # Low Tech (Lt): pre-industrial (atmosphere ≥1 means someone lives there)
    if atmosphere >= 1 and tech_level <= 5:
        codes.append("Lt")

    # Non-Agricultural (Na): barren and overpopulated
    if (atmosphere <= 3 and hydrographics <= 3 and population >= 6):
        codes.append("Na")

    # Non-Industrial (Ni): too small a population to support industry
    if 4 <= population <= 6:
        codes.append("Ni")

    # Poor (Po): barely habitable thin atmosphere, little water
    if 2 <= atmosphere <= 5 and hydrographics <= 3:
        codes.append("Po")

    # Rich (Ri): stable, pleasant, prosperous
    if (atmosphere in (6, 8)
            and 6 <= population <= 8
            and 4 <= government <= 9):
        codes.append("Ri")

    # Vacuum (Va): no atmosphere at all
    if atmosphere == 0:
        codes.append("Va")

    # Waterworld (Wa): almost entirely ocean; atmosphere can be exotic (13+)
    if (3 <= atmosphere <= 9 or atmosphere >= 13) and hydrographics == 10:
        codes.append("Wa")

    return codes


def assign_travel_zone(atmosphere: int, government: int,
                       law_level: int, starport: str) -> str:
    """Step 13 — Travel Zone (p.260).

    Starport X worlds are automatically Red zones — no facilities means
    the world is inaccessible or under interdiction.
    Amber worlds warrant caution: unusual atmosphere, unstable government,
    or extreme law level.
    Green is the default safe zone.

    Amber criteria (p.260):
      Atmosphere 10+, OR Government 0/7/10, OR Law Level 0 or 9+
    """
    if starport == "X":
        return "Red"
    amber = (
        atmosphere >= 10
        or government in (0, 7, 10)
        or law_level == 0
        or law_level >= 9
    )
    return "Amber" if amber else "Green"


# ---------------------------------------------------------------------------
# Social application — called after mainworld selection
# ---------------------------------------------------------------------------

def apply_mainworld_social(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    world: World,
    rng: Optional[random.Random] = None,
    settlement_type: str = "standard",
) -> None:
    """Apply social steps to a physically-complete mainworld (CRB pp.248-261).

    Performs steps 5–10 and 12–13: population, government, law level,
    starport, tech level, minimum-TL advisory, bases, population multiplier,
    trade codes, and travel zone.  Call this after mainworld selection in
    the WBH workflow, passing the same ``rng`` instance used for system
    generation to continue the RNG sequence correctly.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    world.population = generate_population(
        _population_settlement_dm(settlement_type, world.atmosphere)
    )
    world.government = generate_government(world.population)
    world.law_level = (
        0 if world.population == 0
        else generate_law_level(world.government)
    )

    world.starport = generate_starport(world.population)

    world.tech_level = (
        0 if world.population == 0
        else generate_tech_level(
            world.starport, world.size, world.atmosphere,
            world.hydrographics, world.population, world.government,
        )
    )

    min_tl = ATMOSPHERE_MIN_TL.get(world.atmosphere, 0)
    if world.population > 0 and world.tech_level < min_tl:
        world.notes.append(
            f"TL {world.tech_level} is below the minimum TL {min_tl} "
            f"needed to maintain Atmosphere {world.atmosphere} "
            f"({ATMOSPHERE_NAMES.get(world.atmosphere, '?')}). "
            "Population may be doomed."
        )

    world.bases = generate_bases(
        world.starport, world.tech_level, world.population, world.law_level,
    )
    world.population_multiplier = generate_population_multiplier(world.population)
    world.trade_codes = assign_trade_codes(
        world.size, world.atmosphere, world.hydrographics,
        world.population, world.government, world.law_level,
        world.tech_level,
    )
    world.travel_zone = assign_travel_zone(
        world.atmosphere, world.government, world.law_level, world.starport,
    )


# ---------------------------------------------------------------------------
# Master generation function
# ---------------------------------------------------------------------------

def generate_world(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        name: str = "Unknown",
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
        settlement_type: str = "standard",
) -> World:
    """Generate a complete mainworld following the rulebook procedure.

    Steps 1-13 are performed in order, each using the results of
    previous steps exactly as the rulebook specifies.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    elif seed is not None:
        rng = random.Random(seed)
        _rng = rng
    # When neither is given, use current _rng as-is (preserves random.seed() behaviour)
    world = World(name=name, seed=seed)

    # --- Step 1: Size ---
    world.size = generate_size()

    # --- Step 2: Atmosphere ---
    world.atmosphere = generate_atmosphere(world.size)

    # --- Step 3: Temperature ---
    # Temperature is not stored as a UWP digit but is used as a DM source
    # for hydrographics in step 4.
    world.temperature = generate_temperature(world.atmosphere)

    # --- Step 4: Hydrographics ---
    world.hydrographics = generate_hydrographics(
        world.size, world.atmosphere, world.temperature
    )

    # --- Step 5: Population ---
    world.population = generate_population(
        _population_settlement_dm(settlement_type, world.atmosphere)
    )

    # --- Step 6: Government ---
    # Uninhabited worlds (Population 0) have no government.
    world.government = generate_government(world.population)

    # --- Step 7: Law Level ---
    # Uninhabited worlds also have Law Level 0.
    if world.population == 0:
        world.law_level = 0
    else:
        world.law_level = generate_law_level(world.government)

    # --- Step 8: Starport ---
    world.starport = generate_starport(world.population)

    # --- Step 9: Tech Level ---
    # Uninhabited worlds have TL 0.
    if world.population == 0:
        world.tech_level = 0
    else:
        world.tech_level = generate_tech_level(
            world.starport, world.size, world.atmosphere,
            world.hydrographics, world.population, world.government
        )

    # --- Step 9 (supplementary): Minimum TL check ---
    # Record a note if the world's TL is below the minimum required to
    # maintain the atmosphere.  The referee should decide the consequences.
    min_tl = ATMOSPHERE_MIN_TL.get(world.atmosphere, 0)
    if world.population > 0 and world.tech_level < min_tl:
        world.notes.append(
            f"TL {world.tech_level} is below the minimum TL {min_tl} "
            f"needed to maintain Atmosphere {world.atmosphere} "
            f"({ATMOSPHERE_NAMES.get(world.atmosphere, '?')}). "
            "Population may be doomed."
        )

    # --- Step 10: Bases ---
    # Roll for each base type eligible at this starport class.
    # Highport and Corsair rolls include DMs from TL, Population, and Law Level.
    world.bases = generate_bases(
        world.starport, world.tech_level, world.population, world.law_level
    )

    # --- Step 11: Gas Giant (presence, count) and Planetoid Belts --------
    # The Core Rulebook determines presence (2D ≤ 9).
    # The World Builder's Handbook adds counts for both gas giants and
    # planetoid belts, and the population P-digit (multiplier).
    world.has_gas_giant = generate_gas_giant()
    world.gas_giant_count = generate_gas_giant_count() if world.has_gas_giant else 0
    world.belt_count = generate_belt_count(world.has_gas_giant, world.size)
    world.population_multiplier = generate_population_multiplier(world.population)

    # --- Step 12: Trade Codes ---
    world.trade_codes = assign_trade_codes(
        world.size, world.atmosphere, world.hydrographics,
        world.population, world.government, world.law_level,
        world.tech_level
    )

    # --- Step 13: Travel Zone ---
    world.travel_zone = assign_travel_zone(
        world.atmosphere, world.government, world.law_level, world.starport
    )

    return world


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():  # pylint: disable=too-many-branches
    """Generate and print Traveller mainworlds from the command line."""
    parser = argparse.ArgumentParser(
        description="Generate Traveller (2022) mainworlds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--name",  default=None,
                        help="World name (default: auto-numbered)")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of worlds to generate (default: 1)")
    parser.add_argument("--seed",  type=int, default=None,
                        help="Random seed for reproducible results")
    parser.add_argument("--json", action="store_true",
                        help="Output each world as a JSON document instead "
                             "of the human-readable summary.  When --count "
                             "is greater than 1 the output is a JSON array.")
    parser.add_argument("--html", action="store_true",
                        help="Output each world as a self-contained HTML card "
                             "matching the inline display widget.  When --count "
                             "is greater than 1, cards are concatenated inside a "
                             "single HTML page.")
    args = parser.parse_args()

    if args.json and args.html:
        parser.error("--json and --html are mutually exclusive.")

    rng = random.Random(args.seed) if args.seed is not None else None
    if args.seed is not None and not args.json and not args.html:
        print(f"[Using random seed {args.seed}]\n")

    worlds = []
    for i in range(args.count):
        if args.name and args.count == 1:
            name = args.name
        elif args.name:
            name = f"{args.name}-{i+1}"
        else:
            name = f"World-{i+1}"

        world = generate_world(name=name, seed=args.seed, rng=rng)
        worlds.append(world)

    if args.json:
        # Single world → plain object; multiple worlds → array.
        if len(worlds) == 1:
            print(worlds[0].to_json())
        else:
            payload = [w.to_dict() for w in worlds]
            print(json.dumps(payload, indent=2, ensure_ascii=False))

    elif args.html:
        if len(worlds) == 1:
            print(worlds[0].to_html())
        else:
            print(render("world_list.html",
                         worlds=[_world_html_ctx(w) for w in worlds]))

    else:
        for i, world in enumerate(worlds):
            print(world.summary())
            if i < len(worlds) - 1:
                print()


if __name__ == "__main__":
    main()
