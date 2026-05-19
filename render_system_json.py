"""
render_system_json.py
=====================
Render a Traveller system JSON file to a self-contained HTML document.

Usage
-----
    python render_system_json.py <input.json> [output.html]

When *output.html* is omitted the HTML is written to stdout.

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

import json
import sys
from html import escape as _esc
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EHEX = "0123456789ABCDEFG"


def esc(value: Any) -> str:
    """HTML-escape a value coerced to string."""
    return _esc(str(value))


def ehex(code: int) -> str:
    """Convert a numeric UWP code to eHex character (10 = A … 16 = G)."""
    if 0 <= code < len(_EHEX):
        return _EHEX[code]
    return str(code)


def fmt_period(period_yr: float) -> str:
    """Format an orbital period: hours, days, or years."""
    days = period_yr * 365.25
    if days < 1.0:
        return f"{days * 24:.1f}h"
    if days < 365.25:
        return f"{days:.1f}d"
    return f"{period_yr:.2f}y"


def _get(d: dict, *keys: str, default: Any = "") -> Any:
    """Nested dict lookup with a safe default."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


_TIDAL_LABELS = {
    "braking":   "Tidal braking",
    "prograde":  "Prograde (tidally slowed)",
    "retrograde": "Retrograde (tidally induced)",
    "3:2_lock":  "3:2 resonance lock",
    "1:1_lock":  "1:1 tidal lock (synchronous)",
}

_ANOMALY_LABELS = {
    "random":           "Rand",
    "eccentric":        "Ecc",
    "inclined":         "Incl",
    "retrograde":       "Retro",
    "trojan_leading":   "L4",
    "trojan_trailing":  "L5",
}

_BASE_NAMES = {
    "N": "Naval",
    "S": "Scout",
    "M": "Military",
    "H": "Highport",
    "C": "Corsair",
}


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _drow(label: str, value: str) -> str:
    return (
        f'<div class="drow">'
        f'<span class="dlbl">{esc(label)}</span>'
        f'<span>{esc(value)}</span>'
        f'</div>'
    )


def _render_stars(stars: list[dict]) -> str:  # pylint: disable=too-many-locals
    rows = ""
    for star in stars:
        desig = star.get("designation", "?")
        cls   = star.get("classification", "?")
        mass  = star.get("mass_solar", 0.0)
        temp  = star.get("temperature_k", 0)
        lum   = star.get("luminosity_solar", 0.0)
        orb_n = star.get("orbit_number", 0.0)
        orb_a = star.get("orbit_au", 0.0)
        period = star.get("orbit_period_yr")
        ecc   = star.get("orbit_eccentricity", 0.0)
        incl  = star.get("orbit_inclination", 0.0)
        colour = star.get("colour", "")
        notes  = star.get("special_notes", "")

        if orb_n:
            orb_str = f"Orbit# {orb_n:.2f} ({orb_a:.2f} AU)"
            if period is not None:
                orb_str += f"  P={fmt_period(period)}"
            if ecc > 0:
                orb_str += f"  e={ecc:.3f}"
            if incl > 0:
                orb_str += f"  i={incl:.1f}°"
        else:
            orb_str = "Primary"

        note_parts = [p for p in (colour, notes) if p]
        note_str = "  ·  ".join(note_parts)

        rows += (
            f'<tr>'
            f'<td class="mono">{esc(desig)}</td>'
            f'<td class="mono">{esc(cls)}</td>'
            f'<td class="mono">{mass:.2f} M☉</td>'
            f'<td class="mono">{temp:,} K</td>'
            f'<td class="mono">{lum:.3g} L☉</td>'
            f'<td>{esc(orb_str)}</td>'
            f'<td class="note-cell">{esc(note_str)}</td>'
            f'</tr>'
        )
    return (
        '<div class="section-title">Stars</div>'
        '<table>'
        '<thead><tr>'
        '<th>Desig</th><th>Class</th><th>Mass</th>'
        '<th>Temp</th><th>Lum</th><th>Orbit</th><th>Notes</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    )


def _orbit_profile(slot: dict) -> tuple[str, str]:
    """Return (profile_html, type_class) for an orbit slot."""
    wtype = slot.get("world_type", "empty")
    canonical = slot.get("canonical_profile", "")
    gg_sah    = slot.get("gg_sah", "")
    detail    = slot.get("detail")

    if wtype == "empty":
        return "—", "type-empty"

    if canonical:
        type_cls = (
            "type-belt" if wtype == "belt"
            else "type-inh" if _get(detail, "inhabited") else "type-terr"
        )
        return esc(canonical), type_cls

    if detail is not None:
        if wtype == "gas_giant":
            return esc(gg_sah or detail.get("profile", "")), "type-gg"
        prof = detail.get("profile", "")
        if wtype == "belt":
            type_cls = "type-belt"
        elif detail.get("inhabited"):
            type_cls = "type-inh"
        else:
            type_cls = "type-terr"
        return esc(prof), type_cls

    if wtype == "gas_giant" and gg_sah:
        return esc(gg_sah), "type-gg"
    return "", "type-terr"


def _render_moon_rows(moons: list[dict]) -> str:
    rows = ""
    for mi, moon in enumerate(moons, 1):
        is_ring = moon.get("is_ring", False)
        size    = moon.get("size", "?")
        detail  = moon.get("detail")

        if is_ring:
            count = moon.get("ring_count", 1)
            mp = f"R{count:02d}"
            codes_html = ""
        elif detail is not None:
            mp = esc(detail.get("profile", ""))
            codes_html = "".join(
                f'<span class="badge trade">{esc(tc)}</span>'
                for tc in detail.get("trade_codes", [])
            )
        else:
            mp = f"size {esc(str(size))}"
            codes_html = ""

        size_label = "ring" if is_ring else f"size {esc(str(size))}"

        orbit_pd  = moon.get("orbit_pd")
        orbit_km  = moon.get("orbit_km")
        period_h  = moon.get("orbit_period_hours")
        orb_range = moon.get("orbit_range")

        pd_str     = f"{orbit_pd:.1f} PD" if orbit_pd is not None else ""
        km_str     = f"{orbit_km:,.0f} km" if orbit_km is not None else ""
        period_str = fmt_period(period_h / 24 / 365.25) if period_h is not None else ""
        range_str  = orb_range.capitalize() if orb_range else ""

        rows += (
            f'<tr class="moon-row">'
            f'<td></td>'
            f'<td class="mono moon-idx">↳ m{mi}</td>'
            f'<td class="mono">{pd_str}</td>'
            f'<td class="mono">{km_str}</td>'
            f'<td class="mono dim">{period_str}</td>'
            f'<td></td>'
            f'<td class="moon-type">{size_label}</td>'
            f'<td class="mono profile">{mp}</td>'
            f'<td class="codes-cell">{codes_html}</td>'
            f'<td>{range_str}</td>'
            f'<td></td>'
            f'</tr>'
        )
    return rows


def _render_orbits(orbits_data: dict) -> str:  # pylint: disable=too-many-locals
    slots  = orbits_data.get("orbits", [])
    detail_present = any(s.get("detail") is not None for s in slots
                         if s.get("world_type") != "empty")

    rows = ""
    for slot in slots:
        wtype    = slot.get("world_type", "empty")
        star     = slot.get("star", "?")
        idx      = slot.get("slot_index", "")
        orb_n    = slot.get("orbit_number", 0.0)
        orb_a    = slot.get("orbit_au", 0.0)
        temp_z   = slot.get("temperature_zone", "")
        is_mw    = slot.get("is_mainworld_candidate", False)
        notes_s  = slot.get("notes", "")
        period   = slot.get("orbit_period_yr")
        ecc      = slot.get("eccentricity", 0.0)
        incl     = slot.get("inclination", 0.0)
        anom     = slot.get("anomaly_type", "")

        profile_html, type_cls = _orbit_profile(slot)

        detail = slot.get("detail")
        if is_mw:
            codes = slot.get("canonical_profile_trade_codes") or []
            if not codes and detail is not None:
                codes = detail.get("trade_codes", [])
        elif detail is not None and not detail.get("is_gas_giant", False):
            codes = detail.get("trade_codes", [])
        else:
            codes = []
        codes_html = "".join(
            f'<span class="badge trade">{esc(tc)}</span>'
            for tc in codes
        )

        ecc_part  = f"{ecc:.3f}" if ecc > 0 else "—"
        incl_part = f"{incl:.1f}°" if incl > 0 else "—"
        ecc_incl  = f"{ecc_part}/{incl_part}" if (ecc > 0 or incl > 0) else "—"

        period_str = fmt_period(period) if period is not None else "—"

        anom_suffix = _ANOMALY_LABELS.get(anom, "")
        type_display = wtype.replace("_", " ")
        if anom_suffix:
            type_display = f"{type_display} [{anom_suffix}]"

        note_parts = []
        if is_mw:
            note_parts.append("← mainworld")
        if notes_s:
            note_parts.append(notes_s)
        note_cell = "  ".join(note_parts)

        row_cls = "mw-row" if is_mw else ""
        rows += (
            f'<tr class="{row_cls}">'
            f'<td class="mono">{esc(star)}</td>'
            f'<td class="mono">{esc(idx)}</td>'
            f'<td class="mono">{orb_n:.2f}</td>'
            f'<td class="mono">{orb_a:.3f}</td>'
            f'<td class="mono dim">{esc(period_str)}</td>'
            f'<td class="mono">{esc(ecc_incl)}</td>'
            f'<td class="{type_cls}">{esc(type_display)}</td>'
            f'<td class="mono profile">{profile_html}</td>'
            f'<td class="codes-cell">{codes_html}</td>'
            f'<td class="zone-{esc(temp_z)}">{esc(temp_z)}</td>'
            f'<td class="mw-note">{esc(note_cell)}</td>'
            f'</tr>'
        )
        if detail is not None:
            rows += _render_moon_rows(detail.get("moons", []))

    detail_note = "  ·  detail included" if detail_present else ""
    return (
        f'<div class="section-title">Orbital survey{esc(detail_note)}</div>'
        '<div class="table-scroll">'
        '<table>'
        '<thead><tr>'
        '<th>Star</th><th>#</th><th>Orbit#</th><th>AU</th>'
        '<th>Period</th><th>Ecc/Incl</th><th>Type</th>'
        '<th>Profile</th><th>Codes</th><th>Zone</th><th></th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
        '</div>'
    )


def _render_star_zones(orbits_data: dict) -> str:
    zones = orbits_data.get("star_zones", {})
    if not zones:
        return ""
    rows = ""
    for desig, z in zones.items():
        rows += (
            f'<tr>'
            f'<td class="mono">{esc(desig)}</td>'
            f'<td class="mono">{z.get("mao", 0):.2f}</td>'
            f'<td class="mono">{z.get("hzco", 0):.2f}</td>'
            f'<td class="mono">{z.get("hz_inner", 0):.2f} – {z.get("hz_outer", 0):.2f}</td>'
            f'</tr>'
        )
    return (
        '<div class="section-title">Habitable zones</div>'
        '<table style="max-width:420px">'
        '<thead><tr><th>Star</th><th>MAO</th><th>HZCO</th><th>HZ band</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    )


def _render_orbit_counts(orbits_data: dict) -> str:
    parts = [
        f"Gas giants: {orbits_data.get('gas_giant_count', 0)}",
        f"Belts: {orbits_data.get('belt_count', 0)}",
        f"Terrestrial: {orbits_data.get('terrestrial_count', 0)}",
        f"Empty: {orbits_data.get('empty_orbits', 0)}",
    ]
    spans = "  ·  ".join(
        f'<span class="chip">{esc(p)}</span>' for p in parts
    )
    return f'<div class="chip-row">{spans}</div>'


def _render_physical(sd: dict) -> str:
    if "composition" in sd:
        tidal = sd.get("tidal_status", "none")
        tidal_row = (
            _drow("Tidal status", _TIDAL_LABELS.get(tidal, tidal))
            if tidal and tidal != "none" else ""
        )
        ecc_adj = sd.get("eccentricity_adjusted")
        ecc_row = (
            _drow("Eccentricity adjusted", f"{ecc_adj:.3f}")
            if ecc_adj is not None else ""
        )
        body = (
            _drow("Composition", sd.get("composition", ""))
            + _drow("Diameter", f"{sd.get('diameter_km', 0):,} km")
            + _drow("Density", f"{sd.get('density_g_cm3', 0):.2f} g/cm³")
            + _drow("Mass", f"{sd.get('mass_earth', 0):.4f} M⊕")
            + _drow("Surface gravity", f"{sd.get('gravity_g', 0):.3f} G")
            + _drow("Escape velocity", f"{sd.get('escape_velocity_km_s', 0):.2f} km/s")
            + _drow("Axial tilt", f"{sd.get('axial_tilt_deg', 0)}°")
            + _drow("Day length", f"{sd.get('day_length_hours', 0):.1f} h")
            + tidal_row
            + ecc_row
        )
        title = "World body"
    else:
        body = (
            _drow("Belt span",
                  f"{sd.get('inner_au', 0):.3f} – {sd.get('outer_au', 0):.3f} AU")
            + _drow("Bulk", str(sd.get("bulk", "")))
            + _drow("Resource rating", str(sd.get("resource_rating", "")))
            + _drow("Composition",
                    f"M {sd.get('m_type_pct', 0)}%  ·  "
                    f"S {sd.get('s_type_pct', 0)}%  ·  "
                    f"C {sd.get('c_type_pct', 0)}%")
            + _drow("Significant bodies",
                    f"{sd.get('size_1_bodies', 0)} × Sz 1, "
                    f"{sd.get('size_s_bodies', 0)} × Sz S")
        )
        title = "Belt body"

    return (
        f'<div class="inner-card">'
        f'<p class="inner-lbl">{esc(title)}</p>'
        f'{body}'
        f'</div>'
    )


def _render_atmosphere(atm: dict) -> str:  # pylint: disable=too-many-branches,too-many-locals
    detail = atm.get("detail")
    if not detail:
        return ""

    rows = _drow("Profile", atm.get("profile", ""))

    sn = detail.get("subtype_name")
    if sn:
        rows += _drow("Subtype", sn)

    pb = detail.get("pressure_bar")
    if pb is not None:
        rows += _drow("Pressure", f"{pb:.3f} bar")
    elif atm.get("code") in (11, 12, 13):
        rows += _drow("Pressure", "> 10.0 bar (extremely dense)")

    ppo = detail.get("oxygen_partial_pressure_bar")
    if ppo is not None:
        rows += _drow("O₂ partial pressure", f"{ppo:.3f} bar")

    sh = detail.get("scale_height_km")
    if sh is not None:
        rows += _drow("Scale height", f"{sh:.1f} km")

    if detail.get("no_safe_altitude"):
        rows += _drow("Safe altitude", "None (no breathable level)")
    else:
        msa = detail.get("min_safe_altitude_km")
        if msa is not None:
            if msa >= 0:
                rows += _drow("Min safe altitude", f"{msa:.1f} km above baseline")
            else:
                rows += _drow("Max safe depth", f"{abs(msa):.1f} km below baseline")

    for sub in detail.get("unusual_subtypes", []):
        rows += _drow("Unusual subtype",
                      f"{sub.get('subtype_name', '')} ({sub.get('subtype_code', '')})")

    taints = detail.get("taints", [])
    for i, taint in enumerate(taints):
        prefix = f"Taint {i + 1}" if len(taints) > 1 else "Taint"
        rows += _drow(prefix, taint.get("subtype", ""))
        rows += _drow("  Severity", taint.get("severity", ""))
        rows += _drow("  Persistence", taint.get("persistence", ""))

    for hazard in detail.get("hazards", []):
        rows += _drow("Hazard", hazard.get("hazard", ""))
        gases = hazard.get("gases", [])
        if gases:
            rows += _drow("  Gas mix", ", ".join(gases))

    gas_mix = detail.get("gas_mix", [])
    if gas_mix:
        parts = []
        for c in gas_mix:
            part = f"{c.get('gas_name', '')} ({c.get('gas_code', '')})"
            pct = c.get("percentage")
            if pct is not None:
                part += f" {pct}%"
            parts.append(part)
        rows += _drow("Gas mix", "  ·  ".join(parts))

    return (
        '<div class="inner-card">'
        '<p class="inner-lbl">Atmosphere detail</p>'
        f'{rows}'
        '</div>'
    )


def _render_mainworld(mw: dict) -> str:  # pylint: disable=too-many-locals,too-many-statements
    if not mw:
        return '<p class="no-val">No mainworld determined.</p>'

    name      = mw.get("name", "Unknown")
    uwp       = mw.get("uwp", "???????-?")
    zone      = mw.get("travel_zone", "Green")
    _zone_map = {"Green": "zone-green", "Amber": "zone-amber", "Red": "zone-red"}
    zone_cls  = _zone_map.get(zone, "zone-green")

    sp        = mw.get("starport", {})
    sp_code   = sp.get("code", "?") if isinstance(sp, dict) else str(sp)
    sp_desc   = sp.get("description", "") if isinstance(sp, dict) else ""

    size_d    = mw.get("size", {})
    sz_code   = size_d.get("code", 0) if isinstance(size_d, dict) else int(size_d or 0)
    sz_diam   = (size_d.get("diameter_km", f"{sz_code * 1600}")
                 if isinstance(size_d, dict) else f"{sz_code * 1600}")
    sz_grav   = size_d.get("surface_gravity", "") if isinstance(size_d, dict) else ""

    atm_d     = mw.get("atmosphere", {})
    atm_code  = atm_d.get("code", 0) if isinstance(atm_d, dict) else int(atm_d or 0)
    atm_name  = atm_d.get("name", "") if isinstance(atm_d, dict) else ""
    atm_gear  = atm_d.get("survival_gear", "") if isinstance(atm_d, dict) else ""

    hyd_d     = mw.get("hydrographics", {})
    hyd_code  = hyd_d.get("code", 0) if isinstance(hyd_d, dict) else int(hyd_d or 0)
    hyd_desc  = hyd_d.get("description", "") if isinstance(hyd_d, dict) else ""

    pop_d     = mw.get("population", {})
    pop_code  = pop_d.get("code", 0) if isinstance(pop_d, dict) else int(pop_d or 0)
    pop_range = pop_d.get("range", "") if isinstance(pop_d, dict) else ""

    gov_d     = mw.get("government", {})
    gov_code  = gov_d.get("code", 0) if isinstance(gov_d, dict) else int(gov_d or 0)
    gov_name  = gov_d.get("name", "") if isinstance(gov_d, dict) else ""

    law       = mw.get("law_level", 0)
    tl        = mw.get("tech_level", 0)
    temp      = mw.get("temperature", "")
    pbg       = mw.get("pbg", "")

    bases     = mw.get("bases", [])
    bases_str = "  ".join(
        f"{_BASE_NAMES.get(b, b)} ({b})" for b in bases
    ) if bases else "None"

    trade_codes = mw.get("trade_codes", [])
    trade_html = "".join(
        f'<span class="badge trade">{esc(tc)}</span>'
        for tc in trade_codes
    ) or '<span class="no-val">None</span>'

    sz_label = f"{sz_diam} km" if sz_code else "Belt"
    grav_label = f" · {sz_grav}" if sz_grav else ""

    stats_html = f"""
  <div class="stat">
    <p class="sl">UWP</p>
    <p class="sv mono">{esc(uwp)}</p>
    <p class="ss"><span class="badge {zone_cls}">{esc(zone)} zone</span></p>
  </div>
  <div class="stat">
    <p class="sl">Starport {esc(sp_code)}</p>
    <p class="sv">{esc(sp_desc)}</p>
  </div>
  <div class="stat">
    <p class="sl">Size {esc(ehex(sz_code))}</p>
    <p class="sv">{esc(sz_label)}</p>
    <p class="ss">{esc(grav_label.strip(" ·"))}</p>
  </div>
  <div class="stat">
    <p class="sl">Atmosphere {esc(ehex(atm_code))}</p>
    <p class="sv">{esc(atm_name)}</p>
    <p class="ss">{esc(atm_gear)}</p>
  </div>
  <div class="stat">
    <p class="sl">Temperature</p>
    <p class="sv">{esc(temp)}</p>
  </div>
  <div class="stat">
    <p class="sl">Hydrographics {esc(ehex(hyd_code))}</p>
    <p class="sv">{esc(hyd_desc)}</p>
  </div>
  <div class="stat">
    <p class="sl">Population {esc(ehex(pop_code))}</p>
    <p class="sv">{esc(pop_range)}</p>
    <p class="ss">TL {esc(ehex(tl))}</p>
  </div>
  <div class="stat">
    <p class="sl">Government {esc(ehex(gov_code))}</p>
    <p class="sv">{esc(gov_name)}</p>
  </div>
  <div class="stat">
    <p class="sl">Law Level</p>
    <p class="sv mono">{esc(ehex(law))}</p>
  </div>
  <div class="stat">
    <p class="sl">PBG</p>
    <p class="sv mono">{esc(pbg)}</p>
  </div>
  <div class="stat">
    <p class="sl">Bases</p>
    <p class="sv">{esc(bases_str)}</p>
  </div>"""

    html = f'<div class="section-title">Mainworld — {esc(name)}</div>'
    html += f'<div class="mw-grid">{stats_html}</div>'
    html += f'<div class="trade-row"><span class="trade-lbl">Trade codes</span>{trade_html}</div>'

    sd = mw.get("size_detail")
    if sd:
        html += _render_physical(sd)

    html += _render_atmosphere(mw.get("atmosphere", {}))

    hyd_detail = _get(mw, "hydrographics", "detail")
    if isinstance(hyd_detail, dict):
        pct = hyd_detail.get("surface_liquid_pct")
        if pct is not None:
            html += (
                '<div class="inner-card">'
                '<p class="inner-lbl">Hydrographic detail</p>'
                + _drow("Surface liquid", f"{pct}%")
                + '</div>'
            )

    notes = mw.get("notes", [])
    if notes:
        note_rows = "".join(
            f'<li>{esc(n)}</li>' for n in notes
        )
        html += (
            '<div class="inner-card">'
            '<p class="inner-lbl">Notes</p>'
            f'<ul class="note-list">{note_rows}</ul>'
            '</div>'
        )

    return html


# ---------------------------------------------------------------------------
# Full document
# ---------------------------------------------------------------------------

def render(data: dict) -> str:
    """Render a system JSON dict to a self-contained HTML string."""
    stars      = data.get("stars", [])
    age        = data.get("age_gyr")
    orbits_d   = data.get("orbits", {})
    mw         = data.get("mainworld") or {}

    title = esc((mw.get("name") or "Unknown") + " system")
    age_str  = f"{age:.2f} Gyr" if age else "?"
    n_worlds = orbits_d.get("total_worlds", 0)
    star_classes = " + ".join(
        esc(s.get("classification", "?")) for s in stars
    )

    stars_html     = _render_stars(stars)
    zones_html     = _render_star_zones(orbits_d)
    counts_html    = _render_orbit_counts(orbits_d)
    orbits_html    = _render_orbits(orbits_d)
    mainworld_html = _render_mainworld(mw)
    raw_json       = esc(json.dumps(data, indent=2, ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
:root{{
  --bg1:#ffffff;--bg2:#f5f5f3;--bg3:#eeede8;
  --txt1:#1a1a19;--txt2:#6b6a65;--txt3:#b0aea7;
  --bdr:rgba(0,0,0,0.12);--r8:8px;--r12:12px;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
}}
@media(prefers-color-scheme:dark){{:root{{
  --bg1:#1e1e1c;--bg2:#2a2a28;--bg3:#323230;
  --txt1:#e8e6de;--txt2:#9c9a92;--txt3:#6b6a65;
  --bdr:rgba(255,255,255,0.10);
}}}}
body{{background:var(--bg3);margin:0;padding:1.5rem;color:var(--txt1)}}
.card{{background:var(--bg1);border:0.5px solid var(--bdr);border-radius:var(--r12);
  padding:1rem 1.25rem;max-width:1000px;margin:0 auto 1rem}}
.header{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}}
h1{{font-size:22px;font-weight:500;margin:0}}
.sub{{font-size:14px;color:var(--txt2);margin:0}}
.badge{{display:inline-block;font-size:11px;font-weight:500;padding:2px 9px;
  border-radius:var(--r8);margin:2px 2px 2px 0}}
.zone-green{{background:#e1f5ee;color:#085041}}
.zone-amber{{background:#faeeda;color:#633806}}
.zone-red{{background:#fcebeb;color:#791f1f}}
.trade{{background:#faece7;color:#712b13}}
.b-gray{{background:#f1efe8;color:#444441}}
.section-title{{font-size:13px;font-weight:500;color:var(--txt2);
  margin:16px 0 8px;text-transform:uppercase;letter-spacing:0.05em}}
.table-scroll{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;padding:4px 6px;color:var(--txt2);font-weight:500;
  border-bottom:1px solid var(--bdr);white-space:nowrap}}
td{{padding:3px 6px;border-bottom:0.5px solid var(--bdr);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.mono{{font-family:ui-monospace,"Cascadia Code","Fira Mono",monospace}}
.dim{{color:var(--txt3)}}
.profile{{color:var(--txt1)}}
.type-gg{{color:#1a5fa8}}
.type-inh{{color:#085041;font-weight:500}}
.type-terr{{color:var(--txt2)}}
.type-belt{{color:var(--txt3)}}
.type-empty{{color:var(--txt3)}}
.mw-row td{{background:var(--bg2);font-weight:500}}
.mw-note{{font-size:11px;color:#085041}}
.moon-row td{{color:var(--txt2);font-size:11px;background:var(--bg1)}}
.moon-type{{padding-left:24px}}
.moon-idx{{color:var(--txt3)}}
.note-cell{{font-size:11px;color:var(--txt2)}}
.zone-boiling{{color:#791f1f;font-weight:500}}
.zone-hot{{color:#633806;font-weight:500}}
.zone-temperate{{color:#085041;font-weight:500}}
.zone-cold{{color:#0c447c}}
.zone-frozen{{color:var(--txt3)}}
.mw-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}}
@media(max-width:640px){{.mw-grid{{grid-template-columns:repeat(2,1fr)}}}}
.stat{{background:var(--bg2);border-radius:var(--r8);padding:10px 12px}}
.sl{{font-size:11px;color:var(--txt2);margin:0 0 2px}}
.sv{{font-size:14px;font-weight:500;margin:0}}
.ss{{font-size:11px;color:var(--txt2);margin:2px 0 0}}
.trade-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}}
.codes-cell{{white-space:nowrap}}
.trade-lbl{{font-size:12px;color:var(--txt2)}}
.no-val{{font-size:13px;color:var(--txt2);margin:0}}
.inner-card{{background:var(--bg1);border:0.5px solid var(--bdr);border-radius:var(--r8);
  padding:10px 12px;margin-top:10px}}
.inner-lbl{{font-size:11px;color:var(--txt2);margin:0 0 6px}}
.drow{{display:flex;justify-content:space-between;align-items:baseline;
  padding:4px 0;border-bottom:0.5px solid var(--bdr);font-size:12px}}
.drow:last-child{{border-bottom:none}}
.dlbl{{color:var(--txt2);flex-shrink:0;margin-right:8px}}
.chip-row{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}}
.chip{{font-size:12px;color:var(--txt2);background:var(--bg2);
  padding:3px 10px;border-radius:var(--r8)}}
.note-list{{margin:4px 0 0;padding-left:18px;font-size:12px;color:var(--txt2);
  line-height:1.6}}
details summary{{font-size:12px;color:var(--txt2);cursor:pointer;padding:4px 0;margin-top:12px}}
pre{{font-family:ui-monospace,monospace;font-size:11px;color:var(--txt2);
  white-space:pre-wrap;line-height:1.6;margin:8px 0 0}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>{title}</h1>
    <p class="sub mono">{star_classes}</p>
    <span class="badge b-gray">{esc(age_str)}</span>
    <span class="badge b-gray">{n_worlds} worlds</span>
  </div>

  {stars_html}

  {zones_html}

  {counts_html}

  {orbits_html}

  {mainworld_html}

  <details>
    <summary>Raw JSON</summary>
    <pre>{raw_json}</pre>
  </details>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:  # pylint: disable=missing-function-docstring
    if len(sys.argv) < 2:
        print("Usage: render_system_json.py <input.json> [output.html]",
              file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    html = render(data)

    if len(sys.argv) >= 3:
        out = Path(sys.argv[2])
        out.write_text(html, encoding="utf-8")
        print(f"Written to {out}", file=sys.stderr)
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()
