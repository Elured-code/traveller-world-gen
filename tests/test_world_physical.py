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
from unittest.mock import patch

import pytest

from traveller_world_physical import (
    TIDAL_STATUS_LABELS,
    WorldPhysical,
    _age_dm,
    _apply_tidal_lock_result,
    _orbital_period_hours,
    _reroll_axial_tilt_for_lock,
    _roll_tidal_lock_status,
    _tidal_lock_dm,
    generate_world_physical,
)


# ---------------------------------------------------------------------------
# Minimal World stub
# ---------------------------------------------------------------------------

class _World:
    """Minimal stub matching the fields read by generate_world_physical."""
    def __init__(self, size: int = 6, atmosphere: int = 6):
        self.size = size
        self.atmosphere = atmosphere


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
        defaults = dict(size=6, axial_tilt=10.0, atmosphere=6, age_gyr=3.0,
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
