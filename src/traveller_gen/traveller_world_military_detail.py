"""traveller_world_military_detail.py — WBH §9 military detail generation.

Computes military branch existence and effect, state of readiness, military
budget, and military profile string for the mainworld.

Session 138 — Issue #102.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

# pylint: disable=locally-disabled,suppressed-message

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# eHex encoding (0-9 then A-J for 10-18, matching WBH Effect cap of 18)
# ---------------------------------------------------------------------------
_EHEX = "0123456789ABCDEFGHIJ"

def _to_ehex(value: int) -> str:
    idx = max(0, min(value, len(_EHEX) - 1))
    return _EHEX[idx]


# ---------------------------------------------------------------------------
# Minimum TL required for each branch to exist (WBH §9 Branch Descriptions)
# ---------------------------------------------------------------------------
_BRANCH_MIN_TL: dict[str, int] = {
    "enforcement":    0,
    "militia":        0,
    "army":           0,
    "wet_navy":       0,
    "air_force":      4,
    "system_defence": 7,
    "navy":           8,
    "marines":        8,
}

# ---------------------------------------------------------------------------
# State of readiness
# ---------------------------------------------------------------------------
_READINESS_TABLE: list[tuple[int, str, float]] = [
    # (min_roll, label, budget_multiplier)
    (13, "Total war: full mobilisation",              5.0),
    (11, "War or internal insurgency",                2.0),
    (9,  "Heightened tensions, threat of war",        1.2),
    (6,  "Normal readiness",                          1.0),
    (4,  "Low threat level",                          0.75),
    (0,  "Complacent peace",                          0.5),
]

def _militancy_sor_dm(militancy: int) -> int:
    """DM on State of Readiness roll from Militancy trait."""
    if militancy <= 2:
        return -4
    if militancy <= 5:
        return -1
    if militancy <= 8:
        return 1
    if militancy <= 11:
        return 2
    return 4


def _roll_state_of_readiness(militancy: int) -> tuple[str, float]:
    """Roll 2D + Militancy DM and return (label, budget_multiplier)."""
    dm  = _militancy_sor_dm(militancy)
    raw = sum(_rng.randint(1, 6) for _ in range(2)) + dm
    for min_roll, label, mult in _READINESS_TABLE:
        if raw >= min_roll:
            return label, mult
    return _READINESS_TABLE[-1][1], _READINESS_TABLE[-1][2]


def _is_heightened_or_worse(label: str) -> bool:
    """True when state of readiness implies active/potential warfare."""
    return label in (
        "Heightened tensions, threat of war",
        "War or internal insurgency",
        "Total war: full mobilisation",
    )


def _wartime_dm(readiness_label: str) -> int:
    """Additional DM applied to all branch rolls when at war/tension."""
    if readiness_label == "Total war: full mobilisation":
        return 8
    if readiness_label == "War or internal insurgency":
        return 4
    if readiness_label == "Heightened tensions, threat of war":
        return 1
    return 0


# ---------------------------------------------------------------------------
# Militancy DM applied to all branch existence rolls
# ---------------------------------------------------------------------------
def _militancy_branch_dm(militancy: int) -> int:
    if militancy <= 2:
        return -4
    if militancy <= 5:
        return -1
    if militancy <= 8:
        return 1
    if militancy <= 11:
        return 2
    return 4


# ---------------------------------------------------------------------------
# Branch existence roll helpers
# ---------------------------------------------------------------------------

def _roll_branch(dm: int) -> tuple[bool, int]:
    """Roll 2D + DM. Exists on 4+. Returns (exists, effect).

    Effect = max(1, roll - 3) when the branch exists; 0 otherwise.
    Effects above 18 are capped at 18 (J) per WBH p.202.
    """
    raw = _rng.randint(1, 6) + _rng.randint(1, 6) + dm
    if raw < 4:
        return False, 0
    effect = min(18, max(1, raw - 3))
    return True, effect


# ---------------------------------------------------------------------------
# Enforcement Branch (always exists — Effect = 3 + DMs, min 1)
# ---------------------------------------------------------------------------

def _enforcement_effect(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    government: int,
    law_level: int,
    pcr: int,
    militancy: int,
    readiness_label: str,
    factional_uprisings: bool,
) -> int:
    dm = 0
    if government == 0:
        dm -= 5
    elif government == 11:  # B
        dm += 2
    if law_level == 0:
        dm -= 4
    elif law_level == 1:
        dm -= 2
    elif law_level == 2:
        dm -= 1
    elif 9 <= law_level <= 11:  # 9-B
        dm += 2
    elif law_level >= 12:       # C+
        dm += 4
    if pcr <= 4:
        dm += 2
    if factional_uprisings:
        dm += 2
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return min(18, max(1, 3 + dm))


# ---------------------------------------------------------------------------
# Militia Branch
# ---------------------------------------------------------------------------

def _militia_dm(
    government: int,
    law_level: int,
    pcr: int,
    militancy: int,
    readiness_label: str,
) -> int:
    dm = 0
    if government == 1:
        dm -= 4
    elif government == 2:
        dm += 2
    elif government == 6:
        dm -= 6
    dm -= law_level   # DM = -Law Level
    if pcr <= 2:
        dm += 2
    elif pcr <= 4:
        dm += 1
    elif pcr >= 6:
        dm -= 1
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Army Branch
# ---------------------------------------------------------------------------

def _army_dm(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    government: int,
    tech_level: int,
    has_military_base: bool,
    militia_exists: bool,
    militancy: int,
    readiness_label: str,
    risk: bool,
    factional_uprisings: bool,
) -> int:
    dm = 0
    if militia_exists:
        dm -= 2
    if government == 0:
        dm -= 6
    elif government == 7:
        dm += 4
    elif government >= 10:  # A+
        dm += 4
    if tech_level <= 7:
        dm += 4
    elif tech_level >= 8:
        dm -= 2
    if has_military_base:
        dm += 6
    if risk:
        dm += 2
    if factional_uprisings:
        dm += 2
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Wet Navy Branch
# ---------------------------------------------------------------------------

def _wet_navy_dm(
    hydrographics: int,
    government: int,
    tech_level: int,
    militancy: int,
    readiness_label: str,
) -> int:
    dm = 0
    if hydrographics == 0:
        dm -= 20
    elif hydrographics <= 3:
        dm -= 5
    elif hydrographics == 8:
        dm += 2
    elif hydrographics == 9:
        dm += 4
    elif hydrographics >= 10:
        dm += 8
    if government == 7:
        dm += 4
    if tech_level == 0:
        dm -= 8
    elif tech_level <= 9:
        dm -= 2
    elif tech_level >= 10:
        dm -= tech_level  # DM = -TL
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Air Force Branch
# ---------------------------------------------------------------------------

def _air_force_dm(
    atmosphere: int,
    government: int,
    tech_level: int,
    militancy: int,
    readiness_label: str,
) -> int:
    dm = 0
    if tech_level <= 2:
        dm -= 20
    elif tech_level == 3:
        dm -= 10
    elif 10 <= tech_level <= 12:
        dm -= 4
    elif tech_level >= 13:
        dm -= 6

    if tech_level <= 8:
        if atmosphere in (0, 1):
            dm -= 20
        elif atmosphere in (2, 3, 14):  # 14 = E (exotic)
            dm -= 8
        elif atmosphere in (4, 5):
            dm -= 2

    if government == 7:
        dm += 4
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# System Defence Branch
# ---------------------------------------------------------------------------

def _system_defence_dm(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
    population: int,
    tech_level: int,
    starport: str,
    has_highport: bool,
    has_naval_base: bool,
    has_military_base: bool,
    militancy: int,
    readiness_label: str,
    risk: bool,
) -> int:
    dm = 0
    if population <= 3:
        dm -= 6
    elif population <= 5:
        dm -= 2
    if tech_level <= 5:
        dm -= 20
    elif tech_level == 6:
        dm -= 8
    elif tech_level == 7:
        dm -= 6
    elif tech_level == 8:
        dm -= 2
    sp = starport.upper()
    if sp == "A":
        dm += 4
    elif sp == "B":
        dm += 2
    elif sp == "C":
        dm += 1
    elif sp == "E":
        dm -= 2
    elif sp == "X":
        dm -= 8
    if has_highport:
        dm += 2
    if has_naval_base:
        dm += 4
    if has_military_base:
        dm += 2
    if risk:
        dm += 2
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Navy Branch
# ---------------------------------------------------------------------------

def _navy_dm(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
    population: int,
    tech_level: int,
    starport: str,
    has_highport: bool,
    has_naval_base: bool,
    has_military_base: bool,
    expansionism: int,
    militancy: int,
    readiness_label: str,
    risk: bool,
) -> int:
    dm = 0
    if population <= 3:
        dm -= 6
    elif population <= 6:
        dm -= 3
    if tech_level <= 5:
        dm -= 20
    elif tech_level == 6:
        dm -= 12
    elif tech_level == 7:
        dm -= 8
    elif tech_level == 8:
        dm -= 6
    sp = starport.upper()
    if sp == "A":
        dm += 4
    elif sp == "B":
        dm += 1
    elif sp == "E":
        dm -= 2
    elif sp == "X":
        dm -= 8
    if has_highport:
        dm += 2
    if has_naval_base:
        dm += 4
    if has_military_base:
        dm += 2
    if expansionism <= 5:
        dm -= 2
    elif expansionism >= 9:
        dm += 2
    if expansionism >= 12:
        dm += 2  # C+ gives +4 total
    if risk:
        dm += 2
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Marines Branch
# ---------------------------------------------------------------------------

def _marines_dm(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    population: int,
    tech_level: int,
    has_naval_base: bool,
    has_military_base: bool,
    navy_exists: bool,
    system_defence_exists: bool,
    expansionism: int,
    militancy: int,
    readiness_label: str,
    risk: bool,
) -> int:
    dm = 0
    if population <= 5:
        dm -= 4
    if tech_level <= 8:
        dm -= 6
    if has_naval_base:
        dm += 2
    if has_military_base:
        dm += 2
    if not navy_exists:
        dm -= 6
    if not system_defence_exists:
        dm -= 6
    if expansionism <= 5:
        dm -= 4
    elif 9 <= expansionism <= 11:
        dm += 1
    elif expansionism >= 12:
        dm += 2
    if risk:
        dm += 2
    dm += _militancy_branch_dm(militancy)
    dm += _wartime_dm(readiness_label)
    return dm


# ---------------------------------------------------------------------------
# Military Budget
# ---------------------------------------------------------------------------

def _budget_gov_dm(government: int, has_military_base: bool) -> int:  # pylint: disable=too-many-return-statements
    if government in (0, 2, 4):
        return -2
    if government == 5:
        return 1
    if government == 6:
        # Owning-world DMs unknown; apply DM+8 if military base present
        return 8 if has_military_base else 0
    if government == 9:
        return -1
    if government in (10, 15):  # A or F
        return 3
    if government in (11, 12, 14):  # B, C or E
        return 2
    return 0


def _compute_budget(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    government: int,
    law_level: int,
    has_naval_base: bool,
    has_military_base: bool,
    militancy: int,
    efficiency_factor: int,
    gwp_total_mcr: float,
    branches: dict[str, "MilitaryBranch"],
) -> tuple[float, float]:
    """Return (budget_pct, budget_total_mcr)."""
    total_effect = sum(b.effect for b in branches.values())
    dm = 0
    dm += _budget_gov_dm(government, has_military_base)
    if law_level >= 12:   # C+
        dm += 2
    if has_military_base:
        dm += 4
    if has_naval_base:
        dm += 2
    dm += (militancy - 5)  # DM = Militancy - 5
    dm += -4 + math.floor(total_effect / 10)  # Branches DM

    raw = _rng.randint(1, 6) + _rng.randint(1, 6) - 7 + dm
    clamped = max(-9, raw)
    budget_pct = 2.0 * (1.0 + efficiency_factor / 10.0) * (1.0 + clamped / 10.0)
    budget_pct = max(0.0, budget_pct)
    budget_total = gwp_total_mcr * budget_pct / 100.0
    return round(budget_pct, 4), round(budget_total, 2)


# ---------------------------------------------------------------------------
# Military Profile string
# ---------------------------------------------------------------------------

def _military_profile(branches: dict[str, "MilitaryBranch"], budget_pct: float) -> str:
    """Build WBH military profile string: EMAWF-SNM:#.##%."""
    order = ["enforcement", "militia", "army", "wet_navy", "air_force",
             "system_defence", "navy", "marines"]
    digits = [_to_ehex(branches[b].effect) for b in order]
    surface = "".join(digits[:5])
    space   = "".join(digits[5:])
    return f"{surface}-{space}:{budget_pct:.2f}%"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MilitaryBranch:
    """Existence and Effect for one military branch."""
    exists: bool
    effect: int   # 0 when absent; 1–18 (eHex 0–J) when present

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {"exists": self.exists, "effect": self.effect}

    @classmethod
    def from_dict(cls, d: dict) -> "MilitaryBranch":
        """Reconstruct from a to_dict() output."""
        return cls(exists=bool(d.get("exists", False)),
                   effect=int(d.get("effect", 0)))


@dataclass
class MilitaryDetail:  # pylint: disable=too-many-instance-attributes
    """WBH §9 military characteristics for one inhabited mainworld.

    Fields
    ------
    enforcement / militia / army / wet_navy / air_force
    system_defence / navy / marines
        Existence flag and Effect value for each branch.
    state_of_readiness          : text label (e.g. "Normal readiness")
    state_of_readiness_modifier : budget multiplier (0.5 – 5.0)
    military_budget_pct         : basic military budget as % of GWP
    military_budget_total_mcr   : total budget in MCr (GWP × pct × readiness)
    military_profile            : WBH profile string e.g. "53210-321:2.40%"
    """
    enforcement:                 MilitaryBranch
    militia:                     MilitaryBranch
    army:                        MilitaryBranch
    wet_navy:                    MilitaryBranch
    air_force:                   MilitaryBranch
    system_defence:              MilitaryBranch
    navy:                        MilitaryBranch
    marines:                     MilitaryBranch
    state_of_readiness:          str
    state_of_readiness_modifier: float
    military_budget_pct:         float
    military_budget_total_mcr:   float
    military_profile:            str

    def _branches(self) -> dict[str, MilitaryBranch]:
        return {
            "enforcement":    self.enforcement,
            "militia":        self.militia,
            "army":           self.army,
            "wet_navy":       self.wet_navy,
            "air_force":      self.air_force,
            "system_defence": self.system_defence,
            "navy":           self.navy,
            "marines":        self.marines,
        }

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        return {
            "enforcement":                 self.enforcement.to_dict(),
            "militia":                     self.militia.to_dict(),
            "army":                        self.army.to_dict(),
            "wet_navy":                    self.wet_navy.to_dict(),
            "air_force":                   self.air_force.to_dict(),
            "system_defence":              self.system_defence.to_dict(),
            "navy":                        self.navy.to_dict(),
            "marines":                     self.marines.to_dict(),
            "state_of_readiness":          self.state_of_readiness,
            "state_of_readiness_modifier": self.state_of_readiness_modifier,
            "military_budget_pct":         self.military_budget_pct,
            "military_budget_total_mcr":   self.military_budget_total_mcr,
            "military_profile":            self.military_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MilitaryDetail":
        """Reconstruct from a to_dict() output."""
        def _mb(key: str) -> MilitaryBranch:
            return MilitaryBranch.from_dict(d.get(key, {}))
        return cls(
            enforcement                 = _mb("enforcement"),
            militia                     = _mb("militia"),
            army                        = _mb("army"),
            wet_navy                    = _mb("wet_navy"),
            air_force                   = _mb("air_force"),
            system_defence              = _mb("system_defence"),
            navy                        = _mb("navy"),
            marines                     = _mb("marines"),
            state_of_readiness          = str(d.get("state_of_readiness", "Normal readiness")),
            state_of_readiness_modifier = float(d.get("state_of_readiness_modifier", 1.0)),
            military_budget_pct         = float(d.get("military_budget_pct", 0.0)),
            military_budget_total_mcr   = float(d.get("military_budget_total_mcr", 0.0)),
            military_profile            = str(d.get("military_profile", "")),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_military_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
    starport: str,
    has_highport: bool,
    has_naval_base: bool,
    has_military_base: bool,
    population: int,
    government: int,
    law_level: int,
    tech_level: int,
    atmosphere: int,
    hydrographics: int,
    pcr: int,
    militancy: int,
    expansionism: int,
    efficiency_factor: int,
    gwp_total_mcr: float,
    risk: bool = False,
    rng: Optional[random.Random] = None,
) -> MilitaryDetail:
    """Generate detailed military characteristics (WBH §9).

    Parameters
    ----------
    starport        : starport class letter A–X
    has_highport    : True when 'H' in world.bases
    has_naval_base  : True when 'N' in world.bases
    has_military_base : True when 'M' in world.bases
    population      : population code 0–10
    government      : government code 0–15
    law_level       : law level code 0–18
    tech_level      : tech level 0–15+
    atmosphere      : atmosphere code 0–15
    hydrographics   : hydrographics code 0–10
    pcr             : Population Concentration Rating 0–9
    militancy       : Militancy cultural trait 1–35
    expansionism    : Expansionism cultural trait 1–35
    efficiency_factor : EF from WorldImportance
    gwp_total_mcr   : GWP in MCr from WorldImportance
    risk            : True for potentially hostile systems within 10 parsecs
    rng             : injectable RNG; when provided sets module _rng
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    # 1. State of readiness
    sor_label, sor_mult = _roll_state_of_readiness(militancy)
    factional = _is_heightened_or_worse(sor_label)

    # 2. Enforcement (always exists, no roll)
    enf_effect = _enforcement_effect(
        government, law_level, pcr, militancy, sor_label, factional,
    )
    enforcement = MilitaryBranch(exists=True, effect=enf_effect)

    # 3. Militia
    mil_tl_ok = tech_level >= _BRANCH_MIN_TL["militia"]
    if mil_tl_ok:
        m_dm = _militia_dm(government, law_level, pcr, militancy, sor_label)
        militia_exists, militia_effect = _roll_branch(m_dm)
    else:
        militia_exists, militia_effect = False, 0
    militia = MilitaryBranch(exists=militia_exists, effect=militia_effect)

    # 4. Army
    army_tl_ok = tech_level >= _BRANCH_MIN_TL["army"]
    if army_tl_ok:
        a_dm = _army_dm(government, tech_level, has_military_base,
                        militia_exists, militancy, sor_label, risk, factional)
        army_exists, army_effect = _roll_branch(a_dm)
    else:
        army_exists, army_effect = False, 0
    army = MilitaryBranch(exists=army_exists, effect=army_effect)

    # 5. Wet Navy
    wn_tl_ok = tech_level >= _BRANCH_MIN_TL["wet_navy"]
    if wn_tl_ok:
        wn_dm = _wet_navy_dm(hydrographics, government, tech_level,
                             militancy, sor_label)
        wn_exists, wn_effect = _roll_branch(wn_dm)
    else:
        wn_exists, wn_effect = False, 0
    wet_navy = MilitaryBranch(exists=wn_exists, effect=wn_effect)

    # 6. Air Force
    af_tl_ok = tech_level >= _BRANCH_MIN_TL["air_force"]
    if af_tl_ok:
        af_dm = _air_force_dm(atmosphere, government, tech_level,
                              militancy, sor_label)
        af_exists, af_effect = _roll_branch(af_dm)
    else:
        af_exists, af_effect = False, 0
    air_force = MilitaryBranch(exists=af_exists, effect=af_effect)

    # 7. System Defence
    sd_tl_ok = tech_level >= _BRANCH_MIN_TL["system_defence"]
    if sd_tl_ok:
        sd_dm = _system_defence_dm(population, tech_level, starport, has_highport,
                                   has_naval_base, has_military_base,
                                   militancy, sor_label, risk)
        sd_exists, sd_effect = _roll_branch(sd_dm)
    else:
        sd_exists, sd_effect = False, 0
    system_defence = MilitaryBranch(exists=sd_exists, effect=sd_effect)

    # 8. Navy
    nv_tl_ok = tech_level >= _BRANCH_MIN_TL["navy"]
    if nv_tl_ok:
        nv_dm = _navy_dm(population, tech_level, starport, has_highport,
                         has_naval_base, has_military_base, expansionism,
                         militancy, sor_label, risk)
        nv_exists, nv_effect = _roll_branch(nv_dm)
    else:
        nv_exists, nv_effect = False, 0
    navy = MilitaryBranch(exists=nv_exists, effect=nv_effect)

    # 9. Marines (needs Navy and System Defence results)
    mr_tl_ok = tech_level >= _BRANCH_MIN_TL["marines"]
    if mr_tl_ok:
        mr_dm = _marines_dm(population, tech_level, has_naval_base,
                            has_military_base, nv_exists, sd_exists,
                            expansionism, militancy, sor_label, risk)
        mr_exists, mr_effect = _roll_branch(mr_dm)
    else:
        mr_exists, mr_effect = False, 0
    marines = MilitaryBranch(exists=mr_exists, effect=mr_effect)

    branches: dict[str, MilitaryBranch] = {
        "enforcement":    enforcement,
        "militia":        militia,
        "army":           army,
        "wet_navy":       wet_navy,
        "air_force":      air_force,
        "system_defence": system_defence,
        "navy":           navy,
        "marines":        marines,
    }

    # 10. Military budget
    budget_pct, budget_total = _compute_budget(
        government, law_level, has_naval_base, has_military_base,
        militancy, efficiency_factor, gwp_total_mcr, branches,
    )
    # Apply state of readiness multiplier to total
    budget_total = round(budget_total * sor_mult, 2)

    profile = _military_profile(branches, budget_pct)

    return MilitaryDetail(
        enforcement                 = enforcement,
        militia                     = militia,
        army                        = army,
        wet_navy                    = wet_navy,
        air_force                   = air_force,
        system_defence              = system_defence,
        navy                        = navy,
        marines                     = marines,
        state_of_readiness          = sor_label,
        state_of_readiness_modifier = sor_mult,
        military_budget_pct         = budget_pct,
        military_budget_total_mcr   = budget_total,
        military_profile            = profile,
    )


def attach_military_detail(
    system,
    rng: Optional[random.Random] = None,
) -> None:
    """Attach MilitaryDetail to system.mainworld (WBH §9).

    Requires importance_detail (for EF and GWP) and culture_detail
    (for Militancy and Expansionism). No-op when either is absent,
    or when population == 0.
    """
    world = system.mainworld
    if world is None:
        return
    if world.population == 0:
        return
    imp_det = world.importance_detail
    if imp_det is None:
        return

    cul_det = world.culture_detail
    militancy   = cul_det.militancy    if cul_det is not None else 6
    expansionism = cul_det.expansionism if cul_det is not None else 6

    pcr = (world.population_detail.pcr
           if world.population_detail is not None else 0)

    gwp = imp_det.gwp_total_mcr if imp_det.gwp_total_mcr is not None else 0.0
    ef  = imp_det.efficiency_factor or 0

    world.military_detail = generate_military_detail(
        starport          = world.starport,
        has_highport      = "H" in world.bases,
        has_naval_base    = "N" in world.bases,
        has_military_base = "M" in world.bases,
        population        = world.population,
        government        = world.government,
        law_level         = world.law_level,
        tech_level        = world.tech_level,
        atmosphere        = world.atmosphere,
        hydrographics     = world.hydrographics,
        pcr               = pcr,
        militancy         = militancy,
        expansionism      = expansionism,
        efficiency_factor = ef,
        gwp_total_mcr     = gwp,
        rng               = rng,
    )
