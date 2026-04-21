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

import json
import random
import argparse
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def roll(num_dice: int, modifier: int = 0) -> int:
    """Roll *num_dice* six-sided dice and add *modifier*.

    The result is clamped to a minimum of 0 because many Traveller tables
    treat negative totals as zero (e.g. Atmosphere, Hydrographics).
    """
    total = sum(random.randint(1, 6) for _ in range(num_dice))
    return max(0, total + modifier)


# ---------------------------------------------------------------------------
# Hexadecimal helper
# ---------------------------------------------------------------------------

# Traveller uses base-16 for UWP digits above 9: A=10, B=11 ... F=15, G=16
_HEX_DIGITS = "0123456789ABCDEFG"

def to_hex(value: int) -> str:
    """Convert an integer to a single Traveller hexadecimal character."""
    value = max(0, value)
    if value < len(_HEX_DIGITS):
        return _HEX_DIGITS[value]
    return str(value)   # fallback for very high values


# ---------------------------------------------------------------------------
# Lookup tables  (all directly from the 2022 Core Rulebook)
# ---------------------------------------------------------------------------

# Atmosphere descriptions (p.250), indexed by atmosphere code 0-15
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
    elif modified_roll <= 4:
        return "E"
    elif modified_roll <= 6:
        return "D"
    elif modified_roll <= 8:
        return "C"
    elif modified_roll <= 10:
        return "B"
    else:
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
}

def temperature_category(modified_roll: int) -> str:
    """Return temperature category string from modified 2D roll (p.251)."""
    if modified_roll <= 2:
        return "Frozen"
    elif modified_roll <= 4:
        return "Cold"
    elif modified_roll <= 9:
        return "Temperate"
    elif modified_roll <= 11:
        return "Hot"
    else:
        return "Boiling"


# ---------------------------------------------------------------------------
# World dataclass
# ---------------------------------------------------------------------------

@dataclass
class World:
    """Holds all generated characteristics for one mainworld."""
    name:           str   = "Unknown"
    size:           int   = 0
    atmosphere:     int   = 0
    temperature:    str   = "Temperate"
    hydrographics:  int   = 0
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
    # JSON output
    # ------------------------------------------------------------------
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
                "diameter_km": {
                    0: "<1,000", 1: "1,600", 2: "3,200", 3: "4,800",
                    4: "6,400", 5: "8,000", 6: "9,600", 7: "11,200",
                    8: "12,800", 9: "14,400", 10: "16,000",
                }.get(self.size, "Unknown"),
                "surface_gravity": {
                    0: "negligible", 1: "0.05G", 2: "0.15G", 3: "0.25G",
                    4: "0.35G", 5: "0.45G", 6: "0.70G", 7: "0.90G",
                    8: "1.00G", 9: "1.25G", 10: "1.40G",
                }.get(self.size, "Unknown"),
            },
            "atmosphere": {
                "code": self.atmosphere,
                "name": ATMOSPHERE_NAMES.get(self.atmosphere, "Unknown"),
                "survival_gear": ATMOSPHERE_GEAR.get(self.atmosphere, "Unknown"),
            },
            "temperature": self.temperature,
            "hydrographics": {
                "code": self.hydrographics,
                "description": HYDROGRAPHIC_NAMES.get(
                    self.hydrographics, "Unknown"
                ),
            },
            "population": {
                "code": self.population,
                "range": {
                    0: "None", 1: "Few (1+)", 2: "Hundreds", 3: "Thousands",
                    4: "Tens of thousands", 5: "Hundreds of thousands",
                    6: "Millions", 7: "Tens of millions",
                    8: "Hundreds of millions", 9: "Billions",
                    10: "Tens of billions",
                }.get(self.population, "Hundreds of billions+"),
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
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise the world to a JSON string.

        Args:
            indent: Number of spaces used for pretty-printing.
                    Pass ``None`` for compact single-line output.

        Returns:
            A UTF-8–safe JSON string conforming to
            traveller_world_schema.json.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

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

        The output matches the inline display widget shown in Claude
        conversation responses and can be embedded in any HTML page,
        saved as a standalone .html file, or served directly from the
        Azure Functions API.

        Tech Level era labels use the rulebook-correct era names
        (Traveller 2022 Core Rulebook pp. 6-7):
            TL 0-3  = Primitive,  TL 4-6  = Industrial,
            TL 7-9  = Pre-Stellar, TL 10-11 = Early Stellar,
            TL 12-14 = Average Stellar, TL 15+ = High Stellar

        Returns:
            A UTF-8 HTML string. No external resources are required —
            all CSS is inlined in a <style> block.
        """
        d = self.to_dict()

        # --- helper lambdas for HTML escaping and badge rendering --------
        def esc(s: str) -> str:
            """Minimal HTML-escape for inline text values."""
            return (str(s)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;"))

        def row(label: str, value: str, danger: bool = False) -> str:
            """Render one label/value detail row."""
            val_style = (
                'style="font-size:13px;font-weight:500;'
                'color:var(--color-text-danger,#c0392b)"'
                if danger
                else 'style="font-size:13px;font-weight:500"'
            )
            return (
                f'<div class="detail-row">'
                f'<span class="row-label">{esc(label)}</span>'
                f'<span {val_style}>{esc(value)}</span>'
                f'</div>'
            )

        def badge(text: str, css_class: str) -> str:
            return f'<span class="badge {esc(css_class)}">{esc(text)}</span>'

        # --- travel zone badge -------------------------------------------
        zone_class = {
            "Green": "zone-green",
            "Amber": "zone-amber",
            "Red":   "zone-red",
        }.get(self.travel_zone, "zone-green")
        zone_badge = badge(f"{self.travel_zone} zone", zone_class)

        # --- trade code badges -------------------------------------------
        trade_code_full = {
            "Ag": "Ag — Agricultural",   "As": "As — Asteroid",
            "Ba": "Ba — Barren",         "De": "De — Desert",
            "Fl": "Fl — Fluid Oceans",   "Ga": "Ga — Garden",
            "Hi": "Hi — High Population","Ht": "Ht — High Tech",
            "Ic": "Ic — Ice-Capped",     "In": "In — Industrial",
            "Lo": "Lo — Low Population", "Lt": "Lt — Low Tech",
            "Na": "Na — Non-Agricultural","Ni": "Ni — Non-Industrial",
            "Po": "Po — Poor",           "Ri": "Ri — Rich",
            "Va": "Va — Vacuum",         "Wa": "Wa — Waterworld",
        }
        trade_badges = "".join(
            badge(trade_code_full.get(tc, tc), "trade")
            for tc in self.trade_codes
        ) or '<span style="font-size:13px;color:var(--color-text-secondary)">None</span>'

        # --- bases string ------------------------------------------------
        base_full = {
            "N": "N (Naval)", "S": "S (Scout)", "M": "M (Military)",
            "H": "H (Highport)", "C": "C (Corsair)",
        }
        bases_str = "  ".join(base_full.get(b, b) for b in self.bases) or "None"

        # --- TL era -------------------------------------------------------
        tl_era     = self._tl_era(self.tech_level)
        tl_era_css = self._tl_era_css(self.tech_level)

        # --- notes HTML ---------------------------------------------------
        if self.notes:
            notes_items = "".join(
                f'<li style="margin:4px 0;font-size:13px;'
                f'color:var(--color-text-secondary)">{esc(n)}</li>'
                for n in self.notes
            )
            notes_html = (
                f'<div class="inner-card" style="margin-top:12px">'
                f'<p class="inner-label">Notes</p>'
                f'<ul style="margin:4px 0 0;padding-left:20px">'
                f'{notes_items}</ul></div>'
            )
        else:
            notes_html = ""

        # --- survival gear warning (only shown when gear is required) ----
        gear = d["atmosphere"]["survival_gear"]
        gear_danger = gear not in ("None", "Varies")
        survival_row = row("Survival gear", gear, danger=gear_danger)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(self.name)} — {esc(self.uwp())}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  :root {{
    --color-bg-primary:   #ffffff;
    --color-bg-secondary: #f5f5f3;
    --color-bg-tertiary:  #eeede8;
    --color-text-primary: #1a1a19;
    --color-text-secondary: #6b6a65;
    --color-text-danger:  #c0392b;
    --color-border:       rgba(0,0,0,0.12);
    --radius-md: 8px;
    --radius-lg: 12px;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --color-bg-primary:   #1e1e1c;
      --color-bg-secondary: #2a2a28;
      --color-bg-tertiary:  #323230;
      --color-text-primary: #e8e6de;
      --color-text-secondary: #9c9a92;
      --color-text-danger:  #e57373;
      --color-border:       rgba(255,255,255,0.10);
    }}
  }}
  body {{
    background: var(--color-bg-tertiary);
    margin: 0;
    padding: 1.5rem;
    color: var(--color-text-primary);
  }}
  .world-card {{
    background: var(--color-bg-primary);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1rem 1.25rem;
    max-width: 680px;
    margin: 0 auto;
  }}
  .header {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }}
  .world-name {{
    font-size: 22px;
    font-weight: 500;
    margin: 0;
  }}
  .uwp {{
    font-family: ui-monospace, "Cascadia Code", "Fira Mono", monospace;
    font-size: 18px;
    font-weight: 500;
    color: var(--color-text-secondary);
    margin: 0;
  }}
  .badge {{
    display: inline-block;
    font-size: 12px;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: var(--radius-md);
    margin: 2px 3px 2px 0;
  }}
  .zone-green  {{ background:#e1f5ee; color:#085041; }}
  .zone-amber  {{ background:#faeeda; color:#633806; }}
  .zone-red    {{ background:#fcebeb; color:#791f1f; }}
  .trade       {{ background:#faece7; color:#712b13; }}
  .era-primitive     {{ background:#f1efe8; color:#444441; }}
  .era-industrial    {{ background:#faeeda; color:#633806; }}
  .era-prestellar    {{ background:#e6f1fb; color:#0c447c; }}
  .era-earlystellar  {{ background:#e1f5ee; color:#085041; }}
  .era-avgstellar    {{ background:#eeedfe; color:#3c3489; }}
  .era-highstellar   {{ background:#fbeaf0; color:#72243e; }}
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 12px;
  }}
  .stat {{
    background: var(--color-bg-secondary);
    border-radius: var(--radius-md);
    padding: 12px;
  }}
  .stat-label  {{ font-size:12px; color:var(--color-text-secondary); margin:0 0 2px; }}
  .stat-value  {{ font-size:15px; font-weight:500; margin:0; }}
  .stat-sub    {{ font-size:13px; color:var(--color-text-secondary); margin:2px 0 0; }}
  .detail-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }}
  .inner-card {{
    background: var(--color-bg-primary);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 12px;
  }}
  .inner-label {{
    font-size: 12px;
    color: var(--color-text-secondary);
    margin: 0 0 8px;
  }}
  .detail-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 6px 0;
    border-bottom: 0.5px solid var(--color-border);
  }}
  .detail-row:last-child {{ border-bottom: none; }}
  .row-label {{ font-size:13px; color:var(--color-text-secondary); }}
  .trade-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }}
  .trade-label {{ font-size:12px; color:var(--color-text-secondary); }}
  details summary {{
    font-size: 12px;
    color: var(--color-text-secondary);
    cursor: pointer;
    padding: 4px 0;
    margin-top: 12px;
  }}
  pre {{
    font-family: ui-monospace, "Cascadia Code", "Fira Mono", monospace;
    font-size: 12px;
    color: var(--color-text-secondary);
    white-space: pre-wrap;
    line-height: 1.6;
    margin: 8px 0 0;
  }}
  @media (max-width: 500px) {{
    .stat-grid   {{ grid-template-columns: 1fr 1fr; }}
    .detail-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="world-card">

  <div class="header">
    <p class="world-name">{esc(self.name)}</p>
    <p class="uwp">{esc(self.uwp())}</p>
    {zone_badge}
  </div>

  <div class="stat-grid">
    <div class="stat">
      <p class="stat-label">Starport</p>
      <p class="stat-value">{esc(self.starport)} — {esc(STARPORT_QUALITY_LABEL.get(self.starport, "?"))}</p>
      <p class="stat-sub">{esc(STARPORT_FACILITY_DETAIL.get(self.starport, ""))}</p>
    </div>
    <div class="stat">
      <p class="stat-label">Size</p>
      <p class="stat-value">{esc(to_hex(self.size))} — {esc(d["size"]["diameter_km"])} km</p>
      <p class="stat-sub">Surface gravity {esc(d["size"]["surface_gravity"])}</p>
    </div>
    <div class="stat">
      <p class="stat-label">Tech level</p>
      <p class="stat-value">{esc(to_hex(self.tech_level))}</p>
      <p class="stat-sub"><span class="badge {esc(tl_era_css)}" style="margin:0">{esc(tl_era)}</span></p>
    </div>
  </div>

  <div class="detail-grid">
    <div class="inner-card">
      <p class="inner-label">Physical characteristics</p>
      {row("Atmosphere", f'{to_hex(self.atmosphere)} — {d["atmosphere"]["name"]}')}
      {survival_row}
      {row("Temperature", self.temperature)}
      {row("Hydrographics", f'{to_hex(self.hydrographics)} — {d["hydrographics"]["description"].split(" (")[0]}')}
      {row("Gas giants", str(self.gas_giant_count) if self.has_gas_giant else "None")}
      {row("Planetoid belts", str(self.belt_count))}
      {row("PBG", f'{self.population_multiplier}{self.belt_count}{self.gas_giant_count}')}
    </div>
    <div class="inner-card">
      <p class="inner-label">Society</p>
      {row("Population", f'{to_hex(self.population)} — {d["population"]["range"]}{" (P=" + str(self.population_multiplier) + ")" if self.population > 0 else ""}')}
      {row("Government", f'{to_hex(self.government)} — {d["government"]["name"]}')}
      {row("Law level", to_hex(self.law_level))}
      {row("Bases", bases_str)}
    </div>
  </div>

  <div class="trade-row">
    <span class="trade-label">Trade codes</span>
    {trade_badges}
  </div>

  {notes_html}

  <details>
    <summary>Raw JSON</summary>
    <pre>{esc(self.to_json())}</pre>
  </details>

</div>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Human-readable summary
    # ------------------------------------------------------------------
    def summary(self) -> str:
        pop_range = {
            0: "None", 1: "Few (1+)", 2: "Hundreds", 3: "Thousands",
            4: "Tens of thousands", 5: "Hundreds of thousands",
            6: "Millions", 7: "Tens of millions", 8: "Hundreds of millions",
            9: "Billions", 10: "Tens of billions",
        }
        size_km = {
            0: "<1,000 km", 1: "1,600 km", 2: "3,200 km", 3: "4,800 km",
            4: "6,400 km", 5: "8,000 km", 6: "9,600 km", 7: "11,200 km",
            8: "12,800 km", 9: "14,400 km", 10: "16,000 km",
        }
        gravity = {
            0: "negligible", 1: "0.05G", 2: "0.15G", 3: "0.25G",
            4: "0.35G", 5: "0.45G", 6: "0.70G", 7: "0.90G",
            8: "1.00G", 9: "1.25G", 10: "1.40G",
        }

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

        if self.notes:
            lines.append(f"{'-'*56}")
            lines.append("  Notes:")
            for note in self.notes:
                lines.append(f"    * {note}")

        lines.append(f"{'='*56}")
        return "\n".join(lines)


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


def generate_population() -> int:
    """Step 5 — Population (p.251-252): roll 2D-2, range 0-10.

    Population 0 = uninhabited.  The referee may optionally place very
    high-population worlds (11-12) but the dice do not produce these.
    """
    return roll(2, -2)


def generate_government(population: int) -> int:
    """Step 6 — Government (p.252): roll 2D-7 + Population, minimum 0.

    If Population is 0 the world is uninhabited and has no government.
    """
    if population == 0:
        return 0
    return max(0, roll(2, -7 + population))


def generate_law_level(government: int) -> int:
    """Step 7 — Law Level (p.255): roll 2D-7 + Government, minimum 0.

    Law Level 0 = no restrictions; higher values ban progressively more.
    If Population is 0 (handled by caller), Law Level should also be 0.
    """
    return max(0, roll(2, -7 + government))


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


def generate_tech_level(starport: str, size: int, atmosphere: int,
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
        return (random.randint(1, 6) + 1) // 2   # gives 1, 2 or 3

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
    elif result <= 6:
        return 2
    elif result <= 8:
        return 3
    elif result <= 11:
        return 4
    elif result == 12:
        return 5
    else:
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


def assign_trade_codes(size: int, atmosphere: int, hydrographics: int,
                       population: int, government: int,
                       law_level: int, tech_level: int) -> List[str]:
    """Step 12 — Trade Codes (p.260-261).

    Each code is awarded if ALL listed criteria are met.  Criteria are
    taken directly from the Trade Codes table on p.260.
    """
    codes = []

    # Agricultural (Ag): arable worlds with reasonable water and population
    if (4 <= size <= 9 and 4 <= atmosphere <= 8 and 5 <= hydrographics <= 7):
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
    if atmosphere <= 1 and hydrographics >= 1:
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
                       law_level: int) -> str:
    """Step 13 — Travel Zone (p.260).

    Green is the default safe zone (no special designation).
    Amber worlds warrant caution: unusual atmosphere, unstable government,
    or extreme law level.
    Red zones are referee-assigned interdictions (e.g. quarantine, Imperium
    edict) and are only suggested here — the referee makes the final call.

    Amber criteria (p.260):
      Atmosphere 10+, OR Government 0/7/10, OR Law Level 0 or 9+
    """
    amber = (
        atmosphere >= 10
        or government in (0, 7, 10)
        or law_level == 0
        or law_level >= 9
    )
    return "Amber" if amber else "Green"
    # Note: Red zones are not randomly generated — they are referee decisions.


# ---------------------------------------------------------------------------
# Master generation function
# ---------------------------------------------------------------------------

def generate_world(name: str = "Unknown") -> World:
    """Generate a complete mainworld following the rulebook procedure.

    Steps 1-13 are performed in order, each using the results of
    previous steps exactly as the rulebook specifies.
    """
    world = World(name=name)

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
    world.population = generate_population()

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
        world.atmosphere, world.government, world.law_level
    )

    return world


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
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

    if args.seed is not None:
        random.seed(args.seed)
        if not args.json and not args.html:
            print(f"[Using random seed {args.seed}]\n")

    worlds = []
    for i in range(args.count):
        if args.name and args.count == 1:
            name = args.name
        elif args.name:
            name = f"{args.name}-{i+1}"
        else:
            name = f"World-{i+1}"

        world = generate_world(name=name)
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
            # Single world: emit the full standalone HTML document.
            print(worlds[0].to_html())
        else:
            # Multiple worlds: wrap all cards in one HTML page.
            # Strip the outer <html>…</body> wrapper from each card after
            # the first, keeping only the inner <div class="world-card">.
            import re
            cards_html = []
            for w in worlds:
                full = w.to_html()
                # Extract just the world-card div from each world's HTML
                match = re.search(
                    r'(<div class="world-card">.*?</div>)\s*</body>',
                    full, re.DOTALL
                )
                cards_html.append(match.group(1) if match else full)

            # Re-use the CSS from the first world's page, adjust body style
            first_html = worlds[0].to_html()
            # Replace the single-card body content with all cards
            combined = re.sub(
                r'<body>.*</body>',
                '<body>\n'
                + '\n'.join(cards_html)
                + '\n</body>',
                first_html,
                flags=re.DOTALL,
            )
            # Adjust body padding and add gap between cards
            combined = combined.replace(
                "max-width: 680px;\n    margin: 0 auto;",
                "max-width: 680px;\n    margin: 0 auto;\n    margin-bottom: 1.5rem;",
            )
            print(combined)

    else:
        for i, world in enumerate(worlds):
            print(world.summary())
            if i < len(worlds) - 1:
                print()


if __name__ == "__main__":
    main()
