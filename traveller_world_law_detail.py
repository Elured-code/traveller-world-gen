"""
traveller_world_law_detail.py
==============================
Law detail for Traveller mainworlds, following the World Builder's Handbook
Social Characteristics Checklist (§3, pp.163-168).

Implements:
  - Judicial system: Primary and Secondary system codes (I/A/T)
  - Law uniformity: Patchy / Typical / Uniform (P/T/U)
  - Presumption of innocence and death penalty flags
  - Justice profile string in WBH format PSU-I-D (e.g. 'AIT-Y-N')
  - Law subcategory scores: Weapons, Economic, Criminal, Private, Personal Rights
  - Law profile string in WBH format O-WECPR (e.g. '7-86755')

Law level 0 (no law) returns None — no procedures apply.
Secondary world law detail is deferred to issue #135.

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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_JUDICIAL_NAMES: dict[str, str] = {
    "I": "Inquisitorial",
    "A": "Adversarial",
    "T": "Tribunal",
}

_UNIFORMITY_NAMES: dict[str, str] = {
    "P": "Patchy",
    "T": "Typical",
    "U": "Uniform",
}


def _to_hex(value: int) -> str:
    """Convert an integer to a Traveller eHex character (0-Z)."""
    value = max(0, min(value, len(_EHEX) - 1))
    return _EHEX[value]


def _roll2d() -> int:
    return sum(_rng.randint(1, 6) for _ in range(2))


def _roll1d() -> int:
    return _rng.randint(1, 6)


def _roll2d3() -> int:
    """Roll two D3 (1-3), returning sum 2-6."""
    return sum(_rng.randint(1, 3) for _ in range(2))


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class LawDetail:  # pylint: disable=too-many-instance-attributes
    """Full WBH law profile for one mainworld."""
    judicial_primary:         str   # 'I' | 'A' | 'T'
    judicial_secondary:       str   # 'I' | 'A' | 'T'
    law_uniformity:           str   # 'P' | 'T' | 'U'
    presumption_of_innocence: bool
    death_penalty:            bool
    justice_profile:          str   # WBH format PSU-I-D, e.g. 'AIT-Y-N'
    law_weapons:              int   # clamped [0, 18]
    law_economic:             int
    law_criminal:             int
    law_private:              int
    law_personal_rights:      int
    law_profile:              str   # WBH format O-WECPR, e.g. '7-86755'

    @property
    def judicial_primary_label(self) -> str:
        """Human-readable label for judicial_primary."""
        return _JUDICIAL_NAMES.get(self.judicial_primary, "")

    @property
    def judicial_secondary_label(self) -> str:
        """Human-readable label for judicial_secondary."""
        return _JUDICIAL_NAMES.get(self.judicial_secondary, "")

    @property
    def law_uniformity_label(self) -> str:
        """Human-readable label for law_uniformity."""
        return _UNIFORMITY_NAMES.get(self.law_uniformity, "")

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "judicial_primary": self.judicial_primary,
            "judicial_primary_label": self.judicial_primary_label,
            "judicial_secondary": self.judicial_secondary,
            "judicial_secondary_label": self.judicial_secondary_label,
            "law_uniformity": self.law_uniformity,
            "law_uniformity_label": self.law_uniformity_label,
            "presumption_of_innocence": self.presumption_of_innocence,
            "death_penalty": self.death_penalty,
            "justice_profile": self.justice_profile,
            "law_weapons": self.law_weapons,
            "law_economic": self.law_economic,
            "law_criminal": self.law_criminal,
            "law_private": self.law_private,
            "law_personal_rights": self.law_personal_rights,
            "law_profile": self.law_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LawDetail":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            judicial_primary=str(d.get("judicial_primary", "A")),
            judicial_secondary=str(d.get("judicial_secondary", "A")),
            law_uniformity=str(d.get("law_uniformity", "T")),
            presumption_of_innocence=bool(d.get("presumption_of_innocence", True)),
            death_penalty=bool(d.get("death_penalty", False)),
            justice_profile=str(d.get("justice_profile", "")),
            law_weapons=int(d.get("law_weapons", 0)),
            law_economic=int(d.get("law_economic", 0)),
            law_criminal=int(d.get("law_criminal", 0)),
            law_private=int(d.get("law_private", 0)),
            law_personal_rights=int(d.get("law_personal_rights", 0)),
            law_profile=str(d.get("law_profile", "")),
        )


# ---------------------------------------------------------------------------
# Private helpers — Judicial system
# ---------------------------------------------------------------------------

def _judicial_dm(gov_code: int, law_level: int, tech_level: int,
                 gov_authority_code: str) -> int:
    """Accumulate DMs for the primary judicial system roll (WBH §3)."""
    dm = 0
    # Gov 1, 8-12, 15: corporate/bureaucratic/totalitarian → adversarial bias
    if gov_code in (1, 8, 9, 10, 11, 12, 15):
        dm -= 2
    # Gov 13, 14: religious dictatorship/autocracy → inquisitorial bias
    elif gov_code in (13, 14):
        dm += 4
    # High law level → inquisitorial tendency
    if law_level >= 10:
        dm -= 4
    # Low TL → inquisitorial tendency
    if tech_level == 0:
        dm += 4
    elif tech_level <= 2:
        dm += 2
    # Judicial primary authority → adversarial bias
    if gov_authority_code == "J":
        dm -= 2
    return dm


def _judicial_code(result: int) -> str:
    """Map a 2D+DM result to a judicial system code."""
    if result <= 5:
        return "I"
    if result <= 8:
        return "A"
    return "T"


# ---------------------------------------------------------------------------
# Private helpers — Uniformity
# ---------------------------------------------------------------------------

def _uniformity_dm(gov_code: int) -> int:
    """Accumulate DMs for the law uniformity roll (WBH §3)."""
    dm = 0
    if gov_code == 2:
        dm += 1
    elif gov_code in (3, 5) or gov_code >= 10:
        dm -= 1
    return dm


def _uniformity_code(result: int) -> str:
    """Map a 1D+DM result to a law uniformity code."""
    if result <= 2:
        return "P"
    if result == 3:
        return "T"
    return "U"


# ---------------------------------------------------------------------------
# Private helpers — Subcategory scores
# ---------------------------------------------------------------------------

def _subcategory(base: int, dm: int) -> int:
    """Roll 2D3-4 + base + dm, clamped to [0, 18]."""
    raw = base + _roll2d3() - 4 + dm
    return max(0, min(18, raw))


# ---------------------------------------------------------------------------
# Public generator
# ---------------------------------------------------------------------------

def generate_law_detail(  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
        law_level: int,
        gov_code: int,
        tech_level: int = 0,
        pcr: int = 0,
        gov_authority_code: str = "",
        rng: Optional[random.Random] = None,
) -> Optional[LawDetail]:
    """Generate a full WBH law profile for one inhabited mainworld.

    Returns None for law_level 0 (no law — WBH: procedures unnecessary).

    Parameters
    ----------
    law_level : int
        UWP law level code (0–J).
    gov_code : int
        UWP government code (0–F); used for judicial and subcategory DMs.
    tech_level : int
        UWP tech level; used for judicial DMs.
    pcr : int
        Population Concentration Rating from §2; used for subcategory DMs.
        Defaults to 0 when population detail has not been generated.
    gov_authority_code : str
        Government authority code from GovernmentDetail ('L'|'E'|'J'|'B');
        used for judicial DM. Pass '' when government detail is unavailable.
    rng : random.Random, optional
        Injectable RNG; writes to module-level sentinel when provided.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if law_level == 0:
        return None

    # Step 1: Primary judicial system (2D + DMs)
    jdm = _judicial_dm(gov_code, law_level, tech_level, gov_authority_code)
    j_primary = _judicial_code(_roll2d() + jdm)

    # Step 2: Secondary judicial system (2D, no extra DMs)
    j_secondary = _judicial_code(_roll2d())

    # Step 3: Law uniformity (1D + DMs)
    udm = _uniformity_dm(gov_code)
    uniformity = _uniformity_code(_roll1d() + udm)

    # Step 4: Presumption of innocence (2D − law_level + DMs ≥ 0 → Yes)
    poi_dm = -law_level + (2 if j_primary == "A" else 0)
    presumption = (_roll2d() + poi_dm) >= 0

    # Step 5: Death penalty (2D + DMs ≥ 8 → Yes)
    dp_dm = 0
    if gov_code == 0:
        dp_dm -= 4
    if law_level >= 9:
        dp_dm += 4
    death_penalty = (_roll2d() + dp_dm) >= 8

    # Step 6: Law subcategory scores (law_level + 2D3-4 + DMs, clamped [0,18])
    w_dm = -1 if pcr <= 3 else (1 if pcr >= 8 else 0)
    e_dm = {0: -2, 1: 2, 2: -1, 9: 1}.get(gov_code, 0)
    c_dm = 1 if j_primary == "I" else 0
    p_dm = -1 if gov_code in (3, 5, 12) else 0
    r_dm = 2 if gov_code == 1 else (-1 if gov_code in (0, 2) else 0)

    law_weapons       = _subcategory(law_level, w_dm)
    law_economic      = _subcategory(law_level, e_dm)
    law_criminal      = _subcategory(law_level, c_dm)
    law_private       = _subcategory(law_level, p_dm)
    law_personal_rights = _subcategory(law_level, r_dm)

    # Profile strings
    poi_ch = "Y" if presumption else "N"
    dp_ch  = "Y" if death_penalty else "N"
    justice_profile = f"{j_primary}{j_secondary}{uniformity}-{poi_ch}-{dp_ch}"
    law_profile = (
        f"{_to_hex(law_level)}-"
        f"{_to_hex(law_weapons)}"
        f"{_to_hex(law_economic)}"
        f"{_to_hex(law_criminal)}"
        f"{_to_hex(law_private)}"
        f"{_to_hex(law_personal_rights)}"
    )

    return LawDetail(
        judicial_primary=j_primary,
        judicial_secondary=j_secondary,
        law_uniformity=uniformity,
        presumption_of_innocence=presumption,
        death_penalty=death_penalty,
        justice_profile=justice_profile,
        law_weapons=law_weapons,
        law_economic=law_economic,
        law_criminal=law_criminal,
        law_private=law_private,
        law_personal_rights=law_personal_rights,
        law_profile=law_profile,
    )


def attach_law_detail(
        system: "TravellerSystem",
        rng: Optional[random.Random] = None,
) -> None:
    """Attach law detail to the mainworld only.

    Secondary world law detail is deferred to issue #135.
    No-op when mainworld is uninhabited or has law_level 0.
    Uses government_detail.authority_code when available; falls back to ''.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    mw = system.mainworld
    if mw is None or mw.population == 0:
        return

    pop_det = mw.population_detail  # type: ignore[attr-defined]
    pcr = pop_det.pcr if pop_det is not None else 0
    gov_auth = (
        mw.government_detail.authority_code  # type: ignore[attr-defined]
        if mw.government_detail is not None else ""
    )
    mw.law_detail = generate_law_detail(  # type: ignore[attr-defined]
        mw.law_level, mw.government, mw.tech_level,  # type: ignore[attr-defined]
        pcr=pcr,
        gov_authority_code=gov_auth,
        rng=None,
    )
