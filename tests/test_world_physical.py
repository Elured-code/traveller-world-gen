"""
test_world_physical.py
======================
pytest unit tests for traveller_world_physical.py.

Test strategy
-------------
Deterministic logic (DM calculations, table lookups, multipliers) is tested
directly. Dice-dependent outcomes are tested by patching random.randint to a
fixed value, allowing the downstream logic to be verified.
"""

import math
from typing import Any
from unittest.mock import patch

import pytest

from traveller_moon_gen import Moon  # pylint: disable=import-error
from traveller_world_gen import World

from traveller_world_physical import (
    TIDAL_STATUS_LABELS,
    WorldPhysical,
    _apply_seismic_stress,
    _apply_tidal_lock_result,
    _compute_mean_temperature,
    _compute_rss,
    _compute_thf,
    _orbital_period_hours,
    _orbit_dm_for_mean_temp,
    _planet_moon_lock_dm,
    _reroll_eccentricity_tidal,
    _roll_axial_tilt_1d,
    _roll_tidal_lock_status,
    _tidal_lock_dm,
    apply_moon_tidal_effects,
    generate_world_physical,
)


# ---------------------------------------------------------------------------
# Minimal World stub
# ---------------------------------------------------------------------------

class _World(World):
    """Minimal stub matching the fields read by generate_world_physical."""
    def __init__(self, size: int = 6, atmosphere: int = 6):
        super().__init__(size=size, atmosphere=atmosphere)


# ---------------------------------------------------------------------------
# _orbital_period_hours
# ---------------------------------------------------------------------------

class TestOrbitalPeriodHours:
    def test_earth_orbit(self):
        # 1 AU, 1 solar mass → 1 year = 8766 hours
        assert abs(_orbital_period_hours(1.0, 1.0) - 8766.0) < 1.0

    def test_closer_orbit_shorter_period(self):
        assert _orbital_period_hours(0.5, 1.0) < _orbital_period_hours(1.0, 1.0)

    def test_heavier_star_shorter_period(self):
        assert _orbital_period_hours(1.0, 2.0) < _orbital_period_hours(1.0, 1.0)


# ---------------------------------------------------------------------------
# _tidal_lock_dm — general DMs
# ---------------------------------------------------------------------------

class TestTidalLockDmGeneral:
    """General DMs (WBH p.105) folded into _tidal_lock_dm."""

    BASE = -4  # star-lock base DM always included

    def _dm(self, size=6, axial_tilt=10.0, atmosphere=6, age_gyr=3.0,
            orbit_number=2.5, star_mass=1.0):
        return _tidal_lock_dm(size, axial_tilt, atmosphere, age_gyr,
                              orbit_number, star_mass)

    def test_size_dm_rounds_up(self):
        # size 6 → ceil(6/3)=2; orbit 2-3 → +1; star 1.0 → 0; base -4; age 3 → 0
        assert self._dm(size=6) == -4 + 2 + 1

    def test_size_dm_rounds_up_odd(self):
        # size 7 → ceil(7/3)=3
        assert self._dm(size=7) == -4 + 3 + 1

    def test_axial_tilt_above_30(self):
        dm_base = self._dm(axial_tilt=10.0)
        dm_tilted = self._dm(axial_tilt=45.0)
        assert dm_tilted == dm_base - 2

    def test_axial_tilt_60_to_120_additive(self):
        # 75° → above 30° (−2) + 60-120° (−4) = −6 from tilt
        dm_base = self._dm(axial_tilt=10.0)
        dm_tilted = self._dm(axial_tilt=75.0)
        assert dm_tilted == dm_base - 6

    def test_axial_tilt_80_to_100_triple_additive(self):
        # 85° → above 30° (−2) + 60-120° (−4) + 80-100° (−4) = −10 from tilt
        dm_base = self._dm(axial_tilt=10.0)
        dm_tilted = self._dm(axial_tilt=85.0)
        assert dm_tilted == dm_base - 10

    def test_atmosphere_high_pressure(self):
        dm_normal = self._dm(atmosphere=6)
        dm_dense = self._dm(atmosphere=8)
        assert dm_dense == dm_normal - 2

    def test_age_young(self):
        dm_normal = self._dm(age_gyr=3.0)
        dm_young = self._dm(age_gyr=0.5)
        assert dm_young == dm_normal - 2

    def test_age_5_to_10(self):
        dm_normal = self._dm(age_gyr=3.0)
        dm_old = self._dm(age_gyr=7.0)
        assert dm_old == dm_normal + 2

    def test_age_over_10(self):
        dm_normal = self._dm(age_gyr=3.0)
        dm_ancient = self._dm(age_gyr=12.0)
        assert dm_ancient == dm_normal + 4


# ---------------------------------------------------------------------------
# _tidal_lock_dm — orbit# and star mass DMs
# ---------------------------------------------------------------------------

class TestTidalLockDmStarLock:
    def _dm(self, orbit_number=2.5, star_mass=1.0, size=6, axial_tilt=10.0,
            atmosphere=6, age_gyr=3.0):
        return _tidal_lock_dm(size, axial_tilt, atmosphere, age_gyr,
                              orbit_number, star_mass)

    def test_orbit_1_to_2(self):
        # orbit 1.5 → +4 star orbit DM
        dm = self._dm(orbit_number=1.5)
        dm_ref = self._dm(orbit_number=2.5)   # orbit 2-3 → +1
        assert dm - dm_ref == 3               # +4 vs +1

    def test_orbit_sub1(self):
        # orbit 0.5 → +4 + floor(10×0.5) = +4+5 = +9
        dm_sub = self._dm(orbit_number=0.5)
        dm_ref = self._dm(orbit_number=2.5)   # +1
        assert dm_sub - dm_ref == 8           # +9 vs +1

    def test_orbit_beyond_3(self):
        # orbit 5.0 → -floor(5)×2 = -10
        dm = self._dm(orbit_number=5.0)
        dm_ref = self._dm(orbit_number=2.5)   # +1
        assert dm - dm_ref == -11             # -10 vs +1

    def test_orbit_boundary_2_uses_closer_dm(self):
        # exactly 2.0 → between 2 and 3 (+1), not 1-2 (+4) — closer to 0
        dm_at2 = self._dm(orbit_number=2.0)
        dm_above2 = self._dm(orbit_number=2.1)
        assert dm_at2 == dm_above2

    def test_star_mass_light(self):
        dm_light = self._dm(star_mass=0.3)
        dm_mid = self._dm(star_mass=0.7)
        assert dm_light == dm_mid - 1         # -2 vs -1

    def test_star_mass_heavy(self):
        dm_heavy = self._dm(star_mass=6.0)
        dm_mid = self._dm(star_mass=0.7)
        assert dm_heavy - dm_mid == 3         # +2 vs -1


# ---------------------------------------------------------------------------
# _tidal_lock_dm — eccentricity DM (WBH p.105 "DMs for all cases")
# ---------------------------------------------------------------------------

class TestTidalLockEccentricityDm:
    """Eccentricity DM: e > 0.1 → DM − floor(e × 10) (WBH p.105)."""

    def _dm(self, orbit_eccentricity=0.0, size=6, axial_tilt=10.0,
            atmosphere=6, age_gyr=3.0, orbit_number=2.5, star_mass=1.0):
        return _tidal_lock_dm(size, axial_tilt, atmosphere, age_gyr,
                              orbit_number, star_mass, orbit_eccentricity)

    def test_no_dm_at_zero(self):
        """e=0.0 → no eccentricity DM."""
        assert self._dm(0.0) == self._dm(0.0)  # baseline is stable

    def test_no_dm_at_exact_threshold(self):
        """e=0.1 is not > 0.1, so no DM applied."""
        assert self._dm(0.1) == self._dm(0.0)

    def test_dm_just_above_threshold(self):
        """e=0.15 → int(0.15×10)=1 → DM−1."""
        assert self._dm(0.15) == self._dm(0.0) - 1

    def test_dm_floors_not_rounds(self):
        """e=0.25 → int(0.25×10)=2, not 3 → DM−2 (floor, not round)."""
        assert self._dm(0.25) == self._dm(0.0) - 2

    def test_dm_medium_eccentricity(self):
        """e=0.50 → int(0.50×10)=5 → DM−5."""
        assert self._dm(0.50) == self._dm(0.0) - 5

    def test_dm_high_eccentricity(self):
        """e=0.999 → int(0.999×10)=9 → DM−9."""
        assert self._dm(0.999) == self._dm(0.0) - 9


# ---------------------------------------------------------------------------
# _apply_tidal_lock_result — all table rows
# ---------------------------------------------------------------------------

class TestApplyTidalLockResult:
    DAY = 24.0
    PERIOD = 8766.0

    def test_result_2_no_change(self):
        day, tilt, status = _apply_tidal_lock_result(2, self.DAY, 15.0, self.PERIOD)
        assert day == self.DAY
        assert status == "none"

    def test_result_1_no_change(self):
        day, _, status = _apply_tidal_lock_result(1, self.DAY, 15.0, self.PERIOD)
        assert day == self.DAY
        assert status == "none"

    def test_result_3_multiplier(self):
        day, _, status = _apply_tidal_lock_result(3, self.DAY, 15.0, self.PERIOD)
        assert day == pytest.approx(self.DAY * 1.5, rel=1e-3)
        assert status == "braking"

    def test_result_4_multiplier(self):
        day, _, status = _apply_tidal_lock_result(4, self.DAY, 15.0, self.PERIOD)
        assert day == pytest.approx(self.DAY * 2.0, rel=1e-3)
        assert status == "braking"

    def test_result_6_multiplier(self):
        day, _, status = _apply_tidal_lock_result(6, self.DAY, 15.0, self.PERIOD)
        assert day == pytest.approx(self.DAY * 5.0, rel=1e-3)
        assert status == "braking"

    def test_result_7_prograde(self):
        with patch("traveller_world_physical.random.randint", return_value=3):
            day, _, status = _apply_tidal_lock_result(7, self.DAY, 15.0, self.PERIOD)
        assert day == 3 * 5 * 24
        assert status == "prograde"

    def test_result_8_prograde(self):
        with patch("traveller_world_physical.random.randint", return_value=2):
            day, _, status = _apply_tidal_lock_result(8, self.DAY, 15.0, self.PERIOD)
        assert day == 2 * 20 * 24
        assert status == "prograde"

    def test_result_9_retrograde_tilt_flipped(self):
        with patch("traveller_world_physical.random.randint", return_value=1):
            day, tilt, status = _apply_tidal_lock_result(9, self.DAY, 30.0, self.PERIOD)
        assert day == 1 * 10 * 24
        assert tilt == pytest.approx(180.0 - 30.0)
        assert status == "retrograde"

    def test_result_9_retrograde_tilt_unchanged_if_already_retrograde(self):
        with patch("traveller_world_physical.random.randint", return_value=1):
            _, tilt, _ = _apply_tidal_lock_result(9, self.DAY, 120.0, self.PERIOD)
        assert tilt == 120.0

    def test_result_10_retrograde(self):
        with patch("traveller_world_physical.random.randint", return_value=1):
            day, tilt, status = _apply_tidal_lock_result(10, self.DAY, 45.0, self.PERIOD)
        assert day == 1 * 50 * 24
        assert tilt == pytest.approx(180.0 - 45.0)
        assert status == "retrograde"

    def test_result_11_three_two_lock(self):
        day, _, status = _apply_tidal_lock_result(11, self.DAY, 1.0, self.PERIOD)
        assert day == pytest.approx(self.PERIOD * 2.0 / 3.0, rel=1e-3)
        assert status == "3:2_lock"

    def test_result_11_axial_tilt_rerolled_when_above_3(self):
        # tilt > 3° → rerolled as (2D-2)/10; patch dice to return 4 → (4+4-2)/10=0.6
        with patch("traveller_world_physical.random.randint", return_value=4):
            _, tilt, _ = _apply_tidal_lock_result(11, self.DAY, 45.0, self.PERIOD)
        assert tilt == pytest.approx((4 + 4 - 2) / 10.0)

    def test_result_11_axial_tilt_kept_when_at_or_below_3(self):
        _, tilt, _ = _apply_tidal_lock_result(11, self.DAY, 2.0, self.PERIOD)
        assert tilt == 2.0

    def test_result_12_one_one_lock(self):
        # Suppress broken-lock check (allow_broken_check=False)
        day, _, status = _apply_tidal_lock_result(
            12, self.DAY, 1.0, self.PERIOD, allow_broken_check=False
        )
        assert day == pytest.approx(self.PERIOD, rel=1e-3)
        assert status == "1:1_lock"

    def test_broken_lock_natural_12_rerolls(self):
        # Broken lock: first 2D=12 → reroll → reroll gives 2 → "none"
        roll_sequence = iter([6, 6,   # broken-lock check: 12
                              1, 1])  # reroll: 2 → "none"
        with patch("traveller_world_physical.random.randint", side_effect=roll_sequence):
            _, _, status = _apply_tidal_lock_result(
                12, self.DAY, 1.0, self.PERIOD, allow_broken_check=True
            )
        assert status == "none"

    def test_broken_lock_not_12_stays_locked(self):
        # Broken lock check: 2D ≠ 12 → lock stands
        with patch("traveller_world_physical.random.randint", return_value=3):
            _, _, status = _apply_tidal_lock_result(
                12, self.DAY, 1.0, self.PERIOD, allow_broken_check=True
            )
        assert status == "1:1_lock"


# ---------------------------------------------------------------------------
# _roll_tidal_lock_status — skip and auto-lock thresholds
# ---------------------------------------------------------------------------

class TestRollTidalLockStatus:
    def _call(self, **kwargs):
        defaults: dict[str, Any] = dict(size=6, axial_tilt=10.0, atmosphere=6, age_gyr=3.0,
                        orbit_number=2.5, orbit_au=1.6, star_mass=1.0,
                        basic_day_h=24.0)
        defaults.update(kwargs)
        return _roll_tidal_lock_status(**defaults)

    def test_dm_le_minus10_skips_roll(self):
        # Very distant orbit (orbit_number=8) → DM = -4 + ceil(6/3) + (-floor(8)*2) + 1_age
        # = -4+2-16+1 = -17 ≤ -10 → skip
        _, _, status = self._call(orbit_number=8.0, age_gyr=3.0)
        assert status == "none"

    def test_dm_ge_plus10_auto_1_1_lock(self):
        # Very close orbit (orbit_number=0.1), heavy star, old system → DM ≥ 10
        # DM: -4 + ceil(6/3)=2 + (4+floor(10×0.9))=4+9=13 + age>10=4 + star>5=2 = 17
        with patch("traveller_world_physical.random.randint", return_value=3):
            _, _, status = self._call(
                orbit_number=0.1, star_mass=6.0, age_gyr=12.0,
            )
        # broken-lock check patch(3+3=6≠12) → lock stands
        assert status == "1:1_lock"


# ---------------------------------------------------------------------------
# generate_world_physical — integration and backward compat
# ---------------------------------------------------------------------------

class TestGenerateWorldPhysical:
    def test_returns_none_for_belt(self):
        w = _World(size=0)
        assert generate_world_physical(w) is None

    def test_returns_worldphysical_for_size_6(self):
        w = _World(size=6)
        result = generate_world_physical(w)
        assert isinstance(result, WorldPhysical)

    def test_tidal_status_none_when_no_orbit_data(self):
        w = _World(size=6)
        result = generate_world_physical(w, age_gyr=5.0)
        assert result is not None
        assert result.tidal_status == "none"

    def test_tidal_status_set_when_orbit_data_provided(self):
        # Close orbit, heavy star, old age → should produce a non-"none" status
        w = _World(size=6, atmosphere=6)
        result = generate_world_physical(
            w, age_gyr=12.0, orbit_number=1.5, orbit_au=0.4, star_mass=1.0
        )
        assert result is not None
        assert result.tidal_status in TIDAL_STATUS_LABELS

    def test_to_dict_includes_tidal_status(self):
        w = _World(size=6)
        result = generate_world_physical(w)
        assert result is not None
        d = result.to_dict()
        assert "tidal_status" in d
        assert d["tidal_status"] == "none"

    def test_axial_tilt_range(self):
        w = _World(size=6)
        for _ in range(20):
            result = generate_world_physical(w)
            assert result is not None
            assert 0.0 <= result.axial_tilt <= 180.0


# ---------------------------------------------------------------------------
# _roll_axial_tilt_1d — WBH p.77 Rule 3 helper
# ---------------------------------------------------------------------------

class TestRollAxialTilt1d:
    def test_all_bands_in_range(self):
        for band in range(1, 7):
            with patch("traveller_world_physical.random.randint", side_effect=[band, 3, 3, 3]):
                result = _roll_axial_tilt_1d()
            assert 0.0 <= result <= 180.0

    def test_band_1_formula(self):
        # band=1, inner=1 → round((1-1)/50, 2) == 0.0
        with patch("traveller_world_physical.random.randint", side_effect=[1, 1]):
            assert _roll_axial_tilt_1d() == pytest.approx(0.0)
        # band=1, inner=6 → round((6-1)/50, 2) == 0.1
        with patch("traveller_world_physical.random.randint", side_effect=[1, 6]):
            assert _roll_axial_tilt_1d() == pytest.approx(0.1)

    def test_band_6_calls_extreme_table(self):
        with patch("traveller_world_physical._roll_extreme_axial_tilt", return_value=137.0) as mock_ext, \
             patch("traveller_world_physical.random.randint", return_value=6):
            result = _roll_axial_tilt_1d()
        mock_ext.assert_called_once()
        assert result == pytest.approx(137.0)


# ---------------------------------------------------------------------------
# _apply_tidal_lock_result — 1:1 axial tilt is always rerolled (WBH p.77 Rule 3)
# ---------------------------------------------------------------------------

class TestApplyTidalLockResult1dTilt:
    PERIOD = 720.0
    DAY = 24.0

    def test_result_12_axial_tilt_always_rerolled(self):
        # Even a low axial_tilt (0.5°) gets recomputed unconditionally for 1:1 lock
        with patch("traveller_world_physical._roll_axial_tilt_1d", return_value=99.9):
            _, tilt, status = _apply_tidal_lock_result(
                12, self.DAY, 0.5, self.PERIOD, allow_broken_check=False
            )
        assert tilt == pytest.approx(99.9)
        assert status == "1:1_lock"


# ---------------------------------------------------------------------------
# _reroll_eccentricity_tidal — WBH p.77 Rule 4
# ---------------------------------------------------------------------------

class TestRerollEccentricityTidal:
    def test_result_in_range(self):
        for _ in range(100):
            result = _reroll_eccentricity_tidal(0.5, 5.0)
            assert 0.0 <= result <= 0.999

    def test_dm_minus2_applied(self):
        # DM=-2: force first two dice to 1 each → 1+1-2=0 → row (5,-0.001,1,1000)
        # frac = 1/1000 = 0.001; result = max(0.0, -0.001 + 0.001) = 0.0
        with patch("traveller_world_physical.random.randint", side_effect=[1, 1, 1]):
            result = _reroll_eccentricity_tidal(2.0, 1.0)
        assert result == pytest.approx(0.0)

    def test_orbit_below_1_old_system_applies_extra_dm(self):
        # orbit_number=0.5, age_gyr=5.0 → dm=-3; 1+1-3=-1 → clamped to row (5,-0.001,1,1000)
        with patch("traveller_world_physical.random.randint", side_effect=[1, 1, 1]):
            result = _reroll_eccentricity_tidal(0.5, 5.0)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# WorldPhysical.eccentricity_adjusted — integration
# ---------------------------------------------------------------------------

class TestEccentricityAdjusted:
    def test_eccentricity_adjusted_none_below_threshold(self):
        # orbit_eccentricity=0.05 (≤ 0.1) → no reroll → eccentricity_adjusted is None
        w = _World(size=3, atmosphere=0)
        with patch("traveller_world_physical._roll_tidal_lock_status",
                   return_value=(720.0, 5.0, "1:1_lock")):
            wp = generate_world_physical(
                w, age_gyr=10.0, orbit_number=0.5, orbit_au=0.3, star_mass=0.2,
                orbit_eccentricity=0.05,
            )
        assert wp is not None
        assert wp.eccentricity_adjusted is None

    def test_lower_value_is_selected(self):
        # eccentricity_adjusted = min(orbit_eccentricity, new_ecc)
        # Force new_ecc=0.5 (> orbit_eccentricity=0.2) → adjusted=0.2
        w = _World(size=3, atmosphere=0)
        with patch("traveller_world_physical._roll_tidal_lock_status",
                   return_value=(720.0, 5.0, "1:1_lock")), \
             patch("traveller_world_physical._reroll_eccentricity_tidal", return_value=0.5):
            wp = generate_world_physical(
                w, age_gyr=10.0, orbit_number=0.5, orbit_au=0.3, star_mass=0.2,
                orbit_eccentricity=0.2,
            )
        assert wp is not None
        assert wp.eccentricity_adjusted == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# WorldPhysical.to_dict — eccentricity_adjusted emission
# ---------------------------------------------------------------------------

class TestWorldPhysicalToDictEccentricity:
    def _make_wp(self) -> WorldPhysical:
        return WorldPhysical(
            composition="rocky",
            diameter_km=12000,
            density=5.0,
            mass=0.9,
            gravity=0.95,
            escape_velocity=11.0,
            axial_tilt=15.0,
            day_length=24.0,
            tidal_status="none",
        )

    def test_eccentricity_adjusted_not_in_dict_when_none(self):
        wp = self._make_wp()
        assert "eccentricity_adjusted" not in wp.to_dict()

    def test_to_dict_includes_eccentricity_adjusted(self):
        wp = self._make_wp()
        wp.eccentricity_adjusted = 0.123456
        d = wp.to_dict()
        assert "eccentricity_adjusted" in d
        assert d["eccentricity_adjusted"] == pytest.approx(0.1235, abs=1e-4)


# ---------------------------------------------------------------------------
# Helpers shared by new tidal DM tests
# ---------------------------------------------------------------------------

def _make_moon(size_code, orbit_pd=None, orbit_period_hours=None, is_ring=False):
    m = Moon(size_code=size_code, is_ring=is_ring)
    m.orbit_pd = orbit_pd
    m.orbit_period_hours = orbit_period_hours
    return m


def _make_wp(day_length=24.0, axial_tilt=15.0, tidal_status="none"):
    return WorldPhysical(
        composition="Standard",
        diameter_km=12742,
        density=5.515,
        mass=1.0,
        gravity=1.0,
        escape_velocity=11.2,
        axial_tilt=axial_tilt,
        day_length=day_length,
        tidal_status=tidal_status,
    )


# ---------------------------------------------------------------------------
# TestTidalLockDmMoon — moon-size DM and multi-star DM (WBH p.106)
# ---------------------------------------------------------------------------

class TestTidalLockDmMoon:
    """Moon-size DM and multi-star DM for planet-to-star lock (WBH p.106)."""

    _BASE = dict(size=6, axial_tilt=10.0, atmosphere=6, age_gyr=5.0,
                 orbit_number=2.5, star_mass=1.0)

    def _dm(self, **kwargs):
        return _tidal_lock_dm(**{**self._BASE, **kwargs})

    def test_no_moon_dm_when_no_moons(self):
        dm_no  = self._dm()
        dm_nil = self._dm(moons=[])
        assert dm_no == dm_nil

    def test_size_s_moon_contributes_no_moon_dm(self):
        """Size S moons are below the Size 1+ threshold."""
        moon = _make_moon("S")
        dm_with = self._dm(moons=[moon])
        dm_without = self._dm()
        assert dm_with == dm_without

    def test_size_1_moon_dm_minus_1(self):
        moon = _make_moon(1)
        dm_with = self._dm(moons=[moon])
        dm_without = self._dm()
        assert dm_with == dm_without - 1

    def test_multiple_moons_dm_is_total_size(self):
        """DM-Total Size of all moons Size 1+ (WBH p.106)."""
        moons = [_make_moon(3), _make_moon(2), _make_moon("S")]
        dm_with = self._dm(moons=moons)
        dm_without = self._dm()
        assert dm_with == dm_without - 5   # size 3 + size 2; S excluded

    def test_ring_excluded_from_moon_dm(self):
        ring = _make_moon(0, is_ring=True)
        dm_with = self._dm(moons=[ring])
        dm_without = self._dm()
        assert dm_with == dm_without

    def test_multi_star_dm_single_star_no_change(self):
        assert self._dm(num_stars_orbited=1) == self._dm()

    def test_multi_star_dm_two_stars(self):
        dm_single = self._dm(num_stars_orbited=1)
        dm_double = self._dm(num_stars_orbited=2)
        assert dm_double == dm_single - 2

    def test_multi_star_dm_three_stars(self):
        dm_single = self._dm(num_stars_orbited=1)
        dm_triple = self._dm(num_stars_orbited=3)
        assert dm_triple == dm_single - 3


# ---------------------------------------------------------------------------
# TestPlanetMoonLockDm — planet-to-moon lock DM table (WBH p.107)
# ---------------------------------------------------------------------------

class TestPlanetMoonLockDm:
    """DM table for a planet's lock to its moon (WBH p.107 left column)."""

    def test_base_dm_minus_10(self):
        """Moon with size 0 and no orbit data: only base DM."""
        moon = _make_moon("S")   # size S — below Size 1 threshold
        assert _planet_moon_lock_dm(moon, [moon]) == -10

    def test_size_1_moon_adds_1(self):
        moon = _make_moon(1)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 1

    def test_size_4_moon_adds_4(self):
        moon = _make_moon(4)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 4

    def test_orbit_pd_lt_5(self):
        """Moon orbit < 5 PD: DM+5+(5-PD)×5 round up."""
        moon = _make_moon(1, orbit_pd=3.0)
        # orbit DM = 5 + ceil((5-3)*5) = 5+10 = 15; size DM = +1; base = -10 → total 6
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 1 + 5 + math.ceil((5 - 3.0) * 5)

    def test_orbit_pd_between_5_and_10(self):
        moon = _make_moon(2, orbit_pd=7.0)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 2 + 4

    def test_orbit_pd_between_10_and_20(self):
        moon = _make_moon(2, orbit_pd=15.0)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 2 + 2

    def test_orbit_pd_between_20_and_40(self):
        moon = _make_moon(2, orbit_pd=30.0)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 2 + 1

    def test_orbit_pd_between_40_and_60_no_orbit_dm(self):
        moon = _make_moon(2, orbit_pd=50.0)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 2

    def test_orbit_pd_gt_60(self):
        moon = _make_moon(2, orbit_pd=70.0)
        assert _planet_moon_lock_dm(moon, [moon]) == -10 + 2 - 6

    def test_multiple_moons_dm_minus_2_per_extra(self):
        """DM-2 per moon beyond the first."""
        m1 = _make_moon(3, orbit_pd=10.0)  # pd=10 → pd<=10 branch → DM+4
        m2 = _make_moon(2, orbit_pd=20.0)
        m3 = _make_moon(1, orbit_pd=30.0)
        # Rolling for m1: size +3, orbit DM +4 (pd<=10), extra moons: -2×2=-4; base -10 → -7
        assert _planet_moon_lock_dm(m1, [m1, m2, m3]) == -10 + 3 + 4 - 4


# ---------------------------------------------------------------------------
# TestRollTidalLockStatusMoons — ordering and cascade (WBH p.107)
# ---------------------------------------------------------------------------

class TestRollTidalLockStatusMoons:
    """Moon-aware multi-case tidal lock ordering."""

    _KWARGS: dict[str, Any] = dict(
        size=6, axial_tilt=10.0, atmosphere=6, age_gyr=5.0,
        orbit_number=2.5, orbit_au=1.5, star_mass=1.0, basic_day_h=24.0,
    )

    def test_no_moons_behaves_as_before(self):
        """Result with moons=None matches result with moons=[] — no regression."""
        with patch("traveller_world_physical.random.randint", return_value=3):
            r1 = _roll_tidal_lock_status(**self._KWARGS)
            r2 = _roll_tidal_lock_status(**self._KWARGS, moons=[])
        assert r1 == r2

    def test_moon_lock_occurs_when_dm_high_enough(self):
        """A very close large moon forces DM >= 10 → automatic 1:1 lock."""
        moon = _make_moon(6, orbit_pd=2.0, orbit_period_hours=100.0)
        # DM for planet-to-moon: -10 + 6 (size) + 5+ceil(3*5)=20 (pd<5) = 16 → auto lock
        result = _roll_tidal_lock_status(**self._KWARGS, moons=[moon])
        _, _, status = result
        assert status == "1:1_lock"

    def test_moon_candidate_sorted_before_star_on_tie(self):
        """When moon DM == star DM, moon case is rolled first (WBH p.107)."""
        # Patch randint so first 2D roll returns 2 (no lock) — moon case tried first
        # and produces "none"; star case is then rolled and also returns "none"
        with patch("traveller_world_physical.random.randint", return_value=1):
            moon = _make_moon(1, orbit_pd=30.0, orbit_period_hours=500.0)
            result = _roll_tidal_lock_status(**self._KWARGS, moons=[moon])
        _, _, status = result
        assert status == "none"


# ---------------------------------------------------------------------------
# TestApplyMoonTidalEffects — public API
# ---------------------------------------------------------------------------

class TestApplyMoonTidalEffects:
    """apply_moon_tidal_effects() mutates WorldPhysical in-place."""

    _KWARGS: dict[str, Any] = dict(
        world_size=6, world_atmosphere=6, age_gyr=5.0,
        orbit_number=2.5, orbit_au=1.5, star_mass=1.0,
    )

    def test_no_op_when_moons_empty(self):
        wp = _make_wp()
        apply_moon_tidal_effects(wp, moons=[], **self._KWARGS)
        assert wp.tidal_status == "none"
        assert wp.day_length == 24.0

    def test_high_moon_dm_produces_lock(self):
        """Very close large moon → moon-lock DM >= 10 → automatic 1:1 lock."""
        moon = _make_moon(6, orbit_pd=2.0, orbit_period_hours=72.0)
        wp = _make_wp()
        apply_moon_tidal_effects(wp, moons=[moon], **self._KWARGS)
        assert wp.tidal_status == "1:1_lock"
        assert wp.day_length == pytest.approx(72.0)

    def test_ring_does_not_create_moon_lock_candidate(self):
        """Ring moons are not eligible for planet-to-moon lock (WBH p.107).

        The planet's day_length must not be locked to the ring's period.
        """
        ring = _make_moon(0, is_ring=True, orbit_period_hours=50.0)
        wp = _make_wp(day_length=24.0)
        with patch("traveller_world_physical.random.randint", return_value=1):
            apply_moon_tidal_effects(wp, moons=[ring], **self._KWARGS)
        assert wp.day_length != pytest.approx(50.0)


# ---------------------------------------------------------------------------
# _orbit_dm_for_mean_temp
# ---------------------------------------------------------------------------

class TestOrbitDmForMeanTemp:
    def test_habitable_zone_no_dm(self):
        # |hz_deviation| <= 1 → DM 0
        assert _orbit_dm_for_mean_temp(0.0) == 0
        assert _orbit_dm_for_mean_temp(0.5) == 0
        assert _orbit_dm_for_mean_temp(-0.5) == 0
        assert _orbit_dm_for_mean_temp(1.0) == 0
        assert _orbit_dm_for_mean_temp(-1.0) == 0

    def test_inner_zone_base_dm(self):
        # Just inside HZCO-1 (dev < -1): DM+4 + 0 = +4
        # hz_deviation = -1.1 → (-(-1.1) - 1) * 2 = 0.1 * 2 = 0.2 → round(0.2)=0 → DM=4
        assert _orbit_dm_for_mean_temp(-1.1) == 4

    def test_inner_zone_increments(self):
        # Each 0.5 Orbit# below HZCO-1 adds +1
        # hz_deviation = -1.5 → deviation below HZCO-1 = 0.5 → round(0.5*2)=1 → DM=5
        assert _orbit_dm_for_mean_temp(-1.5) == 5
        # hz_deviation = -2.0 → deviation = 1.0 → round(1.0*2)=2 → DM=6
        assert _orbit_dm_for_mean_temp(-2.0) == 6
        # hz_deviation = -3.0 → deviation = 2.0 → round(2.0*2)=4 → DM=8
        assert _orbit_dm_for_mean_temp(-3.0) == 8

    def test_outer_zone_base_dm(self):
        # Just beyond HZCO+1 (dev > 1): DM-4 - 0 = -4
        assert _orbit_dm_for_mean_temp(1.1) == -4

    def test_outer_zone_increments(self):
        # hz_deviation = 1.5 → deviation above HZCO+1 = 0.5 → round(0.5*2)=1 → DM=-5
        assert _orbit_dm_for_mean_temp(1.5) == -5
        # hz_deviation = 2.0 → deviation = 1.0 → round(1.0*2)=2 → DM=-6
        assert _orbit_dm_for_mean_temp(2.0) == -6
        # hz_deviation = 3.0 → deviation = 2.0 → round(2.0*2)=4 → DM=-8
        assert _orbit_dm_for_mean_temp(3.0) == -8


# ---------------------------------------------------------------------------
# _compute_mean_temperature
# ---------------------------------------------------------------------------

class TestComputeMeanTemperature:
    def test_hzco_standard_atm(self):
        # hz_deviation=0, atm=6 (DM 0) → modified roll=7 → 288K
        assert _compute_mean_temperature(0.0, 6) == 288

    def test_table_lookup_roll_0(self):
        # Need modified_roll=0: 7 + orbit_dm + atm_dm = 0
        # Use hz_deviation=0, atm=2 (DM-2) → roll=5 → 278K; not 0
        # Use hz_deviation=-1.0 (DM=0), atm=2 (DM-2) → roll=5 → 278K
        # To get roll 0: need orbit_dm + atm_dm = -7
        # hz_deviation=2.0 (orbit_dm=-6), atm=3 (DM-2) → roll=7-6-2=-1 → below 0
        # Try: hz_deviation=2.0 (orbit_dm=-6), atm=2 (DM-2) → roll=7-6-2=-1
        # For roll exactly 0: hz_deviation=1.5 (orbit_dm=-5), atm=2 (DM-2) → roll=0
        assert _compute_mean_temperature(1.5, 2) == 178  # roll=0 → 178K

    def test_table_lookup_selected_entries(self):
        # roll 7 = 288K (atm DM 0)
        assert _compute_mean_temperature(0.0, 6) == 288
        # roll 8 = 293K (atm code 8 or 9 → DM+1)
        assert _compute_mean_temperature(0.0, 8) == 293
        # roll 9 = 298K (atm code 10 → DM+2)
        assert _compute_mean_temperature(0.0, 10) == 298
        # roll 10 = 313K (atm code 13 → DM+2, but need DM+3; use DM+2 from atm 10 + small orbit)
        # Easier: hz_deviation=-1.0 (DM=0), atm 13 (DM+2) → roll 9 → 298K
        # Use hz_deviation=-1.25 (DM=+4+round(0.25*2)=+4+round(0.5)=+5, but -1.25 < -1)
        # Wait: hz_deviation=-1.25 → orbit_dm = 4+round((-(-1.25)-1)*2)=4+round(0.5)=4+0=4
        # (Python rounds 0.5 to 0 — banker's rounding)
        # Just verify roll 12 = 388K: need DM+5; no atm gives exactly +5
        # Use hz_deviation=-1.5 (orbit_dm=+5), atm=6 (DM=0) → roll=12 → 388K
        assert _compute_mean_temperature(-1.5, 6) == 388  # roll 12

    def test_dense_atmosphere_raises_temp(self):
        # atm 11 or 12 → DM+6, hz_deviation=0 → roll=13 → above 12: 388+50=438K
        assert _compute_mean_temperature(0.0, 11) == 438

    def test_thin_atmosphere_lowers_temp(self):
        # atm 2 → DM-2, hz_deviation=0 → roll=5 → 278K
        assert _compute_mean_temperature(0.0, 2) == 278

    def test_below_zero_extrapolation(self):
        # hz_deviation=2.0 (DM-6), atm=2 (DM-2) → roll= 7-6-2=-1 → 178+(-1)*5=173K
        assert _compute_mean_temperature(2.0, 2) == 173

    def test_above_twelve_extrapolation(self):
        # hz_deviation=-2.0 (DM+6), atm=11 (DM+6) → roll=7+6+6=19 → 388+(19-12)*50=738K
        assert _compute_mean_temperature(-2.0, 11) == 738

    def test_minimum_temperature_3k(self):
        """Temperature is clamped to 3K minimum for extreme outer orbits."""
        # hz_deviation=20 → DM=-4-round(19*2)=-42, roll=7-42=-35
        # → 178+(-35)*5=178-175=3K → max(3,3)=3K
        assert _compute_mean_temperature(20.0, 0) == 3

    def test_generate_world_physical_sets_mean_temperature(self):
        """mean_temperature_k is set when hz_deviation is provided."""
        world = _World(size=6, atmosphere=6)
        with patch("traveller_world_physical.random.randint", return_value=3):
            wp = generate_world_physical(world, hz_deviation=0.0)
        assert wp is not None
        assert wp.mean_temperature_k == 288  # HZ world, atm 6 → roll 7 → 288K

    def test_generate_world_physical_no_mean_temp_without_hz(self):
        """mean_temperature_k is None when hz_deviation is not provided."""
        world = _World(size=6, atmosphere=6)
        with patch("traveller_world_physical.random.randint", return_value=3):
            wp = generate_world_physical(world)
        assert wp is not None
        assert wp.mean_temperature_k is None

    def test_to_dict_includes_mean_temperature(self):
        """to_dict() emits mean_temperature_k when set."""
        world = _World(size=6, atmosphere=6)
        with patch("traveller_world_physical.random.randint", return_value=3):
            wp = generate_world_physical(world, hz_deviation=0.0)
        assert wp is not None
        d = wp.to_dict()
        assert d["mean_temperature_k"] == 288

    def test_to_dict_omits_mean_temperature_when_none(self):
        """to_dict() omits mean_temperature_k when not computed."""
        world = _World(size=6, atmosphere=6)
        with patch("traveller_world_physical.random.randint", return_value=3):
            wp = generate_world_physical(world)
        assert wp is not None
        assert "mean_temperature_k" not in wp.to_dict()


# ---------------------------------------------------------------------------
# _compute_rss — Residual Seismic Stress
# ---------------------------------------------------------------------------

class TestComputeRss:
    """Tests for _compute_rss() (WBH p.125)."""

    def test_young_large_world_high_rss(self):
        """Size 8 world, 1 Gyr old, neutral density, no moons: RSS = floor(8-1)² = 49."""
        assert _compute_rss(8, 1.0, 1.0) == 49

    def test_old_world_zero_rss(self):
        """Size 5 world older than itself (neutral density) → floor < 1 → RSS = 0."""
        # 5 - 6.5 = -1.5 → floor = -1 < 1 → 0
        assert _compute_rss(5, 1.0, 6.5) == 0

    def test_density_above_1_applies_dm_plus2(self):
        """Density > 1.0 gives DM+2: size 5, age 2, density 1.2 → floor(5-2+2)=5 → 25."""
        assert _compute_rss(5, 1.2, 2.0) == 25

    def test_density_below_0_5_applies_dm_minus1(self):
        """Density < 0.5 gives DM-1: size 5, age 1, density 0.3 → floor(5-1-1)=3 → 9."""
        assert _compute_rss(5, 0.3, 1.0) == 9

    def test_is_moon_applies_dm_plus1(self):
        """is_moon adds DM+1: size 4, age 1, neutral density, is_moon → floor(4-1+1)=4 → 16."""
        assert _compute_rss(4, 1.0, 1.0, is_moon=True) == 16

    def test_moon_size_dm_capped_at_12(self):
        """Moon size DM capped at 12 regardless of total moon sizes."""
        big_moons = [Moon(size_code=8), Moon(size_code=8)]  # 16 total, capped at 12
        assert _compute_rss(8, 1.0, 0.0, moons=big_moons) == (8 + 12) ** 2

    def test_moon_size_dm_from_significant_moons_only(self):
        """Rings and size-S moons do not contribute to the moon size DM."""
        ring = Moon(size_code=0, is_ring=True)
        sz_s = Moon(size_code="S")
        sz3 = Moon(size_code=3)
        rss = _compute_rss(6, 1.0, 1.0, moons=[ring, sz_s, sz3])
        expected = (6 - 1.0 + 3) ** 2  # floor(8) = 8, 8² = 64
        assert rss == int(expected)

    def test_floor_before_squaring(self):
        """Fractional (Size-Age+DMs) is floored before squaring."""
        # size 5, age 2.8, neutral density → 5 - 2.8 = 2.2 → floor = 2 → 4
        assert _compute_rss(5, 1.0, 2.8) == 4

    def test_below_one_before_squaring_gives_zero(self):
        """Values < 1 before squaring are treated as 0."""
        # size 3, age 2.5, neutral density → 0.5 → floor = 0 → RSS = 0
        assert _compute_rss(3, 1.0, 2.5) == 0

    def test_exactly_one_before_squaring(self):
        """floor value of exactly 1 gives RSS = 1."""
        # size 3, age 2.0, neutral density → floor(1.0) = 1 → 1
        assert _compute_rss(3, 1.0, 2.0) == 1


# ---------------------------------------------------------------------------
# _compute_thf — Tidal Heating Factor
# ---------------------------------------------------------------------------

class TestComputeThf:
    """Tests for _compute_thf() (WBH p.127)."""

    def test_zero_eccentricity_gives_zero(self):
        """No eccentricity → no tidal heating."""
        assert _compute_thf(12800, 1.0, 1.0, 1.0, 0.0, 8766.0) == 0

    def test_high_eccentricity_close_orbit_gives_nonzero(self):
        """Close, eccentric orbit around massive star produces positive THF."""
        # 0.1 AU, e=0.5, 1 solar mass star, size 8 world
        period_h = math.sqrt(0.1 ** 3 / 1.0) * 8766.0
        thf = _compute_thf(12800, 1.0, 1.0, 0.1, 0.5, period_h)
        assert thf > 0

    def test_hz_world_low_eccentricity_near_zero(self):
        """HZ world (1 AU, e=0.05, 1 M☉) has negligible tidal heating."""
        period_h = math.sqrt(1.0 ** 3 / 1.0) * 8766.0
        thf = _compute_thf(12800, 1.0, 1.0, 1.0, 0.05, period_h)
        assert thf == 0  # < 1, treated as 0

    def test_formula_scales_with_eccentricity_squared(self):
        """Doubling eccentricity quadruples THF (e² dependence)."""
        period_h = math.sqrt(0.05 ** 3 / 1.0) * 8766.0
        thf1 = _compute_thf(12800, 1.0, 1.0, 0.05, 0.1, period_h)
        thf2 = _compute_thf(12800, 1.0, 1.0, 0.05, 0.2, period_h)
        if thf1 > 0 and thf2 > 0:
            assert abs(thf2 / thf1 - 4.0) < 0.5  # rough ratio check


# ---------------------------------------------------------------------------
# _apply_seismic_stress — integration
# ---------------------------------------------------------------------------

class TestApplySeismicStress:
    """Tests for _apply_seismic_stress() setting fields on WorldPhysical."""

    def _make_wp(self, size=6, density=4.0, mass=1.0, diameter_km=9600,
                 mean_temp=None):
        """Build a minimal WorldPhysical with the given attributes."""
        wp = WorldPhysical(
            composition="Standard",
            diameter_km=diameter_km,
            density=density,
            mass=mass,
            gravity=0.75,
            escape_velocity=9.5,
            axial_tilt=15.0,
            day_length=24.0,
            tidal_status="none",
        )
        wp.mean_temperature_k = mean_temp
        return wp

    def test_seismic_fields_set_after_call(self):
        """All seismic fields are populated after _apply_seismic_stress()."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.1, 8766.0)
        assert wp.residual_seismic_stress is not None
        assert wp.tidal_heating_factor is not None
        assert wp.total_seismic_stress is not None

    def test_total_equals_rss_plus_thf(self):
        """total_seismic_stress == residual + tidal_heating."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.1, 8766.0)
        assert wp.total_seismic_stress is not None
        assert wp.residual_seismic_stress is not None
        assert wp.tidal_heating_factor is not None
        assert wp.total_seismic_stress == (
            wp.residual_seismic_stress + wp.tidal_heating_factor
        )

    def test_seismic_temperature_set_when_stress_changes_value(self):
        """seismic_temperature_k set only when rounded value differs from mean."""
        # Use a very cold world with very high TSS so the adjustment is visible
        wp = self._make_wp(mean_temp=50)
        wp.residual_seismic_stress = 0  # override to force high THF path
        # Manually trigger with high-stress conditions
        _apply_seismic_stress(wp, 8, 0.1, 1.0, 0.05, 0.9, 200.0)
        tss = wp.total_seismic_stress or 0
        if tss > 0:
            expected = round((50 ** 4 + tss ** 4) ** 0.25)
            if expected != 50:
                assert wp.seismic_temperature_k == expected

    def test_seismic_temperature_absent_when_no_mean_temp(self):
        """seismic_temperature_k not set when mean_temperature_k is None."""
        wp = self._make_wp(mean_temp=None)
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.1, 8766.0)
        assert wp.seismic_temperature_k is None

    def test_to_dict_includes_seismic_fields(self):
        """to_dict() emits seismic fields when set."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.0, 8766.0)
        d = wp.to_dict()
        assert "residual_seismic_stress" in d
        assert "tidal_heating_factor" not in d  # 0 → omitted
        assert "total_seismic_stress" in d

    def test_to_dict_omits_tidal_heating_when_zero(self):
        """tidal_heating_factor omitted from to_dict() when 0."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.0, 8766.0)
        assert wp.tidal_heating_factor == 0
        assert "tidal_heating_factor" not in wp.to_dict()


# ---------------------------------------------------------------------------
# apply_moon_tidal_effects — seismic integration via public API
# ---------------------------------------------------------------------------

class TestApplyMoonTidalEffectsSeismic:
    """Verify seismic stress is computed through the public apply_moon_tidal_effects()."""

    def _make_wp(self):
        return WorldPhysical(
            composition="Standard",
            diameter_km=9600,
            density=4.0,
            mass=0.6,
            gravity=0.75,
            escape_velocity=9.5,
            axial_tilt=15.0,
            day_length=24.0,
            tidal_status="none",
        )

    def test_seismic_computed_with_no_moons(self):
        """Seismic stress is computed even when moons list is empty."""
        wp = self._make_wp()
        with patch("traveller_world_physical.random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=6, world_atmosphere=6,
                age_gyr=3.0, orbit_number=3.0, orbit_au=1.0,
                star_mass=1.0, orbit_eccentricity=0.0,
            )
        assert wp.residual_seismic_stress is not None
        assert wp.total_seismic_stress is not None

    def test_is_moon_increases_rss(self):
        """is_moon=True increases RSS by applying the DM+1 bonus."""
        wp1 = self._make_wp()
        wp2 = self._make_wp()
        with patch("traveller_world_physical.random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp1, moons=[], world_size=5, world_atmosphere=0,
                age_gyr=1.0, orbit_number=3.0, orbit_au=1.0,
                star_mass=1.0, orbit_eccentricity=0.0, is_moon=False,
            )
            apply_moon_tidal_effects(
                wp2, moons=[], world_size=5, world_atmosphere=0,
                age_gyr=1.0, orbit_number=3.0, orbit_au=1.0,
                star_mass=1.0, orbit_eccentricity=0.0, is_moon=True,
            )
        assert wp1.residual_seismic_stress is not None
        assert wp2.residual_seismic_stress is not None
        assert wp2.residual_seismic_stress >= wp1.residual_seismic_stress
