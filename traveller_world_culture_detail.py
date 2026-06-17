"""
traveller_world_culture_detail.py
====================================
Cultural detail for Traveller mainworlds and secondary worlds, following
the World Builder's Handbook Social Characteristics — Culture section.

Implements (issue #99, Session 127):
  - Cultural Diversity trait (2D + DMs)

Implements (Session 128):
  - Xenophilia trait (2D + DMs)

Implements (Session 129):
  - Uniqueness trait (2D + DMs)
  - Symbology trait (2D + DMs)
  - Cohesion trait (2D + DMs)
  - Progressiveness trait (2D + DMs)
  - Expansionism trait (2D + DMs)
  - Militancy trait (2D + DMs)
  - Full 8-trait cultural profile string (DXUS-CPEM format)

The CRB Cultural Differences table is deferred (not yet transcribed).

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
# pylint: disable=wrong-import-position,import-error,locally-disabled,suppressed-message

import math
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

# Diversity value → descriptive label.
# ≤3 = monolithic; ≥12 = balkanised (WBH Culture section).
_DIVERSITY_LABELS: list[tuple[int, str]] = [
    (3,  "Monolithic"),
    (5,  "Homogeneous"),
    (8,  "Diverse"),
    (11, "Multicultural"),
    (99, "Balkanised"),
]

# Xenophilia value → descriptive label (WBH Culture section).
# ≤3 = active xenophobia; 9+ = welcoming.
_XENOPHILIA_LABELS: list[tuple[int, str]] = [
    (3,  "Xenophobic"),
    (8,  "Moderate"),
    (99, "Welcoming"),
]

# Uniqueness value → descriptive label (WBH Culture section).
# ≤3 = indistinct/cosmopolitan; 12+ = highly unique/exotic.
_UNIQUENESS_LABELS: list[tuple[int, str]] = [
    (3,  "Indistinct"),
    (8,  "Typical"),
    (11, "Distinct"),
    (99, "Exotic"),
]

# Symbology value → descriptive label (WBH Culture section).
# ≤3 = mundane concrete symbols; 12+ = pervasive abstract symbology.
_SYMBOLOGY_LABELS: list[tuple[int, str]] = [
    (3,  "Mundane"),
    (8,  "Moderate"),
    (11, "Prominent"),
    (99, "Pervasive"),
]

# Cohesion value → descriptive label (WBH Culture section).
# ≤3 = strongly individualistic; 12+ = strongly collectivist.
_COHESION_LABELS: list[tuple[int, str]] = [
    (3,  "Individualistic"),
    (8,  "Moderate"),
    (11, "Communal"),
    (99, "Collectivist"),
]

# Progressiveness value → descriptive label (WBH Culture section).
# ≤3 = moribund decay; ≤5 = conservative; 9+ = moving forward; 12+ = change-for-its-own-sake.
_PROGRESSIVENESS_LABELS: list[tuple[int, str]] = [
    (3,  "Moribund"),
    (5,  "Conservative"),
    (8,  "Moderate"),
    (11, "Progressive"),
    (99, "Innovative"),
]

# Expansionism value → descriptive label (WBH Culture section).
# ≤3 = insular; 9+ = actively promotes culture; 12+ = coercive conversion.
_EXPANSIONISM_LABELS: list[tuple[int, str]] = [
    (3,  "Insular"),
    (8,  "Moderate"),
    (11, "Expansive"),
    (99, "Imperialist"),
]

# Militancy value → descriptive label (WBH Culture section).
# ≤3 = peaceful; 9+ = aggressive; 12+ = militaristic/bent on conquest.
_MILITANCY_LABELS: list[tuple[int, str]] = [
    (3,  "Peaceful"),
    (8,  "Moderate"),
    (11, "Aggressive"),
    (99, "Militaristic"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ehex(n: int) -> str:
    """Convert a non-negative int to a single eHex character."""
    idx = max(0, min(n, len(_EHEX) - 1))
    return _EHEX[idx]


def _from_ehex(ch: str) -> int:
    """Convert a single eHex character to its integer value (0–35)."""
    try:
        return _EHEX.index(ch.upper())
    except ValueError:
        return 0


def _parse_cx_string(cx: str) -> tuple:
    """Parse a T5 Cx string such as '(7567)' into (H, A, S, S2) integers."""
    raw = cx.strip("() \t")
    if len(raw) < 4:
        return (0, 0, 0, 0)
    return (
        _from_ehex(raw[0]),   # Heterogeneity → Diversity
        _from_ehex(raw[1]),   # Acceptance    → Xenophilia
        _from_ehex(raw[2]),   # Strangeness   → Uniqueness (scaled)
        _from_ehex(raw[3]),   # Symbols       → Symbology
    )


def _label_from_table(value: int, table: list[tuple[int, str]]) -> str:
    """Return the label for *value* from a threshold table."""
    for threshold, label in table:
        if value <= threshold:
            return label
    return table[-1][1]


def _diversity_label(value: int) -> str:
    """Return the descriptive label for a diversity value."""
    return _label_from_table(value, _DIVERSITY_LABELS)


def _xenophilia_label(value: int) -> str:
    """Return the descriptive label for a xenophilia value."""
    return _label_from_table(value, _XENOPHILIA_LABELS)


def _uniqueness_label(value: int) -> str:
    """Return the descriptive label for a uniqueness value."""
    return _label_from_table(value, _UNIQUENESS_LABELS)


def _symbology_label(value: int) -> str:
    """Return the descriptive label for a symbology value."""
    return _label_from_table(value, _SYMBOLOGY_LABELS)


def _cohesion_label(value: int) -> str:
    """Return the descriptive label for a cohesion value."""
    return _label_from_table(value, _COHESION_LABELS)


def _progressiveness_label(value: int) -> str:
    """Return the descriptive label for a progressiveness value."""
    return _label_from_table(value, _PROGRESSIVENESS_LABELS)


def _expansionism_label(value: int) -> str:
    """Return the descriptive label for an expansionism value."""
    return _label_from_table(value, _EXPANSIONISM_LABELS)


def _militancy_label(value: int) -> str:
    """Return the descriptive label for a militancy value."""
    return _label_from_table(value, _MILITANCY_LABELS)


def _diversity_dm(population: int, government: int, law_level: int, pcr: int) -> int:
    """Compute the total DM for the Diversity roll."""
    dm = 0
    if 1 <= population <= 5:
        dm -= 2
    if population >= 9:
        dm += 2
    if 0 <= government <= 2:
        dm += 1
    if government == 7:
        dm += 4
    if 13 <= government <= 15:
        dm -= 4
    if 0 <= law_level <= 4:
        dm += 1
    if law_level >= 10:
        dm -= 1
    if 0 <= pcr <= 3:
        dm += 1
    if 7 <= pcr <= 9:
        dm -= 2
    return dm


def _xenophilia_dm(
        population: int,
        government: int,
        law_level: int,
        starport: str,
        diversity: int,
) -> int:
    """Compute the total DM for the Xenophilia roll (WBH Culture section)."""
    dm = 0
    if 1 <= population <= 5:
        dm -= 1
    if population >= 9:
        dm += 2
    if government in (13, 14):      # D or E
        dm -= 2
    if law_level >= 10:             # A+
        dm -= 2
    sp = starport.upper()
    if sp == "A":
        dm += 2
    elif sp == "B":
        dm += 1
    elif sp == "D":
        dm -= 1
    elif sp == "E":
        dm -= 2
    elif sp == "X":
        dm -= 4
    if diversity <= 3:              # Diversity 1–3 (Monolithic)
        dm -= 2
    if diversity >= 12:             # Diversity C+
        dm += 1
    return dm


def _uniqueness_dm(starport: str, diversity: int, xenophilia: int) -> int:
    """Compute the total DM for the Uniqueness roll (WBH Culture section)."""
    dm = 0
    sp = starport.upper()
    if sp == "A":
        dm -= 2
    elif sp == "B":
        dm -= 1
    elif sp == "D":
        dm += 1
    elif sp == "E":
        dm += 2
    elif sp == "X":
        dm += 4
    if diversity <= 3:              # Diversity 1–3 (Monolithic)
        dm += 2
    if 9 <= xenophilia <= 11:       # Xenophilia 9–B
        dm -= 1
    if xenophilia >= 12:            # Xenophilia C+
        dm -= 2
    return dm


def _cohesion_dm(government: int, law_level: int, pcr: int, diversity: int) -> int:
    """Compute the total DM for the Cohesion roll (WBH Culture section)."""
    dm = 0
    if government in (3, 12):      # 3 or C
        dm += 2
    if government in (5, 6, 9):    # 5, 6 or 9
        dm += 1
    if law_level <= 2:             # Law Level 0–2
        dm -= 2
    if law_level >= 10:            # Law Level A+
        dm += 2
    if pcr <= 3:                   # PCR 0–3
        dm -= 2
    if pcr >= 7:                   # PCR 7+
        dm += 2
    if diversity <= 2:             # Diversity 1–2
        dm += 4
    elif diversity <= 5:           # Diversity 3–5
        dm += 2
    elif 9 <= diversity <= 11:     # Diversity 9–B
        dm -= 2
    elif diversity >= 12:          # Diversity C+
        dm -= 4
    return dm


def _progressiveness_dm(  # pylint: disable=too-many-branches,too-many-positional-arguments,too-many-arguments
        population: int,
        government: int,
        law_level: int,
        diversity: int,
        xenophilia: int,
        cohesion: int,
) -> int:
    """Compute the total DM for the Progressiveness roll (WBH Culture section)."""
    dm = 0
    if 6 <= population <= 8:        # Population 6–8
        dm -= 1
    if population >= 9:             # Population 9+
        dm -= 2
    if government == 5:             # Government 5
        dm += 1
    if government == 11:            # Government B
        dm -= 2
    if government in (13, 14):      # Government D or E
        dm -= 6
    if 9 <= law_level <= 11:        # Law Level 9–B
        dm -= 1
    if law_level >= 12:             # Law Level C+
        dm -= 4
    if diversity <= 3:              # Diversity 1–3
        dm -= 2
    if diversity >= 12:             # Diversity C+
        dm += 1
    if xenophilia <= 5:             # Xenophilia 1–5
        dm -= 1
    if xenophilia >= 9:             # Xenophilia 9+
        dm += 2
    if cohesion <= 5:               # Cohesion 1–5
        dm += 2
    if cohesion >= 9:               # Cohesion 9+
        dm -= 2
    return dm


def _expansionism_dm(government: int, diversity: int, xenophilia: int) -> int:
    """Compute the total DM for the Expansionism roll (WBH Culture section)."""
    dm = 0
    if government == 10 or government >= 12:  # Government A or C+
        dm += 2
    if diversity <= 3:                         # Diversity 1–3
        dm += 3
    if diversity >= 12:                        # Diversity C+
        dm -= 3
    if xenophilia <= 5:                        # Xenophilia 1–5
        dm += 1
    if xenophilia >= 9:                        # Xenophilia 9+
        dm -= 2
    return dm


def _militancy_dm(government: int, law_level: int, xenophilia: int, expansionism: int) -> int:
    """Compute the total DM for the Militancy roll (WBH Culture section)."""
    dm = 0
    if government >= 10:                       # Government A+
        dm += 3
    if 9 <= law_level <= 11:                   # Law Level 9–B
        dm += 1
    if law_level >= 12:                        # Law Level C+
        dm += 2
    if xenophilia <= 5:                        # Xenophilia 1–5
        dm += 1
    if xenophilia >= 9:                        # Xenophilia 9+
        dm -= 2
    if expansionism <= 5:                      # Expansionism 1–5
        dm -= 1
    if 9 <= expansionism <= 11:                # Expansionism 9–B
        dm += 1
    if expansionism >= 12:                     # Expansionism C+
        dm += 2
    return dm


def _symbology_dm(government: int, tech_level: int, uniqueness: int) -> int:
    """Compute the total DM for the Symbology roll (WBH Culture section)."""
    dm = 0
    if government in (13, 14):      # D or E
        dm += 2
    if tech_level <= 1:             # TL 0–1
        dm -= 3
    elif tech_level <= 3:           # TL 2–3
        dm -= 1
    elif 9 <= tech_level <= 11:     # TL 9–11
        dm += 2
    elif tech_level >= 12:          # TL 12+
        dm += 4
    if 9 <= uniqueness <= 11:       # Uniqueness 9–B
        dm += 1
    if uniqueness >= 12:            # Uniqueness C+
        dm += 3
    return dm


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class CultureDetail:  # pylint: disable=too-many-instance-attributes
    """Cultural profile for one inhabited world (WBH Culture section)."""

    diversity: int          # raw trait value (1–35)
    diversity_label: str    # e.g. "Diverse"
    xenophilia: int         # raw trait value (1–35)
    xenophilia_label: str   # e.g. "Welcoming"
    uniqueness: int         # raw trait value (1–35)
    uniqueness_label: str   # e.g. "Exotic"
    symbology: int          # raw trait value (1–35)
    symbology_label: str    # e.g. "Pervasive"
    cohesion: int               # raw trait value (1–35)
    cohesion_label: str         # e.g. "Collectivist"
    progressiveness: int        # raw trait value (1–35)
    progressiveness_label: str  # e.g. "Innovative"
    expansionism: int           # raw trait value (1–35)
    expansionism_label: str     # e.g. "Imperialist"
    militancy: int              # raw trait value (1–35)
    militancy_label: str        # e.g. "Militaristic"
    # DXUS-CPEM format: 8 eHex chars + 1 hyphen separator = 9 chars total
    cultural_profile: str

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "diversity":         self.diversity,
            "diversity_label":   self.diversity_label,
            "xenophilia":        self.xenophilia,
            "xenophilia_label":  self.xenophilia_label,
            "uniqueness":        self.uniqueness,
            "uniqueness_label":  self.uniqueness_label,
            "symbology":         self.symbology,
            "symbology_label":   self.symbology_label,
            "cohesion":               self.cohesion,
            "cohesion_label":         self.cohesion_label,
            "progressiveness":        self.progressiveness,
            "progressiveness_label":  self.progressiveness_label,
            "expansionism":           self.expansionism,
            "expansionism_label":     self.expansionism_label,
            "militancy":              self.militancy,
            "militancy_label":        self.militancy_label,
            "cultural_profile":       self.cultural_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CultureDetail":
        """Reconstruct from a dict produced by to_dict()."""
        diversity = int(d.get("diversity", 1))
        xenophilia = int(d.get("xenophilia", 1))
        uniqueness = int(d.get("uniqueness", 1))
        symbology = int(d.get("symbology", 1))
        cohesion = int(d.get("cohesion", 1))
        progressiveness = int(d.get("progressiveness", 1))
        expansionism = int(d.get("expansionism", 1))
        militancy = int(d.get("militancy", 1))
        default_profile = (
            _ehex(diversity) + _ehex(xenophilia)
            + _ehex(uniqueness) + _ehex(symbology)
            + "-"
            + _ehex(cohesion) + _ehex(progressiveness)
            + _ehex(expansionism) + _ehex(militancy)
        )
        return cls(
            diversity=diversity,
            diversity_label=str(d.get("diversity_label",
                _label_from_table(diversity, _DIVERSITY_LABELS))),
            xenophilia=xenophilia,
            xenophilia_label=str(d.get("xenophilia_label",
                _label_from_table(xenophilia, _XENOPHILIA_LABELS))),
            uniqueness=uniqueness,
            uniqueness_label=str(d.get("uniqueness_label",
                _label_from_table(uniqueness, _UNIQUENESS_LABELS))),
            symbology=symbology,
            symbology_label=str(d.get("symbology_label",
                _label_from_table(symbology, _SYMBOLOGY_LABELS))),
            cohesion=cohesion,
            cohesion_label=str(d.get("cohesion_label",
                _label_from_table(cohesion, _COHESION_LABELS))),
            progressiveness=progressiveness,
            progressiveness_label=str(d.get("progressiveness_label",
                _label_from_table(progressiveness, _PROGRESSIVENESS_LABELS))),
            expansionism=expansionism,
            expansionism_label=str(d.get("expansionism_label",
                _label_from_table(expansionism, _EXPANSIONISM_LABELS))),
            militancy=militancy,
            militancy_label=str(d.get("militancy_label",
                _label_from_table(militancy, _MILITANCY_LABELS))),
            cultural_profile=str(d.get("cultural_profile", default_profile)),
        )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_culture_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        population: int,
        government: int,
        law_level: int,
        pcr: int = 0,
        starport: str = "",
        tech_level: int = 0,
        rng: Optional[random.Random] = None,
) -> Optional[CultureDetail]:
    """Generate the cultural profile for one inhabited world.

    Returns None when ``population == 0`` (uninhabited — no procedures apply).

    Parameters
    ----------
    population : int
        UWP Population code (0 = uninhabited).
    government : int
        UWP Government code.
    law_level : int
        UWP Law Level.
    pcr : int
        Population Concentration Rating (0–9).  Defaults to 0 when
        population detail has not been generated.
    starport : str
        UWP Starport code ("A"–"X").  Affects Xenophilia and Uniqueness DMs.
        Secondary worlds use a different spaceport scale; pass "" to apply
        no starport DM.
    tech_level : int
        UWP Tech Level.  Affects Symbology DMs only.  Defaults to 0 (applies
        TL 0-1 DM of -3) when tech detail has not been generated.
    rng : Optional[random.Random]
        Injectable RNG.  When provided, replaces the module-level ``_rng``.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    if population == 0:
        return None

    div_dm = _diversity_dm(population, government, law_level, pcr)
    diversity = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + div_dm)

    xen_dm = _xenophilia_dm(population, government, law_level, starport, diversity)
    xenophilia = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + xen_dm)

    unq_dm = _uniqueness_dm(starport, diversity, xenophilia)
    uniqueness = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + unq_dm)

    sym_dm = _symbology_dm(government, tech_level, uniqueness)
    symbology = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + sym_dm)

    coh_dm = _cohesion_dm(government, law_level, pcr, diversity)
    cohesion = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + coh_dm)

    pro_dm = _progressiveness_dm(population, government, law_level,
                                 diversity, xenophilia, cohesion)
    progressiveness = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + pro_dm)

    exp_dm = _expansionism_dm(government, diversity, xenophilia)
    expansionism = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + exp_dm)

    mil_dm = _militancy_dm(government, law_level, xenophilia, expansionism)
    militancy = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + mil_dm)

    profile = (
        _ehex(diversity) + _ehex(xenophilia)
        + _ehex(uniqueness) + _ehex(symbology)
        + "-"
        + _ehex(cohesion) + _ehex(progressiveness)
        + _ehex(expansionism) + _ehex(militancy)
    )

    return CultureDetail(
        diversity=diversity,
        diversity_label=_diversity_label(diversity),
        xenophilia=xenophilia,
        xenophilia_label=_xenophilia_label(xenophilia),
        uniqueness=uniqueness,
        uniqueness_label=_uniqueness_label(uniqueness),
        symbology=symbology,
        symbology_label=_symbology_label(symbology),
        cohesion=cohesion,
        cohesion_label=_cohesion_label(cohesion),
        progressiveness=progressiveness,
        progressiveness_label=_progressiveness_label(progressiveness),
        expansionism=expansionism,
        expansionism_label=_expansionism_label(expansionism),
        militancy=militancy,
        militancy_label=_militancy_label(militancy),
        cultural_profile=profile,
    )


def generate_culture_detail_from_cx(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,unused-argument
        cx: str,
        population: int,
        importance: int,
        government: int,
        law_level: int,
        pcr: int = 0,
        starport: str = "",
        tech_level: int = 0,
        rng: Optional[random.Random] = None,
) -> Optional[CultureDetail]:
    """Generate cultural detail using the T5 Cultural Extension (Cx) string.

    The first four traits (Diversity, Xenophilia, Uniqueness, Symbology) are
    derived from the Cx HASS string read from TravellerMap.  The remaining four
    traits (Cohesion, Progressiveness, Expansionism, Militancy) are still rolled
    with dice + DMs.

    Conversion rules (WBH §Cultural Extension Conversion):
      Diversity  = H, clamped to [max(1, Pop-5), Pop+5]
      Xenophilia = A, clamped to [max(1, Imp+Pop-5), Imp+Pop+5]
      Uniqueness = max(1, ceil(S × 3/2))
      Symbology  = S2, clamped to [max(1, TL-5), TL+5]

    Returns None when population == 0.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    if population == 0:
        return None

    h, a, s, s2 = _parse_cx_string(cx)

    div_lo = max(1, population - 5)
    diversity = min(population + 5, max(div_lo, 1, h))

    xen_centre = importance + population
    xen_lo = max(1, xen_centre - 5)
    xenophilia = min(xen_centre + 5, max(xen_lo, 1, a))

    uniqueness = max(1, math.ceil(s * 3 / 2))

    sym_lo = max(1, tech_level - 5)
    symbology = min(tech_level + 5, max(sym_lo, 1, s2))

    coh_dm = _cohesion_dm(government, law_level, pcr, diversity)
    cohesion = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + coh_dm)

    pro_dm = _progressiveness_dm(population, government, law_level,
                                 diversity, xenophilia, cohesion)
    progressiveness = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + pro_dm)

    exp_dm = _expansionism_dm(government, diversity, xenophilia)
    expansionism = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + exp_dm)

    mil_dm = _militancy_dm(government, law_level, xenophilia, expansionism)
    militancy = max(1, _rng.randint(1, 6) + _rng.randint(1, 6) + mil_dm)

    profile = (
        _ehex(diversity) + _ehex(xenophilia)
        + _ehex(uniqueness) + _ehex(symbology)
        + "-"
        + _ehex(cohesion) + _ehex(progressiveness)
        + _ehex(expansionism) + _ehex(militancy)
    )

    return CultureDetail(
        diversity=diversity,
        diversity_label=_diversity_label(diversity),
        xenophilia=xenophilia,
        xenophilia_label=_xenophilia_label(xenophilia),
        uniqueness=uniqueness,
        uniqueness_label=_uniqueness_label(uniqueness),
        symbology=symbology,
        symbology_label=_symbology_label(symbology),
        cohesion=cohesion,
        cohesion_label=_cohesion_label(cohesion),
        progressiveness=progressiveness,
        progressiveness_label=_progressiveness_label(progressiveness),
        expansionism=expansionism,
        expansionism_label=_expansionism_label(expansionism),
        militancy=militancy,
        militancy_label=_militancy_label(militancy),
        cultural_profile=profile,
    )


# ---------------------------------------------------------------------------
# Attach function
# ---------------------------------------------------------------------------

def _culture_detail_for_det(det: object) -> Optional[CultureDetail]:
    """Generate CultureDetail for a WorldDetail (secondary world).

    Secondary worlds use spaceport codes (Y/H/G/F), not the A–X starport
    scale, so no starport DM applies to xenophilia or uniqueness.
    """
    pop: int = getattr(det, "population", 0)
    gov: int = getattr(det, "government", 0)
    law: int = getattr(det, "law_level", 0)
    tl: int = getattr(det, "tech_level", 0)
    pop_detail = getattr(det, "population_detail", None)
    pcr: int = pop_detail.pcr if pop_detail is not None else 0
    return generate_culture_detail(
        population=pop, government=gov, law_level=law, pcr=pcr,
        starport="", tech_level=tl, rng=None,
    )


def _attach_det_culture(det: object) -> None:
    """Attach culture detail to one WorldDetail and its inhabited moons."""
    det.culture_detail = _culture_detail_for_det(det)  # type: ignore[attr-defined]
    for moon in getattr(det, "moons", []):
        moon_det = getattr(moon, "detail", None)
        if moon_det is not None and getattr(moon_det, "inhabited", False):
            moon_det.culture_detail = _culture_detail_for_det(moon_det)


def attach_culture_detail(
        system: "TravellerSystem",
        rng: Optional[random.Random] = None,
) -> None:
    """Attach cultural detail to mainworld and all inhabited secondaries.

    Calls generate_culture_detail() for system.mainworld when inhabited.
    Also applies to each inhabited secondary WorldDetail and moon WorldDetail.
    Uses population_detail.pcr when available; falls back to pcr=0.
    No-op when mainworld is uninhabited.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    mw = system.mainworld
    if mw is not None and mw.population > 0:
        pop_det = mw.population_detail  # type: ignore[attr-defined]
        pcr = pop_det.pcr if pop_det is not None else 0
        cx: str = getattr(mw, "cx", "")
        if cx:
            mw.culture_detail = generate_culture_detail_from_cx(  # type: ignore[attr-defined]
                cx=cx,
                population=mw.population,    # type: ignore[attr-defined]
                importance=getattr(mw, "importance", 0),
                government=mw.government,    # type: ignore[attr-defined]
                law_level=mw.law_level,      # type: ignore[attr-defined]
                pcr=pcr,
                starport=mw.starport,        # type: ignore[attr-defined]
                tech_level=mw.tech_level,    # type: ignore[attr-defined]
                rng=None,
            )
        else:
            mw.culture_detail = generate_culture_detail(  # type: ignore[attr-defined]
                population=mw.population,   # type: ignore[attr-defined]
                government=mw.government,   # type: ignore[attr-defined]
                law_level=mw.law_level,     # type: ignore[attr-defined]
                pcr=pcr,
                starport=mw.starport,       # type: ignore[attr-defined]
                tech_level=mw.tech_level,   # type: ignore[attr-defined]
                rng=None,
            )

    for orbit in system.system_orbits.orbits:
        if orbit.is_mainworld_candidate:
            continue
        det = orbit.detail
        if det is None or not det.inhabited:
            continue
        _attach_det_culture(det)
