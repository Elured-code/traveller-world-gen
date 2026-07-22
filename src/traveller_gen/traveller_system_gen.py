"""
traveller_system_gen.py
=======================
Full system generation for the Traveller RPG, integrating:
  - Stellar generation  (traveller_stellar_gen.py  — WBH pp.14-29)
  - Orbit placement     (traveller_orbit_gen.py     — WBH pp.36-51)
  - Mainworld generation (traveller_world_gen.py    — CRB pp.248-261)

The key integration point is the Habitable Zones Regions table (WBH p.46-47),
which maps an orbit's HZ deviation to the raw 2D roll used for the CRB
temperature table (p.251).  Rather than rolling temperature randomly,
the orbit's position in the HZ is used to derive the raw roll, ensuring
the mainworld's temperature is consistent with its orbital distance from
the parent star(s).

Habitable Zones Regions table (WBH p.46):
  Raw roll  |  HZCO deviation  |  Temperature zone
  ------    |  ---------------  |  ----------------
  2-        |  +1.1 or more    |  Frozen
  3         |  +1.00           |  Cold
  4         |  +0.50           |  Cold
  5         |  +0.20           |  Temperate
  6         |  +0.10           |  Temperate
  7         |  +0.00           |  Temperate (HZCO)
  8         |  -0.10           |  Temperate
  9         |  -0.20           |  Temperate
  10        |  -0.50           |  Hot
  11        |  -1.00           |  Hot
  12+       |  -1.1 or less    |  Boiling

The raw roll is then fed into the CRB temperature procedure as the
pre-determined 2D result (before atmosphere DMs are added).

World Builder's Handbook and the gas giant/belt counts from the orbit
generation are passed through to the World dataclass, replacing the
independently-rolled values that generate_world() would normally produce.

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

# pylint: disable=too-many-lines
import json
import random
import secrets
from dataclasses import dataclass
from typing import Optional

from .traveller_stellar_gen import StarSystem, generate_stellar_data
from .traveller_orbit_gen import SystemOrbits, OrbitSlot, generate_orbits
from .traveller_belt_physical import BeltPhysical
from .traveller_hydro_detail import generate_hydrographic_detail
from .html_render import render
from .world_codes import APP_VERSION, gg_diameter_from_sah
from .traveller_world_gen import (
    World,
    generate_size,
    generate_atmosphere,
    generate_nhz_atmosphere,
    generate_atmosphere_detail,
    generate_gas_mix,
    generate_unusual_subtype,
    temperature_category,
    generate_hydrographics,
    to_hex,
    TEMPERATURE_DM,
)


# ---------------------------------------------------------------------------
# HZ deviation → raw temperature roll  (WBH p.46-47)
# ---------------------------------------------------------------------------

def hz_deviation_to_raw_roll(hz_deviation: float) -> int:
    """
    Convert an orbit's HZ deviation to the raw 2D temperature roll
    used in the CRB temperature table (p.251), via the WBH Habitable
    Zones Regions table (p.46).

    The raw roll is the 2D result BEFORE atmosphere DMs are applied.
    A raw roll of 7 corresponds to the HZCO itself (deviation 0).
    Negative deviation (closer = hotter) raises the raw roll toward Boiling.
    Positive deviation (further = colder) lowers the raw roll toward Frozen.

    Returns an int in range 2-12 (clamped).
    """
    if hz_deviation >= 1.1:
        raw = 2        # Frozen
    elif hz_deviation >= 1.0:
        raw = 3        # Cold
    elif hz_deviation >= 0.5:
        raw = 4        # Cold
    elif hz_deviation >= 0.2:
        raw = 5        # Temperate (cool)
    elif hz_deviation >= 0.1:
        raw = 6        # Temperate
    elif hz_deviation >= 0.0:
        raw = 7        # Temperate (HZCO)
    elif hz_deviation >= -0.1:
        raw = 8        # Temperate (warm)
    elif hz_deviation >= -0.2:
        raw = 9        # Temperate (warm)
    elif hz_deviation >= -0.5:
        raw = 10       # Hot
    elif hz_deviation >= -1.0:
        raw = 11       # Hot
    else:
        raw = 12       # Boiling

    return max(2, min(12, raw))


def generate_temperature_from_orbit(atmosphere: int, hz_deviation: float) -> str:
    """
    Determine temperature using orbital position rather than a random roll.

    The raw roll from hz_deviation_to_raw_roll() is used as the 2D result,
    then the atmosphere DM is added exactly as the CRB specifies (p.251).
    This ensures the world's temperature is consistent with its orbit.
    """
    raw_roll = hz_deviation_to_raw_roll(hz_deviation)
    atm_dm = TEMPERATURE_DM.get(atmosphere, 0)
    modified_roll = raw_roll + atm_dm
    return temperature_category(modified_roll)


# ---------------------------------------------------------------------------
# Main integration: generate a complete system
# ---------------------------------------------------------------------------

@dataclass
class TravellerSystem:  # pylint: disable=too-many-instance-attributes
    """A fully generated Traveller star system with mainworld."""

    stellar_system: StarSystem
    system_orbits: SystemOrbits
    mainworld: Optional[World]
    mainworld_orbit: Optional[OrbitSlot]
    nhz_atmospheres: bool = False
    orbital_eccentricity: bool = False
    orbital_inclination: bool = False
    seed: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialise this system to a JSON-compatible dict."""
        d = self.stellar_system.to_dict()
        d["orbits"] = self.system_orbits.to_dict()
        d["mainworld"] = self.mainworld.to_dict() if self.mainworld else None
        d["nhz_atmospheres"] = self.nhz_atmospheres
        d["orbital_eccentricity"] = self.orbital_eccentricity
        d["orbital_inclination"] = self.orbital_inclination
        if self.seed is not None:
            d["seed"] = self.seed
        d["_app_version"] = APP_VERSION
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialise this system to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "TravellerSystem":
        """Reconstruct a TravellerSystem from a dict produced by to_dict().

        OrbitSlot.detail is not restored (WorldDetail reconstruction is out of
        scope); the loaded system displays with detail_attached=False.
        """
        stellar = StarSystem.from_dict(d)
        orbits = SystemOrbits.from_dict(d.get("orbits", {}), stellar)
        mw_d = d.get("mainworld")
        mainworld = World.from_dict(mw_d) if mw_d else None
        return cls(
            stellar_system=stellar,
            system_orbits=orbits,
            mainworld=mainworld,
            mainworld_orbit=orbits.mainworld_orbit,
            nhz_atmospheres=bool(d.get("nhz_atmospheres", False)),
            orbital_eccentricity=bool(d.get("orbital_eccentricity", False)),
            orbital_inclination=bool(d.get("orbital_inclination", False)),
            seed=int(d["seed"]) if "seed" in d else None,
        )

    def summary(self) -> str:
        """
        Human-readable full system summary.

        If attach_detail() has been called, the orbital section uses
        system_body_table() which shows secondary world profiles and
        significant moon sub-rows.  Without detail attached it falls
        back to SystemOrbits.summary() which shows type and zone only.
        """
        # Check whether detail has been attached to any non-empty orbit
        detail_attached = any(
            getattr(o, "detail", None) is not None
            for o in self.system_orbits.orbits
            if o.world_type != "empty"
        )

        if detail_attached:
            from .traveller_world_detail import system_body_table  # pylint: disable=import-outside-toplevel
            orbital_section = system_body_table(self)
        else:
            orbital_section = self.system_orbits.summary()

        lines = [self.stellar_system.summary(), "", orbital_section]

        if self.mainworld and self.mainworld_orbit:
            mw = self.mainworld
            mo = self.mainworld_orbit
            lines.append("")
            lines.append("=" * 60)
            lines.append(f"  Mainworld  —  {mw.name}  {mw.uwp()}")
            lines.append(
                f"  Star {mo.star_designation}  Orbit# {mo.orbit_number:.2f}"
                f"  ({mo.orbit_au:.3f} AU)  HZ dev {mo.hz_deviation:+.2f}"
            )
            lines.append("=" * 60)
            lines.append(mw.summary())
        return "\n".join(lines)

    def _system_card_context(self, detail_attached: bool = False) -> dict:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Build the context dict for system_card.html (also reused by to_poster_html()).

        Parameters
        ----------
        detail_attached : bool
            Pass True when attach_detail() has already been called so the
            card includes secondary world profiles and satellite data.
        """
        mw = self.mainworld

        # ── Star rows ─────────────────────────────────────────────────────
        star_rows = []
        for star in self.stellar_system.stars:
            orb = (f"Orbit# {star.orbit_number:.2f} ({star.orbit_au:.2f} AU)"
                   if star.orbit_number else "")
            desig    = star.designation
            mao_v    = self.system_orbits.star_mao.get(desig)
            hzco_v   = self.system_orbits.star_hzco.get(desig)
            hz_in_v  = self.system_orbits.star_hz_inner.get(desig)
            hz_out_v = self.system_orbits.star_hz_outer.get(desig)
            if star.role == "primary":
                primary_of = "--"
            elif star.role == "companion":
                primary_of = desig[:-1]
            else:  # close / near / far secondary
                primary_of = self.stellar_system.primary.designation
            star_rows.append({
                "designation":    desig,
                "primary":        primary_of,
                "classification": star.classification(),
                "mass":           f"{star.mass:.2f}",
                "temperature":    f"{star.temperature:,}",
                "luminosity":     f"{star.luminosity:.3g}",
                "orbit":          orb,
                "mao":      f"{mao_v:.2f}"    if mao_v    is not None else "—",
                "hz_inner": f"{hz_in_v:.2f}"  if hz_in_v  is not None else "—",
                "hzco":     f"{hzco_v:.2f}"   if hzco_v   is not None else "—",
                "hz_outer": f"{hz_out_v:.2f}" if hz_out_v is not None else "—",
            })

        # ── Orbital rows ──────────────────────────────────────────────────
        orbit_rows = []
        for o in self.system_orbits.orbits:
            detail = getattr(o, "detail", None)
            if o.world_type == "empty":
                profile = "—"
                type_cls = "type-empty"
            elif o.canonical_profile:
                # Canonical mainworld: always show the fetched UWP verbatim.
                profile = o.canonical_profile
                type_cls = ("type-belt" if o.world_type == "belt"
                            else "type-inh" if mw and mw.population > 0
                            else "type-terr")
            elif detail is not None:
                # Gas giant orbits: use gg_sah as profile (gg_sah is always
                # the gas giant profile; detail.profile may be a satellite UWP).
                if o.world_type == "gas_giant":
                    profile = o.gg_sah or detail.profile
                    type_cls = "type-gg"
                else:
                    profile = detail.profile
                    type_cls = ("type-belt" if o.world_type == "belt"
                                else "type-inh" if detail.inhabited
                                else "type-terr")
            else:
                if o.world_type == "gas_giant" and o.gg_sah:
                    profile = o.gg_sah
                    type_cls = "type-gg"
                else:
                    profile = ""
                    type_cls = "type-terr"

            note_parts = []
            if o.is_mainworld_candidate:
                note_parts.append("← mainworld")
            if o.notes:
                note_parts.append(o.notes)
            if o.world_type == "gas_giant" and o.gg_mass_earth is not None:
                gg_diam_km = gg_diameter_from_sah(o.gg_sah or "") * 12800.0
                if gg_diam_km > 0:
                    gg_density = (
                        o.gg_mass_earth / (gg_diam_km / 12742.0) ** 3
                    ) * 5.515
                    note_parts.append(
                        f"{o.gg_mass_earth:.0f} M⊕ · {gg_density:.2f} g/cm³"
                    )
            if detail is not None and isinstance(detail.physical, BeltPhysical):
                note_parts.append(f"Profile: {detail.physical.profile_str}")

            if o.is_mainworld_candidate and mw:
                orbit_codes = list(mw.trade_codes)
            elif detail is not None and not detail.is_gas_giant:
                orbit_codes = list(detail.trade_codes)
            else:
                orbit_codes = []

            ecc_incl = (
                f"{o.eccentricity:.3f}/{o.inclination:.1f}°"
                if (o.eccentricity > 0 or o.inclination > 0)
                else "—"
            )

            moons = []
            if detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):
                    if moon.is_ring:
                        moon_profile = f"R{moon.ring_count:02d}"
                        moon_codes = []
                    elif moon.detail is not None:
                        moon_profile = moon.detail.profile
                        moon_codes = list(moon.detail.trade_codes)
                    else:
                        moon_profile = f"size {moon.size_str}"
                        moon_codes = []
                    moon_biosphere = ""
                    if moon.detail is not None:
                        mb = moon.detail.biomass_rating
                        mc = moon.detail.biocomplexity_rating
                        if mb is not None and mb > 0 and mc is not None:
                            moon_biosphere = f"{to_hex(mb)}, {to_hex(mc)}"
                    moon_ecc_incl = (
                        f"{moon.orbit_eccentricity:.3f}"
                        f"/{moon.orbit_inclination:.1f}°"
                        if not moon.is_ring
                        and (moon.orbit_eccentricity > 0
                             or moon.orbit_inclination > 0)
                        else ""
                    )
                    moons.append({
                        "name": moon.name,
                        "idx": mi,
                        "pd_str": (f"{moon.orbit_pd:.1f} PD"
                                   if moon.orbit_pd is not None else ""),
                        "km_str": (f"{moon.orbit_km:,.0f} km"
                                   if moon.orbit_km is not None else ""),
                        "type_str": ("ring" if moon.is_ring
                                     else f"size {moon.size_str}"),
                        "profile": moon_profile,
                        "codes": moon_codes,
                        "range_str": (moon.orbit_range.capitalize()
                                      if moon.orbit_range else ""),
                        "temp_zone": moon.temperature_zone,
                        "biosphere_str": moon_biosphere,
                        "ecc_incl": moon_ecc_incl,
                    })

            # Biosphere: biomass, biocomplexity for terrestrial worlds
            biosphere_str = ""
            if o.is_mainworld_candidate and mw:
                bm = mw.biomass_rating
                bc = mw.biocomplexity_rating
                if bm is not None and bm > 0 and bc is not None:
                    biosphere_str = f"{to_hex(bm)}, {to_hex(bc)}"
            elif detail is not None and not detail.is_gas_giant:
                bm = detail.biomass_rating
                bc = detail.biocomplexity_rating
                if bm is not None and bm > 0 and bc is not None:
                    biosphere_str = f"{to_hex(bm)}, {to_hex(bc)}"

            orbit_rows.append({
                "name": o.name,
                "star_desig": o.star_designation,
                "slot_index": o.slot_index,
                "orbit_num": f"{o.orbit_number:.2f}",
                "orbit_au": f"{o.orbit_au:.3f}",
                "_sort_au": o.orbit_au,
                "_own_desig": None,
                "ecc_incl": ecc_incl,
                "world_type": o.world_type,
                "type_cls": type_cls,
                "profile": profile,
                "codes": orbit_codes,
                "temp_zone": o.temperature_zone,
                "mw_mark": "  ".join(note_parts),
                "row_cls": "mw-row" if o.is_mainworld_candidate else "",
                "moons": moons,
                "biosphere_str": biosphere_str,
            })

        # Non-primary stars are otherwise invisible in this table unless they
        # happen to have their own orbit slots (companions never do — planets
        # don't orbit them directly under WBH rules; a close/near/far
        # secondary may have none too, e.g. when its own exclusion zone
        # leaves it no room). Companion stars (Aa, Ab, ...) are filed under
        # their own immediate parent (designation[:-1]), sorted by their real
        # orbit_au among that parent's own listings — same group as any
        # planets that parent has. Close/near/far secondary stars (B, C, ...)
        # are filed under the system primary, at their own real orbit_au, so
        # they interleave with the primary's own planets/companions in true
        # orbital order; `_own_desig` marks these rows so the assembly step
        # below can splice each secondary's own local sequence (its own
        # planets and its own companions, in their own orbital order) in
        # immediately afterward — before any of the primary's other, more
        # distant planets.
        pri_desig = self.stellar_system.primary.designation
        for st in self.stellar_system.stars:
            if st.role == "companion":
                parent_d   = st.designation[:-1]
                own_desig  = None
            elif st.role in ("close", "near", "far"):
                parent_d   = pri_desig
                own_desig  = st.designation
            else:
                continue  # the primary itself
            comp_ecc_incl = (
                f"{st.orbit_eccentricity:.3f}/{st.orbit_inclination:.1f}°"
                if (st.orbit_eccentricity > 0 or st.orbit_inclination > 0)
                else "—"
            )
            orbit_rows.append({
                "name": st.name,
                "star_desig": parent_d,
                "slot_index": "",
                "orbit_num": f"{st.orbit_number:.2f}" if st.orbit_number is not None else "",
                "orbit_au": f"{st.orbit_au:.3f}" if st.orbit_au is not None else "",
                "_sort_au": st.orbit_au if st.orbit_au is not None else 0.0,
                "_own_desig": own_desig,
                "ecc_incl": comp_ecc_incl,
                "world_type": "star",
                "type_cls": "type-star",
                "profile": st.classification(),
                "codes": [],
                "temp_zone": "",
                "mw_mark": "",
                "row_cls": "",
                "moons": [],
                "biosphere_str": "",
            })

        # Assemble the final display order: the primary's own planets,
        # companion stars, and secondary-star rows interleave by real orbital
        # radius; each secondary star's own local sequence (recursively built
        # the same way) is spliced in immediately after its row, before the
        # primary's next, more distant item.
        def _local_items(desig: str) -> list:
            return sorted(
                (r for r in orbit_rows if r["star_desig"] == desig),
                key=lambda r: r["_sort_au"],
            )

        ordered_rows: list = []
        for row in _local_items(pri_desig):
            ordered_rows.append(row)
            own_desig = row.get("_own_desig")
            if own_desig:
                ordered_rows.extend(_local_items(own_desig))
        orbit_rows = ordered_rows

        return {
            "title": (mw.name if mw else "Unknown") + " system",
            "star_classes": " + ".join(
                s.classification() for s in self.stellar_system.stars),
            "age": (f"{self.stellar_system.age_gyr:.2f} Gyr"
                    if self.stellar_system.age_gyr else "?"),
            "nw": self.system_orbits.total_worlds,
            "star_rows": star_rows,
            "orbit_rows": orbit_rows,
            "detail_attached": detail_attached,
            "json_str": self.to_json(),
        }

    def to_html(self, detail_attached: bool = False) -> str:
        """Return a self-contained HTML system card.

        Suitable for saving as a standalone .html file or serving directly
        from the API /api/system/{name}/card endpoint.

        Parameters
        ----------
        detail_attached : bool
            Pass True when attach_detail() has already been called so the
            card includes secondary world profiles and satellite data.
        """
        return render("system_card.html", **self._system_card_context(detail_attached))

    def to_poster_html(self, perspective: bool = True) -> str:
        """Return a self-contained A3-poster HTML page for this system.

        Combines a perspective system map, a curated star/orbit summary, and
        the mainworld's key stats onto one printable page (CSS
        `@page { size: A3 landscape }`). Requires a mainworld; raises
        ValueError otherwise (a poster with no mainworld has nothing to
        highlight in its sidebar).

        This is intentionally a curated "highlights" view, not the full
        system_card.html/world_card.html detail — see context/gen-ui.md.
        """
        if self.mainworld is None:
            raise ValueError("to_poster_html() requires a mainworld")

        # pylint: disable=import-outside-toplevel
        from .system_map import build_svg, PALETTE_LIGHT
        from .traveller_world_gen import _world_html_ctx

        svg_str, canvas_h = build_svg(
            self, canvas_w=1600, perspective=perspective, show_table=False,
            palette=PALETTE_LIGHT,
        )
        svg_str = svg_str.replace(
            '<svg xmlns="http://www.w3.org/2000/svg" ',
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 1600 {canvas_h}" preserveAspectRatio="xMidYMid meet" ',
            1,
        )

        star_rows = [
            {
                "designation": s.designation,
                "classification": s.classification(),
                "mass": f"{s.mass:.2f}",
            }
            for s in self.stellar_system.stars
        ]

        notable = []
        for o in self.system_orbits.orbits:
            if o.is_mainworld_candidate or len(notable) >= 5:
                continue
            detail = getattr(o, "detail", None)
            if o.world_type == "gas_giant":
                notable.append({
                    "name": o.name or "—",
                    "profile": o.gg_sah or (detail.profile if detail else ""),
                    "world_type": "Gas giant",
                })
            elif detail is not None and detail.inhabited:
                notable.append({
                    "name": o.name or "—",
                    "profile": detail.profile,
                    "world_type": "Secondary world",
                })

        detail_attached = any(
            getattr(o, "detail", None) is not None
            for o in self.system_orbits.orbits
            if o.world_type != "empty"
        )

        return render("poster_a3.html",
            title=self.mainworld.name + " system",
            star_classes=" + ".join(
                s.classification() for s in self.stellar_system.stars),
            age=(f"{self.stellar_system.age_gyr:.2f} Gyr"
                 if self.stellar_system.age_gyr else "?"),
            nw=self.system_orbits.total_worlds,
            svg=svg_str,
            stars=star_rows,
            notable=notable,
            mw=_world_html_ctx(self.mainworld),
            full_card=self._system_card_context(detail_attached),
        )

    def to_survey_form_html(self) -> str:  # pylint: disable=too-many-locals
        """Return a self-contained IISS Class 0/I Survey form HTML page."""
        footnote_syms = "¹²³⁴⁵⁶⁷⁸⁹"

        mw = self.mainworld
        designation = mw.name if mw else "Unknown"
        age_gyr = f"{self.stellar_system.age_gyr:.2f}"
        stellar_count = len(self.stellar_system.stars)

        footnote_idx = 0
        notes_lines: list[str] = []
        star_rows = []

        for star in self.stellar_system.stars:
            period_yr = star.orbit_period_yr
            is_primary = star.orbit_number == 0.0

            # Period formatted: always years in the table column
            if is_primary or period_yr is None:
                period_str = "—"
            else:
                period_str = f"{period_yr:.3f}y"

            # Footnote only for sub-year periods; note in standard days
            footnote = ""
            if (not is_primary
                    and period_yr is not None
                    and period_yr < 1.0
                    and footnote_idx < len(footnote_syms)):
                footnote = footnote_syms[footnote_idx]
                footnote_idx += 1
                notes_lines.append(
                    f"{footnote} {period_yr * 365.25:.3f} standard days"
                )

            ecc_v = star.orbit_eccentricity
            hzco_v = self.system_orbits.star_hzco.get(star.designation)

            star_rows.append({
                "component": star.designation,
                "footnote": footnote,
                "star_class": star.classification(),
                "mass": f"{star.mass:.3f}",
                "temp": f"{star.temperature:,}" if star.temperature > 0 else "—",
                "diameter": f"{star.diameter:.3f}",
                "luminosity": f"{star.luminosity:.4g}",
                "orbit": "0" if is_primary else f"{star.orbit_number:.2f}",
                "au": "—" if is_primary else f"{star.orbit_au:.3f}",
                "ecc": "—" if ecc_v == 0.0 else f"{ecc_v:.2f}",
                "period": period_str,
                "hzco": f"{hzco_v:.2f}" if hzco_v is not None else "—",
            })

        return render("survey_class0i.html",
            designation=designation,
            age_gyr=age_gyr,
            stellar_count=stellar_count,
            star_rows=star_rows,
            notes="\n".join(notes_lines),
        )

    def to_survey_form_html_class2(self) -> str:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Return a self-contained IISS Class II/III Survey form HTML page."""
        footnote_syms = "¹²³⁴⁵⁶⁷⁸⁹"

        mw = self.mainworld
        designation = mw.name if mw else "Unknown"
        age_gyr = f"{self.stellar_system.age_gyr:.2f}"
        stellar_count = len(self.stellar_system.stars)

        footnote_idx = 0
        notes_lines: list[str] = []
        star_rows = []

        for star in self.stellar_system.stars:
            period_yr = star.orbit_period_yr
            is_primary = star.orbit_number == 0.0

            if is_primary or period_yr is None:
                period_str = "—"
            else:
                period_str = f"{period_yr:.3f}y"

            footnote = ""
            if (not is_primary
                    and period_yr is not None
                    and period_yr < 1.0
                    and footnote_idx < len(footnote_syms)):
                footnote = footnote_syms[footnote_idx]
                footnote_idx += 1
                notes_lines.append(
                    f"{footnote} {period_yr * 365.25:.3f} standard days"
                )

            ecc_v  = star.orbit_eccentricity
            mao_v  = self.system_orbits.star_mao.get(star.designation)
            hzco_v = self.system_orbits.star_hzco.get(star.designation)

            star_rows.append({
                "component": star.designation,
                "footnote": footnote,
                "star_class": star.classification(),
                "mass": f"{star.mass:.3f}",
                "temp": f"{star.temperature:,}" if star.temperature > 0 else "—",
                "diameter": f"{star.diameter:.3f}",
                "luminosity": f"{star.luminosity:.4g}",
                "orbit": "0" if is_primary else f"{star.orbit_number:.2f}",
                "au": "—" if is_primary else f"{star.orbit_au:.3f}",
                "ecc": "—" if ecc_v == 0.0 else f"{ecc_v:.2f}",
                "period": period_str,
                "mao": f"{mao_v:.2f}" if mao_v is not None else "—",
                "hzco": f"{hzco_v:.2f}" if hzco_v is not None else "—",
            })

        orbit_rows = []
        for o in self.system_orbits.orbits:
            if o.world_type == "empty":
                continue
            detail = getattr(o, "detail", None)

            if o.world_type == "gas_giant":
                object_type = "GG"
                sah_uwp = o.gg_sah or (detail.profile if detail else "")
            elif o.world_type == "belt":
                object_type = "Belt"
                sah_uwp = o.canonical_profile or (detail.profile if detail else "")
            else:
                object_type = "Terrestrial"
                sah_uwp = o.canonical_profile or (detail.profile if detail else "")

            note_parts = [o.temperature_zone.title()]
            if o.notes:
                note_parts.append(o.notes)
            if o.world_type == "gas_giant" and o.gg_mass_earth is not None:
                note_parts.append(f"{o.gg_mass_earth:.0f} M⊕")
            if detail is not None and detail.moons:
                moon_parts = []
                for moon in detail.moons:
                    if moon.is_ring:
                        moon_parts.append(f"R{moon.ring_count:02d}")
                    else:
                        moon_parts.append(f"Size {moon.size_str}")
                note_parts.append(", ".join(moon_parts))

            period_yr = o.orbit_period_yr
            orbit_rows.append({
                "primary": o.star_designation,
                "object_type": object_type,
                "orbit_num": f"{o.orbit_number:.2f}",
                "au": f"{o.orbit_au:.3f}",
                "ecc": f"{o.eccentricity:.2f}" if o.eccentricity > 0.0 else "—",
                "period": f"{period_yr:.3f}y" if period_yr is not None else "—",
                "sah_uwp": sah_uwp,
                "sub": str(len(detail.moons)) if detail is not None else "",
                "notes": " · ".join(note_parts),
            })

        return render("survey_class2iii.html",
            designation=designation,
            age_gyr=age_gyr,
            stellar_count=stellar_count,
            gg_count=self.system_orbits.gas_giant_count,
            belt_count=self.system_orbits.belt_count,
            terrestrial_count=self.system_orbits.terrestrial_count,
            class_iii_status="",
            star_rows=star_rows,
            orbit_rows=orbit_rows,
            notes="\n".join(notes_lines),
        )

    def to_survey_form_html_class4(self) -> str:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Return a self-contained IISS Class IV Survey form HTML page."""
        gov_names = {
            0: "None", 1: "Company/Corporation", 2: "Participating Democracy",
            3: "Self-Perpetuating Oligarchy", 4: "Representative Democracy",
            5: "Feudal Technocracy", 6: "Captive Government", 7: "Balkanisation",
            8: "Civil Service Bureaucracy", 9: "Impersonal Bureaucracy",
            10: "Charismatic Dictatorship", 11: "Non-Charismatic Dictatorship",
            12: "Charismatic Oligarchy", 13: "Religious Dictatorship",
            14: "Religious Autocracy", 15: "Totalitarian Oligarchy",
        }

        mw = self.mainworld
        world_name = mw.name if mw else "Unknown"
        uwp = mw.uwp() if mw else "???????-?"
        travel_zone = (mw.travel_zone or "Green") if mw else "Green"
        sector_location = "—"
        system_age = f"{self.stellar_system.primary.age_gyr:.2f}"
        primary = self.stellar_system.primary
        primary_star = f"{primary.designation} {primary.classification()}"

        trade_codes = " ".join(mw.trade_codes) if mw else ""

        # Population context
        pop_ctx = None
        if mw and mw.population_detail is not None:
            pd = mw.population_detail
            capital_port = ""
            for city in pd.cities:
                if "Cw" in (city.codes or []):
                    capital_port = f"(city #{pd.cities.index(city)+1})"
                    break
            if not capital_port:
                capital_port = mw.starport

            cities_ctx = [
                {
                    "population": f"{c.population:,}",
                    "codes": " ".join(c.codes) if c.codes else "",
                }
                for c in pd.cities[:10]
            ]
            pop_ctx = {
                "total_pop": f"{pd.total_population:,}",
                "p_value": pd.p_value,
                "pcr": pd.pcr,
                "pcr_label": pd.pcr_label,
                "urbanisation_pct": pd.urbanisation_pct,
                "major_city_count": pd.major_city_count,
                "capital_port": capital_port,
                "population_profile": pd.population_profile,
                "cities": cities_ctx,
            }

        # Government context
        gov_ctx = None
        if mw and mw.government_detail is not None:
            gd = mw.government_detail
            gov_code = mw.government
            gov_name = gov_names.get(gov_code, f"Type {gov_code}")
            structure = gd.structure or (
                f"{gd.structure_leg}/{gd.structure_exec}/{gd.structure_jud}"
                if gd.authority == "Balanced" else ""
            )
            gov_ctx = {
                "gov_code": gov_code,
                "gov_name": gov_name,
                "centralisation": gd.centralisation,
                "authority": gd.authority,
                "structure": structure,
                "government_profile": gd.government_profile,
                "factions": [
                    {
                        "numeral": f.numeral,
                        "government_name": f.government_name,
                        "strength_code": f.strength_code,
                        "strength_label": f.strength_label,
                        "relationship_code": f.relationship_code,
                        "relationship_label": f.relationship_label,
                    }
                    for f in gd.factions
                ],
            }

        # Law context
        law_ctx = None
        if mw and mw.law_detail is not None:
            ld = mw.law_detail
            law_ctx = {
                "overall": mw.law_level,
                "primary_system": ld.judicial_primary,
                "primary_label": ld.judicial_primary_label,
                "secondary_system": (
                    f"{ld.judicial_secondary} {ld.judicial_secondary_label}"
                    if ld.judicial_secondary != ld.judicial_primary else "—"
                ),
                "uniformity": ld.law_uniformity,
                "uniformity_label": ld.law_uniformity_label,
                "presumption": "Yes" if ld.presumption_of_innocence else "No",
                "death_penalty": "Yes" if ld.death_penalty else "No",
                "justice_profile": ld.justice_profile,
                "law_weapons": ld.law_weapons,
                "law_economic": ld.law_economic,
                "law_criminal": ld.law_criminal,
                "law_private": ld.law_private,
                "law_personal_rights": ld.law_personal_rights,
                "law_profile": ld.law_profile,
            }

        # Technology context
        tech_ctx = None
        if mw and mw.tech_detail is not None:
            td = mw.tech_detail
            tech_ctx = {
                "tl_high": td.tl_high_common,
                "tl_low": td.tl_low_common,
                "tl_energy": td.tl_energy,
                "tl_electronics": td.tl_electronics,
                "tl_manufacturing": td.tl_manufacturing,
                "tl_medical": td.tl_medical,
                "tl_environmental": td.tl_environmental,
                "tl_land": td.tl_land,
                "tl_sea": td.tl_sea,
                "tl_air": td.tl_air,
                "tl_space": td.tl_space,
                "tl_military_personal": td.tl_military_personal,
                "tl_military_heavy": td.tl_military_heavy,
                "tl_novelty": td.tl_novelty,
                "technology_profile": td.technology_profile,
            }

        # Culture context
        cult_ctx = None
        if mw and mw.culture_detail is not None:
            cd = mw.culture_detail
            cult_ctx = {
                "diversity": cd.diversity,
                "diversity_label": cd.diversity_label,
                "xenophilia": cd.xenophilia,
                "xenophilia_label": cd.xenophilia_label,
                "uniqueness": cd.uniqueness,
                "uniqueness_label": cd.uniqueness_label,
                "symbology": cd.symbology,
                "symbology_label": cd.symbology_label,
                "cohesion": cd.cohesion,
                "cohesion_label": cd.cohesion_label,
                "progressiveness": cd.progressiveness,
                "progressiveness_label": cd.progressiveness_label,
                "expansionism": cd.expansionism,
                "expansionism_label": cd.expansionism_label,
                "militancy": cd.militancy,
                "militancy_label": cd.militancy_label,
                "cultural_profile": cd.cultural_profile,
                "cultural_extension": cd.cultural_extension,
            }

        # Economics/Importance context
        imp_ctx = None
        if mw and mw.importance_detail is not None:
            imp = mw.importance_detail
            resource_factor = (
                mw.size_detail.resource_factor
                if mw.size_detail is not None and not isinstance(mw.size_detail, BeltPhysical)
                else None
            )
            gwp_total_fmt = (
                f"{imp.gwp_total_mcr:,.0f}" if imp.gwp_total_mcr is not None else None
            )
            dev_fmt = (
                f"{imp.development_score:.2f}"
                if imp.development_score is not None else None
            )
            imp_ctx = {
                "trade_codes": trade_codes,
                "importance": imp.importance_str,
                "resource_factor": resource_factor,
                "labour_factor": imp.labour_factor,
                "infrastructure_factor": imp.infrastructure_factor,
                "efficiency_factor": imp.efficiency_factor,
                "resource_units": imp.resource_units,
                "economics_profile": imp.economics_profile,
                "gwp_per_capita": imp.gwp_per_capita,
                "gwp_total_mcr": gwp_total_fmt,
                "world_trade_number": imp.world_trade_number,
                "inequality_rating": imp.inequality_rating,
                "development_score": dev_fmt,
            }

        # Starport context
        sp_ctx = None
        if mw and mw.starport_detail is not None:
            sp = mw.starport_detail
            bases = mw.bases or []
            known = {"N", "S", "M", "W"}
            other_bases = " ".join(b for b in bases if b not in known)
            sp_ctx = {
                "starport_class": mw.starport,
                "has_highport": "Yes" if sp.has_highport else "No",
                "expected_weekly": sp.expected_weekly,
                "docking_capacity": (
                    f"{sp.downport_capacity:,}"
                    + (f" + {sp.highport_capacity:,} HP" if sp.highport_capacity else "")
                ),
                "shipyard_capacity": (
                    f"{sp.shipyard_capacity:,}" if sp.shipyard_capacity else None
                ),
                "shipyard_annual_output": (
                    f"{sp.shipyard_annual_output:,}" if sp.shipyard_annual_output else None
                ),
                "starport_profile": sp.starport_profile,
                "base_navy": "Y" if "N" in bases else "",
                "base_scout": "Y" if "S" in bases else "",
                "base_military": "Y" if "M" in bases else "",
                "base_waystation": "Y" if "W" in bases else "",
                "base_other": other_bases,
            }

        # Military context
        mil_ctx = None
        if mw and mw.military_detail is not None:
            md = mw.military_detail
            branch_list = [
                {"name": name, "exists": br.exists, "effect": br.effect}
                for name, br in [
                    ("Enforcement",    md.enforcement),
                    ("Militia",        md.militia),
                    ("Army",           md.army),
                    ("Wet Navy",       md.wet_navy),
                    ("Air Force",      md.air_force),
                    ("System Defence", md.system_defence),
                    ("Navy",           md.navy),
                    ("Marines",        md.marines),
                ]
            ]
            branch_pairs = [
                branch_list[i:i + 2] for i in range(0, len(branch_list), 2)
            ]
            mil_ctx = {
                "budget_pct": f"{md.military_budget_pct:.1f}%",
                "readiness": md.state_of_readiness,
                "military_profile": md.military_profile,
                "branches": branch_list,
                "branch_pairs": branch_pairs,
            }

        return render("survey_class4.html",
            world_name=world_name,
            uwp=uwp,
            travel_zone=travel_zone,
            sector_location=sector_location,
            system_age=system_age,
            primary_star=primary_star,
            pop=pop_ctx,
            gov=gov_ctx,
            law=law_ctx,
            tech=tech_ctx,
            cult=cult_ctx,
            imp=imp_ctx,
            sp=sp_ctx,
            mil=mil_ctx,
        )


def generate_mainworld_at_orbit(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-statements
    name: str,
    orbit: OrbitSlot,
    gas_giant_count: int,
    belt_count: int,
    system_age_gyr: Optional[float] = None,
    nhz_atmospheres: bool = False,
    rng: Optional[random.Random] = None,
) -> World:
    """
    Generate a mainworld whose temperature is constrained by its orbital
    position, following the WBH Habitable Zones Regions table (p.46-47).

    Generates physical characteristics only (steps 1–4, atmosphere detail,
    hydrographic detail, gas giant / belt counts).  Social steps (5–10,
    12–13: population, government, law, starport, TL, bases, trade codes,
    travel zone) are deferred — the returned world carries placeholder
    values (starport='X', pop/gov/law/tl=0, bases=[], trade_codes=[],
    travel_zone='Green').  Call ``apply_mainworld_social()`` after
    mainworld selection to complete the world.

    WBH atmosphere detail is attached via ``generate_atmosphere_detail()``;
    *system_age_gyr* feeds the WBH p.80 DM+1 for systems older than 4 Gyr.
    """
    from . import traveller_world_gen as _twg  # pylint: disable=import-outside-toplevel
    if rng is not None:
        _twg._rng = rng  # pylint: disable=protected-access
    world = World(name=name)

    # If the mainworld orbit is a belt, the physical characteristics are
    # fixed: size=0, atmosphere=0, hydrographics=0 (WBH p.53 — "Size 0 world
    # is a special case… a belt of planetoids").
    # Temperature is set to the orbital zone value but has no physical meaning
    # for a diffuse belt.
    if orbit.world_type == "belt":
        world.size = 0
        world.atmosphere = 0
        world.hydrographics = 0
        world.temperature = generate_temperature_from_orbit(
            atmosphere=0,
            hz_deviation=orbit.hz_deviation,
        )
    elif orbit.world_type == "gas_giant":
        # The mainworld is a satellite of the gas giant, not the giant itself.
        # Size is constrained: at least 1, at most gg_diameter-1 (WBH p.57).
        gg_sah = getattr(orbit, "gg_sah", "")
        gg_diam = gg_diameter_from_sah(gg_sah)
        world.size = min(max(generate_size(), 1), gg_diam - 1)
        _nhz = (nhz_atmospheres
                and orbit.hz_deviation is not None
                and abs(orbit.hz_deviation) > 1.0)
        if _nhz:
            world.atmosphere, _nhz_key = generate_nhz_atmosphere(
                world.size, orbit.hz_deviation
            )
        else:
            world.atmosphere = generate_atmosphere(world.size)
            _nhz_key = None
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=orbit.hz_deviation,
        )
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, system_age_gyr, world.temperature,
            hz_deviation=orbit.hz_deviation,
            exotic_key_override=_nhz_key,
        )
        world.hydrographics = generate_hydrographics(
            world.size, world.atmosphere, world.temperature
        )
        if world.atmosphere_detail is not None:
            generate_gas_mix(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, orbit.hz_deviation, world.hydrographics,
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )
        world.notes.append(
            f"Mainworld is a satellite of gas giant {gg_sah or '?'} "
            f"at Orbit# {orbit.orbit_number:.2f} ({orbit.orbit_au:.2f} AU)"
        )
    else:
        # Steps 1-2: Size and Atmosphere (random as normal, or NHZ override)
        world.size = generate_size()
        _nhz = (nhz_atmospheres
                and orbit.hz_deviation is not None
                and abs(orbit.hz_deviation) > 1.0)
        if _nhz:
            world.atmosphere, _nhz_key = generate_nhz_atmosphere(
                world.size, orbit.hz_deviation
            )
        else:
            world.atmosphere = generate_atmosphere(world.size)
            _nhz_key = None

        # Step 3: Temperature — derived from orbital position (WBH p.46-47)
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=orbit.hz_deviation,
        )

        # Atmosphere detail needs temperature to characterise exotic/corrosive subtypes
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, system_age_gyr, world.temperature,
            hz_deviation=orbit.hz_deviation,
            exotic_key_override=_nhz_key,
        )

        # Step 4: Hydrographics (uses orbital-constrained temperature)
        world.hydrographics = generate_hydrographics(
            world.size, world.atmosphere, world.temperature
        )
        if world.atmosphere_detail is not None:
            generate_gas_mix(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, orbit.hz_deviation, world.hydrographics,
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )

    # Hydrographic detail — surface-liquid percentage and fluid type (WBH pp.91-95)
    world.hydrographic_detail = generate_hydrographic_detail(
        world.hydrographics, world.size,
        atmosphere=world.atmosphere,
        temperature=world.temperature,
        rng=rng,
    )

    # Step 11: Gas giants and belts — use orbit generation counts (no dice)
    world.has_gas_giant = gas_giant_count > 0
    world.gas_giant_count = gas_giant_count
    world.belt_count = belt_count

    # Steps 5–10, 12–13 (social/starport/TL/bases/trade codes/travel zone) are
    # deferred until after mainworld selection — see apply_mainworld_social().

    # Record orbital context in notes
    world.notes.append(
        f"Orbits Star {orbit.star_designation} at Orbit# {orbit.orbit_number:.2f}"
        f" ({orbit.orbit_au:.3f} AU). HZ deviation {orbit.hz_deviation:+.2f}."
    )

    return world


def generate_full_system(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: str = "Unknown",
    seed: Optional[int] = None,
    nhz_atmospheres: bool = False,
    orbital_eccentricity: bool = False,
    orbital_inclination: bool = False,
    rng: Optional[random.Random] = None,
) -> TravellerSystem:
    """
    Generate a complete Traveller star system with stellar data, orbital
    structure, and a fully characterised mainworld.

    Args:
        name:                 Mainworld name.
        seed:                 Optional RNG seed for reproducible results.
        nhz_atmospheres:      When True, worlds outside the habitable zone use
                              WBH Non-Habitable Zone atmosphere tables.
        orbital_eccentricity: When True, roll orbital eccentricity for all
                              worlds and companion stars (WBH p.27).
        orbital_inclination:  When True, roll orbital inclination for all
                              worlds and companion stars (WBH p.28).
        rng:                  Optional pre-seeded random.Random instance.
                              When provided, seed is ignored.

    Returns:
        A TravellerSystem containing stellar data, orbits, and mainworld.
    """
    if rng is None:
        if seed is None:
            seed = secrets.randbelow(2 ** 31)
        rng = random.Random(seed)

    # Step 1: Stars
    stellar = generate_stellar_data(rng=rng)

    # Step 2: Orbits and mainworld orbit selection
    orbits = generate_orbits(stellar, orbital_eccentricity=orbital_eccentricity,
                             orbital_inclination=orbital_inclination, rng=rng)

    mw_orbit = orbits.mainworld_orbit
    mainworld = None

    if mw_orbit is not None:
        mainworld = generate_mainworld_at_orbit(
            name=name,
            orbit=mw_orbit,
            gas_giant_count=orbits.gas_giant_count,
            belt_count=orbits.belt_count,
            system_age_gyr=stellar.age_gyr,
            nhz_atmospheres=nhz_atmospheres,
            rng=rng,
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=mainworld,
        mainworld_orbit=mw_orbit,
        nhz_atmospheres=nhz_atmospheres,
        orbital_eccentricity=orbital_eccentricity,
        orbital_inclination=orbital_inclination,
        seed=seed,
    )


def generate_system_from_world(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    world: World,
    seed: Optional[int] = None,
    nhz_atmospheres: bool = False,
    orbital_eccentricity: bool = False,
    orbital_inclination: bool = False,
    rng: Optional[random.Random] = None,
) -> TravellerSystem:
    """
    Generate a complete Traveller star system around an existing mainworld.

    The world's UWP, bases, trade codes, and PBG values are preserved
    exactly. New stellar data and orbital structure are generated
    procedurally. The mainworld's temperature is recalculated from its
    assigned orbital position to remain consistent with the host star's
    habitable zone.

    The canonical UWP is stamped on the mainworld orbit slot so the
    HTML/JSON output always shows the correct profile, following the same
    pattern used for TravellerMap canonical systems.

    Args:
        world: An existing World object (e.g. from World.from_dict()).
        seed:  Optional RNG seed for reproducible stellar/orbital generation.

    Returns:
        A TravellerSystem with the supplied world placed as the mainworld.
    """
    if rng is None:
        if seed is None:
            seed = secrets.randbelow(2 ** 31)
        rng = random.Random(seed)

    stellar = generate_stellar_data(rng=rng)
    orbits = generate_orbits(stellar, orbital_eccentricity=orbital_eccentricity,
                             orbital_inclination=orbital_inclination, rng=rng)

    from . import traveller_world_gen as _twg  # pylint: disable=import-outside-toplevel
    _twg._rng = rng  # pylint: disable=protected-access

    # Reconcile PBG: honour the world's canonical gas giant and belt counts
    # rather than the freshly generated orbit counts.
    orbits.gas_giant_count = world.gas_giant_count
    orbits.belt_count = world.belt_count

    mw_orbit = orbits.mainworld_orbit

    if mw_orbit is not None:
        # Stamp canonical UWP on the orbit slot (mirrors TravellerMap path).
        mw_orbit.canonical_profile = world.uwp()

        # Recalculate temperature from orbital position ("orbital temperature,
        # not random" design rule — the JSON value is discarded).
        world.temperature = generate_temperature_from_orbit(
            atmosphere=world.atmosphere,
            hz_deviation=mw_orbit.hz_deviation,
        )
        world.notes.append(
            f"System generated from existing mainworld UWP {world.uwp()}. "
            f"Placed at Star {mw_orbit.star_designation} Orbit# "
            f"{mw_orbit.orbit_number:.2f} ({mw_orbit.orbit_au:.3f} AU), "
            f"HZ deviation {mw_orbit.hz_deviation:+.2f}; "
            f"temperature recalculated as {world.temperature}."
        )

    world.atmosphere_detail = generate_atmosphere_detail(
        world.atmosphere,
        world.size,
        stellar.age_gyr,
        world.temperature,
        hz_deviation=mw_orbit.hz_deviation if mw_orbit is not None else None,
    )
    if world.atmosphere_detail is not None:
        generate_gas_mix(
            world.atmosphere_detail, world.atmosphere, world.size,
            world.temperature,
            mw_orbit.hz_deviation if mw_orbit is not None else None,
            world.hydrographics,
        )
        generate_unusual_subtype(
            world.atmosphere_detail, world.atmosphere,
            world.size, world.hydrographics,
        )

    return TravellerSystem(
        stellar_system=stellar,
        system_orbits=orbits,
        mainworld=world,
        mainworld_orbit=mw_orbit,
        nhz_atmospheres=nhz_atmospheres,
        orbital_eccentricity=orbital_eccentricity,
        orbital_inclination=orbital_inclination,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Mainworld selection (WBH pp.155-156)
# ---------------------------------------------------------------------------

def _refuel_score(hydro: int, orbit: "OrbitSlot") -> int:
    """Return 0-2 refuelling score: 2=GG satellite, 1=hydro≥5, 0=dry."""
    if orbit.world_type == "gas_giant":
        return 2
    return 1 if hydro >= 5 else 0


def _candidate_score(
    hab: int, sophont: bool, resource: int, refuel: int,
) -> int:
    """WBH weighted score for one mainworld candidate."""
    return hab * 50 + (50 if sophont else 0) + resource * 30 + refuel * 10


def select_mainworld(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    system: TravellerSystem,
    rng: Optional[random.Random] = None,
) -> bool:
    """Score all terrestrial candidates and promote the winner to mainworld.

    Scoring (WBH pp.155-156):
      habitability_rating × 50 + native_sophont × 50
      + resource_rating × 30 + refuelling_score × 10

    On a 3D roll of 18 a candidate is chosen randomly instead.
    Requires ``attach_detail()`` and ``_attach_mainworld_physical()`` to have
    run first so that habitability, sophont, and resource data are available.

    Returns ``True`` when the mainworld orbit changed (swap occurred).  When
    ``True``, the caller must re-run ``_attach_mainworld_physical()`` and
    ``_apply_mainworld_moon_tidal()`` for the new mainworld, then call
    ``apply_mainworld_social()``.  Returns ``False`` when the pre-selected
    mainworld was confirmed as the winner (no structural change).
    """
    from .traveller_world_detail import WorldDetail  # pylint: disable=import-outside-toplevel

    r = rng if rng is not None else random

    mw        = system.mainworld
    mw_orbit  = system.mainworld_orbit

    if mw is None or mw_orbit is None:
        return False

    # ------------------------------------------------------------------ #
    # Build candidate list: (orbit_or_None, WorldDetail_or_None, score)  #
    # orbit=None means the entry represents the current mainworld (World) #
    # ------------------------------------------------------------------ #
    candidates: list = []

    # Current mainworld candidate
    mw_hab      = mw.habitability_rating or 0
    mw_sophont  = mw.native_sophont
    mw_resource = (
        int(getattr(mw.size_detail, "resource_rating", 0) or 0)
        if mw.size_detail is not None else 0
    )
    mw_refuel   = _refuel_score(mw.hydrographics, mw_orbit)
    mw_score    = _candidate_score(mw_hab, mw_sophont, mw_resource, mw_refuel)
    candidates.append((None, mw_score))   # None → current mainworld

    # Secondary terrestrial candidates
    for orbit in system.system_orbits.orbits:
        if orbit.world_type != "terrestrial":
            continue
        if orbit.is_mainworld_candidate:
            continue
        det = orbit.detail
        if det is None or det.is_gas_giant:
            continue
        hab     = det.habitability_rating or 0
        sophont = det.native_sophont
        # Secondaries have no WorldPhysical → resource_rating = 0
        hydro   = int(det.sah[2], 16) if len(det.sah) > 2 else 0
        refuel  = _refuel_score(hydro, orbit)
        score   = _candidate_score(hab, sophont, 0, refuel)
        candidates.append((orbit, score))

    if len(candidates) <= 1:
        return False   # only the mainworld — nothing to compare

    # ------------------------------------------------------------------ #
    # Wild-card: 3D=18 → random selection                                #
    # ------------------------------------------------------------------ #
    wild = r.randint(1, 6) + r.randint(1, 6) + r.randint(1, 6)
    if wild == 18:
        winner_orbit, _ = candidates[r.randrange(len(candidates))]
    else:
        winner_orbit, _ = max(candidates, key=lambda c: c[1])

    # winner_orbit=None means the current mainworld won → no change
    if winner_orbit is None:
        return False

    # ------------------------------------------------------------------ #
    # Swap: promote winner_orbit to mainworld                             #
    # ------------------------------------------------------------------ #
    # a. Update orbit flags
    mw_orbit.is_mainworld_candidate        = False
    winner_orbit.is_mainworld_candidate    = True

    # b. Regenerate winner as a full World
    from . import traveller_world_gen as _twg  # pylint: disable=import-outside-toplevel
    age_gyr = system.stellar_system.primary.age_gyr
    new_mw  = generate_mainworld_at_orbit(
        name=mw.name,
        orbit=winner_orbit,
        gas_giant_count=system.system_orbits.gas_giant_count,
        belt_count=system.system_orbits.belt_count,
        system_age_gyr=age_gyr,
        nhz_atmospheres=system.nhz_atmospheres,
        rng=rng,
    )

    # c. Demote old mainworld to WorldDetail (physical data only)
    old_sah    = (f"{to_hex(mw.size)}"
                  f"{to_hex(mw.atmosphere)}"
                  f"{to_hex(mw.hydrographics)}")
    old_detail = WorldDetail(sah=old_sah)
    old_detail.biomass_rating       = mw.biomass_rating
    old_detail.biocomplexity_rating = mw.biocomplexity_rating
    old_detail.habitability_rating  = mw.habitability_rating
    old_detail.native_sophont       = mw.native_sophont
    mw_orbit.detail                 = old_detail

    # d. Clear the winner's secondary WorldDetail
    winner_orbit.detail = None

    # e. Commit to system
    _twg._rng           = rng if rng is not None else _twg._rng  # pylint: disable=protected-access
    system.mainworld       = new_mw
    system.mainworld_orbit = winner_orbit
    return True


# ---------------------------------------------------------------------------
# Body naming
# ---------------------------------------------------------------------------

_PHONETIC_LETTERS = [
    "ay", "bee", "cee", "dee", "ee", "ef", "gee", "haich",
    "eye", "jay", "kay", "el", "em", "en", "oh", "pee",
    "cue", "ar", "es", "tee", "you", "vee", "double-you",
    "ex", "why", "zed",
]
_DEFAULT_SYSTEM_NAME = "Unknown"  # sentinel used everywhere (CLI, gen-ui,
                                  # generate_full_system()) when no name is
                                  # supplied — matches "--name NAME" default.


def attach_body_names(system: TravellerSystem) -> None:
    """Assign placeholder names to all bodies in the system.

    Must be called after attach_detail() so that moon lists are populated.
    Safe to call multiple times (idempotent).
    """
    mw_name = system.mainworld.name if system.mainworld else _DEFAULT_SYSTEM_NAME

    # Name every star, including companions, as <systemname> <designation>.
    for star in system.stellar_system.stars:
        star.name = f"{mw_name} {star.designation}"

    # Name orbit slots: one ordinal counter per star, combining worlds and
    # belts in orbital-radius order (empty slots and the mainworld itself
    # don't consume a number — the mainworld keeps the bare system name).
    orbits_by_star: dict[str, list] = {}
    for orbit in system.system_orbits.orbits:
        if orbit.world_type == "empty":
            continue
        orbits_by_star.setdefault(orbit.star_designation, []).append(orbit)

    for star_desig, orbits in orbits_by_star.items():
        orbits.sort(key=lambda o: o.orbit_au)
        counter = 0
        for orbit in orbits:
            if orbit is system.mainworld_orbit:
                orbit.name = mw_name
                # mainworld_orbit and mainworld are always set together.
                system.mainworld.name = orbit.name  # type: ignore[union-attr]
            else:
                counter += 1
                orbit.name = f"{mw_name} {star_desig}-{counter}"

            # Propagate name to WorldDetail and assign phonetic moon names.
            if orbit.detail is None:
                continue
            orbit.detail.name = orbit.name
            moon_idx = 0
            for moon in orbit.detail.moons:
                if moon.is_ring:
                    continue
                letter = (_PHONETIC_LETTERS[moon_idx] if moon_idx < len(_PHONETIC_LETTERS)
                          else str(moon_idx + 1))
                moon.name = f"{orbit.name} {letter}"
                if moon.detail is not None:
                    moon.detail.name = moon.name
                moon_idx += 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Generate a Traveller star system and print it to stdout."""
    import argparse  # pylint: disable=import-outside-toplevel
    import sys as _sys  # pylint: disable=import-outside-toplevel

    parser = argparse.ArgumentParser(
        description=(
            "Generate a complete Traveller star system with mainworld. "
            "Use --detail to include all secondary world and moon profiles. "
            "Use --format to select output: text (default), json, or html."
        )
    )
    parser.add_argument("--name",   default="Unknown",
                        help="Mainworld name")
    parser.add_argument("--seed",   type=int, default=None,
                        help="RNG seed for reproducible results")
    parser.add_argument("--count",  type=int, default=1,
                        help="Number of systems to generate")
    parser.add_argument("--detail", action="store_true",
                        help="Attach all secondary world SAH/social profiles and moon data")
    parser.add_argument("--nhz-atmospheres", action="store_true",
                        help="Use WBH Non-Habitable Zone atmosphere tables for out-of-HZ worlds")
    parser.add_argument("--orbital-eccentricity", action="store_true",
                        help="Roll eccentricity for each orbit slot (WBH p.27)")
    parser.add_argument("--orbital-inclination", action="store_true",
                        help="Roll inclination for each orbit slot (WBH p.28)")
    parser.add_argument("--runaway-greenhouse", action="store_true",
                        help="Apply the WBH p.79 runaway greenhouse check to the mainworld "
                             "and (with --detail) every eligible secondary world and moon")
    # --format supersedes the legacy --json flag; --json kept for back-compat
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument("--format", choices=["text", "json", "html"],
                           default=None,
                           help="Output format: text (default), json, or html")
    fmt_group.add_argument("--json",   action="store_true",
                           help="Output as JSON (shorthand for --format json)")
    fmt_group.add_argument("--html",   action="store_true",
                           help="Output as self-contained HTML card (implies --detail)")
    args = parser.parse_args()

    # Resolve final format and detail flag
    if args.html:
        out_format = "html"
        want_detail = True
    elif args.json:
        out_format = "json"
        want_detail = args.detail
    elif args.format:
        out_format = args.format
        want_detail = args.detail or (args.format == "html")
    else:
        out_format = "text"
        want_detail = args.detail

    # pylint: disable=import-outside-toplevel
    from .system_pipeline import PipelineOptions, run_detail_pipeline

    for i in range(args.count):
        seed_val: Optional[int] = args.seed if i == 0 else None
        if seed_val is None:
            seed_val = secrets.randbelow(2 ** 31)
        rng = random.Random(seed_val)

        system = generate_full_system(
            name=args.name if args.count == 1 else f"{args.name}-{i+1}",
            rng=rng,
            nhz_atmospheres=args.nhz_atmospheres,
            orbital_eccentricity=args.orbital_eccentricity,
            orbital_inclination=args.orbital_inclination,
        )
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=want_detail,
            runaway_greenhouse=args.runaway_greenhouse,
        ))

        if out_format == "json":
            print(system.to_json())
        elif out_format == "html":
            if args.count > 1:
                _sys.stderr.write(
                    "Warning: --html with --count > 1 outputs multiple HTML documents.\n"
                )
            print(system.to_html(detail_attached=want_detail))
        else:
            if args.count > 1:
                print(f"\n{'='*60}\nSystem {i+1}\n{'='*60}")
            print(system.summary())


if __name__ == "__main__":
    main()
