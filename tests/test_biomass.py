"""
test_biomass.py
===============
pytest unit tests for generate_biomass_rating() (WBH pp.127-131).

Test strategy
-------------
Deterministic DM calculations are verified by patching random.randint to a
fixed base roll (typically 7 = "average" 2D) and asserting the final result.
Special cases and edge conditions are tested exhaustively.
"""

import random
from unittest.mock import patch

import pytest  # pylint: disable=import-error

from traveller_world_detail import (  # pylint: disable=import-error
    generate_biomass_rating,
    _ATM_BIOMASS_DM,
    _HYDRO_BIOMASS_DM,
    _SC2_ATM_SET,
    _SC2_ADJUSTMENT,
    _OXYGEN_ATM_SET,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roll_biomass(atm, hydro, age_gyr, temperature_zone,
                  mean_temp_k=None, has_biologic_taint=False,
                  dice_total=7):
    """Call generate_biomass_rating with a fixed 2D total."""
    # Each call uses two randint(1,6) calls; we fix them both to half
    half = dice_total // 2
    rem  = dice_total - half
    with patch("traveller_world_detail.random.randint", side_effect=[half, rem]):
        return generate_biomass_rating(
            atm=atm, hydro=hydro, age_gyr=age_gyr,
            temperature_zone=temperature_zone,
            mean_temp_k=mean_temp_k,
            has_biologic_taint=has_biologic_taint,
        )


# ---------------------------------------------------------------------------
# Atmosphere DMs
# ---------------------------------------------------------------------------

class TestAtmosphereDM:
    def test_atm_0_dm_minus6(self):
        # 2D=7, atm DM=-6, hydro=5 (DM 0), age=3 (DM 0), temperate (+2)
        # rolled: 7-6+2=3; SC2 applies (atm 0, add 5) → 3+5=8
        assert _roll_biomass(0, 5, 3.0, "temperate") == 8

    def test_atm_1_dm_minus4(self):
        # 7-4+2=5; SC2 applies (atm 1, add 3) → 5+3=8
        assert _roll_biomass(1, 5, 3.0, "temperate") == 8

    def test_atm_2_dm_minus3(self):
        assert _roll_biomass(2, 5, 3.0, "temperate") == 6

    def test_atm_3_dm_minus3(self):
        assert _roll_biomass(3, 5, 3.0, "temperate") == 6

    def test_atm_4_dm_minus2(self):
        assert _roll_biomass(4, 5, 3.0, "temperate") == 7

    def test_atm_5_dm_minus2(self):
        assert _roll_biomass(5, 5, 3.0, "temperate") == 7

    def test_atm_6_dm_zero(self):
        assert _roll_biomass(6, 5, 3.0, "temperate") == 9

    def test_atm_7_dm_zero(self):
        assert _roll_biomass(7, 5, 3.0, "temperate") == 9

    def test_atm_8_dm_plus2(self):
        # 7+2+2=11; SC2 not applicable (atm 8 not in SC2 set)
        assert _roll_biomass(8, 5, 3.0, "temperate") == 11

    def test_atm_9_dm_plus2(self):
        assert _roll_biomass(9, 5, 3.0, "temperate") == 11

    def test_atm_d13_dm_plus2(self):
        # Atmosphere D = code 13: DM+2
        assert _roll_biomass(13, 5, 3.0, "temperate") == 11

    def test_atm_a10_dm_minus3(self):
        # 7-3+2=6; SC2 adj for atm 10 = +2 → 6+2=8
        assert _roll_biomass(10, 5, 3.0, "temperate") == 8

    def test_atm_b11_dm_minus5(self):
        # 7-5+2=4; SC2 adj for atm 11 = +4 → 4+4=8
        assert _roll_biomass(11, 5, 3.0, "temperate") == 8

    def test_atm_c12_dm_minus7(self):
        # 7-7+2=2; SC2 adj for atm 12 = +6 → 2+6=8
        assert _roll_biomass(12, 5, 3.0, "temperate") == 8

    def test_atm_e14_dm_minus3(self):
        # 7-3+2=6; atm 14 not in SC2 set
        assert _roll_biomass(14, 5, 3.0, "temperate") == 6

    def test_atm_f15_dm_minus5(self):
        # 7-5+2=4; SC2 adj for atm 15 = +4 → 4+4=8
        assert _roll_biomass(15, 5, 3.0, "temperate") == 8

    def test_atm_above_15_treated_as_15(self):
        # Code 16 (not standard, but guard exists) → same as 15
        result_15  = _roll_biomass(15, 5, 3.0, "temperate")
        result_16  = _roll_biomass(16, 5, 3.0, "temperate")
        assert result_15 == result_16


# ---------------------------------------------------------------------------
# Hydrographics DMs
# ---------------------------------------------------------------------------

class TestHydrographicsDM:
    def test_hydro_0_dm_minus4(self):
        # 7+0-4=3; atm 6, age 3, temperate +2 → 7+0-4+2=5
        assert _roll_biomass(6, 0, 3.0, "temperate") == 5

    def test_hydro_1_dm_minus2(self):
        assert _roll_biomass(6, 1, 3.0, "temperate") == 7

    def test_hydro_3_dm_minus2(self):
        assert _roll_biomass(6, 3, 3.0, "temperate") == 7

    def test_hydro_4_dm_zero(self):
        assert _roll_biomass(6, 4, 3.0, "temperate") == 9

    def test_hydro_5_dm_zero(self):
        assert _roll_biomass(6, 5, 3.0, "temperate") == 9

    def test_hydro_6_dm_plus1(self):
        assert _roll_biomass(6, 6, 3.0, "temperate") == 10

    def test_hydro_8_dm_plus1(self):
        assert _roll_biomass(6, 8, 3.0, "temperate") == 10

    def test_hydro_9_dm_plus2(self):
        assert _roll_biomass(6, 9, 3.0, "temperate") == 11

    def test_hydro_10_dm_plus2(self):
        assert _roll_biomass(6, 10, 3.0, "temperate") == 11


# ---------------------------------------------------------------------------
# Age DMs (cumulative)
# ---------------------------------------------------------------------------

class TestAgeDM:
    def test_age_below_0_2_applies_both_minus6_and_minus2(self):
        # age=0.1: DM-6 (< 0.2) AND DM-2 (< 1.0) → total -8
        # 7 + 0 (atm6) + 0 (hydro5) -8 +2 (temperate) = 1
        assert _roll_biomass(6, 5, 0.1, "temperate") == 1

    def test_age_between_0_2_and_1_applies_minus2_only(self):
        # age=0.5: only DM-2 (< 1.0) → 7+0+0-2+2=7
        assert _roll_biomass(6, 5, 0.5, "temperate") == 7

    def test_age_between_1_and_4_no_age_dm(self):
        # age=3.0: no age DM → 7+0+0+2=9
        assert _roll_biomass(6, 5, 3.0, "temperate") == 9

    def test_age_above_4_dm_plus1(self):
        # age=5.0: DM+1 → 7+0+0+1+2=10
        assert _roll_biomass(6, 5, 5.0, "temperate") == 10

    def test_age_exactly_0_2_is_not_below_0_2(self):
        # age=0.2: only DM-2 (< 1.0 applies, < 0.2 does NOT) → 7+0+0-2+2=7
        assert _roll_biomass(6, 5, 0.2, "temperate") == 7

    def test_age_exactly_1_is_not_below_1(self):
        # age=1.0: no age DM → 7+0+0+2=9
        assert _roll_biomass(6, 5, 1.0, "temperate") == 9

    def test_age_exactly_4_is_not_above_4(self):
        # age=4.0: no age DM → 7+0+0+2=9
        assert _roll_biomass(6, 5, 4.0, "temperate") == 9


# ---------------------------------------------------------------------------
# Temperature DMs — simplified path
# ---------------------------------------------------------------------------

class TestTemperatureSimplified:
    def test_temperate_plus2(self):
        assert _roll_biomass(6, 5, 3.0, "temperate") == 9

    def test_cold_minus2(self):
        # 7+0(atm6)+0(hydro5)+0(age3)-2(cold)=5
        assert _roll_biomass(6, 5, 3.0, "cold") == 5

    def test_frozen_minus6(self):
        # 7+0+0+0-6=1
        assert _roll_biomass(6, 5, 3.0, "frozen") == 1

    def test_boiling_minus6(self):
        # 7+0+0+0-6=1
        assert _roll_biomass(6, 5, 3.0, "boiling") == 1

    def test_hot_zero(self):
        assert _roll_biomass(6, 5, 3.0, "hot") == 7

    def test_case_insensitive(self):
        assert _roll_biomass(6, 5, 3.0, "Temperate") == _roll_biomass(6, 5, 3.0, "temperate")

    def test_unknown_zone_zero(self):
        assert _roll_biomass(6, 5, 3.0, "exotic") == 7


# ---------------------------------------------------------------------------
# Temperature DMs — detailed K path
# ---------------------------------------------------------------------------

class TestTemperatureKPath:
    def test_mean_temp_above_353_dm_minus4(self):
        # mean_temp_k=400 → DM-4; 7+0+0-4=3
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 3

    def test_mean_temp_below_273_dm_minus2(self):
        # mean_temp_k=200 → DM-2; 7+0+0-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=200) == 5

    def test_mean_temp_in_279_303_range_dm_plus2(self):
        # mean_temp_k=290 → DM+2; 7+0+0+2=9
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=290) == 9

    def test_mean_temp_hot_and_in_sweet_spot_does_not_apply_sweet_spot(self):
        # mean_temp_k=360 → above 353, so DM-4; 279-303 check fails
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=360) == 3

    def test_mean_temp_below_273_also_in_sweet_spot_range_impossible(self):
        # 200 is below 273 → DM-2; not in 279-303 → 7+0+0-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=200) == 5

    def test_mean_temp_neutral_zone_no_dm(self):
        # mean_temp_k=310 → not above 353, not below 273, not in 279-303 → DM 0
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=310) == 7

    def test_mean_temp_k_overrides_simplified_zone(self):
        # Even though temperature_zone="temperate" (+2), mean_temp_k takes precedence
        # mean_temp_k=290 → DM+2 (same result, but via K path)
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=290) == 9
        # mean_temp_k=400 → DM-4; simplified would be +2 but K path wins
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 3


# ---------------------------------------------------------------------------
# DM clamping
# ---------------------------------------------------------------------------

class TestDMClamping:
    def test_max_dm_clamped_to_plus4(self):
        # atm 8 (+2) + hydro 9 (+2) + age > 4 (+1) + temperate (+2) = +7 → clamped to +4
        # 7 + 4 = 11
        assert _roll_biomass(8, 9, 5.0, "temperate") == 11

    def test_min_dm_clamped_to_minus12(self):
        # atm 0 (-6) + hydro 0 (-4) + age 0.1 (-6, -2) + boiling (-6) = -24 → clamped to -12
        # 7 - 12 = -5 → 0 (no life)
        assert _roll_biomass(0, 0, 0.1, "boiling") == 0

    def test_floor_result_zero(self):
        # Confirm negative rolled result returns 0 not a negative value
        result = _roll_biomass(0, 0, 0.1, "frozen", dice_total=2)
        assert result == 0

    def test_result_never_negative(self):
        # Many bad conditions — result must be ≥ 0
        for seed in range(50):
            random.seed(seed)
            r = generate_biomass_rating(0, 0, 0.05, "frozen")
            assert r >= 0


# ---------------------------------------------------------------------------
# Special Case 1 — biologic taint
# ---------------------------------------------------------------------------

class TestSpecialCase1:
    def test_biologic_taint_rolled_zero_becomes_one(self):
        # dice_total=2, atm=0 (DM-6), hydro=0 (DM-4), age=3, boiling (-6)
        # combined DM before clamp: -16 → clamped to -12; 2-12=-10 → 0 normally
        # With biologic taint: should become 1
        result = _roll_biomass(0, 0, 3.0, "boiling",
                               has_biologic_taint=True, dice_total=2)
        assert result == 1

    def test_biologic_taint_with_positive_roll_unchanged(self):
        # dice=7, good conditions → rolled positive; SC1 doesn't change it
        result = _roll_biomass(6, 5, 3.0, "temperate",
                               has_biologic_taint=True, dice_total=7)
        assert result == 9  # same as without biologic taint

    def test_no_biologic_taint_rolled_zero_stays_zero(self):
        result = _roll_biomass(0, 0, 3.0, "boiling",
                               has_biologic_taint=False, dice_total=2)
        assert result == 0


# ---------------------------------------------------------------------------
# Special Case 2 — inhospitable atmosphere adjustment
# ---------------------------------------------------------------------------

class TestSpecialCase2:
    def test_atm0_positive_biomass_adds_5(self):
        # dice=7, atm=0 (DM-6), hydro=5, age=3, temperate (+2) → 7-6+2=3; 3+5=8
        assert _roll_biomass(0, 5, 3.0, "temperate") == 8

    def test_atm1_positive_biomass_adds_3(self):
        # 7-4+2=5; 5+3=8
        assert _roll_biomass(1, 5, 3.0, "temperate") == 8

    def test_atm_a10_positive_biomass_adds_2(self):
        # 7-3+2=6; 6+2=8
        assert _roll_biomass(10, 5, 3.0, "temperate") == 8

    def test_atm_b11_positive_biomass_adds_4(self):
        # 7-5+2=4; 4+4=8
        assert _roll_biomass(11, 5, 3.0, "temperate") == 8

    def test_atm_c12_positive_biomass_adds_6(self):
        # 7-7+2=2; 2+6=8
        assert _roll_biomass(12, 5, 3.0, "temperate") == 8

    def test_atm_f15_positive_biomass_adds_4(self):
        # 7-5+2=4; 4+4=8
        assert _roll_biomass(15, 5, 3.0, "temperate") == 8

    def test_sc2_not_applied_when_rolled_zero(self):
        # atm=0, very bad conditions → rolled ≤ 0 → returns 0, SC2 never applies
        result = _roll_biomass(0, 0, 3.0, "boiling", dice_total=2)
        assert result == 0

    def test_atm_in_sc2_set(self):
        assert 0 in _SC2_ATM_SET
        assert 1 in _SC2_ATM_SET
        assert 10 in _SC2_ATM_SET
        assert 11 in _SC2_ATM_SET
        assert 12 in _SC2_ATM_SET
        assert 15 in _SC2_ATM_SET
        assert 6 not in _SC2_ATM_SET
        assert 8 not in _SC2_ATM_SET

    def test_sc2_adjustments_correct(self):
        assert _SC2_ADJUSTMENT[0]  == 5   # |DM-6| - 1
        assert _SC2_ADJUSTMENT[1]  == 3   # |DM-4| - 1
        assert _SC2_ADJUSTMENT[10] == 2   # |DM-3| - 1
        assert _SC2_ADJUSTMENT[11] == 4   # |DM-5| - 1
        assert _SC2_ADJUSTMENT[12] == 6   # |DM-7| - 1
        assert _SC2_ADJUSTMENT[15] == 4   # |DM-5| - 1


# ---------------------------------------------------------------------------
# Garden world baseline
# ---------------------------------------------------------------------------

class TestGardenWorld:
    def test_garden_world_high_biomass(self):
        # atm 6 (DM 0), hydro 7 (+1), age 5 (+1), temperate (+2) → DM+4 (clamped to +4)
        # 7+4=11 — healthy garden world
        assert _roll_biomass(6, 7, 5.0, "temperate") == 11

    def test_average_world_moderate_biomass(self):
        # atm 6 (0), hydro 5 (0), age 3 (0), temperate (+2) → 7+2=9
        assert _roll_biomass(6, 5, 3.0, "temperate") == 9


# ---------------------------------------------------------------------------
# Optional rule — oxygen atmosphere minimum biomass (WBH p.131)
# The rule is applied by _apply_biomass(); tested here via _OXYGEN_ATM_SET
# and a local mirror of the floor logic.
# ---------------------------------------------------------------------------

def _oxygen_floor(biomass: int, atm: int) -> int:
    """Mirror of the _oxygen_floor closure in _apply_biomass for testing."""
    if biomass == 0 and atm in _OXYGEN_ATM_SET:
        return 1
    return biomass


class TestOptionalOxygenRule:
    def test_oxygen_set_contents(self):
        assert _OXYGEN_ATM_SET == frozenset({2, 3, 4, 5, 6, 7, 8, 9, 13, 14})

    def test_non_oxygen_codes_excluded(self):
        for atm in (0, 1, 10, 11, 12, 15):
            assert atm not in _OXYGEN_ATM_SET

    def test_zero_biomass_on_oxygen_atm_raises_to_1(self):
        for atm in _OXYGEN_ATM_SET:
            assert _oxygen_floor(0, atm) == 1

    def test_positive_biomass_on_oxygen_atm_unchanged(self):
        for atm in _OXYGEN_ATM_SET:
            assert _oxygen_floor(3, atm) == 3
            assert _oxygen_floor(1, atm) == 1

    def test_zero_biomass_on_non_oxygen_atm_stays_zero(self):
        for atm in (0, 1, 10, 11, 12, 15):
            assert _oxygen_floor(0, atm) == 0

    def test_floor_not_applied_above_zero(self):
        assert _oxygen_floor(5, 6) == 5

    def test_floor_raises_only_to_one_not_higher(self):
        assert _oxygen_floor(0, 8) == 1  # not 2 or more
