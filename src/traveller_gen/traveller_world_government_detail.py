"""
traveller_world_government_detail.py
=====================================
Government detail for Traveller mainworlds and secondary worlds, following
the World Builder's Handbook Social Characteristics Checklist (§3).

Implements:
  - Step 1: Degree of Centralisation (Confederal / Federal / Unitary)
  - Step 2: Government Primary Authority (Legislative / Executive / Judicial / Balanced)
  - Step 3: Government Structure (Demos / Single Council / Multiple Councils / Ruler)
  - Government profile string in WBH format G-CAS (or G-CB-LS-ES-JS for Balanced)
  - Internal factions: count, government type, strength, and relationship to ruling body

Government code 0 (no government structure) returns None — no procedures apply.
Government code 7 (Balkanisation) returns None — procedure deferred to issue #130.

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

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GOV_NAMES: dict[int, str] = {
    0: "None",
    1: "Company/Corporation",
    2: "Participating Democracy",
    3: "Self-Perpetuating Oligarchy",
    4: "Representative Democracy",
    5: "Feudal Technocracy",
    6: "Captive Government",
    7: "Balkanisation",
    8: "Civil Service Bureaucracy",
    9: "Impersonal Bureaucracy",
    10: "Charismatic Dictatorship",
    11: "Non-Charismatic Dictatorship",
    12: "Charismatic Oligarchy",
    13: "Religious Dictatorship",
    14: "Religious Autocracy",
    15: "Totalitarian Oligarchy",
}

_AUTHORITY_NAMES: dict[str, str] = {
    "L": "Legislative",
    "E": "Executive",
    "J": "Judicial",
    "B": "Balanced",
}

_STRUCTURE_NAMES: dict[str, str] = {
    "D": "Demos",
    "S": "Single Council",
    "M": "Multiple Councils",
    "R": "Ruler",
}

# Functional Structure table: index = (2D result − 2), clamped to [0, 10]
# Results ≤3 → D; 4 → S; 5,6 → M; 7,8 → R; 9 → M; 10 → S; 11 → M; ≥12 → S
_STRUCT_TABLE: list[str] = ["D", "D", "S", "M", "M", "R", "R", "M", "S", "M", "S"]

# Authority table: 2D+DM result → code; ≤4 → L, ≥12 → E, others by key
_AUTHORITY_TABLE: dict[int, str] = {5: "E", 6: "J", 7: "B", 8: "L", 9: "B", 10: "E", 11: "J"}

# Faction strength: index = (2D result − 2), clamped to [0, 10]
_FACTION_STRENGTH: list[tuple[str, str]] = [
    ("O", "Obscure group"),                     # 2
    ("O", "Obscure group"),                     # 3
    ("F", "Fringe group"),                      # 4
    ("F", "Fringe group"),                      # 5
    ("M", "Minor group"),                       # 6
    ("M", "Minor group"),                       # 7
    ("N", "Notable group"),                     # 8
    ("N", "Notable group"),                     # 9
    ("S", "Significant"),                       # 10
    ("S", "Significant"),                       # 11
    ("P", "Overwhelming popular support"),      # 12
]

# Faction relationship: 1D+DM result clamped to [0, 9]
_FACTION_RELATIONSHIP: dict[int, tuple[str, str]] = {
    0: ("0", "Alliance"),
    1: ("1", "Cooperation"),
    2: ("2", "Truce"),
    3: ("3", "Competition"),
    4: ("4", "Resistance"),
    5: ("5", "Riots"),
    6: ("6", "Uprising"),
    7: ("7", "Insurgency"),
    8: ("8", "War"),
    9: ("9", "Total War"),
}

_ROMAN: list[str] = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV",
]

_EHEX = "0123456789ABCDEF"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Faction:
    """One external faction within a world government."""
    numeral: str            # Roman numeral label (II, III, …)
    government_type: int    # UWP government code (0–F)
    government_name: str    # human-readable government type
    strength_code: str      # O|F|M|N|S|P
    strength_label: str     # e.g. "Fringe group"
    relationship_code: str  # 0–9
    relationship_label: str # e.g. "Competition"

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "numeral": self.numeral,
            "government_type": self.government_type,
            "government_name": self.government_name,
            "strength_code": self.strength_code,
            "strength_label": self.strength_label,
            "relationship_code": self.relationship_code,
            "relationship_label": self.relationship_label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Faction":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            numeral=str(d.get("numeral", "II")),
            government_type=int(d.get("government_type", 0)),
            government_name=str(d.get("government_name", "")),
            strength_code=str(d.get("strength_code", "O")),
            strength_label=str(d.get("strength_label", "")),
            relationship_code=str(d.get("relationship_code", "0")),
            relationship_label=str(d.get("relationship_label", "")),
        )


@dataclass
class GovernmentDetail:  # pylint: disable=too-many-instance-attributes
    """Full WBH Social Characteristics government profile for one world."""
    centralisation_code: str    # "C" | "F" | "U"
    centralisation: str         # "Confederal" | "Federal" | "Unitary"
    authority_code: str         # "L" | "E" | "J" | "B"
    authority: str              # "Legislative" | "Executive" | "Judicial" | "Balanced"
    structure_code: str         # primary function code "D"|"S"|"M"|"R"; "" when Balanced
    structure: str              # primary function label; "" when Balanced
    # For Balanced authority: per-branch structures (all "" for non-Balanced)
    structure_leg_code: str     # Legislative branch code; "" unless authority == "B"
    structure_leg: str          # Legislative branch label
    structure_exec_code: str    # Executive branch code
    structure_exec: str         # Executive branch label
    structure_jud_code: str     # Judicial branch code
    structure_jud: str          # Judicial branch label
    government_profile: str     # e.g. "4-FES" or "4-FB-LS-ES-JS"
    factions: list = field(default_factory=list)  # List[Faction] — external factions only

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        d: dict = {
            "centralisation_code": self.centralisation_code,
            "centralisation": self.centralisation,
            "authority_code": self.authority_code,
            "authority": self.authority,
            "structure_code": self.structure_code,
            "structure": self.structure,
            "government_profile": self.government_profile,
            "factions": [f.to_dict() for f in self.factions],
        }
        if self.structure_leg_code:
            d["structure_leg_code"] = self.structure_leg_code
            d["structure_leg"] = self.structure_leg
            d["structure_exec_code"] = self.structure_exec_code
            d["structure_exec"] = self.structure_exec
            d["structure_jud_code"] = self.structure_jud_code
            d["structure_jud"] = self.structure_jud
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GovernmentDetail":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            centralisation_code=str(d.get("centralisation_code", "F")),
            centralisation=str(d.get("centralisation", "Federal")),
            authority_code=str(d.get("authority_code", "L")),
            authority=str(d.get("authority", "Legislative")),
            structure_code=str(d.get("structure_code", "")),
            structure=str(d.get("structure", "")),
            structure_leg_code=str(d.get("structure_leg_code", "")),
            structure_leg=str(d.get("structure_leg", "")),
            structure_exec_code=str(d.get("structure_exec_code", "")),
            structure_exec=str(d.get("structure_exec", "")),
            structure_jud_code=str(d.get("structure_jud_code", "")),
            structure_jud=str(d.get("structure_jud", "")),
            government_profile=str(d.get("government_profile", "")),
            factions=[Faction.from_dict(f) for f in d.get("factions", [])],
        )


# ---------------------------------------------------------------------------
# Private helpers — Centralisation
# ---------------------------------------------------------------------------

def _centralisation_dm(gov_code: int, pcr: int) -> int:
    """Accumulate DMs for the centralisation roll (WBH §3 Step 1)."""
    dm = 0
    if 2 <= gov_code <= 5:
        dm -= 1
    elif gov_code in (6, 8, 9, 10, 11):   # Government 6, 8–B
        dm += 1
    elif gov_code >= 12:                   # Government C+
        dm += 2
    # Government 7 (Balkanised) also gets DM+1 per faction, but that case is deferred
    if pcr <= 3:
        dm -= 1
    elif 7 <= pcr <= 8:
        dm += 1
    elif pcr == 9:
        dm += 3
    return dm


# ---------------------------------------------------------------------------
# Private helpers — Authority
# ---------------------------------------------------------------------------

def _authority_dm(gov_code: int, centralisation_code: str) -> int:
    """Accumulate DMs for the authority roll (WBH §3 Step 2)."""
    dm = 0
    if gov_code in (1, 6, 10, 13, 14):    # Government 1, 6, A, D, E
        dm += 6
    elif gov_code == 2:
        dm -= 4
    elif gov_code in (3, 5, 12):           # Government 3, 5, C
        dm -= 2
    elif gov_code in (11, 15):             # Government B, F
        dm += 4
    if centralisation_code == "C":
        dm -= 1
    elif centralisation_code == "U":
        dm += 2
    return dm


# ---------------------------------------------------------------------------
# Private helpers — Structure
# ---------------------------------------------------------------------------

def _struct_from_table(result: int) -> str:
    """Map a 2D result to a structure code via the Functional Structure table."""
    return _STRUCT_TABLE[max(0, min(10, result - 2))]


def _roll_one_structure(gov_code: int, is_legislative: bool) -> str:  # pylint: disable=too-many-return-statements
    """Roll structure for one government function branch (WBH §3 Step 3).

    is_legislative: True when rolling the legislative branch (matters for the
    special rule that applies to non-special governments with legislative authority).
    """
    # Government 2: always Demos
    if gov_code == 2:
        return "D"
    # Government 3 or F (15): 1D, 1–4 = Single Council, 5–6 = Multiple Councils
    if gov_code in (3, 15):
        return "S" if _rng.randint(1, 6) <= 4 else "M"
    # Government A, B, D, E (10, 11, 13, 14): 1D, 1–5 = Ruler, 6 = Single Council
    if gov_code in (10, 11, 13, 14):
        return "R" if _rng.randint(1, 6) <= 5 else "S"
    # All other governments with legislative function: 2D, 2–3=D, 4–8=M, 9+=S
    if is_legislative:
        r = _rng.randint(1, 6) + _rng.randint(1, 6)
        if r <= 3:
            return "D"
        if r <= 8:
            return "M"
        return "S"
    # General case: 2D on Functional Structure table
    return _struct_from_table(_rng.randint(1, 6) + _rng.randint(1, 6))


# ---------------------------------------------------------------------------
# Private helpers — Factions
# ---------------------------------------------------------------------------

def _d3() -> int:
    """Roll D3 (ceil of 1D/2): 1, 2, or 3."""
    return (_rng.randint(1, 6) + 1) // 2


def _faction_count_dm(gov_code: int) -> int:
    """DM for the faction count roll."""
    if gov_code in (0, 7):
        return 1
    if gov_code >= 10:    # Government A+
        return -1
    return 0


def _roll_faction_gov(pop_code: int) -> int:
    """Roll a government code for a faction using the world's population code.

    Rerolled or clamped away from 7 to avoid cascading Balkanised sub-factions.
    """
    result = max(0, min(13, _rng.randint(1, 6) + _rng.randint(1, 6) - 7 + pop_code))
    if result == 7:
        result = 6   # clamp to Captive Government rather than spawning sub-factions
    return result


def _roll_faction_strength() -> tuple[str, str]:
    """Roll faction strength (2D). Returns (code, label)."""
    result = max(2, min(12, _rng.randint(1, 6) + _rng.randint(1, 6)))
    return _FACTION_STRENGTH[result - 2]


def _roll_faction_relationship(same_gov_code: bool) -> tuple[str, str]:
    """Roll faction relationship to the ruling government (1D+DM).

    DM+1 between ruling faction and all external factions (WBH table).
    DM-1 when the faction has the same government code as the ruling body.
    Returns (code, label).
    """
    dm = 1   # ruling vs external: always DM+1
    if same_gov_code:
        dm -= 1
    result = max(0, min(9, _rng.randint(1, 6) + dm))
    return _FACTION_RELATIONSHIP[result]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_centralisation(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        gov_code: int, pcr: int = 0,
        rng: Optional[random.Random] = None) -> tuple[str, str]:
    """Roll Degree of Centralisation (WBH §3 Step 1).

    Returns (centralisation_code, centralisation_label).
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    dm = _centralisation_dm(gov_code, pcr)
    result = _rng.randint(1, 6) + _rng.randint(1, 6) + dm
    if result <= 5:
        return "C", "Confederal"
    if result <= 8:
        return "F", "Federal"
    return "U", "Unitary"


def generate_authority(
        gov_code: int, centralisation_code: str,
        rng: Optional[random.Random] = None) -> tuple[str, str]:
    """Roll Government Primary Authority (WBH §3 Step 2).

    Returns (authority_code, authority_label).
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    dm = _authority_dm(gov_code, centralisation_code)
    result = _rng.randint(1, 6) + _rng.randint(1, 6) + dm
    if result <= 4:
        code = "L"
    elif result >= 12:
        code = "E"
    else:
        code = _AUTHORITY_TABLE.get(result, "L")
    return code, _AUTHORITY_NAMES[code]


def generate_factions(
        gov_code: int, pop_code: int,
        rng: Optional[random.Random] = None) -> list:
    """Generate external factions for one world (WBH §3 Factions).

    Returns List[Faction].  The ruling government itself (faction I) is not
    included; only challenger factions (II, III, …) are returned.
    A result of ≤1 from the D3+DM roll means no significant external factions.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    dm = _faction_count_dm(gov_code)
    count = _d3() + dm
    if count <= 1:
        return []
    factions = []
    for i in range(count - 1):
        numeral = _ROMAN[i + 1] if (i + 1) < len(_ROMAN) else f"F{i + 2}"
        faction_gov = _roll_faction_gov(pop_code)
        s_code, s_label = _roll_faction_strength()
        same_gov = faction_gov == gov_code
        r_code, r_label = _roll_faction_relationship(same_gov)
        factions.append(Faction(
            numeral=numeral,
            government_type=faction_gov,
            government_name=_GOV_NAMES.get(faction_gov, "Unknown"),
            strength_code=s_code,
            strength_label=s_label,
            relationship_code=r_code,
            relationship_label=r_label,
        ))
    return factions


def generate_government_detail(  # pylint: disable=too-many-locals
        gov_code: int,
        pop_code: int,
        pcr: int = 0,
        rng: Optional[random.Random] = None,
) -> Optional[GovernmentDetail]:
    """Generate a full WBH government profile for one inhabited world.

    Returns None for gov_code 0 (no government — WBH: procedures unnecessary)
    or gov_code 7 (Balkanisation — deferred to issue #130).

    Parameters
    ----------
    gov_code : int
        UWP government code (0–F).
    pop_code : int
        UWP population code; used for rolling faction government types.
    pcr : int
        Population Concentration Rating from §2; used for centralisation DMs.
        Defaults to 0 when population detail has not been generated.
    rng : random.Random, optional
        Injectable RNG; writes to module-level sentinel when provided.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if gov_code in (0, 7):
        return None

    c_code, c_label = generate_centralisation(gov_code, pcr)
    a_code, a_label = generate_authority(gov_code, c_code)

    # Step 3: Structure
    if a_code == "B":
        sl = _roll_one_structure(gov_code, is_legislative=True)
        se = _roll_one_structure(gov_code, is_legislative=False)
        sj = _roll_one_structure(gov_code, is_legislative=False)
        struct_code, struct_label = "", ""
        sl_code, sl_lbl = sl, _STRUCTURE_NAMES[sl]
        se_code, se_lbl = se, _STRUCTURE_NAMES[se]
        sj_code, sj_lbl = sj, _STRUCTURE_NAMES[sj]
    else:
        s = _roll_one_structure(gov_code, is_legislative=a_code == "L")
        struct_code, struct_label = s, _STRUCTURE_NAMES[s]
        sl_code = sl_lbl = se_code = se_lbl = sj_code = sj_lbl = ""

    factions = generate_factions(gov_code, pop_code)

    # Build government profile string
    g_hex = _EHEX[gov_code] if gov_code < len(_EHEX) else str(gov_code)
    if a_code == "B":
        profile = f"{g_hex}-{c_code}B-L{sl_code}-E{se_code}-J{sj_code}"
    else:
        profile = f"{g_hex}-{c_code}{a_code}{struct_code}"

    return GovernmentDetail(
        centralisation_code=c_code,
        centralisation=c_label,
        authority_code=a_code,
        authority=a_label,
        structure_code=struct_code,
        structure=struct_label,
        structure_leg_code=sl_code,
        structure_leg=sl_lbl,
        structure_exec_code=se_code,
        structure_exec=se_lbl,
        structure_jud_code=sj_code,
        structure_jud=sj_lbl,
        government_profile=profile,
        factions=factions,
    )


def _gov_detail_for_det(det: object) -> Optional[GovernmentDetail]:  # type: ignore[type-arg]
    """Generate GovernmentDetail for a WorldDetail object (secondary world)."""
    gov_code: int = getattr(det, "government", 0)
    pop_code: int = getattr(det, "population", 0)
    pop_detail = getattr(det, "population_detail", None)
    pcr: int = pop_detail.pcr if pop_detail is not None else 0
    return generate_government_detail(gov_code, pop_code, pcr=pcr, rng=None)


def _attach_det_government(det: object) -> None:  # type: ignore[type-arg]
    """Attach government detail to one WorldDetail and its inhabited moons."""
    det.government_detail = _gov_detail_for_det(det)  # type: ignore[attr-defined]
    for moon in getattr(det, "moons", []):
        moon_det = getattr(moon, "detail", None)
        if moon_det is not None and getattr(moon_det, "inhabited", False):
            moon_det.government_detail = _gov_detail_for_det(moon_det)


def attach_government_detail(
        system: "TravellerSystem",
        rng: Optional[random.Random] = None,
) -> None:
    """Attach government detail to mainworld and all inhabited secondaries.

    Calls generate_government_detail() for system.mainworld when inhabited.
    Also applies to each inhabited secondary WorldDetail and moon WorldDetail.
    Uses population_detail.pcr when available; falls back to pcr=0.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    mw = system.mainworld
    if mw is not None and mw.population > 0:
        pcr = mw.population_detail.pcr if mw.population_detail is not None else 0
        mw.government_detail = generate_government_detail(
            mw.government, mw.population, pcr=pcr, rng=None,
        )

    for orbit in system.system_orbits.orbits:
        if orbit.is_mainworld_candidate:
            continue
        det = orbit.detail
        if det is None or not det.inhabited:
            continue
        _attach_det_government(det)
