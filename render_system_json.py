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
from pathlib import Path
from typing import Any

from html_render import render as _render_template
from tables import TIDAL_STATUS_LABELS, ZONE_CSS_CLASS, BASE_FULL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EHEX = "0123456789ABCDEFG"


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


_ANOMALY_LABELS = {
    "random":          "Rand",
    "eccentric":       "Ecc",
    "inclined":        "Incl",
    "retrograde":      "Retro",
    "trojan_leading":  "L4",
    "trojan_trailing": "L5",
}


# ---------------------------------------------------------------------------
# Context builders — return plain dicts, no HTML
# ---------------------------------------------------------------------------

def _star_rows(stars: list[dict]) -> list[dict]:
    rows = []
    for star in stars:
        orb_n  = star.get("orbit_number", 0.0)
        orb_a  = star.get("orbit_au", 0.0)
        period = star.get("orbit_period_yr")
        ecc    = star.get("orbit_eccentricity", 0.0)
        incl   = star.get("orbit_inclination", 0.0)

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

        colour = star.get("colour", "")
        notes  = star.get("special_notes", "")
        note_str = "  ·  ".join(p for p in (colour, notes) if p)

        rows.append({
            "designation":    star.get("designation", "?"),
            "classification": star.get("classification", "?"),
            "mass_str":       f"{star.get('mass_solar', 0.0):.2f} M☉",
            "temp_str":       f"{star.get('temperature_k', 0):,} K",
            "lum_str":        f"{star.get('luminosity_solar', 0.0):.3g} L☉",
            "orbit_str":      orb_str,
            "note_str":       note_str,
        })
    return rows


def _zone_rows(orbits_data: dict) -> list[dict]:
    zones = orbits_data.get("star_zones", {})
    return [
        {
            "designation": desig,
            "mao":     f"{z.get('mao', 0):.2f}",
            "hzco":    f"{z.get('hzco', 0):.2f}",
            "hz_band": f"{z.get('hz_inner', 0):.2f} – {z.get('hz_outer', 0):.2f}",
        }
        for desig, z in zones.items()
    ]


def _orbit_counts(orbits_data: dict) -> dict:
    return {
        "gas_giants":  orbits_data.get("gas_giant_count", 0),
        "belts":       orbits_data.get("belt_count", 0),
        "terrestrial": orbits_data.get("terrestrial_count", 0),
        "empty":       orbits_data.get("empty_orbits", 0),
    }


def _moon_rows(moons: list[dict]) -> list[dict]:
    rows = []
    for mi, moon in enumerate(moons, 1):
        is_ring = moon.get("is_ring", False)
        detail  = moon.get("detail")
        size    = moon.get("size", "?")

        if is_ring:
            profile = f"R{moon.get('ring_count', 1):02d}"
            codes   = []
        elif detail is not None:
            profile = detail.get("profile", "")
            codes   = detail.get("trade_codes", [])
        else:
            profile = f"size {size}"
            codes   = []

        orbit_pd = moon.get("orbit_pd")
        orbit_km = moon.get("orbit_km")
        period_h = moon.get("orbit_period_hours")
        orb_range = moon.get("orbit_range", "")

        rows.append({
            "idx":        mi,
            "pd_str":     f"{orbit_pd:.1f} PD" if orbit_pd is not None else "",
            "km_str":     f"{orbit_km:,.0f} km" if orbit_km is not None else "",
            "period_str": fmt_period(period_h / 24 / 365.25) if period_h is not None else "",
            "size_label": "ring" if is_ring else f"size {size}",
            "profile":    profile,
            "codes":      codes,
            "range_str":  orb_range.capitalize() if orb_range else "",
        })
    return rows


def _orbit_profile(slot: dict) -> tuple[str, str]:
    """Return (profile_str, type_css_class) for an orbit slot."""
    wtype     = slot.get("world_type", "empty")
    canonical = slot.get("canonical_profile", "")
    gg_sah    = slot.get("gg_sah", "")
    detail    = slot.get("detail")

    if wtype == "empty":
        return "—", "type-empty"

    if canonical:
        if wtype == "belt":
            type_cls = "type-belt"
        elif detail is not None and _get(detail, "inhabited"):
            type_cls = "type-inh"
        else:
            type_cls = "type-terr"
        return canonical, type_cls

    if detail is not None:
        if wtype == "gas_giant":
            return gg_sah or detail.get("profile", ""), "type-gg"
        prof = detail.get("profile", "")
        if wtype == "belt":
            type_cls = "type-belt"
        elif detail.get("inhabited"):
            type_cls = "type-inh"
        else:
            type_cls = "type-terr"
        return prof, type_cls

    if wtype == "gas_giant" and gg_sah:
        return gg_sah, "type-gg"
    return "", "type-terr"


def _orbit_rows(orbits_data: dict) -> tuple[list[dict], bool]:  # pylint: disable=too-many-locals
    slots = orbits_data.get("orbits", [])
    detail_present = any(
        s.get("detail") is not None
        for s in slots if s.get("world_type") != "empty"
    )

    rows = []
    for slot in slots:
        wtype   = slot.get("world_type", "empty")
        is_mw   = slot.get("is_mainworld_candidate", False)
        detail  = slot.get("detail")
        ecc     = slot.get("eccentricity", 0.0)
        incl    = slot.get("inclination", 0.0)
        period  = slot.get("orbit_period_yr")
        anom    = slot.get("anomaly_type", "")
        notes_s = slot.get("notes", "")

        profile, type_cls = _orbit_profile(slot)

        if is_mw:
            codes = slot.get("canonical_profile_trade_codes") or []
            if not codes and detail is not None:
                codes = detail.get("trade_codes", [])
        elif detail is not None and not detail.get("is_gas_giant", False):
            codes = detail.get("trade_codes", [])
        else:
            codes = []

        ecc_part  = f"{ecc:.3f}" if ecc > 0 else "—"
        incl_part = f"{incl:.1f}°" if incl > 0 else "—"
        ecc_incl  = f"{ecc_part}/{incl_part}" if (ecc > 0 or incl > 0) else "—"

        anom_suffix  = _ANOMALY_LABELS.get(anom, "")
        type_display = wtype.replace("_", " ")
        if anom_suffix:
            type_display = f"{type_display} [{anom_suffix}]"

        note_parts = []
        if is_mw:
            note_parts.append("← mainworld")
        if notes_s:
            note_parts.append(notes_s)

        rows.append({
            "star":             slot.get("star", "?"),
            "slot_index":       slot.get("slot_index", ""),
            "orbit_num":        f"{slot.get('orbit_number', 0.0):.2f}",
            "orbit_au":         f"{slot.get('orbit_au', 0.0):.3f}",
            "period_str":       fmt_period(period) if period is not None else "—",
            "ecc_incl":         ecc_incl,
            "world_type_display": type_display,
            "type_cls":         type_cls,
            "profile":          profile,
            "codes":            codes,
            "temp_zone":        slot.get("temperature_zone", ""),
            "note_cell":        "  ".join(note_parts),
            "row_cls":          "mw-row" if is_mw else "",
            "moons":            _moon_rows(detail.get("moons", [])) if detail else [],
        })
    return rows, detail_present


def _phys_rows(sd: dict) -> tuple[str, list[dict]]:
    """Return (section title, [{label, value}]) for a size_detail block."""
    if "composition" in sd:
        rows: list[dict] = [
            {"label": "Composition",     "value": sd.get("composition", "")},
            {"label": "Diameter",        "value": f"{sd.get('diameter_km', 0):,} km"},
            {"label": "Density",         "value": f"{sd.get('density_g_cm3', 0):.2f} g/cm³"},
            {"label": "Mass",            "value": f"{sd.get('mass_earth', 0):.4f} M⊕"},
            {"label": "Surface gravity", "value": f"{sd.get('gravity_g', 0):.3f} G"},
            {"label": "Escape velocity", "value": f"{sd.get('escape_velocity_km_s', 0):.2f} km/s"},
            {"label": "Axial tilt",      "value": f"{sd.get('axial_tilt_deg', 0)}°"},
            {"label": "Day length",      "value": f"{sd.get('day_length_hours', 0):.1f} h"},
        ]
        mean_temp = sd.get("mean_temperature_k")
        if mean_temp is not None:
            rows.append({"label": "Mean temperature", "value": f"{mean_temp} K"})
        tidal = sd.get("tidal_status", "none")
        if tidal and tidal != "none":
            rows.append({"label": "Tidal status",
                         "value": TIDAL_STATUS_LABELS.get(tidal, tidal)})
        ecc_adj = sd.get("eccentricity_adjusted")
        if ecc_adj is not None:
            rows.append({"label": "Eccentricity adjusted", "value": f"{ecc_adj:.3f}"})
        rss = sd.get("residual_seismic_stress")
        if rss is not None:
            rows.append({"label": "Residual seismic stress", "value": str(rss)})
        thf = sd.get("tidal_heating_factor")
        if thf:
            rows.append({"label": "Tidal heating factor", "value": str(thf)})
        tss = sd.get("total_seismic_stress")
        if tss is not None:
            rows.append({"label": "Total seismic stress", "value": str(tss)})
        seis_t = sd.get("seismic_temperature_k")
        if seis_t is not None:
            rows.append({"label": "Seismic temperature", "value": f"{seis_t} K"})
        return "World body", rows

    rows = [
        {"label": "Belt span",
         "value": f"{sd.get('inner_au', 0):.3f} – {sd.get('outer_au', 0):.3f} AU"},
        {"label": "Bulk",            "value": str(sd.get("bulk", ""))},
        {"label": "Resource rating", "value": str(sd.get("resource_rating", ""))},
        {"label": "Composition",
         "value": (f"M {sd.get('m_type_pct', 0)}%  ·  "
                   f"S {sd.get('s_type_pct', 0)}%  ·  "
                   f"C {sd.get('c_type_pct', 0)}%")},
        {"label": "Significant bodies",
         "value": (f"{sd.get('size_1_bodies', 0)} × Sz 1, "
                   f"{sd.get('size_s_bodies', 0)} × Sz S")},
    ]
    return "Belt body", rows


def _atm_rows(atm: dict) -> list[dict]:  # pylint: disable=too-many-branches,too-many-locals
    detail = atm.get("detail")
    if not detail:
        return []

    rows: list[dict] = [{"label": "Profile", "value": atm.get("profile", "")}]

    sn = detail.get("subtype_name")
    if sn:
        rows.append({"label": "Subtype", "value": sn})

    pb = detail.get("pressure_bar")
    if pb is not None:
        rows.append({"label": "Pressure", "value": f"{pb:.3f} bar"})
    elif atm.get("code") in (11, 12, 13):
        rows.append({"label": "Pressure", "value": "> 10.0 bar (extremely dense)"})

    ppo = detail.get("oxygen_partial_pressure_bar")
    if ppo is not None:
        rows.append({"label": "O₂ partial pressure", "value": f"{ppo:.3f} bar"})

    sh = detail.get("scale_height_km")
    if sh is not None:
        rows.append({"label": "Scale height", "value": f"{sh:.1f} km"})

    if detail.get("no_safe_altitude"):
        rows.append({"label": "Safe altitude", "value": "None (no breathable level)"})
    else:
        msa = detail.get("min_safe_altitude_km")
        if msa is not None:
            if msa >= 0:
                rows.append({"label": "Min safe altitude",
                             "value": f"{msa:.1f} km above baseline"})
            else:
                rows.append({"label": "Max safe depth",
                             "value": f"{abs(msa):.1f} km below baseline"})

    for sub in detail.get("unusual_subtypes", []):
        rows.append({"label": "Unusual subtype",
                     "value": f"{sub.get('subtype_name', '')} ({sub.get('subtype_code', '')})"})

    taints = detail.get("taints", [])
    for i, taint in enumerate(taints):
        prefix = f"Taint {i + 1}" if len(taints) > 1 else "Taint"
        rows.append({"label": prefix,        "value": taint.get("subtype", "")})
        rows.append({"label": "  Severity",  "value": taint.get("severity", "")})
        rows.append({"label": "  Persistence","value": taint.get("persistence", "")})

    for hazard in detail.get("hazards", []):
        rows.append({"label": "Hazard", "value": hazard.get("hazard", "")})
        gases = hazard.get("gases", [])
        if gases:
            rows.append({"label": "  Gas mix", "value": ", ".join(gases)})

    gas_mix = detail.get("gas_mix", [])
    if gas_mix:
        parts = []
        for c in gas_mix:
            part = f"{c.get('gas_name', '')} ({c.get('gas_code', '')})"
            pct  = c.get("percentage")
            if pct is not None:
                part += f" {pct}%"
            parts.append(part)
        rows.append({"label": "Gas mix", "value": "  ·  ".join(parts)})

    return rows


def _mw_ctx(mw: dict) -> dict:  # pylint: disable=too-many-locals
    """Build the mainworld context dict from the JSON mainworld block."""
    zone     = mw.get("travel_zone", "Green")
    zone_cls = ZONE_CSS_CLASS.get(zone, "zone-green")

    sp      = mw.get("starport", {})
    sp_code = sp.get("code", "?") if isinstance(sp, dict) else str(sp)
    sp_desc = sp.get("description", "") if isinstance(sp, dict) else ""

    size_d  = mw.get("size", {})
    sz_code = size_d.get("code", 0) if isinstance(size_d, dict) else int(size_d or 0)
    sz_diam = (size_d.get("diameter_km", sz_code * 1600)
               if isinstance(size_d, dict) else sz_code * 1600)
    sz_grav = size_d.get("surface_gravity", "") if isinstance(size_d, dict) else ""

    atm_d    = mw.get("atmosphere", {})
    atm_code = atm_d.get("code", 0) if isinstance(atm_d, dict) else int(atm_d or 0)

    hyd_d    = mw.get("hydrographics", {})
    hyd_code = hyd_d.get("code", 0) if isinstance(hyd_d, dict) else int(hyd_d or 0)

    pop_d    = mw.get("population", {})
    pop_code = pop_d.get("code", 0) if isinstance(pop_d, dict) else int(pop_d or 0)

    gov_d    = mw.get("government", {})
    gov_code = gov_d.get("code", 0) if isinstance(gov_d, dict) else int(gov_d or 0)

    law = mw.get("law_level", 0)
    tl  = mw.get("tech_level", 0)

    bases    = mw.get("bases", [])
    bases_str = ("  ".join(f"{(BASE_FULL.get(b) or b).split(' — ', 1)[-1]} ({b})" for b in bases)
                 if bases else "None")

    sd = mw.get("size_detail")
    phys_title, phys_rows = _phys_rows(sd) if sd else ("", [])

    atm_rows = _atm_rows(atm_d) if isinstance(atm_d, dict) else []

    hyd_detail = _get(mw, "hydrographics", "detail")
    hyd_pct    = (hyd_detail.get("surface_liquid_pct")
                  if isinstance(hyd_detail, dict) else None)

    return {
        "name":       mw.get("name", "Unknown"),
        "uwp":        mw.get("uwp", "???????-?"),
        "zone":       zone,
        "zone_cls":   zone_cls,
        "sp_code":    sp_code,
        "sp_desc":    sp_desc,
        "sz_hex":     ehex(sz_code),
        "sz_label":   f"{sz_diam} km" if sz_code else "Belt",
        "grav_label": sz_grav,
        "atm_hex":    ehex(atm_code),
        "atm_name":   atm_d.get("name", "") if isinstance(atm_d, dict) else "",
        "atm_gear":   atm_d.get("survival_gear", "") if isinstance(atm_d, dict) else "",
        "hyd_hex":    ehex(hyd_code),
        "hyd_desc":   hyd_d.get("description", "") if isinstance(hyd_d, dict) else "",
        "pop_hex":    ehex(pop_code),
        "pop_range":  pop_d.get("range", "") if isinstance(pop_d, dict) else "",
        "tl_hex":     ehex(tl),
        "gov_hex":    ehex(gov_code),
        "gov_name":   gov_d.get("name", "") if isinstance(gov_d, dict) else "",
        "law_hex":    ehex(law),
        "temp":       mw.get("temperature", ""),
        "pbg":        mw.get("pbg", ""),
        "bases_str":  bases_str,
        "trade_codes": mw.get("trade_codes", []),
        "phys_title": phys_title,
        "phys_rows":  phys_rows,
        "atm_rows":   atm_rows,
        "hyd_pct":    hyd_pct,
        "notes":      mw.get("notes", []),
    }


# ---------------------------------------------------------------------------
# Public render entry point
# ---------------------------------------------------------------------------

def render(data: dict) -> str:
    """Render a system JSON dict to a self-contained HTML string."""
    stars    = data.get("stars", [])
    age      = data.get("age_gyr")
    orbits_d = data.get("orbits", {})
    mw_raw   = data.get("mainworld") or {}

    star_classes = " + ".join(s.get("classification", "?") for s in stars)
    orbit_rows, detail_present = _orbit_rows(orbits_d)

    return _render_template(
        "system_detail.html",
        title        = (mw_raw.get("name") or "Unknown") + " system",
        star_classes = star_classes,
        age_str      = f"{age:.2f} Gyr" if age else "?",
        n_worlds     = orbits_d.get("total_worlds", 0),
        star_rows    = _star_rows(stars),
        zone_rows    = _zone_rows(orbits_d),
        orbit_counts = _orbit_counts(orbits_d),
        orbit_rows   = orbit_rows,
        detail_present = detail_present,
        mw           = _mw_ctx(mw_raw) if mw_raw else None,
        json_str     = json.dumps(data, indent=2, ensure_ascii=False),
    )


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
