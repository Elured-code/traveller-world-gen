"""
traveller_orbit_gen.py
======================
Planetary orbit generation for the Traveller RPG
(World Builder's Handbook, Sept 2023 edition).

Implements the world placement procedure from WBH pp.36-51:
  - World counts: gas giants (p.36), belts (p.36), terrestrials (p.37)
  - Minimum Allowable Orbit# (MAO) by star type/class (p.38)
  - Habitable Zone Centre Orbit# (HZCO) via sqrt(luminosity) (p.41)
  - Habitable zone breadth +/-1.0 Orbit# (p.42)
  - Baseline number and baseline Orbit# (Steps 3a/3b/3c, p.44-46)
  - Empty orbits (Step 4, p.47)
  - System spread and orbit slot placement (Steps 5-6, p.48-49)
  - World type placement in order: empty, gas giants, belts, terrestrials (p.51)
  - Mainworld candidate selection (p.51)

Out of scope: anomalous orbits (Step 7), eccentricity (Step 9),
orbital periods, Special Circumstances chapter.

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
import json, math, random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from traveller_stellar_gen import Star, StarSystem, _orbit_to_au, ORBIT_AU


def roll(n: int, dm: int = 0) -> int:
    return max(0, sum(random.randint(1, 6) for _ in range(n)) + dm)


# ---------------------------------------------------------------------------
# MAO table (WBH p.38)
# ---------------------------------------------------------------------------
MAO_TABLE: Dict[Tuple[str, int, str], float] = {
    ("O",0,"Ia"):0.63, ("O",5,"Ia"):0.55,
    ("O",0,"Ib"):0.60, ("O",5,"Ib"):0.50,
    ("O",0,"II"):0.55, ("O",5,"II"):0.45,
    ("O",0,"III"):0.53,("O",5,"III"):0.38,
    ("O",0,"V"):0.50,  ("O",5,"V"):0.30,
    ("O",0,"VI"):0.01, ("O",5,"VI"):0.01,
    ("B",0,"Ia"):0.50, ("B",5,"Ia"):1.67,
    ("B",0,"Ib"):0.35, ("B",5,"Ib"):0.63,
    ("B",0,"II"):0.30, ("B",5,"II"):0.35,
    ("B",0,"III"):0.25,("B",5,"III"):0.15,
    ("B",0,"IV"):0.20, ("B",5,"IV"):0.13,
    ("B",0,"V"):0.18,  ("B",5,"V"):0.09,
    ("B",0,"VI"):0.01, ("B",5,"VI"):0.01,
    ("A",0,"Ia"):3.34, ("A",5,"Ia"):4.17,
    ("A",0,"Ib"):1.40, ("A",5,"Ib"):2.17,
    ("A",0,"II"):0.75, ("A",5,"II"):1.17,
    ("A",0,"III"):0.13,("A",5,"III"):0.13,
    ("A",0,"IV"):0.10, ("A",5,"IV"):0.07,
    ("A",0,"V"):0.06,  ("A",5,"V"):0.05,
    ("F",0,"Ia"):4.42, ("F",5,"Ia"):5.00,
    ("F",0,"Ib"):2.50, ("F",5,"Ib"):3.25,
    ("F",0,"II"):1.33, ("F",5,"II"):1.87,
    ("F",0,"III"):0.13,("F",5,"III"):0.13,
    ("F",0,"IV"):0.07, ("F",5,"IV"):0.06,
    ("F",0,"V"):0.04,  ("F",5,"V"):0.03,
    ("G",0,"Ia"):5.21, ("G",5,"Ia"):5.34,
    ("G",0,"Ib"):3.59, ("G",5,"Ib"):3.84,
    ("G",0,"II"):2.24, ("G",5,"II"):2.67,
    ("G",0,"III"):0.25,("G",5,"III"):0.38,
    ("G",0,"IV"):0.07, ("G",5,"IV"):0.10,
    ("G",0,"V"):0.03,  ("G",5,"V"):0.02,
    ("G",0,"VI"):0.02, ("G",5,"VI"):0.02,
    ("K",0,"Ia"):5.59, ("K",5,"Ia"):6.17,
    ("K",0,"Ib"):4.17, ("K",5,"Ib"):4.84,
    ("K",0,"II"):3.17, ("K",5,"II"):4.00,
    ("K",0,"III"):0.50,("K",5,"III"):1.00,
    ("K",0,"V"):0.02,  ("K",5,"V"):0.02,
    ("K",0,"VI"):0.02, ("K",5,"VI"):0.01,
    ("M",0,"Ia"):6.80, ("M",5,"Ia"):7.20, ("M",9,"Ia"):7.80,
    ("M",0,"Ib"):5.42, ("M",5,"Ib"):6.17, ("M",9,"Ib"):6.59,
    ("M",0,"II"):4.59, ("M",5,"II"):5.30, ("M",9,"II"):5.92,
    ("M",0,"III"):1.68,("M",5,"III"):3.00,("M",9,"III"):4.34,
    ("M",0,"V"):0.02,  ("M",5,"V"):0.01,  ("M",9,"V"):0.01,
    ("M",0,"VI"):0.01, ("M",5,"VI"):0.01, ("M",9,"VI"):0.01,
}


def _interp(
    spectral: str,
    subtype: int,
    lum_class: str,
    table: Dict[Tuple[str, int, str], float],
) -> float:
    anchors = [0,5,9] if spectral == "M" else [0,5]
    for i in range(len(anchors)-1):
        lo, hi = anchors[i], anchors[i+1]
        if lo <= subtype <= hi:
            vlo = table.get((spectral, lo, lum_class))
            vhi = table.get((spectral, hi, lum_class))
            if vlo is not None and vhi is not None:
                return vlo + (vhi - vlo) * (subtype - lo) / (hi - lo)
            break
    for a in [0, 5, 9]:
        v = table.get((spectral, a, lum_class))
        if v is not None:
            return v
    return 0.02


def get_mao(star: Star) -> float:
    if star.spectral_type in ("D","BD"):
        return 0.01
    st = star.subtype if star.subtype is not None else 0
    return _interp(star.spectral_type, st, star.lum_class, MAO_TABLE)


def _au_to_orbit(au: float) -> float:
    keys = sorted(ORBIT_AU.keys())
    vals = [ORBIT_AU[k] for k in keys]
    if au <= vals[0]: return float(keys[0])
    if au >= vals[-1]: return float(keys[-1])
    for i in range(len(vals)-1):
        if vals[i] <= au <= vals[i+1]:
            frac = (au - vals[i]) / (vals[i+1] - vals[i])
            return keys[i] + (keys[i+1] - keys[i]) * frac
    return float(keys[-1])


def get_hzco(star: Star, combined_lum: Optional[float] = None) -> float:
    lum = combined_lum if combined_lum is not None else star.luminosity
    hzco_au = math.sqrt(max(lum, 1e-10))
    return _au_to_orbit(hzco_au)


def _temp_zone(deviation: float, hzco: float, orbit: float) -> str:
    if hzco < 1.0 or orbit < 1.0:
        denom = max(min(hzco, orbit), 0.01)
        dev = deviation / denom
    else:
        dev = deviation
    if dev >= 1.0:   return "frozen"
    elif dev >= 0.2: return "cold"
    elif dev >= -0.2:return "temperate"
    elif dev >= -1.0:return "hot"
    else:            return "boiling"


@dataclass
class OrbitSlot:
    star_designation: str
    orbit_number: float
    orbit_au: float
    slot_index: int
    world_type: str
    is_habitable_zone: bool
    hz_deviation: float
    temperature_zone: str
    is_mainworld_candidate: bool = False
    notes: str = ""
    canonical_profile: str = ""  # UWP set when mainworld comes from canonical data

    def to_dict(self) -> dict:
        d = {
            "star": self.star_designation,
            "orbit_number": round(self.orbit_number, 2),
            "orbit_au": round(self.orbit_au, 3),
            "slot_index": self.slot_index,
            "world_type": self.world_type,
            "is_habitable_zone": self.is_habitable_zone,
            "hz_deviation": round(self.hz_deviation, 2),
            "temperature_zone": self.temperature_zone,
            "is_mainworld_candidate": self.is_mainworld_candidate,
            "notes": self.notes,
        }
        if self.canonical_profile:
            d["canonical_profile"] = self.canonical_profile
        # Include secondary world / satellite detail if attach_detail() has run
        detail = getattr(self, "detail", None)
        if detail is not None:
            d["detail"] = detail.to_dict()
        return d


@dataclass
class SystemOrbits:
    stellar_system: StarSystem
    gas_giant_count: int = 0
    belt_count: int = 0
    terrestrial_count: int = 0
    total_worlds: int = 0
    empty_orbits: int = 0
    orbits: List[OrbitSlot] = field(default_factory=list)
    mainworld_orbit: Optional[OrbitSlot] = None
    star_mao: Dict[str, float] = field(default_factory=dict)
    star_hzco: Dict[str, float] = field(default_factory=dict)
    star_hz_inner: Dict[str, float] = field(default_factory=dict)
    star_hz_outer: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "gas_giant_count": self.gas_giant_count,
            "belt_count": self.belt_count,
            "terrestrial_count": self.terrestrial_count,
            "total_worlds": self.total_worlds,
            "empty_orbits": self.empty_orbits,
            "star_zones": {
                d: {
                    "mao": round(self.star_mao.get(d,0),2),
                    "hzco": round(self.star_hzco.get(d,0),2),
                    "hz_inner": round(self.star_hz_inner.get(d,0),2),
                    "hz_outer": round(self.star_hz_outer.get(d,0),2),
                } for d in self.star_mao
            },
            "orbits": [o.to_dict() for o in self.orbits],
            "mainworld_orbit": self.mainworld_orbit.to_dict() if self.mainworld_orbit else None,
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        """
        Human-readable orbital summary.

        If attach_detail() has been called on the parent TravellerSystem,
        each orbit line will include its secondary world profile and any
        significant moons.  Without detail attached, only world type and
        zone are shown.
        """
        lines = ["=" * 88]
        lines.append(
            f"  Orbits: {self.total_worlds} worlds  "
            f"({self.gas_giant_count} GG, {self.belt_count} belts, "
            f"{self.terrestrial_count} terrestrial, {self.empty_orbits} empty slots)"
        )
        lines.append("=" * 88)
        for d, mao in self.star_mao.items():
            hzco = self.star_hzco.get(d, 0)
            inner = self.star_hz_inner.get(d, 0)
            outer = self.star_hz_outer.get(d, 0)
            lines.append(
                f"  Star {d}  MAO={mao:.2f}  HZCO={hzco:.2f}  "
                f"HZ {inner:.2f}–{outer:.2f}"
            )
        lines.append("-" * 88)
        lines.append(
            f"  {'Star':<5} {'#':<4} {'Orbit#':<8} {'AU':<9} "
            f"{'Type':<14} {'Profile':<20} {'Zone':<12} Notes"
        )
        lines.append("  " + "-" * 82)
        for o in self.orbits:
            hz   = "★" if o.is_habitable_zone else " "
            mw   = "  ← mainworld" if o.is_mainworld_candidate else ""
            detail = getattr(o, "detail", None)
            if o.canonical_profile:
                profile = o.canonical_profile
            elif detail is not None:
                profile = detail.profile
            elif o.world_type == "empty":
                profile = "—"
            else:
                profile = "—"
            lines.append(
                f"  {o.star_designation:<5} {o.slot_index:<4} "
                f"{o.orbit_number:<8.2f} {o.orbit_au:<9.3f} "
                f"{o.world_type:<14} {profile:<20} "
                f"{o.temperature_zone:<12}{hz}{mw}"
            )
            # Moon sub-rows when detail is attached
            if detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):
                    if moon.is_ring:
                        rc = getattr(moon, "_ring_count", 1)
                        mp = f"R{rc:02d}"
                        ms = "ring system"
                    elif moon.detail is not None:
                        mp = moon.detail.profile
                        ms = f"size {moon.size_str}"
                    else:
                        mp = f"size {moon.size_str}"
                        ms = ""
                    lines.append(
                        f"  {'':5} {'':4} {'':8} {'':9} "
                        f"  {'moon '+str(mi):<12} {mp:<20} {'':12}  {ms}"
                    )
        lines.append("=" * 88)
        if self.mainworld_orbit:
            mw = self.mainworld_orbit
            lines.append(
                f"  Mainworld: Star {mw.star_designation}  "
                f"Orbit# {mw.orbit_number:.2f} ({mw.orbit_au:.3f} AU)  "
                f"{mw.temperature_zone.title()}  {mw.world_type}"
            )
            lines.append("=" * 88)
        return "\n".join(lines)


def generate_orbits(system: StarSystem) -> SystemOrbits:
    result = SystemOrbits(stellar_system=system)
    primary_stars = [s for s in system.stars if s.role != "companion"]
    has_companion = any(s.role == "companion" for s in system.stars)
    secondary_count = sum(1 for s in primary_stars if s.role != "primary")
    primary = system.primary

    # World counts (WBH p.36-37)
    if roll(2) <= 9:
        r = roll(2)
        gg = 1 if r<=4 else 2 if r<=6 else 3 if r<=8 else 4 if r<=11 else 5 if r==12 else 6
    else:
        gg = 0
    belts = 0
    if roll(2) >= 8:
        r = roll(2, 1 if gg>0 else 0)
        belts = 1 if r<=6 else 2 if r<=11 else 3
    tp = max(1, roll(2) - 2)
    result.gas_giant_count = gg
    result.belt_count = belts
    result.terrestrial_count = tp
    result.total_worlds = gg + belts + tp

    # Empty orbits (WBH p.47)
    er = roll(2)
    empty = 0 if er<=9 else er-9
    result.empty_orbits = empty

    # MAO and HZCO per star
    star_hzco: Dict[str, float] = {}
    star_mao:  Dict[str, float] = {}
    star_avail: Dict[str, Tuple[float,float]] = {}

    for star in primary_stars:
        mao = get_mao(star)
        comp_lum = sum(
            s.luminosity for s in system.stars
            if s.role == "companion" and s.designation.startswith(star.designation)
            and s.designation != star.designation
        )
        hzco = get_hzco(star, star.luminosity + comp_lum)
        star_mao[star.designation] = mao
        star_hzco[star.designation] = hzco

        # Available orbit range — table ends at orbit# 17 (8512 AU)
        max_o = 17.0
        if star.role == "primary":
            for other in primary_stars:
                if other.role in ("close","near","far") and other.orbit_number:
                    excl = other.orbit_number - 1.0
                    if excl > mao:
                        max_o = min(max_o, excl)
        elif star.role in ("close","near","far") and star.orbit_number:
            max_o = max(mao+0.1, star.orbit_number - 3.0)
        elif star.role == "companion":
            max_o = 0.65

        star_avail[star.designation] = (mao, max_o)
        result.star_mao[star.designation] = mao
        result.star_hzco[star.designation] = hzco
        result.star_hz_inner[star.designation] = max(mao, hzco - 1.0)
        result.star_hz_outer[star.designation] = min(max_o, hzco + 1.0)

    # Allocate worlds to stars proportionally by available orbit range
    if len(primary_stars) == 1:
        alloc = {primary_stars[0].designation: result.total_worlds}
    else:
        total_range = sum(
            max(0.0, star_avail[s.designation][1] - star_avail[s.designation][0])
            for s in primary_stars
        )
        alloc: Dict[str, int] = {}
        remaining = result.total_worlds
        for i, star in enumerate(primary_stars):
            if i == len(primary_stars)-1:
                alloc[star.designation] = remaining
            else:
                rng = max(0.0, star_avail[star.designation][1] - star_avail[star.designation][0])
                n = round(result.total_worlds * rng / max(total_range, 0.01))
                n = max(0, min(n, remaining))
                alloc[star.designation] = n
                remaining -= n

    # World type pool
    pool = ["gas_giant"]*gg + ["belt"]*belts + ["terrestrial"]*tp
    random.shuffle(pool)
    pool_idx = 0

    for star in primary_stars:
        d = star.designation
        n_worlds = alloc.get(d, 0)
        n_empty_here = empty if star == primary_stars[0] else 0
        total_slots = n_worlds + n_empty_here
        if total_slots <= 0:
            continue

        mao = star_mao[d]
        hzco = star_hzco[d]
        min_o, max_o = star_avail[d]

        # Baseline number (WBH p.44)
        bn_dm = 0
        if has_companion: bn_dm -= 2
        if star.lum_class in ("Ia","Ib","II"): bn_dm += 3
        elif star.lum_class == "III": bn_dm += 2
        elif star.lum_class == "IV":  bn_dm += 1
        elif star.lum_class == "VI":  bn_dm -= 1
        bn_dm -= secondary_count
        tw = result.total_worlds
        if tw < 6: bn_dm -= 4
        elif tw <= 9: bn_dm -= 3
        elif tw <= 12: bn_dm -= 2
        elif tw <= 15: bn_dm -= 1
        elif tw >= 18: bn_dm += 1
        baseline_num = max(0, roll(2, bn_dm))

        # Baseline Orbit# (WBH p.44-46)
        vs = 0.1 if hzco >= 1.0 else 0.01
        n_total_stars = len(primary_stars)
        if 1 <= baseline_num <= total_slots:
            # Step 3a: baseline world is in the habitable zone
            var = (roll(2)-7) * vs
            baseline_orbit = max(mao, hzco + var)
        elif baseline_num < 1:
            # Step 3b: cold system — all worlds are beyond the HZCO.
            # WBH p.45: Baseline Orbit# = HZCO − baseline_number + Total Worlds + (2D-7)/10
            # baseline_number is ≤0 so subtracting it adds its absolute value.
            # Total Worlds is added as whole Orbit#s (no 0.1 multiplier) to push
            # the baseline — and therefore the innermost world — well outside the HZ.
            anchor = max(mao, hzco)
            if anchor >= 1.0:
                var = (roll(2)-7) / 10.0
                # FIX: add total_worlds as whole Orbit#s, not total_slots*0.1
                baseline_orbit = anchor + abs(baseline_num) + n_worlds + var
            else:
                # Sub-Orbit#1 HZCO: use 1/10 scaling throughout (WBH p.45)
                var = (roll(2)-2) / 100.0
                baseline_orbit = anchor + abs(baseline_num)/10.0 + n_worlds/10.0 + var
            baseline_orbit = max(mao, baseline_orbit)
            baseline_num = 1
        else:
            # Step 3c: hot system — all worlds are inside the HZCO
            inner = hzco - baseline_num + total_slots
            if inner < 1.0 or hzco < 1.0:
                var = (roll(2)-7) / 100.0
                baseline_orbit = hzco - baseline_num/10.0 + total_slots/10.0 + var
            else:
                var = (roll(2)-7) * vs
                baseline_orbit = inner + var
            baseline_orbit = max(mao, min(baseline_orbit, hzco - 0.01))
            baseline_num = total_slots

        baseline_orbit = max(mao, min(baseline_orbit, max_o - 0.01))

        # Spread (WBH p.48)
        # Formula: Spread = (Baseline Orbit# - MAO) / Baseline Number
        spread = (baseline_orbit - mao) / max(1, baseline_num)
        # Maximum Spread = Primary's Available Orbits / (All Slots + Total Stars)
        # Denominator uses total_slots (worlds + empty) so every slot gets a
        # spread unit, preventing outer slots from piling up at the ceiling.
        avail = max_o - mao
        max_spread = avail / max(total_slots + n_total_stars, 1)
        # Minimum spread: when baseline_num is large the formula above collapses
        # to HZCO/total_slots (~0.4 for a G star with 8 worlds), pinning all
        # slots near the inner system.  Enforce a floor so worlds span at least
        # half the available range.
        min_spread = avail / max(total_slots * 2, 1)
        spread = max(min_spread, min(spread, max_spread))
        spread = min(spread, max_spread)
        spread = max(0.01, spread)

        # Place slots (WBH p.48-49)
        # Inner Slot Orbit# = (MAO + Spread) + (2D-7) × Spread/10
        # Each subsequent slot: Previous + Spread + (2D-7) × Spread/10
        slots: List[float] = []
        current = mao + spread + (roll(2)-7)*0.1*spread
        current = max(mao, current)
        for _ in range(total_slots):
            current = max(mao, min(current, max_o))
            # Additive gap check (was multiplicative `* 1.1`, which triggered
            # constantly once orbit# exceeded spread/0.1 and halved every step).
            if slots and current - slots[-1] < spread * 0.4:
                current = min(slots[-1] + spread * 0.5, max_o)
            # Stop if we cannot advance past the last slot (at ceiling)
            if slots and round(current, 2) == round(slots[-1], 2):
                break
            slots.append(round(current, 2))
            current += spread + (roll(2)-7)*0.1*spread

        # Assign world types
        empty_set = set(random.sample(range(len(slots)), min(n_empty_here, len(slots))))
        for si, on in enumerate(slots):
            au = _orbit_to_au(on)
            dev = on - hzco
            in_hz = abs(dev) <= 1.0
            tz = _temp_zone(dev, hzco, on)
            if si in empty_set:
                wtype = "empty"
            elif pool_idx < len(pool):
                wtype = pool[pool_idx]; pool_idx += 1
            else:
                wtype = "terrestrial"
            result.orbits.append(OrbitSlot(
                star_designation=d, orbit_number=on, orbit_au=au,
                slot_index=si+1, world_type=wtype,
                is_habitable_zone=in_hz, hz_deviation=round(dev,3),
                temperature_zone=tz,
            ))

    result.orbits.sort(key=lambda o: (o.star_designation, o.orbit_au))

    # Recount from what was actually placed — early breaks or pool exhaustion
    # can leave metadata counts from the initial dice rolls out of sync.
    result.gas_giant_count   = sum(1 for o in result.orbits if o.world_type == "gas_giant")
    result.belt_count        = sum(1 for o in result.orbits if o.world_type == "belt")
    result.terrestrial_count = sum(1 for o in result.orbits if o.world_type == "terrestrial")
    result.total_worlds      = (result.gas_giant_count
                                + result.belt_count
                                + result.terrestrial_count)

    # Mainworld selection (WBH p.51)
    candidates = [o for o in result.orbits if o.world_type != "empty"]
    if candidates:
        pd = system.primary.designation

        def score(o):
            ts = 0 if o.world_type == "terrestrial" else 2
            hs = 0 if o.is_habitable_zone else 5
            tp_s = {"temperate":0,"cold":1,"hot":1,"frozen":3,"boiling":4}.get(o.temperature_zone,5)
            ps = 0 if o.star_designation == pd else 1
            return (ts+hs+tp_s+ps, abs(o.hz_deviation))

        best = min(candidates, key=score)
        best.is_mainworld_candidate = True
        result.mainworld_orbit = best
        notes = []
        if best.is_habitable_zone: notes.append("in HZ")
        if best.hz_deviation < -0.5: notes.append("warm side")
        elif best.hz_deviation > 0.5: notes.append("cool side")
        best.notes = ", ".join(notes)

    return result


def generate_full_system(seed=None):
    from traveller_stellar_gen import generate_stellar_data
    if seed is not None:
        random.seed(seed)
    system = generate_stellar_data()
    orbits = generate_orbits(system)
    return system, orbits


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    system, orbits = generate_full_system(args.seed)
    if args.json:
        d = system.to_dict(); d["orbits"] = orbits.to_dict()
        print(json.dumps(d, indent=2))
    else:
        print(system.summary())
        print(orbits.summary())
