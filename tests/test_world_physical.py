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

from tables import TIDAL_STATUS_LABELS
from traveller_world_physical import (
    WorldPhysical,
    RunawayGreenhouseResult,
    _apply_seismic_stress,
    _compute_stellar_day,
    _apply_tidal_lock_result,
    _axial_tilt_factor,
    _compute_mean_temperature,
    _compute_rss,
    _compute_tidal_ss,
    _compute_tidal_amplitude,
    _geographic_factor,
    _moon_mass_earth,
    _moon_tidal_effect_m,
    _orbital_period_hours,
    _orbit_dm_for_mean_temp,
    _planet_moon_lock_dm,
    _reroll_eccentricity_tidal,
    _roll_albedo,
    _roll_axial_tilt_1d,
    _roll_greenhouse_factor,
    _roll_tidal_lock_status,
    _rotation_factor,
    _star_tidal_effect_m,
    _tidal_lock_dm,
    apply_moon_tidal_effects,
    apply_biological_resource_dms,
    check_runaway_greenhouse,
    generate_advanced_mean_temperature,
    generate_world_physical,
    _density_resource_dm,
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
        """A very close large moon forces DM >= 10 → automatic 1:1 lock.

        Patch randint=1 so the broken-lock check (2D=2, not 12) never fires.
        """
        moon = _make_moon(6, orbit_pd=2.0, orbit_period_hours=100.0)
        # DM for planet-to-moon: -10 + 6 (size) + 5+ceil(3*5)=20 (pd<5) = 16 → auto lock
        with patch("traveller_world_physical.random.randint", return_value=1):
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

    def test_below_10k_triggers_1d5_roll(self):
        """When extrapolated result < 10K (modified roll ≤ -34), returns 1D+5."""
        # hz_deviation=20 → orbit_dm=-42, roll=7-42=-35 → T=178+(-35)*5=3K < 10K
        with patch("traveller_world_physical.random.randint", return_value=4) as mock_roll:
            result = _compute_mean_temperature(20.0, 0)
        mock_roll.assert_called_once_with(1, 6)
        assert result == 9  # 4 + 5

    def test_1d5_result_range(self):
        """1D+5 produces values 6–11K for die results 1–6."""
        for die in range(1, 7):
            with patch("traveller_world_physical.random.randint", return_value=die):
                result = _compute_mean_temperature(20.0, 0)
            assert result == die + 5

    def test_threshold_roll_minus33_uses_extrapolation(self):
        """Modified roll of -33 gives 13K via extrapolation, not 1D+5."""
        # Need orbit_dm + atm_dm = -40 so that 7 + (-40) = -33
        # hz_deviation=21 → orbit_dm = -4 - round(20*2) = -44
        # atm=10 → DM+2 → modified_roll = 7 - 44 + 2 = -35 (too low)
        # hz_deviation=19 → orbit_dm = -4 - round(18*2) = -40
        # atm=0 → DM=0 → modified_roll = 7 - 40 = -33 → T = 178 + (-33)*5 = 13K
        with patch("traveller_world_physical.random.randint") as mock_roll:
            result = _compute_mean_temperature(19.0, 0)
        mock_roll.assert_not_called()
        assert result == 13  # 178 + (-33)*5 = 13K, no 1D+5

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
# _compute_tidal_ss — Tidal Seismic Stress
# ---------------------------------------------------------------------------

class TestComputeTidalSS:
    """Tests for _compute_tidal_ss() (WBH p.127)."""

    def test_zero_eccentricity_gives_zero(self):
        """No eccentricity → no tidal seismic stress."""
        assert _compute_tidal_ss(12800, 1.0, 1.0, 1.0, 0.0, 8766.0) == 0

    def test_high_eccentricity_close_orbit_gives_nonzero(self):
        """Close, eccentric orbit around massive star produces positive tidal SS."""
        # 0.1 AU, e=0.5, 1 solar mass star, size 8 world
        period_h = math.sqrt(0.1 ** 3 / 1.0) * 8766.0
        tss = _compute_tidal_ss(12800, 1.0, 1.0, 0.1, 0.5, period_h)
        assert tss > 0

    def test_hz_world_low_eccentricity_near_zero(self):
        """HZ world (1 AU, e=0.05, 1 M☉) has negligible tidal seismic stress."""
        period_h = math.sqrt(1.0 ** 3 / 1.0) * 8766.0
        tss = _compute_tidal_ss(12800, 1.0, 1.0, 1.0, 0.05, period_h)
        assert tss == 0  # < 1, treated as 0

    def test_formula_scales_with_eccentricity_squared(self):
        """Doubling eccentricity quadruples tidal SS (e² dependence)."""
        period_h = math.sqrt(0.05 ** 3 / 1.0) * 8766.0
        tss1 = _compute_tidal_ss(12800, 1.0, 1.0, 0.05, 0.1, period_h)
        tss2 = _compute_tidal_ss(12800, 1.0, 1.0, 0.05, 0.2, period_h)
        if tss1 > 0 and tss2 > 0:
            assert abs(tss2 / tss1 - 4.0) < 0.5  # rough ratio check


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
        assert wp.tidal_seismic_stress is not None
        assert wp.total_seismic_stress is not None

    def test_total_equals_rss_plus_tidal_ss(self):
        """total_seismic_stress == residual + tidal_seismic_stress."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.1, 8766.0)
        assert wp.total_seismic_stress is not None
        assert wp.residual_seismic_stress is not None
        assert wp.tidal_seismic_stress is not None
        assert wp.total_seismic_stress == (
            wp.residual_seismic_stress + wp.tidal_seismic_stress
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
        assert "tidal_seismic_stress" not in d  # 0 → omitted
        assert "total_seismic_stress" in d

    def test_to_dict_omits_tidal_ss_when_zero(self):
        """tidal_seismic_stress omitted from to_dict() when 0."""
        wp = self._make_wp()
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.0, 8766.0)
        assert wp.tidal_seismic_stress == 0
        assert "tidal_seismic_stress" not in wp.to_dict()

    def test_advanced_mean_temperature_updated_in_place_by_seismic(self):
        """_apply_seismic_stress() updates advanced_mean_temperature_k in-place
        using ⁴√(T⁴ + TSS⁴) when tss > 0 and the rounded value changes."""
        wp = self._make_wp(mean_temp=50)
        wp.advanced_mean_temperature_k = 50
        _apply_seismic_stress(wp, 8, 0.1, 1.0, 0.05, 0.9, 200.0)
        tss = wp.total_seismic_stress or 0
        if tss > 0:
            expected = max(50, round((50 ** 4 + tss ** 4) ** 0.25))
            assert wp.advanced_mean_temperature_k == expected

    def test_advanced_mean_temperature_unchanged_when_none(self):
        """advanced_mean_temperature_k stays None when not set before seismic stress."""
        wp = self._make_wp(mean_temp=50)
        # advanced_mean_temperature_k left at None (default)
        _apply_seismic_stress(wp, 6, 2.0, 1.0, 1.0, 0.1, 8766.0)
        assert wp.advanced_mean_temperature_k is None

    def test_high_low_temperature_updated_with_advanced_mean(self):
        """high_temperature_k and low_temperature_k are also updated when
        advanced_mean_temperature_k is adjusted for seismic heating."""
        wp = self._make_wp(mean_temp=50)
        wp.advanced_mean_temperature_k = 50
        wp.high_temperature_k = 60
        wp.low_temperature_k = 40
        _apply_seismic_stress(wp, 8, 0.1, 1.0, 0.05, 0.9, 200.0)
        tss = wp.total_seismic_stress or 0
        if tss > 0 and wp.advanced_mean_temperature_k != 50:
            assert wp.high_temperature_k >= 60
            assert wp.low_temperature_k >= 40
            assert wp.high_temperature_k == max(60, round((60 ** 4 + tss ** 4) ** 0.25))
            assert wp.low_temperature_k  == max(40, round((40 ** 4 + tss ** 4) ** 0.25))

    def test_advanced_mean_temperature_roundtrips_from_dict_after_seismic(self):
        """advanced_mean_temperature_k (after seismic adjustment) survives round-trip."""
        wp = self._make_wp(mean_temp=50)
        wp.advanced_mean_temperature_k = 50
        _apply_seismic_stress(wp, 8, 0.1, 1.0, 0.05, 0.9, 200.0)
        d = wp.to_dict()
        wp2 = WorldPhysical.from_dict(d)
        assert wp2.advanced_mean_temperature_k == wp.advanced_mean_temperature_k

    def test_advanced_mean_temperature_no_less_than_original_after_seismic(self):
        """Seismic heating never reduces advanced_mean_temperature_k."""
        original = 50
        wp = self._make_wp(mean_temp=original)
        wp.advanced_mean_temperature_k = original
        _apply_seismic_stress(wp, 8, 0.1, 1.0, 0.05, 0.9, 200.0)
        assert wp.advanced_mean_temperature_k >= original


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


# ---------------------------------------------------------------------------
# Surface Tidal Amplitude (WBH pp.107-108)
# ---------------------------------------------------------------------------

class TestStarTidalEffectM:
    """_star_tidal_effect_m: (star_mass_solar * world_size) / (32 * AU³)"""

    def test_sol_on_terra(self):
        # WBH reference: Sol (1.0 solar) on Terra (size 8) at 1 AU = 0.25 m
        result = _star_tidal_effect_m(1.0, 8, 1.0)
        assert abs(result - 0.25) < 1e-9

    def test_scales_linearly_with_size(self):
        # Size 4 should give exactly half of size 8 at same distance
        effect_8 = _star_tidal_effect_m(1.0, 8, 1.0)
        effect_4 = _star_tidal_effect_m(1.0, 4, 1.0)
        assert abs(effect_4 - effect_8 / 2) < 1e-9

    def test_scales_with_au_cubed(self):
        # Doubling AU reduces effect by factor of 8
        effect_1au = _star_tidal_effect_m(1.0, 8, 1.0)
        effect_2au = _star_tidal_effect_m(1.0, 8, 2.0)
        assert abs(effect_2au - effect_1au / 8) < 1e-9

    def test_world_size_zero_returns_zero(self):
        assert _star_tidal_effect_m(1.0, 0, 1.0) == 0.0

    def test_orbit_au_zero_returns_zero(self):
        assert _star_tidal_effect_m(1.0, 8, 0.0) == 0.0


class TestMoonMassEarth:
    """_moon_mass_earth: (diameter_km / 12742)³ with Terran density assumption."""

    def test_size_s_moon(self):
        moon = _make_moon("S")
        expected = (800.0 / 12742.0) ** 3
        assert abs(_moon_mass_earth(moon) - expected) < 1e-12

    def test_size_2_moon(self):
        moon = _make_moon(2)
        expected = (3200.0 / 12742.0) ** 3
        assert abs(_moon_mass_earth(moon) - expected) < 1e-12

    def test_ring_returns_zero(self):
        moon = _make_moon(0, is_ring=True)
        assert _moon_mass_earth(moon) == 0.0

    def test_size_0_returns_zero(self):
        moon = Moon(size_code=0, is_ring=False)
        assert _moon_mass_earth(moon) == 0.0


class TestMoonTidalEffectM:
    """_moon_tidal_effect_m: (moon_mass * world_size) / (3.2 * (orbit_km/1e6)³)"""

    def test_luna_on_terra(self):
        # Luna: mass 0.0123 ME, orbit 384 400 km, Terra size 8 → ≈ 0.54 m
        moon = _make_moon(2)  # size 2 approximates Luna
        moon.orbit_km = 384_400.0
        # Use actual Luna mass for the reference check
        luna_mass = 0.0123
        dist_mkm = 384_400.0 / 1_000_000.0
        expected = (luna_mass * 8) / (3.2 * dist_mkm ** 3)
        assert abs(expected - 0.54) < 0.01  # sanity-check the reference

    def test_ring_excluded(self):
        moon = _make_moon(0, is_ring=True)
        moon.orbit_km = 100_000.0
        assert _moon_tidal_effect_m(moon, 8) == 0.0

    def test_no_orbit_km_excluded(self):
        moon = _make_moon(3)
        # orbit_km defaults to None via _make_moon without orbit_pd
        assert _moon_tidal_effect_m(moon, 8) == 0.0

    def test_scales_with_world_size(self):
        moon = _make_moon(3)
        moon.orbit_km = 200_000.0
        effect_8 = _moon_tidal_effect_m(moon, 8)
        effect_4 = _moon_tidal_effect_m(moon, 4)
        assert abs(effect_4 - effect_8 / 2) < 1e-10

    def test_scales_with_distance_cubed(self):
        moon = _make_moon(3)
        moon.orbit_km = 100_000.0
        moon2 = _make_moon(3)
        moon2.orbit_km = 200_000.0
        effect_close = _moon_tidal_effect_m(moon, 8)
        effect_far = _moon_tidal_effect_m(moon2, 8)
        assert abs(effect_close / effect_far - 8.0) < 1e-9


class TestComputeTidalAmplitude:
    """_compute_tidal_amplitude: star + moon effects summed."""

    def test_star_only_no_moons(self):
        result = _compute_tidal_amplitude(8, 1.0, 1.0, moons=None)
        assert abs(result - 0.25) < 1e-4

    def test_star_plus_moon(self):
        moon = _make_moon(3)
        moon.orbit_km = 200_000.0
        result = _compute_tidal_amplitude(8, 1.0, 1.0, moons=[moon])
        star_part = _star_tidal_effect_m(1.0, 8, 1.0)
        moon_part = _moon_tidal_effect_m(moon, 8)
        assert abs(result - round(star_part + moon_part, 4)) < 1e-9

    def test_ring_moon_not_counted(self):
        ring = _make_moon(0, is_ring=True)
        ring.orbit_km = 50_000.0
        result_with_ring = _compute_tidal_amplitude(8, 1.0, 1.0, moons=[ring])
        result_no_moons = _compute_tidal_amplitude(8, 1.0, 1.0, moons=None)
        assert abs(result_with_ring - result_no_moons) < 1e-9

    def test_moon_without_orbit_km_not_counted(self):
        moon = _make_moon(4)
        # orbit_km is None (no placement)
        result_with = _compute_tidal_amplitude(8, 1.0, 1.0, moons=[moon])
        result_without = _compute_tidal_amplitude(8, 1.0, 1.0, moons=None)
        assert abs(result_with - result_without) < 1e-9


class TestTidalAmplitudeIntegration:
    """Verify tidal_amplitude_m is set by generate_world_physical and apply_moon_tidal_effects."""

    def test_generate_world_physical_sets_star_amplitude(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        assert wp.tidal_amplitude_m is not None
        assert abs(wp.tidal_amplitude_m - 0.25) < 1e-4

    def test_apply_moon_tidal_effects_updates_amplitude(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        star_only = wp.tidal_amplitude_m

        moon = _make_moon(3)
        moon.orbit_km = 200_000.0
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[moon], world_size=8, world_atmosphere=6,
                age_gyr=5.0, orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp.tidal_amplitude_m is not None
        assert wp.tidal_amplitude_m > star_only

    def test_tidal_amplitude_in_to_dict(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        d = wp.to_dict()
        assert "tidal_amplitude_m" in d
        assert d["tidal_amplitude_m"] == round(wp.tidal_amplitude_m, 4)


class TestTidalStressFactor:
    """tidal_stress_factor = floor(tidal_amplitude_m / 10) (WBH p.126)."""

    def test_tsf_zero_when_amplitude_below_10(self):
        # Sol acting on Terra at 1 AU gives ~0.25 m → TSF = 0
        amp = _compute_tidal_amplitude(8, 1.0, 1.0, moons=None)
        assert math.floor(amp / 10) == 0

    def test_tsf_nonzero_when_amplitude_above_10(self):
        # Close orbit: size-8 world at 0.2 AU around 1 solar-mass star
        # star tidal effect = (1.0 × 8) / (32 × 0.2³) = 8 / 0.256 = 31.25 m → TSF = 3
        amp = _compute_tidal_amplitude(8, 1.0, 0.2, moons=None)
        assert amp > 10.0
        assert math.floor(amp / 10) == 3

    def test_tsf_set_on_worldphysical_after_apply_moon_tidal_effects(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=8, world_atmosphere=6,
                age_gyr=5.0, orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp.tidal_stress_factor is not None
        assert wp.tidal_stress_factor == math.floor(wp.tidal_amplitude_m / 10)

    def test_tsf_included_in_total_seismic_stress(self):
        # Close inner-zone orbit so TSF is non-zero
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=1.0,
                orbit_number=0.5, orbit_au=0.2, star_mass=1.0,
            )
        assert wp is not None
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=8, world_atmosphere=6,
                age_gyr=1.0, orbit_number=0.5, orbit_au=0.2, star_mass=1.0,
            )
        assert wp.tidal_stress_factor is not None
        assert wp.tidal_stress_factor > 0
        expected_total = (
            (wp.residual_seismic_stress or 0)
            + (wp.tidal_seismic_stress or 0)
            + wp.tidal_stress_factor
        )
        assert wp.total_seismic_stress == expected_total

    def test_tsf_in_to_dict_when_nonzero(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=1.0,
                orbit_number=0.5, orbit_au=0.2, star_mass=1.0,
            )
        assert wp is not None
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=8, world_atmosphere=6,
                age_gyr=1.0, orbit_number=0.5, orbit_au=0.2, star_mass=1.0,
            )
        d = wp.to_dict()
        assert wp.tidal_stress_factor is not None
        if wp.tidal_stress_factor > 0:
            assert "tidal_stress_factor" in d
            assert d["tidal_stress_factor"] == wp.tidal_stress_factor

    def test_tsf_absent_from_to_dict_when_zero(self):
        # HZ orbit (1 AU) → TSF = 0 → not emitted
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            wp = generate_world_physical(
                world, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=8, world_atmosphere=6,
                age_gyr=5.0, orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp.tidal_stress_factor == 0
        assert "tidal_stress_factor" not in wp.to_dict()


class TestGGSatelliteTidal:
    """Gas giant primary tidal contribution for mainworld-as-GG-satellite (issue #74)."""

    _ORBIT_AU  = 5.2    # Jupiter-like GG orbit around star
    _STAR_MASS = 1.0
    _AGE       = 1.0
    _ORBIT_NUM = 6.0

    def _make_wp(self):
        with patch("random.randint", return_value=3):
            world = World("Test")
            world.size = 8
            world.atmosphere = 6
            return generate_world_physical(
                world, age_gyr=self._AGE,
                orbit_number=self._ORBIT_NUM, orbit_au=self._ORBIT_AU,
                star_mass=self._STAR_MASS,
            )

    def _apply(self, wp, gg_mass_earth=0.0, gg_satellite_moon=None):
        with patch("random.randint", return_value=3):
            apply_moon_tidal_effects(
                wp, moons=[], world_size=8, world_atmosphere=6,
                age_gyr=self._AGE, orbit_number=self._ORBIT_NUM,
                orbit_au=self._ORBIT_AU, star_mass=self._STAR_MASS,
                gg_mass_earth=gg_mass_earth,
                gg_satellite_moon=gg_satellite_moon,
            )

    def _sat_moon(self, orbit_km, ecc=0.0, period_h=100.0):
        sat = Moon(size_code=5)
        sat.orbit_km = orbit_km
        sat.orbit_eccentricity = ecc
        sat.orbit_period_hours = period_h
        return sat

    def test_gg_tidal_amplitude_increases(self):
        """GG tidal pull raises tidal_amplitude_m even when satellite eccentricity is zero."""
        wp_base = self._make_wp()
        wp_gg   = self._make_wp()
        assert wp_base is not None and wp_gg is not None
        self._apply(wp_base)
        self._apply(wp_gg, gg_mass_earth=81.0,
                    gg_satellite_moon=self._sat_moon(orbit_km=500_000.0, ecc=0.0))
        assert wp_gg.tidal_amplitude_m > wp_base.tidal_amplitude_m
        assert (wp_gg.tidal_stress_factor or 0) >= (wp_base.tidal_stress_factor or 0)

    def test_gg_tidal_ss_unaffected_by_satellite_eccentricity(self):
        """GG satellite eccentricity does not add to tidal seismic stress.

        The _compute_tidal_ss formula is calibrated for star→planet distances and
        produces nonsensical values at moon distances; it is not applied for GG
        parent contributions. The GG tidal effect flows through TSF via amplitude.
        """
        wp_base = self._make_wp()
        wp_gg   = self._make_wp()
        assert wp_base is not None and wp_gg is not None
        self._apply(wp_base)
        self._apply(wp_gg, gg_mass_earth=81.0,
                    gg_satellite_moon=self._sat_moon(orbit_km=500_000.0, ecc=0.3, period_h=48.0))
        assert (wp_gg.tidal_seismic_stress or 0) == (wp_base.tidal_seismic_stress or 0)
        assert (wp_gg.tidal_amplitude_m or 0.0) > (wp_base.tidal_amplitude_m or 0.0)
        assert (wp_gg.total_seismic_stress or 0) > (wp_base.total_seismic_stress or 0)

    def test_gg_zero_mass_is_backward_compatible(self):
        """gg_mass_earth=0 (default) produces identical results to omitting GG params."""
        wp1 = self._make_wp()
        wp2 = self._make_wp()
        assert wp1 is not None and wp2 is not None
        self._apply(wp1)
        self._apply(wp2, gg_mass_earth=0.0, gg_satellite_moon=None)
        assert wp1.tidal_amplitude_m   == wp2.tidal_amplitude_m
        assert wp1.tidal_stress_factor == wp2.tidal_stress_factor
        assert wp1.tidal_seismic_stress == wp2.tidal_seismic_stress
        assert wp1.total_seismic_stress == wp2.total_seismic_stress

    def test_tsf_capped_at_500(self):
        """TSF is capped at 500 regardless of tidal amplitude (liquefaction limit)."""
        wp = self._make_wp()
        assert wp is not None
        # A GG satellite at 50,000 km from an 81 ME giant produces amplitude >> 5,000 m
        self._apply(wp, gg_mass_earth=81.0,
                    gg_satellite_moon=self._sat_moon(orbit_km=50_000.0, ecc=0.0))
        assert wp.tidal_stress_factor is not None
        assert wp.tidal_stress_factor <= 500


# ---------------------------------------------------------------------------
# _roll_albedo
# ---------------------------------------------------------------------------

def _make_wp_stub(density: float = 4.0) -> WorldPhysical:
    """Minimal WorldPhysical stub for advanced temp tests."""
    return WorldPhysical(
        composition="Standard",
        diameter_km=12_742,
        density=density,
        mass=1.0,
        gravity=1.0,
        escape_velocity=11.2,
        axial_tilt=23.5,
        day_length=24.0,
        tidal_status="none",
    )


class TestRollAlbedo:
    """_roll_albedo — deterministic boundaries and clamping."""

    def test_rocky_world_base_min(self):
        # Rocky (density>0.5); 2D-2 min=0 → 0.04+0=0.04; atm 0 no modifier; hydro 0 no modifier
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2×1=2; 2-2=0; base=0.04+0×0.02=0.04; clamp min 0.02 → 0.04
            result = _roll_albedo(atmosphere=0, hydrographics=0, density=4.0, hz_deviation=0.0)
        assert result == pytest.approx(0.04, abs=1e-6)

    def test_rocky_world_base_max_no_modifiers(self):
        # Rocky; 2D-2 max=10; base=0.04+10×0.02=0.24; atm 0; hydro 0
        with patch("traveller_world_physical.random.randint", return_value=6):
            result = _roll_albedo(atmosphere=0, hydrographics=0, density=4.0, hz_deviation=0.0)
        assert result == pytest.approx(0.24, abs=1e-6)

    def test_icy_world_classification(self):
        # density ≤ 0.5, hz_deviation ≤ 2.0 → icy; 2D-3 min=-1 → 0.20-0.05=0.15; clamp 0.02
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2×1=2; 2-3=-1; base=0.20+(-1×0.05)=0.15; atm 0; hydro 0
            result = _roll_albedo(atmosphere=0, hydrographics=0, density=0.4, hz_deviation=1.0)
        assert result == pytest.approx(0.15, abs=1e-6)

    def test_icy_far_world_classification(self):
        # density ≤ 0.5, hz_deviation > 2.0 → icy-far
        # 2D-2 with all-6: 12-2=10; base=0.25+10×0.07=0.95
        with patch("traveller_world_physical.random.randint", return_value=6):
            result = _roll_albedo(atmosphere=0, hydrographics=0, density=0.4, hz_deviation=3.0)
        assert result == pytest.approx(0.95, abs=1e-6)

    def test_albedo_clamped_above_0_98(self):
        # Very high rolls should be clamped to 0.98
        with patch("traveller_world_physical.random.randint", return_value=6):
            # Icy-far base=0.95; atm heavy (2D-2)×0.05=10×0.05=0.50 → 1.45 → clamped 0.98
            result = _roll_albedo(atmosphere=11, hydrographics=0, density=0.4, hz_deviation=3.0)
        assert result == pytest.approx(0.98, abs=1e-6)

    def test_albedo_clamped_below_0_02(self):
        # Very low rolls should produce at least 0.02
        with patch("traveller_world_physical.random.randint", return_value=1):
            # Icy base 0.15; atm thin (2D-3)=-1×0.01=-0.01; hydro 2-5 (2D-2)=0×0.02=0
            # 0.15-0.01=0.14; still above 0.02
            result = _roll_albedo(atmosphere=1, hydrographics=3, density=0.4, hz_deviation=1.0)
        assert result >= 0.02

    def test_mid_atmosphere_adds_positive(self):
        with patch("traveller_world_physical.random.randint", return_value=3):
            base = _roll_albedo(atmosphere=0, hydrographics=0, density=4.0, hz_deviation=0.0)
        with patch("traveller_world_physical.random.randint", return_value=3):
            mid = _roll_albedo(atmosphere=6, hydrographics=0, density=4.0, hz_deviation=0.0)
        assert mid > base

    def test_hydro_6_plus_adds_modifier(self):
        with patch("traveller_world_physical.random.randint", return_value=4):
            no_hydro = _roll_albedo(atmosphere=0, hydrographics=0, density=4.0, hz_deviation=0.0)
        with patch("traveller_world_physical.random.randint", return_value=4):
            high_hydro = _roll_albedo(atmosphere=0, hydrographics=8, density=4.0, hz_deviation=0.0)
        # 2D-4 with die=4: 2×4-4=4; 4×0.03=0.12; so high_hydro should be > no_hydro
        assert high_hydro > no_hydro

    def test_result_in_valid_range(self):
        import random as rng
        rng.seed(42)
        for _ in range(50):
            result = _roll_albedo(6, 5, 3.5, 0.5)
            assert 0.02 <= result <= 0.98


# ---------------------------------------------------------------------------
# _roll_greenhouse_factor
# ---------------------------------------------------------------------------

class TestRollGreenhouseFactor:
    """_roll_greenhouse_factor — vacuum, standard, exotic, extreme."""

    def test_vacuum_returns_zero(self):
        result = _roll_greenhouse_factor(atmosphere=0, pressure_bar=0.0)
        assert result == 0.0

    def test_standard_atm_positive(self):
        # Standard atm 6, pressure 1.0 bar; initial=0.5; 3D min=3 → +0.03; result≥0.53
        with patch("traveller_world_physical.random.randint", return_value=1):
            result = _roll_greenhouse_factor(atmosphere=6, pressure_bar=1.0)
        assert result == pytest.approx(0.5 + 3 * 0.01, abs=1e-6)

    def test_standard_atm_scales_with_pressure(self):
        with patch("traveller_world_physical.random.randint", return_value=3):
            low = _roll_greenhouse_factor(atmosphere=6, pressure_bar=1.0)
            high = _roll_greenhouse_factor(atmosphere=6, pressure_bar=4.0)
        assert high > low

    def test_exotic_atm_multiplier_clamp(self):
        # Atm 10 exotic; 1D=1 → max(0.5, 1-1)=max(0.5, 0)=0.5; initial=0.5×√1=0.5 → 0.5×0.5=0.25
        with patch("traveller_world_physical.random.randint", return_value=1):
            result = _roll_greenhouse_factor(atmosphere=10, pressure_bar=1.0)
        assert result == pytest.approx(0.5 * 0.5, abs=1e-4)

    def test_exotic_atm_higher_die(self):
        # 1D=4 → max(0.5, 4-1)=max(0.5, 3)=3; initial=0.5; result=0.5×3=1.5
        with patch("traveller_world_physical.random.randint", return_value=4):
            result = _roll_greenhouse_factor(atmosphere=10, pressure_bar=1.0)
        assert result == pytest.approx(0.5 * 3.0, abs=1e-4)

    def test_extreme_atm_die_1_to_5(self):
        # Atm 11 extreme; 1D=3 → multiplier=3; initial=0.5; result=0.5×3=1.5
        with patch("traveller_world_physical.random.randint", return_value=3):
            result = _roll_greenhouse_factor(atmosphere=11, pressure_bar=1.0)
        assert result == pytest.approx(0.5 * 3.0, abs=1e-4)

    def test_extreme_atm_die_6_uses_3d(self):
        # 1D=6 → multiplier=3D=3×6=18; initial=0.5; result=0.5×18=9.0
        def _seq_randint(*_args):
            return 6
        with patch("traveller_world_physical.random.randint", side_effect=_seq_randint):
            result = _roll_greenhouse_factor(atmosphere=11, pressure_bar=1.0)
        # 3D with all 6 → 18
        assert result == pytest.approx(0.5 * 18.0, abs=1e-4)

    def test_atm_14_is_standard(self):
        # Atm 14 (Low) is in _ATM_GH_STANDARD
        with patch("traveller_world_physical.random.randint", return_value=2):
            result = _roll_greenhouse_factor(atmosphere=14, pressure_bar=1.0)
        assert result > 0.0
        # Should equal initial + 3D×0.01 = 0.5 + 6×0.01 = 0.56
        assert result == pytest.approx(0.5 + 6 * 0.01, abs=1e-6)

    def test_atm_13_very_dense_standard(self):
        with patch("traveller_world_physical.random.randint", return_value=2):
            result = _roll_greenhouse_factor(atmosphere=13, pressure_bar=10.0)
        # initial = 0.5 × √10 ≈ 1.5811; + 6×0.01 = 1.6411
        assert result == pytest.approx(0.5 * math.sqrt(10.0) + 6 * 0.01, abs=1e-4)


# ---------------------------------------------------------------------------
# generate_advanced_mean_temperature
# ---------------------------------------------------------------------------

class TestGenerateAdvancedMeanTemperature:
    """generate_advanced_mean_temperature — mutation, formula, edge cases."""

    def _run(self, atmosphere=6, hydrographics=5, pressure_bar=1.0,
             luminosity=1.0, orbit_au=1.0, hz_deviation=0.0,
             density=4.0) -> WorldPhysical:
        wp = _make_wp_stub(density=density)
        generate_advanced_mean_temperature(
            wp,
            atmosphere=atmosphere,
            hydrographics=hydrographics,
            pressure_bar=pressure_bar,
            luminosity=luminosity,
            orbit_au=orbit_au,
            hz_deviation=hz_deviation,
        )
        return wp

    def test_sets_all_three_fields(self):
        wp = self._run()
        assert wp.albedo is not None
        assert wp.greenhouse_factor is not None
        assert wp.advanced_mean_temperature_k is not None

    def test_temperature_minimum_3k(self):
        # orbit_au=0 → formula skipped → 3K floor
        wp = _make_wp_stub()
        generate_advanced_mean_temperature(
            wp, atmosphere=0, hydrographics=0,
            pressure_bar=0.0, luminosity=1.0, orbit_au=0.0, hz_deviation=0.0,
        )
        assert wp.advanced_mean_temperature_k == 3

    def test_zero_luminosity_gives_3k(self):
        wp = _make_wp_stub()
        generate_advanced_mean_temperature(
            wp, atmosphere=0, hydrographics=0,
            pressure_bar=0.0, luminosity=0.0, orbit_au=1.0, hz_deviation=0.0,
        )
        assert wp.advanced_mean_temperature_k == 3

    def test_earth_like_approx_288k(self):
        # Earth-like params; albedo~0.3, greenhouse~0.33, L=1, AU=1
        # T = 279 × (1 × 0.7 × 1.33)^0.25 ≈ 279 × (0.931)^0.25 ≈ 279 × 0.982 ≈ 274
        # Not exact due to stochastic albedo/greenhouse; just check reasonable range
        import random as rng
        rng.seed(12345)
        wp = self._run(luminosity=1.0, orbit_au=1.0)
        assert 150 <= wp.advanced_mean_temperature_k <= 500

    def test_closer_orbit_higher_temp(self):
        import random as rng
        rng.seed(99)
        wp_close = self._run(orbit_au=0.5)
        rng.seed(99)
        wp_far = self._run(orbit_au=2.0)
        assert wp_close.advanced_mean_temperature_k > wp_far.advanced_mean_temperature_k

    def test_higher_luminosity_higher_temp(self):
        import random as rng
        rng.seed(77)
        wp_dim = self._run(luminosity=0.1)
        rng.seed(77)
        wp_bright = self._run(luminosity=10.0)
        assert wp_bright.advanced_mean_temperature_k > wp_dim.advanced_mean_temperature_k

    def test_none_pressure_uses_10_bar_fallback(self):
        # None pressure should not raise; falls back to 10.0 bar for greenhouse
        wp = _make_wp_stub()
        generate_advanced_mean_temperature(
            wp, atmosphere=6, hydrographics=5,
            pressure_bar=None, luminosity=1.0, orbit_au=1.0, hz_deviation=0.0,
        )
        assert wp.advanced_mean_temperature_k is not None
        assert wp.greenhouse_factor is not None

    def test_albedo_clamped_in_valid_range(self):
        import random as rng
        rng.seed(1)
        for _ in range(20):
            wp = self._run()
            assert 0.02 <= (wp.albedo or 0.0) <= 0.98

    def test_greenhouse_factor_non_negative(self):
        import random as rng
        rng.seed(2)
        for _ in range(20):
            wp = self._run()
            assert (wp.greenhouse_factor or 0.0) >= 0.0

    def test_vacuum_atmosphere_zero_greenhouse(self):
        with patch("traveller_world_physical.random.randint", return_value=3):
            wp = self._run(atmosphere=0, pressure_bar=0.0, luminosity=1.0, orbit_au=1.0)
        assert wp.greenhouse_factor == 0.0

    def test_to_dict_includes_new_fields(self):
        import random as rng
        rng.seed(5)
        wp = self._run()
        d = wp.to_dict()
        assert "albedo" in d
        assert "greenhouse_factor" in d
        assert "advanced_mean_temperature_k" in d

    def test_to_dict_absent_before_call(self):
        wp = _make_wp_stub()
        d = wp.to_dict()
        assert "albedo" not in d
        assert "greenhouse_factor" not in d
        assert "advanced_mean_temperature_k" not in d


# ---------------------------------------------------------------------------
# _axial_tilt_factor
# ---------------------------------------------------------------------------

class TestAxialTiltFactor:
    """_axial_tilt_factor — normalization, sine, orbital year modifiers."""

    def test_zero_tilt_gives_zero(self):
        assert _axial_tilt_factor(0.0, 8766.0) == pytest.approx(0.0, abs=1e-9)

    def test_90_degree_tilt_gives_one(self):
        assert _axial_tilt_factor(90.0, 8766.0) == pytest.approx(1.0, abs=1e-6)

    def test_45_degree_tilt(self):
        assert _axial_tilt_factor(45.0, 8766.0) == pytest.approx(math.sin(math.radians(45)), abs=1e-6)

    def test_tilt_above_90_reflected(self):
        # 135° → effective 45°; same as 45°
        assert _axial_tilt_factor(135.0, 8766.0) == pytest.approx(_axial_tilt_factor(45.0, 8766.0), abs=1e-9)

    def test_tilt_180_gives_zero(self):
        # 180° → effective 0° → sin(0°) = 0
        assert _axial_tilt_factor(180.0, 8766.0) == pytest.approx(0.0, abs=1e-9)

    def test_short_year_halves_factor(self):
        # orbital_period_hours < 876.6 → halved
        normal = _axial_tilt_factor(30.0, 8766.0)
        short  = _axial_tilt_factor(30.0, 500.0)
        assert short == pytest.approx(normal * 0.5, abs=1e-9)

    def test_long_year_increases_factor(self):
        # orbital_period_hours > 2×8766 = 17532 → factor increases
        normal = _axial_tilt_factor(30.0, 8766.0)
        long_  = _axial_tilt_factor(30.0, 30000.0)
        assert long_ > normal

    def test_long_year_caps_at_1(self):
        # Very long year with large tilt → capped at 1.0
        assert _axial_tilt_factor(90.0, 500000.0) == pytest.approx(1.0, abs=1e-9)

    def test_long_year_increase_capped_at_0_25(self):
        # Factor + 0.01×yr increase must not exceed factor + 0.25
        base = _axial_tilt_factor(10.0, 8766.0)
        very_long = _axial_tilt_factor(10.0, 1_000_000.0)
        assert very_long <= base + 0.25 + 1e-9


# ---------------------------------------------------------------------------
# _rotation_factor
# ---------------------------------------------------------------------------

class TestRotationFactor:
    """_rotation_factor — formula, exceptions."""

    def test_day_2500h_gives_1(self):
        assert _rotation_factor(2500.0, "none") == pytest.approx(1.0, abs=1e-6)

    def test_day_above_2500_capped_at_1(self):
        assert _rotation_factor(3000.0, "none") == pytest.approx(1.0, abs=1e-6)

    def test_day_100h(self):
        assert _rotation_factor(100.0, "none") == pytest.approx(math.sqrt(100) / 50, abs=1e-6)

    def test_day_25h(self):
        assert _rotation_factor(25.0, "none") == pytest.approx(math.sqrt(25) / 50, abs=1e-6)

    def test_1_1_lock_always_1(self):
        assert _rotation_factor(24.0, "1:1_lock") == pytest.approx(1.0, abs=1e-9)
        assert _rotation_factor(8766.0, "1:1_lock") == pytest.approx(1.0, abs=1e-9)

    def test_non_lock_status_uses_formula(self):
        for status in ("none", "braking", "prograde", "retrograde", "3:2_lock"):
            assert _rotation_factor(100.0, status) == pytest.approx(math.sqrt(100) / 50, abs=1e-6)

    def test_result_non_negative(self):
        assert _rotation_factor(1.0, "none") >= 0.0


# ---------------------------------------------------------------------------
# _geographic_factor
# ---------------------------------------------------------------------------

class TestGeographicFactor:
    """_geographic_factor — HYD formula."""

    def test_hydro_0(self):
        assert _geographic_factor(0) == pytest.approx(10 / 20, abs=1e-9)

    def test_hydro_10(self):
        assert _geographic_factor(10) == pytest.approx(0 / 20, abs=1e-9)

    def test_hydro_5(self):
        assert _geographic_factor(5) == pytest.approx(5 / 20, abs=1e-9)

    def test_decreases_with_higher_hydro(self):
        assert _geographic_factor(3) > _geographic_factor(7)

    def test_hydro_10_gives_zero(self):
        assert _geographic_factor(10) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# High/Low temperature in generate_advanced_mean_temperature
# ---------------------------------------------------------------------------

class TestHighLowTemperature:
    """High and low temperature output of generate_advanced_mean_temperature."""

    def _run(self, atmosphere=6, hydrographics=5, pressure_bar=1.0,
             luminosity=1.0, orbit_au=1.0, hz_deviation=0.0,
             orbit_eccentricity=0.0, star_mass=1.0, density=4.0,
             axial_tilt=23.5, day_length=24.0, tidal_status="none") -> WorldPhysical:
        wp = WorldPhysical(
            composition="Standard", diameter_km=12_742, density=density,
            mass=1.0, gravity=1.0, escape_velocity=11.2,
            axial_tilt=axial_tilt, day_length=day_length, tidal_status=tidal_status,
        )
        generate_advanced_mean_temperature(
            wp, atmosphere=atmosphere, hydrographics=hydrographics,
            pressure_bar=pressure_bar, luminosity=luminosity,
            orbit_au=orbit_au, hz_deviation=hz_deviation,
            orbit_eccentricity=orbit_eccentricity, star_mass=star_mass,
        )
        return wp

    def test_high_and_low_set(self):
        import random as rng
        rng.seed(1)
        wp = self._run()
        assert wp.high_temperature_k is not None
        assert wp.low_temperature_k is not None

    def test_high_ge_mean_ge_low(self):
        import random as rng
        rng.seed(2)
        wp = self._run()
        assert wp.high_temperature_k >= wp.advanced_mean_temperature_k  # type: ignore[operator]
        assert wp.advanced_mean_temperature_k >= wp.low_temperature_k   # type: ignore[operator]

    def test_zero_eccentricity_high_gt_mean_gt_low(self):
        # With eccentricity=0, near_au=far_au=orbit_au but luminosity modifier still differs
        import random as rng
        rng.seed(3)
        wp = self._run(orbit_eccentricity=0.0, axial_tilt=45.0)
        assert wp.high_temperature_k >= wp.advanced_mean_temperature_k  # type: ignore[operator]

    def test_higher_eccentricity_wider_range(self):
        import random as rng
        rng.seed(4)
        wp_lo_ecc = self._run(orbit_eccentricity=0.0)
        rng.seed(4)
        wp_hi_ecc = self._run(orbit_eccentricity=0.3)
        spread_lo = wp_lo_ecc.high_temperature_k - wp_lo_ecc.low_temperature_k  # type: ignore[operator]
        spread_hi = wp_hi_ecc.high_temperature_k - wp_hi_ecc.low_temperature_k  # type: ignore[operator]
        assert spread_hi >= spread_lo

    def test_tidal_lock_rotation_factor_1(self):
        # 1:1 lock sets rotation_factor=1.0; with high tilt produces wide spread
        import random as rng
        rng.seed(5)
        wp = self._run(axial_tilt=45.0, tidal_status="1:1_lock")
        assert wp.high_temperature_k > wp.low_temperature_k  # type: ignore[operator]

    def test_dense_atmosphere_narrows_spread(self):
        # High pressure increases atm_factor → smaller luminosity_modifier → narrower spread
        import random as rng
        rng.seed(6)
        wp_thin  = self._run(pressure_bar=0.1, axial_tilt=45.0)
        rng.seed(6)
        wp_thick = self._run(pressure_bar=10.0, axial_tilt=45.0)
        spread_thin  = (wp_thin.high_temperature_k  or 0) - (wp_thin.low_temperature_k  or 0)
        spread_thick = (wp_thick.high_temperature_k or 0) - (wp_thick.low_temperature_k or 0)
        assert spread_thick <= spread_thin

    def test_zero_tilt_no_axial_contribution(self):
        # Axial tilt 0° → axial tilt factor = 0, still get rotation + geo contributions
        import random as rng
        rng.seed(7)
        wp = self._run(axial_tilt=0.0, orbit_eccentricity=0.0)
        assert wp.high_temperature_k is not None
        assert wp.low_temperature_k is not None

    def test_to_dict_includes_high_low(self):
        import random as rng
        rng.seed(8)
        wp = self._run()
        d = wp.to_dict()
        assert "high_temperature_k" in d
        assert "low_temperature_k" in d

    def test_to_dict_absent_before_call(self):
        wp = _make_wp_stub()
        d = wp.to_dict()
        assert "high_temperature_k" not in d
        assert "low_temperature_k" not in d

    def test_all_temps_at_least_3k(self):
        import random as rng
        rng.seed(9)
        for _ in range(20):
            wp = self._run(luminosity=0.001, orbit_au=5.0)
            assert (wp.high_temperature_k or 0) >= 3
            assert (wp.low_temperature_k  or 0) >= 3


# ---------------------------------------------------------------------------
# TestComputeStellarDay — unit tests for _compute_stellar_day (WBH p.106)
# ---------------------------------------------------------------------------

class TestComputeStellarDay:
    """Direct unit tests for _compute_stellar_day — pure function, no RNG."""

    # 1 AU around a 1 M☉ star → T_orb = sqrt(1³/1) * 8766 = 8766.0 h
    _T_ORB = 8766.0

    def test_prograde_none_status(self):
        # Prograde: T_sol = (T_sid × T_orb) / (T_orb − T_sid)
        t_sid = 24.0
        expected = round((t_sid * self._T_ORB) / (self._T_ORB - t_sid), 1)
        assert _compute_stellar_day(t_sid, self._T_ORB, "none") == expected

    def test_prograde_braking_status(self):
        t_sid = 100.0
        expected = round((t_sid * self._T_ORB) / (self._T_ORB - t_sid), 1)
        assert _compute_stellar_day(t_sid, self._T_ORB, "braking") == expected

    def test_prograde_prograde_status(self):
        t_sid = 200.0
        expected = round((t_sid * self._T_ORB) / (self._T_ORB - t_sid), 1)
        assert _compute_stellar_day(t_sid, self._T_ORB, "prograde") == expected

    def test_retrograde_shorter_than_sidereal(self):
        # Retrograde: T_sol = (T_sid × T_orb) / (T_orb + T_sid)
        # Denominator is always > T_orb, so T_sol < T_sid
        t_sid = 24.0
        result = _compute_stellar_day(t_sid, self._T_ORB, "retrograde")
        expected = round((t_sid * self._T_ORB) / (self._T_ORB + t_sid), 1)
        assert result == expected
        assert result < t_sid

    def test_1_1_lock_returns_none(self):
        # Star is stationary in the sky; stellar day is undefined
        assert _compute_stellar_day(self._T_ORB, self._T_ORB, "1:1_lock") is None

    def test_3_2_lock_stellar_day_is_twice_orbital(self):
        # 3:2 resonance: T_sid = (2/3) × T_orb → T_sol = 2 × T_orb (like Mercury)
        t_sid = round((2 / 3) * self._T_ORB, 1)
        result = _compute_stellar_day(t_sid, self._T_ORB, "3:2_lock")
        assert result is not None
        assert abs(result - 2 * self._T_ORB) < 1.0  # within 1 h of 2×T_orb

    def test_edge_denom_zero_prograde_returns_none(self):
        # T_sid == T_orb in a prograde status (defensive edge case)
        assert _compute_stellar_day(self._T_ORB, self._T_ORB, "none") is None

    def test_edge_denom_negative_prograde_returns_none(self):
        # T_sid > T_orb in a prograde status (physically impossible, defensive)
        assert _compute_stellar_day(self._T_ORB + 1.0, self._T_ORB, "none") is None


# ---------------------------------------------------------------------------
# TestStellarDayIntegration — wired through generate_world_physical
# ---------------------------------------------------------------------------

class TestStellarDayIntegration:
    """Integration: stellar_day_hours set and serialised by generate_world_physical."""

    def test_stellar_day_absent_without_orbital_data(self):
        w = _World(size=6)
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(w)
        assert wp is not None
        assert wp.stellar_day_hours is None

    def test_stellar_day_present_with_orbital_data(self):
        w = _World(size=6, atmosphere=1)  # atm 1 → low tidal lock DM
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(
                w, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        assert wp.stellar_day_hours is not None
        assert wp.stellar_day_hours > 0.0

    def test_stellar_day_none_for_1_1_lock(self):
        # Force 1:1 tidal lock by making _roll_tidal_lock_status return that status
        w = _World(size=6, atmosphere=0)
        t_orb = round((1.0 ** 1.5) * 8766.0, 1)
        with patch("traveller_world_physical._roll_tidal_lock_status",
                   return_value=(t_orb, 0.0, "1:1_lock")):
            wp = generate_world_physical(
                w, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        assert wp.tidal_status == "1:1_lock"
        assert wp.stellar_day_hours is None

    def test_to_dict_includes_stellar_day_when_set(self):
        w = _World(size=6, atmosphere=1)
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(
                w, age_gyr=5.0,
                orbit_number=3.0, orbit_au=1.0, star_mass=1.0,
            )
        assert wp is not None
        d = wp.to_dict()
        assert "stellar_day_hours" in d
        assert d["stellar_day_hours"] == wp.stellar_day_hours

    def test_to_dict_omits_stellar_day_when_none(self):
        w = _World(size=6)
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(w)
        assert wp is not None
        assert "stellar_day_hours" not in wp.to_dict()


# ---------------------------------------------------------------------------
# check_runaway_greenhouse() — WBH p.79
# ---------------------------------------------------------------------------


class TestCheckRunawayGreenhouse:
    """Unit tests for check_runaway_greenhouse()."""

    # --- Trigger conditions ---

    def test_no_roll_for_atm_0(self):
        assert check_runaway_greenhouse(0, 350, 5.0, 6) is None

    def test_no_roll_for_atm_1(self):
        assert check_runaway_greenhouse(1, 350, 5.0, 6) is None

    def test_no_roll_for_atm_16(self):
        assert check_runaway_greenhouse(16, 400, 5.0, 6) is None

    def test_no_roll_for_atm_17(self):
        assert check_runaway_greenhouse(17, 400, 5.0, 6) is None

    def test_no_roll_when_temp_exactly_303(self):
        assert check_runaway_greenhouse(6, 303, 5.0, 6) is None

    def test_roll_attempted_when_temp_304(self):
        """304 K is the minimum that triggers the check."""
        with patch("traveller_world_physical.random.randint", return_value=6):
            # 2×6=12, age DM +ceil(5.0)=+5, temp DM +(304-303)//10=0 → 17 ≥ 12
            result = check_runaway_greenhouse(6, 304, 5.0, 6)
        assert result is not None

    # --- DM calculations ---

    def test_dm_age_rounds_up(self):
        """Age 3.1 Gyr → DM+4 (ceil), not DM+3 (floor)."""
        # Force 2D to return 2 (minimum). Need dm_age + dm_temp ≥ 10 to hit 12.
        # dm_temp = (323-303)//10 = 2. So we need dm_age ≥ 8. Use age 7.1 → ceil=8.
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2×1=2, dm_age=ceil(7.1)=8, dm_temp=(323-303)//10=2 → 12: runaway
            result = check_runaway_greenhouse(6, 323, 7.1, 6)
        assert result is not None

    def test_dm_age_exact_integer(self):
        """Age exactly 5.0 Gyr → DM+5 (ceil(5.0)=5)."""
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2, dm_age=5, dm_temp=(313-303)//10=1 → 8: no runaway
            result = check_runaway_greenhouse(6, 313, 5.0, 6)
        assert result is None

    def test_dm_temp_floor_division(self):
        """DM+1 per full 10 K above 303: 312 K → DM+0 (not DM+1)."""
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2, dm_age=1(ceil 0.5), dm_temp=(312-303)//10=0 → 3: no runaway
            result = check_runaway_greenhouse(6, 312, 0.5, 6)
        assert result is None

    def test_dm_temp_exact_10_above(self):
        """313 K is exactly 10 above 303 → DM+1."""
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2, dm_age=ceil(0.1)=1, dm_temp=1 → 4: no runaway
            result = check_runaway_greenhouse(6, 313, 0.1, 6)
        assert result is None

    # --- Roll threshold ---

    def test_roll_below_12_no_runaway(self):
        """Ensure that a combined total of 11 returns None."""
        # Set 2D to return 2 (1+1), age=4.5→dm_age=5, temp=303+40→dm_temp=4 → 11
        with patch("traveller_world_physical.random.randint", return_value=1):
            result = check_runaway_greenhouse(6, 343, 4.5, 6)
        # 2 + 5 + 4 = 11 → no runaway
        assert result is None

    def test_roll_exactly_12_triggers_runaway(self):
        """Combined total of exactly 12 → runaway."""
        with patch("traveller_world_physical.random.randint", return_value=1):
            # 2 + ceil(5.0)=5 + (353-303)//10=5 = 12 → runaway
            result = check_runaway_greenhouse(6, 353, 5.0, 6)
        assert result is not None

    # --- Already exotic/corrosive/insidious: no atmosphere code change ---

    @pytest.mark.parametrize("atm", [10, 11, 12, 15])
    def test_already_abc_f_no_new_atmosphere(self, atm):
        with patch("traveller_world_physical.random.randint", return_value=6):
            result = check_runaway_greenhouse(atm, 400, 5.0, 6)
        assert result is not None
        assert result.new_atmosphere is None

    # --- New atmosphere code selection for Atm 2–9, D, E ---

    def test_new_atm_die_1_gives_exotic(self):
        """1D result ≤ 1 → A (10)."""
        # Force 2D part to ensure runaway (both 6), then 1D forced to 1
        rolls = iter([6, 6, 1])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(6, 400, 0.1, 6)
        assert result is not None
        assert result.new_atmosphere == 10

    def test_new_atm_die_3_gives_corrosive(self):
        """1D result 2–4 → B (11)."""
        rolls = iter([6, 6, 3])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(6, 400, 0.1, 6)
        assert result is not None
        assert result.new_atmosphere == 11

    def test_new_atm_die_6_gives_insidious(self):
        """1D result ≥ 5 → C (12)."""
        rolls = iter([6, 6, 6])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(6, 400, 0.1, 6)
        assert result is not None
        assert result.new_atmosphere == 12

    def test_size_dm_minus2_biases_toward_a(self):
        """Size 3 (2–5 range) applies DM-2: die 3 → adjusted 1 → A."""
        rolls = iter([6, 6, 3])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(6, 400, 0.1, 3)
        assert result is not None
        assert result.new_atmosphere == 10  # 3 + (-2) = 1 → A

    def test_tainted_atm_dm_plus1_biases_toward_c(self):
        """Tainted Atm 7 (tainted) applies DM+1: die 4 → adjusted 5 → C."""
        rolls = iter([6, 6, 4])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(7, 400, 0.1, 6)
        assert result is not None
        assert result.new_atmosphere == 12  # 4 + 1 = 5 → C

    def test_d_atmosphere_gets_new_code(self):
        """Atm D (13) → code changes on runaway."""
        rolls = iter([6, 6, 3])
        with patch("traveller_world_physical.random.randint", side_effect=rolls):
            result = check_runaway_greenhouse(13, 400, 0.1, 6)
        assert result is not None
        assert result.new_atmosphere == 11  # die 3 → B

    # --- to_dict integration ---

    def test_to_dict_includes_runaway_greenhouse_when_true(self):
        w = _World(size=6, atmosphere=1)
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(w)
        assert wp is not None
        wp.runaway_greenhouse = True
        d = wp.to_dict()
        assert d.get("runaway_greenhouse") is True

    def test_to_dict_omits_runaway_greenhouse_when_none(self):
        w = _World(size=6)
        with patch("random.randint", return_value=3):
            wp = generate_world_physical(w)
        assert wp is not None


# ---------------------------------------------------------------------------
# Resource rating — WBH p.131
# ---------------------------------------------------------------------------

class TestDensityResourceDm:
    def test_high_density_gives_plus2(self):
        assert _density_resource_dm(1.13) == 2

    def test_exactly_1_12_gives_zero(self):
        assert _density_resource_dm(1.12) == 0

    def test_low_density_gives_minus2(self):
        assert _density_resource_dm(0.49) == -2

    def test_exactly_0_5_gives_zero(self):
        assert _density_resource_dm(0.5) == 0

    def test_mid_density_gives_zero(self):
        assert _density_resource_dm(0.8) == 0


class TestApplyBiologicalResourceDms:
    def test_no_life_no_change(self):
        assert apply_biological_resource_dms(5, None, None, None) == 5

    def test_biomass_3_plus2(self):
        assert apply_biological_resource_dms(5, 3, None, None) == 7

    def test_biomass_2_no_dm(self):
        assert apply_biological_resource_dms(5, 2, None, None) == 5

    def test_biodiversity_8_to_a_plus1(self):
        assert apply_biological_resource_dms(5, None, 9, None) == 6

    def test_biodiversity_b_plus_plus2(self):
        assert apply_biological_resource_dms(5, None, 11, None) == 7

    def test_compatibility_8_plus_plus2(self):
        assert apply_biological_resource_dms(5, None, None, 8) == 7

    def test_compatibility_low_with_biomass_minus1(self):
        assert apply_biological_resource_dms(5, 1, None, 3) == 4

    def test_compatibility_low_without_biomass_no_dm(self):
        # DM-1 only applies when biomass >= 1
        assert apply_biological_resource_dms(5, 0, None, 3) == 5

    def test_clamped_to_max_12(self):
        assert apply_biological_resource_dms(11, 5, 12, 9) == 12

    def test_clamped_to_min_2(self):
        assert apply_biological_resource_dms(2, 1, None, 2) == 2


class TestWorldResourceRating:
    def test_always_set_after_generate_world_physical(self):
        w = _World(size=6)
        with patch("random.randint", return_value=4):
            wp = generate_world_physical(w)
        assert wp is not None
        assert wp.resource_rating is not None

    def test_always_in_valid_range(self):
        import random as _random
        rng = _random.Random(42)
        for size in range(1, 11):
            w = _World(size=size)
            wp = generate_world_physical(w, rng=rng)
            assert wp is not None
            assert 2 <= wp.resource_rating <= 12

    def test_size_0_returns_none(self):
        w = _World(size=0)
        with patch("random.randint", return_value=4):
            result = generate_world_physical(w)
        assert result is None

    def test_to_dict_emits_resource_rating(self):
        w = _World(size=5)
        with patch("random.randint", return_value=4):
            wp = generate_world_physical(w)
        assert wp is not None
        assert "resource_rating" in wp.to_dict()
        assert isinstance(wp.to_dict()["resource_rating"], int)

    def test_from_dict_round_trips(self):
        w = _World(size=5)
        with patch("random.randint", return_value=4):
            wp = generate_world_physical(w)
        assert wp is not None
        restored = WorldPhysical.from_dict(wp.to_dict())
        assert restored.resource_rating == wp.resource_rating
        assert "runaway_greenhouse" not in wp.to_dict()
