"""
traveller_belt_physical.py
==========================
Physical characteristics for asteroid belts (WBH pp. 131-133).

Scope
-----
Applies to any orbit slot with world_type == "belt", whether a secondary
world slot or the designated mainworld. Called from attach_detail() in
traveller_world_detail.py, which has access to the full system context
needed for the orbital DMs.

Rules implemented
-----------------
Belt Span (WBH p.131):
  Span (AU) = (system orbit spread × 2D) / 10
  "System orbit spread" = (max Orbit# − MAO) / n_orbits — the per-slot step
  used in orbit placement, NOT the AU range of the system.
  DM: +1 if next orbit slot is a gas giant; +2 if belt is the outermost slot.

Belt Composition Percentages (WBH p.132):
  Roll 2D+DM. DM: -4 if belt orbit# < HZCO; +4 if belt orbit# > HZCO+2.
  Result selects per-type formula for m-type (metallic), s-type (silicate),
  and c-type (carbonaceous) percentages. Remainder is "other".
  Normalisation: if m+s+c > 100%, trim m first, then s.

Belt Bulk (WBH p.132):
  Bulk = 2D+2 + DMs, minimum 1.
  DM: -(age_gyr ÷ 2, round down); +(c_type% ÷ 10, round down).

Belt Resource Rating (WBH p.133):
  Rating = 2D-7 + DMs, clamped to [2, 12].
  DMs: +Bulk; +(m_type% ÷ 10, round down); -(c_type% ÷ 10, round down).
  If mainworld has Industrial trade code and TL ≥ 8: subtract 1D (exploitation).

Belt Significant Bodies (WBH p.133):
  Size 1: max(0, 2D-12 + Bulk + DMs)
    DMs: +2 if beyond HZCO+3; -4 if span < 0.1 AU.
  Size S: max(0, (2D - 9 + DM) × (Bulk + 1))
    DMs: +1 if HZCO+2 to +3; +3 if beyond HZCO+3; +1 if span > 1.0 AU.
    If span < 0.1 AU: halve Size S count (round up).
  Optional variance (implemented per WBH): if >50 Size S and outermost orbit,
    multiply by 1D/D3 and add 1D.

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
from typing import Optional

from traveller_world_atmosphere_detail import _compute_mean_temperature

_rng: random.Random = random  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    """Sum of n d6 rolls plus dm, minimum 0."""
    return max(0, sum(_rng.randint(1, 6) for _ in range(n)) + dm)


def _d2() -> int:
    return _rng.randint(1, 2)


def _d3() -> int:
    return (_rng.randint(1, 6) + 1) // 2


# ---------------------------------------------------------------------------
# Belt Composition Table (WBH p.132)
# ---------------------------------------------------------------------------

# Each row: ((m_base, m_mult, m_d3), (s_base, s_mult, s_d3), (c_base, c_mult, c_d3))
# Formula per component: base + die × mult, where die is D3 or D6.
# mult == 0 means fixed value (no die roll).
_COMP_TABLE: list[tuple[tuple, tuple, tuple]] = [
    #                m-type               s-type               c-type      result
    ((60, 5, False), ( 0, 5, False), ( 0, 0, False)),  # 0-
    ((50, 5, False), ( 5, 5, False), ( 0, 1, True )),  # 1  (c = D3)
    ((40, 5, False), (15, 5, False), ( 0, 1, False)),  # 2
    ((25, 5, False), (30, 5, False), ( 0, 1, False)),  # 3
    ((15, 5, False), (35, 5, False), ( 5, 1, False)),  # 4
    (( 5, 5, False), (40, 5, False), ( 5, 2, False)),  # 5
    (( 0, 5, False), (40, 5, False), ( 0, 5, False)),  # 6
    (( 5, 2, False), (35, 5, False), (10, 5, False)),  # 7
    (( 5, 1, False), (30, 5, False), (20, 5, False)),  # 8
    (( 0, 1, False), (15, 5, False), (40, 5, False)),  # 9
    (( 0, 1, False), ( 5, 5, False), (50, 5, False)),  # 10
    (( 0, 1, True ), ( 5, 2, False), (60, 5, False)),  # 11 (m = D3)
    (( 0, 0, False), ( 0, 1, False), (70, 5, False)),  # 12+
]


def _roll_pct(base: int, mult: int, use_d3: bool) -> int:
    """Roll one composition percentage: base + die × mult."""
    if mult == 0:
        return base
    die = _d3() if use_d3 else _rng.randint(1, 6)
    return base + die * mult


def _roll_composition(hz_deviation: float) -> tuple[int, int, int, int]:
    """Roll belt composition percentages (WBH p.132).

    Returns (m_type_pct, s_type_pct, c_type_pct, other_pct).
    """
    dm = 0
    if hz_deviation < 0:
        dm = -4   # inside HZCO — hotter, more metallic
    elif hz_deviation > 2:
        dm = 4    # beyond HZCO+2 — colder, more carbonaceous

    raw = _roll(2, dm)
    row = _COMP_TABLE[max(0, min(raw, 12))]
    m = _roll_pct(*row[0])
    s = _roll_pct(*row[1])
    c = _roll_pct(*row[2])

    # Normalise: trim m first, then s, if total exceeds 100%
    total = m + s + c
    if total > 100:
        excess = total - 100
        m_cut = min(m, excess)
        m -= m_cut
        excess -= m_cut
        s -= min(s, excess)
        other = 0
    else:
        other = 100 - m - s - c

    return m, s, c, other


# ---------------------------------------------------------------------------
# Belt Span (WBH p.131)
# ---------------------------------------------------------------------------

def _roll_belt_span(
        orbit_spread: float,
        next_is_gas_giant: bool,
        is_outermost: bool,
) -> float:
    """Roll belt span in AU."""
    dm = (1 if next_is_gas_giant else 0) + (2 if is_outermost else 0)
    roll = _roll(2, dm)
    return round(orbit_spread * roll / 10, 3)


# ---------------------------------------------------------------------------
# Belt Bulk (WBH p.132)
# ---------------------------------------------------------------------------

def _roll_bulk(age_gyr: float, c_pct: int) -> int:
    """Roll belt bulk (2D+2 + DMs, minimum 1)."""
    dm = -int(age_gyr / 2) + int(c_pct / 10)
    return max(1, _roll(2, 2 + dm))


# ---------------------------------------------------------------------------
# Belt Resource Rating (WBH p.133)
# ---------------------------------------------------------------------------

def _roll_resource_rating(
        bulk: int,
        m_pct: int,
        c_pct: int,
        is_exploited: bool,
) -> int:
    """Roll belt resource rating (2D-7 + DMs, clamped to [2, 12])."""
    dm = bulk + int(m_pct / 10) + math.floor(-c_pct / 10)
    result = _roll(2, -7 + dm)
    if is_exploited:
        result -= _rng.randint(1, 6)
    return max(2, min(12, result))


# ---------------------------------------------------------------------------
# Belt Significant Bodies (WBH p.133)
# ---------------------------------------------------------------------------

def _roll_size_1_bodies(bulk: int, hz_deviation: float, span_au: float) -> int:
    """Roll number of Size 1 planetoids (2D-12 + Bulk + DMs, minimum 0)."""
    dm = 0
    if hz_deviation > 3:
        dm += 2
    if span_au < 0.1:
        dm -= 4
    return _roll(2, -12 + bulk + dm)


def _roll_size_s_bodies(
        bulk: int,
        hz_deviation: float,
        span_au: float,
        is_outermost: bool,
) -> int:
    """Roll number of Size S planetoids ((2D-9+DM) × (Bulk+1), minimum 0)."""
    dm = 0
    if hz_deviation > 3:
        dm += 3
    elif hz_deviation > 2:
        dm += 1
    if span_au > 1.0:
        dm += 1

    roll = _rng.randint(1, 6) + _rng.randint(1, 6)
    count = max(0, (roll - 9 + dm) * (bulk + 1))

    if span_au < 0.1:
        count = math.ceil(count / 2)

    # Optional variance: >50 bodies in outermost orbit
    if count > 50 and is_outermost:
        multiplier = _rng.randint(1, 6) / _d3()
        count = round(count * multiplier + _rng.randint(1, 6))
        count = max(0, count)

    return count


# ---------------------------------------------------------------------------
# BeltPhysical dataclass
# ---------------------------------------------------------------------------

@dataclass
class BeltPhysical:  # pylint: disable=too-many-instance-attributes
    """Physical characteristics for an asteroid belt."""

    inner_au: float      # inner boundary of belt span
    outer_au: float      # outer boundary of belt span
    m_type_pct: int      # metallic percentage
    s_type_pct: int      # silicate (rocky) percentage
    c_type_pct: int      # carbonaceous percentage
    other_pct: int       # residual "other" composition percentage
    bulk: int            # belt bulk (2D2+DMs, min 1)
    resource_rating: int # resource rating (2-12)
    size_1_bodies: int   # count of Size 1 significant planetoids
    size_s_bodies: int   # count of Size S significant planetoids
    mean_temperature_k: int  # Basic Mean Temperature (WBH p.47); atmosphere DM = 0 for belts

    @property
    def profile_str(self) -> str:
        """Belt profile: S-CC.CC.CC.CC-B-R-#-s (WBH Class III shorthand).

        S = span in AU; CC.CC.CC.CC = M/S/C/O composition percentages;
        B = bulk; R = resource rating; # = Size 1 bodies; s = Size S bodies.
        """
        span = round(self.outer_au - self.inner_au, 3)
        comp = (
            f"{self.m_type_pct}.{self.s_type_pct}"
            f".{self.c_type_pct}.{self.other_pct}"
        )
        return (
            f"{span}-{comp}"
            f"-{self.bulk}-{self.resource_rating}"
            f"-{self.size_1_bodies}-{self.size_s_bodies}"
        )

    def to_dict(self) -> dict:
        """Return belt physical characteristics as a JSON-compatible dict."""
        return {
            "inner_au":       self.inner_au,
            "outer_au":       self.outer_au,
            "m_type_pct":     self.m_type_pct,
            "s_type_pct":     self.s_type_pct,
            "c_type_pct":     self.c_type_pct,
            "other_pct":      self.other_pct,
            "bulk":           self.bulk,
            "resource_rating":   self.resource_rating,
            "size_1_bodies":     self.size_1_bodies,
            "size_s_bodies":     self.size_s_bodies,
            "mean_temperature_k": self.mean_temperature_k,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BeltPhysical":
        """Reconstruct a BeltPhysical from a dict produced by to_dict()."""
        return cls(
            inner_au=float(d.get("inner_au", 0.0)),
            outer_au=float(d.get("outer_au", 0.0)),
            m_type_pct=int(d.get("m_type_pct", 0)),
            s_type_pct=int(d.get("s_type_pct", 0)),
            c_type_pct=int(d.get("c_type_pct", 0)),
            other_pct=int(d.get("other_pct", 0)),
            bulk=int(d.get("bulk", 5)),
            resource_rating=int(d.get("resource_rating", 7)),
            size_1_bodies=int(d.get("size_1_bodies", 0)),
            size_s_bodies=int(d.get("size_s_bodies", 0)),
            mean_temperature_k=int(d.get("mean_temperature_k", 0)),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_belt_physical(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        orbit_au: float,
        hz_deviation: float,
        age_gyr: float,
        orbit_spread: float,
        next_is_gas_giant: bool,
        is_outermost: bool,
        is_exploited: bool,
        rng: Optional[random.Random] = None,
) -> BeltPhysical:
    """Generate physical characteristics for an asteroid belt (WBH pp.131-133).

    Parameters
    ----------
    orbit_au : float
        Belt's orbital distance in AU (centre of belt span).
    hz_deviation : float
        orbit_number - HZCO for this star; negative = warmer than HZ.
    age_gyr : float
        System age in Gyr (for bulk DM).
    orbit_spread : float
        Per-slot orbital step size in Orbit# units: (max Orbit# − MAO) / n_orbits.
        This is the WBH "system orbit spread" used in the belt span formula (p.131).
    next_is_gas_giant : bool
        True if the next outward orbit slot is a gas giant (span DM).
    is_outermost : bool
        True if this is the outermost slot in the system (span DM; size S variance).
    is_exploited : bool
        True if the mainworld has the Industrial trade code and TL >= 8
        (resource rating reduction).
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    span_au = _roll_belt_span(orbit_spread, next_is_gas_giant, is_outermost)
    inner_au = round(max(0.0, orbit_au - span_au / 2), 3)
    outer_au = round(orbit_au + span_au / 2, 3)

    m_pct, s_pct, c_pct, other_pct = _roll_composition(hz_deviation)
    bulk = _roll_bulk(age_gyr, c_pct)
    resource = _roll_resource_rating(bulk, m_pct, c_pct, is_exploited)
    size_1 = _roll_size_1_bodies(bulk, hz_deviation, span_au)
    size_s = _roll_size_s_bodies(bulk, hz_deviation, span_au, is_outermost)
    mean_temp = _compute_mean_temperature(hz_deviation, 0)

    return BeltPhysical(
        inner_au=inner_au,
        outer_au=outer_au,
        m_type_pct=m_pct,
        s_type_pct=s_pct,
        c_type_pct=c_pct,
        other_pct=other_pct,
        bulk=bulk,
        resource_rating=resource,
        size_1_bodies=size_1,
        size_s_bodies=size_s,
        mean_temperature_k=mean_temp,
    )
