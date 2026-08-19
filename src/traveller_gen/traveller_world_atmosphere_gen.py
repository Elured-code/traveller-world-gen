"""WBH atmosphere phase 1–5 generation (extracted from traveller_world_gen)."""
# pylint: disable=too-many-lines

import math
import random
_rng: random.Random = random  # type: ignore[assignment]
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Private helpers (avoid circular imports with traveller_world_gen)
# ---------------------------------------------------------------------------

_HEX_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_hex(value: int) -> str:
    """Convert an integer to a single Traveller eHex character."""
    value = max(0, min(value, len(_HEX_DIGITS) - 1))
    return _HEX_DIGITS[value]


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
    raw_1d = _rng.randint(1, 6)
    raw_2d = _rng.randint(1, 6) + _rng.randint(1, 6)
    fraction = (raw_1d + dm) / 20 + (raw_2d - 7) / 100
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
        raw_sub = max(2, min(12, _dice(2) + dm))
        subtype_name, subtype_code = _TAINT_SUBTYPE_TABLE[raw_sub]
        if subtype_code == "H" and ppo is not None and ppo <= 0.5:
            continue
        if subtype_code == "L" and ppo is not None and ppo >= 0.1:
            continue
        break
    needs_second = raw_sub == 10

    sev_dm = 4 if subtype_code in _O2_TAINT_CODES else 0
    sev_code = _taint_severity_code(_dice(2) + sev_dm)

    per_dm = (6 if sev_code >= 8 else 4) if subtype_code in _O2_TAINT_CODES else 0
    per_code = _taint_persistence_code(_dice(2) + per_dm)

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
        return _to_hex(code)
    if code in (16, 17):
        return _to_hex(code)
    if code == 15:
        if detail.unusual_subtypes:
            codes = ".".join(
                s.subtype_code for s in detail.unusual_subtypes if s.subtype_code
            )
            return f"F-S{codes}"
        return "F"
    parts = [_to_hex(code)]
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
# NHZ atmosphere generation
# ---------------------------------------------------------------------------

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

    result = max(0, _dice(2) + (-7 + size))

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
