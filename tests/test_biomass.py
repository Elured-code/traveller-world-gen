"""
test_biomass.py
===============
pytest unit tests for generate_biomass_rating() and
generate_biocomplexity_rating() (WBH pp.127-131).

Test strategy
-------------
Deterministic DM calculations are verified by patching random.randint to a
fixed base roll (typically 7 = "average" 2D) and asserting the final result.
Special cases and edge conditions are tested exhaustively.
"""

import random
from unittest.mock import MagicMock, patch

import pytest  # pylint: disable=import-error

from traveller_world_detail import (  # pylint: disable=import-error
    generate_biomass_rating,
    generate_biocomplexity_rating,
    generate_sophont_checks,
    generate_biodiversity_rating,
    generate_compatibility_rating,
    _ATM_BIOMASS_DM,
    _HYDRO_BIOMASS_DM,
    _SC2_ATM_SET,
    _SC2_ADJUSTMENT,
    _OXYGEN_ATM_SET,
    _ATM_COMPAT_DM,
    _INHERENT_TAINTED_CODES,
    _apply_biomass,
    attach_detail,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roll_biomass(atm, hydro, age_gyr, temperature_zone,
                  mean_temp_k=None, high_temp_k=None,
                  has_biologic_taint=False, dice_total=7):
    """Call generate_biomass_rating with a fixed 2D total."""
    # Each call uses two randint(1,6) calls; we fix them both to half
    half = dice_total // 2
    rem  = dice_total - half
    with patch("traveller_world_detail.random.randint", side_effect=[half, rem]):
        return generate_biomass_rating(
            atm=atm, hydro=hydro, age_gyr=age_gyr,
            temperature_zone=temperature_zone,
            mean_temp_k=mean_temp_k,
            high_temp_k=high_temp_k,
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
    def test_above_353_applies_both_high_and_mean_dm(self):
        # mean_temp_k=400 → High DM-2 + Mean DM-4 = DM-6; 7+0+0-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 1

    def test_below_273_applies_both_high_and_mean_dm(self):
        # mean_temp_k=200 → High DM-4 + Mean DM-2 = DM-6; 7+0+0-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=200) == 1

    def test_mean_temp_in_279_303_range_dm_plus2(self):
        # mean_temp_k=290 → DM+2 (no High/Mean extreme); 7+0+0+2=9
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=290) == 9

    def test_above_353_does_not_also_apply_sweet_spot(self):
        # mean_temp_k=360 → DM-6; 279-303 check fails (360 not in range); 7-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=360) == 1

    def test_below_273_does_not_also_apply_sweet_spot(self):
        # mean_temp_k=200 → DM-6; 200 not in 279-303; 7-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=200) == 1

    def test_mean_temp_neutral_zone_no_dm(self):
        # mean_temp_k=310 → not above 353, not below 273, not in 279-303 → DM 0
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=310) == 7

    def test_mean_temp_k_overrides_simplified_zone(self):
        # Even though temperature_zone="temperate" (+2), mean_temp_k takes precedence
        # mean_temp_k=290 → DM+2 (same result, but via K path)
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=290) == 9
        # mean_temp_k=400 → DM-6; simplified would be +2 but K path wins
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 1

    def test_boundary_exactly_353_no_extreme_dm(self):
        # mean_temp_k=353 → not strictly above 353, not below 273 → DM 0; 7+0=7
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=353) == 7

    def test_boundary_exactly_273_no_extreme_dm(self):
        # mean_temp_k=273 → not above 353, not strictly below 273 → DM 0; 7+0=7
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=273) == 7

    def test_combined_dm_matches_footnote_boiling(self):
        # Verify that the K-path gives equivalent result to footnote for hot worlds.
        # mean_temp_k=400 on atm 6, hydro 5, age 3.0:
        # DM = 0+0+0 + (-2 high) + (-4 mean) = -6; 7-6=1
        # Footnote zone path for boiling: DM-6; 7-6=1 → same answer ✓
        assert _roll_biomass(6, 5, 3.0, "boiling") == 1  # zone path
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 1  # K path


# ---------------------------------------------------------------------------
# Split high_temp_k / mean_temp_k DMs
# ---------------------------------------------------------------------------

class TestHighTempKSplit:
    """When high_temp_k is provided separately, it drives the 'High temperature'
    rows while mean_temp_k drives the 'Mean temperature' rows independently."""

    def test_high_above_353_only_applies_high_row_dm(self):
        # mean_temp=280 (sweet spot +2), high_temp=360 (>353: high DM-2)
        # Net temp DMs: -2 + 2 = 0; base 7+0+0+0 = 7
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=280, high_temp_k=360) == 7

    def test_mean_above_353_still_applies_mean_row_dm(self):
        # mean=400, high=None → proxy path: high DM-2 + mean DM-4 = -6; 7-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 1

    def test_high_above_353_mean_above_353_both_apply(self):
        # high=400, mean=400: high DM-2 + mean DM-4 = -6; 7-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=400, high_temp_k=400) == 1

    def test_high_above_353_mean_normal_net_minus2(self):
        # high=360, mean=310 (not in any range): high DM-2; 7-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=310, high_temp_k=360) == 5

    def test_high_below_273_applies_high_dm_minus4(self):
        # high=200, mean=280 (sweet spot +2): high DM-4 + mean DM+2 = -2; 7-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=280, high_temp_k=200) == 5

    def test_mean_below_273_applies_mean_dm_minus2(self):
        # high=280, mean=200 (<273: mean DM-2); high row: 280 not extreme → 0; net -2; 7-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=200, high_temp_k=280) == 5

    def test_both_below_273_applies_both_dms(self):
        # high=200, mean=200: high DM-4 + mean DM-2 = -6; 7-6=1
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=200, high_temp_k=200) == 1

    def test_sweet_spot_mean_high_above_threshold(self):
        # mean=290 (sweet spot +2), high=360 (>353: -2): net 0; 7+0=7
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=290, high_temp_k=360) == 7

    def test_high_temp_k_none_falls_back_to_mean_proxy(self):
        # Original proxy behaviour preserved when high_temp_k not given
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=400) == 1
        assert _roll_biomass(6, 5, 3.0, "temperate", mean_temp_k=200) == 1

    def test_only_high_temp_k_no_mean(self):
        # high=400, mean=None: only high row applies (DM-2); mean rows skipped;
        # simplified zone path also skipped since high_temp_k is not None; 7-2=5
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=None, high_temp_k=400) == 5

    def test_only_high_below_273_no_mean(self):
        # high=200, mean=None: high DM-4; 7-4=3
        assert _roll_biomass(6, 5, 3.0, "temperate",
                              mean_temp_k=None, high_temp_k=200) == 3


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


# ---------------------------------------------------------------------------
# Biocomplexity Rating (WBH pp.127-131)
#
# Roll: 2D - 7 + min(biomass, 9), then apply DMs:
#   Atmosphere not 4-9 : DM-2
#   Low-oxygen taint   : DM-2
#   Age DMs (exclusive ranges, worst-at-boundary):
#     ≤ 1 Gyr   → DM-10
#     ≤ 2 Gyr   → DM-8
#     ≤ 3 Gyr   → DM-4
#     ≤ 4 Gyr   → DM-2
#     > 4 Gyr   → no DM
#   Minimum result: 1
# ---------------------------------------------------------------------------

def _roll_biocomplexity(biomass, atm, age_gyr, has_low_o=False, dice_total=7):
    """Call generate_biocomplexity_rating with a fixed 2D total.

    dice_total=7 → 2D-7 = 0, so base = 0 + min(biomass,9) = min(biomass,9).
    """
    half = dice_total // 2
    rem  = dice_total - half
    with patch("traveller_world_detail.random.randint", side_effect=[half, rem]):
        return generate_biocomplexity_rating(biomass, atm, age_gyr, has_low_o)


class TestBiocomplexityAtmosphereDM:
    """Atmosphere not 4-9 applies DM-2 (WBH pp.127-131)."""

    # Baseline: biomass=5, dice=7 → base=5; age=5.0 (no age DM); no low-O taint.

    def test_atm_in_range_4_no_dm(self):
        # atm 4 is in [4,9] → no atmosphere DM; 5 + 0 = 5
        assert _roll_biocomplexity(5, 4, 5.0) == 5

    def test_atm_in_range_9_no_dm(self):
        # atm 9 is in [4,9] → no atmosphere DM; 5 + 0 = 5
        assert _roll_biocomplexity(5, 9, 5.0) == 5

    def test_atm_in_range_6_no_dm(self):
        assert _roll_biocomplexity(5, 6, 5.0) == 5

    def test_atm_0_dm_minus2(self):
        # atm 0 not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 0, 5.0) == 3

    def test_atm_3_dm_minus2(self):
        # atm 3 not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 3, 5.0) == 3

    def test_atm_10_dm_minus2(self):
        # atm 10 (A, exotic) not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 10, 5.0) == 3

    def test_atm_12_dm_minus2(self):
        # atm 12 (C, insidious) not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 12, 5.0) == 3

    def test_atm_13_dm_minus2(self):
        # atm 13 (D, dense high-O₂) not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 13, 5.0) == 3

    def test_atm_15_dm_minus2(self):
        # atm 15 (F, unusual) not in [4,9] → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 15, 5.0) == 3


class TestBiocomplexityLowOxygenDM:
    """Low-oxygen taint applies DM-2 (WBH pp.127-131)."""

    def test_no_low_o_taint_no_dm(self):
        # has_low_o=False, atm 6, age 5 → no extra DM; 5 + 0 = 5
        assert _roll_biocomplexity(5, 6, 5.0, has_low_o=False) == 5

    def test_low_o_taint_dm_minus2(self):
        # has_low_o=True, atm 6, age 5 → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 6, 5.0, has_low_o=True) == 3

    def test_low_o_taint_stacks_with_atm_dm(self):
        # has_low_o=True, atm 0 (DM-2), age 5 → DM-4; 5 - 4 = 1
        assert _roll_biocomplexity(5, 0, 5.0, has_low_o=True) == 1


class TestBiocomplexityAgeDM:
    """Age DMs — exclusive ranges, worst-at-boundary (WBH pp.127-131)."""

    # Baseline: biomass=5, atm=6 (no atmosphere DM), no low-O taint.
    # With dice=7: base = 5.

    def test_age_above_4_no_dm(self):
        # age=5.0 → no age DM; 5 + 0 = 5
        assert _roll_biocomplexity(5, 6, 5.0) == 5

    def test_age_exactly_4_dm_minus2(self):
        # age=4.0 (boundary ≤4 Gyr) → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 6, 4.0) == 3

    def test_age_3_5_dm_minus2(self):
        # 3 < age=3.5 ≤ 4 → DM-2; 5 - 2 = 3
        assert _roll_biocomplexity(5, 6, 3.5) == 3

    def test_age_exactly_3_dm_minus4(self):
        # age=3.0 (boundary ≤3 Gyr) → DM-4; 5 - 4 = 1
        assert _roll_biocomplexity(5, 6, 3.0) == 1

    def test_age_2_5_dm_minus4(self):
        # 2 < age=2.5 ≤ 3 → DM-4; 5 - 4 = 1
        assert _roll_biocomplexity(5, 6, 2.5) == 1

    def test_age_exactly_2_dm_minus8(self):
        # age=2.0 (boundary ≤2 Gyr) → DM-8; max(1, 5-8) = 1
        assert _roll_biocomplexity(5, 6, 2.0) == 1

    def test_age_1_5_dm_minus8(self):
        # 1 < age=1.5 ≤ 2 → DM-8; max(1, 5-8) = 1
        assert _roll_biocomplexity(5, 6, 1.5) == 1

    def test_age_exactly_1_dm_minus10(self):
        # age=1.0 (boundary ≤1 Gyr, worst case) → DM-10; max(1, 5-10) = 1
        assert _roll_biocomplexity(5, 6, 1.0) == 1

    def test_age_0_5_dm_minus10(self):
        # age=0.5 ≤ 1 → DM-10; max(1, 5-10) = 1
        assert _roll_biocomplexity(5, 6, 0.5) == 1


class TestBiocomplexitySpecialCases:
    """Floor, biomass cap, and DM stacking (WBH pp.127-131)."""

    def test_result_minimum_is_1(self):
        # Worst possible conditions still return at least 1
        # biomass=1, dice=2, atm=0 (DM-2), age=0.5 (DM-10):
        # base = 2-7+1 = -4; dm = -12; result = max(1, -4-12) = 1
        half, rem = 1, 1
        with patch("traveller_world_detail.random.randint", side_effect=[half, rem]):
            result = generate_biocomplexity_rating(1, 0, 0.5)
        assert result >= 1

    def test_biomass_capped_at_9_for_roll(self):
        # biomass=15 and biomass=9 with dice=7 should give identical results
        assert _roll_biocomplexity(15, 6, 5.0) == _roll_biocomplexity(9, 6, 5.0)

    def test_biomass_12_equals_biomass_9(self):
        # biomass=12 → capped to 9; base = 7-7+9 = 9; no DMs; result = 9
        assert _roll_biocomplexity(12, 6, 5.0) == 9

    def test_all_dms_stack(self):
        # atm=0 (DM-2), has_low_o=True (DM-2), age=1.0 (DM-10) → total DM-14
        # biomass=5, dice=7: base=5; 5-14=-9 → max(1,-9) = 1
        assert _roll_biocomplexity(5, 0, 1.0, has_low_o=True) == 1

    def test_high_biomass_high_age_good_atm(self):
        # biomass=9, atm=6, age=5.0 → no DMs; base = 7-7+9 = 9
        assert _roll_biocomplexity(9, 6, 5.0) == 9

    def test_result_never_below_1_across_seeds(self):
        for seed in range(50):
            random.seed(seed)
            result = generate_biocomplexity_rating(1, 0, 0.1, has_low_oxygen_taint=True)
            assert result >= 1


# ---------------------------------------------------------------------------
# Sophont checks (WBH p.131)
#
# Current sophont:  2D + min(bio, 9) - 7 >= 13 → 2D >= 20 - min(bio, 9)
# Extinct sophont:  2D + min(bio, 9) - 7 + DMs >= 13 (DM+1 if age > 5 Gyrs)
# Biocomplexity >= 8 required for either check to fire.
# If current sophont found, extinct check is skipped.
# ---------------------------------------------------------------------------

def _roll_sophont(biocomplexity, age_gyr, dice_rolls):
    """Call generate_sophont_checks with a fixed sequence of 2D rolls."""
    with patch("traveller_world_detail.random.randint", side_effect=dice_rolls):
        return generate_sophont_checks(biocomplexity, age_gyr)


class TestSophontChecks:
    """Native and extinct sophont rolls (WBH p.131)."""

    def test_current_sophont_on_high_roll(self):
        # bio=9, age=3.0: threshold = 20 - 9 = 11; roll 6+6=12 → 12+9-7=14 >= 13 → current
        native, extinct = _roll_sophont(9, 3.0, [6, 6])
        assert native is True
        assert extinct is False

    def test_current_sophont_exact_threshold_bio9(self):
        # bio=9: need 2D >= 11; roll 5+6=11 → 11+9-7=13 >= 13 → current
        native, extinct = _roll_sophont(9, 3.0, [5, 6])
        assert native is True
        assert extinct is False

    def test_no_current_sophont_below_threshold_bio9(self):
        # bio=9: need 2D >= 11; roll 5+5=10 → 10+9-7=12 < 13 → no current
        native, extinct = _roll_sophont(9, 3.0, [5, 5, 5, 5])
        assert native is False

    def test_current_sophont_exact_threshold_bio8(self):
        # bio=8: need 2D >= 12; roll 6+6=12 → 12+8-7=13 >= 13 → current
        native, extinct = _roll_sophont(8, 3.0, [6, 6])
        assert native is True
        assert extinct is False

    def test_no_current_sophont_bio8_roll11(self):
        # bio=8: need 2D >= 12; roll 5+6=11 → 11+8-7=12 < 13 → no current
        native, extinct = _roll_sophont(8, 3.0, [5, 6, 5, 5])
        assert native is False

    def test_biocomplexity_above_9_capped_at_9(self):
        # bio=12 behaves as bio=9; need 2D >= 11; roll 5+6=11 → current
        native, extinct = _roll_sophont(12, 3.0, [5, 6])
        assert native is True

    def test_extinct_sophont_when_current_fails(self):
        # bio=9, age=3.0 (no age DM): current fails (roll 5+5=10 < 11);
        # extinct: same threshold, roll 6+6=12 → 12+9-7=14 >= 13 → extinct
        native, extinct = _roll_sophont(9, 3.0, [5, 5, 6, 6])
        assert native is False
        assert extinct is True

    def test_extinct_check_skipped_when_current_found(self):
        # current succeeds on first 2 rolls; only 2 randint calls consumed
        native, extinct = _roll_sophont(9, 3.0, [6, 6])
        assert native is True
        assert extinct is False

    def test_extinct_age_dm_plus1_when_age_above_5(self):
        # bio=8, age=6.0 (DM+1): current fails (roll 5+6=11, need 12);
        # extinct: threshold = 20 - 8 - 1 = 11; roll 5+6=11 → 11+8-7+1=13 >= 13 → extinct
        native, extinct = _roll_sophont(8, 6.0, [5, 6, 5, 6])
        assert native is False
        assert extinct is True

    def test_extinct_no_age_dm_when_age_exactly_5(self):
        # age=5.0 is NOT > 5 → no DM; bio=8: current fails, extinct needs 2D >= 12
        # roll 5+6=11 for extinct → 11+8-7=12 < 13 → no extinct
        native, extinct = _roll_sophont(8, 5.0, [5, 6, 5, 6])
        assert native is False
        assert extinct is False

    def test_no_sophont_both_rolls_fail(self):
        # bio=9, age=3: current roll 5+5=10 → 12 < 13; extinct roll 4+5=9 → 11 < 13
        native, extinct = _roll_sophont(9, 3.0, [5, 5, 4, 5])
        assert native is False
        assert extinct is False


# ---------------------------------------------------------------------------
# Biodiversity Rating (WBH p.130)
# ---------------------------------------------------------------------------

def _roll_biodiversity(biomass: int, biocomplexity: int, rolls: list[int]) -> int:
    """Helper: patch randint to fixed values and call generate_biodiversity_rating."""
    it = iter(rolls)
    with patch("traveller_world_detail.random.randint", side_effect=lambda a, b: next(it)):
        return generate_biodiversity_rating(biomass, biocomplexity)


class TestBiodiversityRating:
    """Biodiversity rating formula: 2D − 7 + ⌈(biomass + biocomplexity) / 2⌉, min 0."""

    def test_minimum_is_zero(self):
        # rolls 1+1=2; bio=1, cx=1 → 2-7+ceil((1+1)/2)=2-7+1=−4 → clamped to 0
        assert _roll_biodiversity(1, 1, [1, 1]) == 0

    def test_biocomplexity_ceil_odd(self):
        # bio=1, cx=3 → ceil((1+3)/2)=ceil(2)=2; rolls 6+6=12 → 12-7+2=7
        assert _roll_biodiversity(1, 3, [6, 6]) == 7

    def test_biocomplexity_ceil_even(self):
        # bio=1, cx=4 → ceil((1+4)/2)=ceil(2.5)=3; rolls 12 → 12-7+3=8
        # bio=1, cx=6 → ceil((1+6)/2)=ceil(3.5)=4; rolls 12 → 12-7+4=9
        assert _roll_biodiversity(1, 4, [6, 6]) == 8
        assert _roll_biodiversity(1, 6, [6, 6]) == 9

    def test_high_biomass_raises_result(self):
        # rolls 4+3=7; bio=9, cx=9 → 7-7+ceil((9+9)/2)=0+9=9
        assert _roll_biodiversity(9, 9, [4, 3]) == 9

    def test_result_always_nonnegative_seed_sweep(self):
        for seed in range(50):
            random.seed(seed)
            result = generate_biodiversity_rating(1, 1)
            assert result >= 0

    def test_high_value_encodes_as_ehex(self):
        # Ensure biodiversity >= 10 produces a single eHex char in profile
        from traveller_world_gen import to_hex  # pylint: disable=import-outside-toplevel
        rating = _roll_biodiversity(9, 9, [6, 6])  # 12-7+ceil(9)=14
        assert len(to_hex(rating)) == 1


# ---------------------------------------------------------------------------
# Compatibility Rating (WBH p.130)
# ---------------------------------------------------------------------------

def _roll_compat(
    biocomplexity: int,
    atm: int,
    age_gyr: float,
    rolls: list[int],
    has_taint: bool = False,
) -> int:
    """Helper: patch randint and call generate_compatibility_rating."""
    it = iter(rolls)
    with patch("traveller_world_detail.random.randint", side_effect=lambda a, b: next(it)):
        return generate_compatibility_rating(biocomplexity, atm, age_gyr, has_taint)


class TestCompatibilityRating:
    """Compatibility rating: 2D − ⌊biocomplexity / 2⌋ + DMs, min 0."""

    def test_minimum_is_zero(self):
        # atm 12 (C) → DM-10; cx=9 → 9//2=4; rolls 1+1=2 → 2-4-10=-12 → 0
        assert _roll_compat(9, 12, 3.0, [1, 1]) == 0

    def test_biocomplexity_floor_div(self):
        # cx=3 → 3//2=1; cx=5 → 5//2=2
        # atm 6 (+2), age 3.0; rolls 6+6=12
        assert _roll_compat(3, 6, 3.0, [6, 6]) == 13   # 12-1+2=13
        assert _roll_compat(5, 6, 3.0, [6, 6]) == 12   # 12-2+2=12

    def test_atm_6_dm_plus2(self):
        # Standard atmosphere: best DM
        assert _ATM_COMPAT_DM[6] == 2

    def test_atm_0_dm_minus8(self):
        assert _ATM_COMPAT_DM[0] == -8

    def test_atm_12_insidious_dm_minus10(self):
        assert _ATM_COMPAT_DM[12] == -10

    def test_age_over_8_gyr_applies_dm(self):
        # atm 6 (+2), cx=1 (floor 0); rolls 6+6=12
        # age 3.0 → no age DM → 12+2=14
        # age 9.0 → DM-2 → 12+2-2=12
        assert _roll_compat(1, 6, 3.0, [6, 6]) == 14
        assert _roll_compat(1, 6, 9.0, [6, 6]) == 12

    def test_otherwise_tainted_applies_when_not_inherent(self):
        # atm 13 (D) → DM-1; has_taint=True, atm not in {2,4,7,9} → extra DM-2
        # cx=1 (floor 0); rolls 6+6=12 → 12-1-2=-3 → 9
        without = _roll_compat(1, 13, 3.0, [6, 6], has_taint=False)
        with_taint = _roll_compat(1, 13, 3.0, [6, 6], has_taint=True)
        assert without == 11   # 12-1=11
        assert with_taint == 9  # 12-1-2=9

    def test_otherwise_tainted_not_double_counted_for_inherent(self):
        # atm 7 is already DM-2 in the table; has_taint on an inherent code
        # should NOT add another DM-2.
        assert 7 in _INHERENT_TAINTED_CODES
        without = _roll_compat(1, 7, 3.0, [6, 6], has_taint=False)
        with_taint = _roll_compat(1, 7, 3.0, [6, 6], has_taint=True)
        assert without == with_taint  # identical: DM not applied twice

    def test_lifeform_profile_four_ehex_chars(self):
        # Roll a world with known biomass/biocomplexity/biodiversity/compatibility
        # and verify the profile string is exactly 4 eHex characters.
        from traveller_world_gen import to_hex  # pylint: disable=import-outside-toplevel
        bio = 5
        cx = 3
        div = _roll_biodiversity(bio, cx, [4, 4])   # 8-7+ceil((5+3)/2)=1+4=5
        comp = _roll_compat(cx, 6, 3.0, [4, 4])    # 8-1+2=9
        profile = f"{to_hex(bio)}{to_hex(cx)}{to_hex(div)}{to_hex(comp)}"
        assert len(profile) == 4
        for ch in profile:
            assert ch in "0123456789ABCDEFGHIJ"

    def test_biomass_zero_fields_are_none(self):
        # The _apply_biomass() guard means no calls happen for biomass=0;
        # verify the World fields are None by default.
        from traveller_world_gen import World  # pylint: disable=import-outside-toplevel
        w = World(
            name="Test", size=6, atmosphere=6, temperature="Temperate",
            hydrographics=5, population=0, government=0, law_level=0,
            starport="X", tech_level=0, has_gas_giant=False,
            gas_giant_count=0, belt_count=0, population_multiplier=0,
            bases=[], trade_codes=[], travel_zone="Green", notes=[],
        )
        assert w.biodiversity_rating is None
        assert w.compatibility_rating is None
        assert w.lifeform_profile is None

    def test_from_dict_restores_all_three_fields(self):
        from traveller_world_gen import World  # pylint: disable=import-outside-toplevel
        d = {
            "name": "X", "size": 6, "atmosphere": 6, "temperature": "Temperate",
            "hydrographics": 5, "population": 5, "government": 3, "law_level": 2,
            "starport": "C", "tech_level": 8, "has_gas_giant": False,
            "gas_giant_count": 0, "belt_count": 0, "population_multiplier": 5,
            "bases": [], "trade_codes": [], "travel_zone": "Green", "notes": [],
            "biomass_rating": 4, "biocomplexity_rating": 3,
            "biodiversity_rating": 7, "compatibility_rating": 9,
            "lifeform_profile": "4379",
        }
        w = World.from_dict(d)
        assert w.biodiversity_rating == 7
        assert w.compatibility_rating == 9
        assert w.lifeform_profile == "4379"


# ---------------------------------------------------------------------------
# NHZ atmosphere codes 16 (G) and 17 (H) — biomass, biocomplexity, compatibility
# Issue #112 — confirm DM tables handle non-HZ atmosphere codes correctly.
# ---------------------------------------------------------------------------

class TestNHZAtmosphereCodes:
    """NHZ atmosphere codes 16 (G — helium) and 17 (H — hydrogen).

    Biomass/biocomplexity: both clamped to code 15 (F) via min(atm, 15).
    Compatibility: explicit -8 entries in _ATM_COMPAT_DM (same as vacuum/trace).
    """

    # Biomass clamping -------------------------------------------------------

    def test_atm_h17_biomass_treated_as_f15(self):
        """Code 17 (H) gives the same biomass result as code 15 (F)."""
        result_15 = _roll_biomass(15, 5, 3.0, "temperate")
        result_17 = _roll_biomass(17, 5, 3.0, "temperate")
        assert result_15 == result_17

    def test_atm_g16_sc2_clamped_to_f15(self):
        # dice=7, atm 16→15 (DM-5), hydro=5 (DM 0), age=3, temperate (+2)
        # pre-SC2: 7-5+2=4; SC2: atm_key=15 in SC2_SET, add 4 → 4+4=8
        assert _roll_biomass(16, 5, 3.0, "temperate") == 8

    def test_atm_h17_sc2_clamped_to_f15(self):
        assert _roll_biomass(17, 5, 3.0, "temperate") == 8

    # Biocomplexity DM -------------------------------------------------------

    def test_atm_g16_biocomplexity_not_in_4_9_range(self):
        # biomass=5, dice=7: base=5; atm 16 not in [4,9] → DM-2; age 5.0 → no age DM
        assert _roll_biocomplexity(5, 16, 5.0) == 3

    def test_atm_h17_biocomplexity_dm_minus2(self):
        assert _roll_biocomplexity(5, 17, 5.0) == 3

    # Compatibility table entries --------------------------------------------

    def test_atm_g16_compat_dm_minus8(self):
        """Code 16 (G — helium gas) has explicit DM-8 in _ATM_COMPAT_DM."""
        assert _ATM_COMPAT_DM[16] == -8

    def test_atm_h17_compat_dm_minus8(self):
        """Code 17 (H — hydrogen gas) has explicit DM-8 in _ATM_COMPAT_DM."""
        assert _ATM_COMPAT_DM[17] == -8

    def test_atm_g16_compat_matches_vacuum(self):
        """NHZ helium atmosphere is as hostile to compatibility as vacuum."""
        assert _ATM_COMPAT_DM[16] == _ATM_COMPAT_DM[0]

    def test_atm_h17_compat_matches_vacuum(self):
        assert _ATM_COMPAT_DM[17] == _ATM_COMPAT_DM[0]

    def test_atm_g16_compat_integration(self):
        # cx=5, age=3.0, rolls 6+6=12: base=12-(5//2)=10; DM-8 → max(0,2)=2
        assert _roll_compat(5, 16, 3.0, [6, 6]) == 2

    def test_atm_h17_compat_integration(self):
        assert _roll_compat(5, 17, 3.0, [6, 6]) == 2

    def test_atm_g16_not_inherent_tainted(self):
        """Code 16 is not inherently tainted; otherwise-tainted DM-2 can apply."""
        assert 16 not in _INHERENT_TAINTED_CODES

    def test_atm_h17_not_inherent_tainted(self):
        assert 17 not in _INHERENT_TAINTED_CODES


# ---------------------------------------------------------------------------
# Worlds far outside the habitable zone (hz_deviation >= 3 or <= -3)
# Issue #112 — biomass is always 0 for vacuum/trace/NHZ worlds in frozen or
# boiling zones, whether the simplified zone path or the K-temperature path
# is used.
# ---------------------------------------------------------------------------

class TestExtremeHZDeviationWorlds:
    """Biomass for worlds with large HZ offsets and hostile atmospheres."""

    # Simplified zone path (no temperature K data) --------------------------

    def test_frozen_vacuum_always_lifeless(self):
        # atm 0 (-6), hydro 0 (-4), frozen (-6) → DM-16 clamped -12; 12-12=0
        assert _roll_biomass(0, 0, 3.0, "frozen", dice_total=12) == 0

    def test_frozen_trace_always_lifeless(self):
        # atm 1 (-4), hydro 0 (-4), frozen (-6) → DM-14 clamped -12; 12-12=0
        assert _roll_biomass(1, 0, 3.0, "frozen", dice_total=12) == 0

    def test_boiling_vacuum_always_lifeless(self):
        assert _roll_biomass(0, 0, 3.0, "boiling", dice_total=12) == 0

    def test_boiling_trace_always_lifeless(self):
        assert _roll_biomass(1, 0, 3.0, "boiling", dice_total=12) == 0

    def test_frozen_nhz_atm16_always_lifeless(self):
        # atm 16 (→15, DM-5), hydro 0 (-4), frozen (-6) → DM-15 clamped -12; 12-12=0
        assert _roll_biomass(16, 0, 3.0, "frozen", dice_total=12) == 0

    def test_frozen_nhz_atm17_always_lifeless(self):
        assert _roll_biomass(17, 0, 3.0, "frozen", dice_total=12) == 0

    def test_boiling_nhz_atm16_always_lifeless(self):
        assert _roll_biomass(16, 0, 3.0, "boiling", dice_total=12) == 0

    def test_boiling_nhz_atm17_always_lifeless(self):
        assert _roll_biomass(17, 0, 3.0, "boiling", dice_total=12) == 0

    # K-temperature path (mainworld with WorldPhysical advanced temp data) --

    def test_very_cold_vacuum_lifeless_k_path(self):
        # mean_temp_k=50 (<273): high DM-4, mean DM-2; atm 0 (-6), hydro 0 (-4)
        # total -16 clamped -12; 12-12=0
        assert _roll_biomass(0, 0, 3.0, "frozen",
                              mean_temp_k=50, dice_total=12) == 0

    def test_very_hot_vacuum_lifeless_k_path(self):
        # mean_temp_k=700 (>353): high DM-2, mean DM-4; atm 0 (-6), hydro 0 (-4)
        # total -16 clamped -12; 12-12=0
        assert _roll_biomass(0, 0, 3.0, "boiling",
                              mean_temp_k=700, dice_total=12) == 0

    def test_very_cold_nhz_atm_lifeless_k_path(self):
        # atm 16 (→15, DM-5), hydro 0 (-4), very cold (-4 high, -2 mean)
        # total -15 clamped -12; 12-12=0
        assert _roll_biomass(16, 0, 3.0, "frozen",
                              mean_temp_k=50, dice_total=12) == 0

    def test_very_hot_nhz_atm_lifeless_k_path(self):
        assert _roll_biomass(17, 0, 3.0, "boiling",
                              mean_temp_k=1200, dice_total=12) == 0

    # Seed sweeps -----------------------------------------------------------

    def test_frozen_world_biomass_never_negative_seed_sweep(self):
        for seed in range(50):
            random.seed(seed)
            assert generate_biomass_rating(0, 0, 3.0, "frozen") >= 0

    def test_boiling_world_biomass_never_negative_seed_sweep(self):
        for seed in range(50):
            random.seed(seed)
            assert generate_biomass_rating(0, 0, 3.0, "boiling") >= 0


# ---------------------------------------------------------------------------
# atmosphere_detail = None guard conditions (issue #112)
# Guards in _apply_biomass when mainworld.atmosphere_detail is None: NHZ
# mainworlds and worlds outside the HZ may have None when atmosphere detail
# was not generated or the code produces no taint object.
# ---------------------------------------------------------------------------

class TestAtmosphereDetailNoneGuard:
    """atmosphere_detail = None does not crash _apply_biomass and defaults
    biologic/has_taint/has_low_o all to False."""

    def test_biologic_guard_false_when_none(self):
        """biologic taint defaults to False when atmosphere_detail is None."""
        atmosphere_detail = None
        biologic = any(
            getattr(t, "subtype", "") == "Biologic"
            for t in (atmosphere_detail.taints if atmosphere_detail else [])
        )
        assert biologic is False

    def test_has_low_o_guard_false_when_none(self):
        """has_low_o defaults to False when atmosphere_detail is None."""
        atmosphere_detail = None
        has_low_o = any(
            getattr(t, "subtype_code", "") == "L"
            for t in (atmosphere_detail.taints if atmosphere_detail else [])
        )
        assert has_low_o is False

    def test_has_taint_guard_false_when_none(self):
        """has_taint is False when atmosphere_detail is None."""
        atmosphere_detail = None
        has_taint = bool(atmosphere_detail and atmosphere_detail.taints)
        assert has_taint is False

    def test_apply_biomass_no_crash_with_none_atmosphere_detail(self):
        """_apply_biomass runs without error when atmosphere_detail is None."""
        from traveller_system_gen import generate_full_system    # pylint: disable=import-outside-toplevel
        from traveller_world_physical import generate_world_physical  # pylint: disable=import-outside-toplevel
        system = None
        for seed in range(100):
            s = generate_full_system(seed=seed)
            if s.mainworld is not None and s.mainworld.size > 0:
                system = s
                break
        assert system is not None
        mw = system.mainworld
        mw_orbit = system.mainworld_orbit
        # generate_world_physical sets size_detail (WorldPhysical with mean_temperature_k)
        mw.size_detail = generate_world_physical(
            mw,
            age_gyr=system.stellar_system.primary.age_gyr,
            hz_deviation=mw_orbit.hz_deviation if mw_orbit else None,
        )
        mw.atmosphere_detail = None
        _apply_biomass(system)          # must not raise
        assert mw.biomass_rating is not None

    def test_biomass_zero_leaves_downstream_fields_none(self):
        """When _apply_biomass produces biomass_rating == 0, biodiversity/
        compatibility/lifeform_profile remain None."""
        from traveller_system_gen import generate_full_system    # pylint: disable=import-outside-toplevel
        from traveller_world_physical import generate_world_physical  # pylint: disable=import-outside-toplevel
        system = None
        for seed in range(100):
            s = generate_full_system(seed=seed)
            if s.mainworld is not None and s.mainworld.size > 0:
                system = s
                break
        assert system is not None
        mw = system.mainworld
        assert mw is not None
        mw_orbit = system.mainworld_orbit
        mw.size_detail = generate_world_physical(
            mw,
            age_gyr=system.stellar_system.primary.age_gyr,
            hz_deviation=mw_orbit.hz_deviation if mw_orbit else None,
        )
        # Force lifeless conditions: vacuum, no water, no taint info
        mw.atmosphere = 0
        mw.hydrographics = 0
        mw.atmosphere_detail = None
        mw.biodiversity_rating = None
        mw.compatibility_rating = None
        mw.lifeform_profile = None
        # dice=1+1=2 with atm 0 (DM-6), hydro 0 (DM-4) guarantees biomass=0
        with patch("traveller_world_detail.random.randint", return_value=1):
            _apply_biomass(system)
        assert mw.biomass_rating == 0
        assert mw.biodiversity_rating is None
        assert mw.compatibility_rating is None
        assert mw.lifeform_profile is None


# ---------------------------------------------------------------------------
# Optional inhospitable rule (WBH p.130 Suggested Usage)
# ---------------------------------------------------------------------------

class TestOptionalInhospitableRule:
    """
    When optional_inhospitable_rule=True, out-of-HZ secondary terrestrial worlds
    are deferred to a single 2D group roll; only a natural 12 allows one randomly
    chosen world a normal biomass roll — all others receive biomass_rating = 0.
    """

    # ---- minimal mock factories ----

    @staticmethod
    def _make_system(orbits):
        """Return a minimal mock TravellerSystem for _apply_biomass."""
        system = MagicMock()
        system.mainworld = None
        system.stellar_system.primary.age_gyr = 3.0
        system.system_orbits.orbits = orbits
        return system

    @staticmethod
    def _make_orbit(sah="000", is_hz=False, temp_zone="frozen", is_main=False):
        """Return a mock non-gas-giant, non-belt secondary orbit slot."""
        orbit = MagicMock()
        orbit.world_type = "terrestrial"
        orbit.is_mainworld_candidate = is_main
        orbit.is_habitable_zone = is_hz
        orbit.temperature_zone = temp_zone
        orbit.detail = MagicMock()
        orbit.detail.sah = sah
        orbit.detail.moons = []
        orbit.detail.biomass_rating = None
        return orbit

    @staticmethod
    def _make_moon(sah="000"):
        """Return a non-ring mock moon with a writable detail stub."""
        moon = MagicMock()
        moon.is_ring = False
        moon.detail = MagicMock()
        moon.detail.sah = sah
        moon.detail.biomass_rating = None
        return moon

    # ---- rule disabled (default) ----

    def test_rule_disabled_nhz_world_rolls_individually(self):
        """With rule off, each out-of-HZ world rolls its biomass independently
        (exactly 2 random.randint calls; no group roll is made)."""
        orbit = self._make_orbit(sah="000", is_hz=False, temp_zone="frozen")
        system = self._make_system([orbit])
        with patch("traveller_world_detail.random.randint", return_value=1) as mock_roll:
            _apply_biomass(system)
        # 2 calls = 1 biomass 2D; no group-roll calls
        assert mock_roll.call_count == 2
        assert orbit.detail.biomass_rating == 0  # atm0/hydro0/frozen DMs → always 0

    # ---- rule enabled, group roll < 12 ----

    def test_rule_on_non12_all_nhz_worlds_get_zero(self):
        """Group roll 7 (< 12): every out-of-HZ world is zeroed; no individual dice."""
        orbits = [
            self._make_orbit(sah="000", is_hz=False),
            self._make_orbit(sah="880", is_hz=False, temp_zone="temperate"),
        ]
        system = self._make_system(orbits)
        with patch("traveller_world_detail.random.randint",
                   side_effect=[3, 4]) as mock_roll:
            _apply_biomass(system, optional_inhospitable_rule=True)
        assert mock_roll.call_count == 2          # group roll only
        assert orbits[0].detail.biomass_rating == 0
        assert orbits[1].detail.biomass_rating == 0

    def test_rule_on_non12_hz_world_unaffected(self):
        """Group roll < 12 does not affect in-HZ worlds; they are still rolled."""
        nhz  = self._make_orbit(sah="000", is_hz=False)
        hz   = self._make_orbit(sah="880", is_hz=True, temp_zone="temperate")
        system = self._make_system([nhz, hz])
        # Loop processes nhz (→ _inhospitable), then hz (→ _roll_world_and_moons).
        # After the loop: group roll for _inhospitable.
        # bc=14≥8 → sophont check (6,6 → current_roll=14≥13 → 2 dice only)
        # Order: [hz_bio*2, hz_bc*2, hz_sophont*2, group*2]
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6, 6, 6, 1, 1]):
            _apply_biomass(system, optional_inhospitable_rule=True)
        assert nhz.detail.biomass_rating == 0
        # SAH "880" → atm=8(DM+2), hydro=0(DM-4), temperate(DM+2), net DM=0
        # dice 6+6=12, rolled=12 → biomass 12
        assert hz.detail.biomass_rating == 12

    # ---- rule enabled, natural 12 ----

    def test_rule_on_natural12_winner_gets_biomass_roll(self):
        """Natural 12: the selected world receives a normal biomass roll."""
        winner = self._make_orbit(sah="880", is_hz=False, temp_zone="temperate")
        loser  = self._make_orbit(sah="000", is_hz=False)
        system = self._make_system([winner, loser])
        # [group*2, winner_bio*2, winner_bc*2, winner_sophont*2]
        # bc=14≥8 → sophont check (6,6 → current_roll=14≥13 → 2 dice only)
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6, 6, 6, 6, 6]):
            with patch("traveller_world_detail.random.randrange", return_value=0):
                _apply_biomass(system, optional_inhospitable_rule=True)
        # SAH "880" → atm=8(DM+2), hydro=0(DM-4), temperate(DM+2), net DM=0 → biomass 12
        assert winner.detail.biomass_rating == 12
        assert loser.detail.biomass_rating == 0

    def test_rule_on_natural12_loser_gets_zero_not_rolled(self):
        """Natural 12: the losing world is zeroed directly (no biomass 2D for it)."""
        winner = self._make_orbit(sah="000", is_hz=False)   # biomass=0 if rolled
        loser  = self._make_orbit(sah="880", is_hz=False, temp_zone="temperate")
        system = self._make_system([winner, loser])
        # winner's biomass=0 → no biocomplexity; loser is zeroed without dice.
        # Exactly 4 calls: 2 group + 2 winner biomass.
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6]) as mock_roll:
            with patch("traveller_world_detail.random.randrange", return_value=0):
                _apply_biomass(system, optional_inhospitable_rule=True)
        assert mock_roll.call_count == 4   # no extra dice for loser
        assert loser.detail.biomass_rating == 0

    def test_rule_on_natural12_winner_moons_get_rolled(self):
        """Natural 12: the winner's moons receive biomass rolls alongside it."""
        moon   = self._make_moon(sah="880")
        winner = self._make_orbit(sah="880", is_hz=False, temp_zone="temperate")
        winner.detail.moons = [moon]
        loser  = self._make_orbit(sah="000", is_hz=False)
        system = self._make_system([winner, loser])
        # [group*2, winner_bio*2, winner_bc*2, winner_sophont*2, moon_bio*2, moon_bc*2, moon_sophont*2]
        # bc=14≥8 for both winner and moon → sophont check (6,6 → 2 dice each)
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6]):
            with patch("traveller_world_detail.random.randrange", return_value=0):
                _apply_biomass(system, optional_inhospitable_rule=True)
        # moon SAH "880" → atm=8(DM+2), hydro=0(DM-4), temperate(DM+2), net DM=0 → biomass 12
        assert moon.detail.biomass_rating == 12

    def test_rule_on_natural12_loser_moons_get_zero(self):
        """Natural 12: a losing world's moons receive biomass_rating = 0."""
        moon  = self._make_moon(sah="880")
        loser = self._make_orbit(sah="880", is_hz=False, temp_zone="temperate")
        loser.detail.moons = [moon]
        winner = self._make_orbit(sah="000", is_hz=False)
        system = self._make_system([winner, loser])
        # winner biomass=0 (atm0/frozen/dice12 → 0); no biocomplexity; loser zeroed.
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6]):
            with patch("traveller_world_detail.random.randrange", return_value=0):
                _apply_biomass(system, optional_inhospitable_rule=True)
        assert moon.detail.biomass_rating == 0

    # ---- edge case: no NHZ secondary worlds ----

    def test_no_nhz_worlds_no_group_roll(self):
        """With no out-of-HZ secondary worlds the group roll is never made."""
        in_hz = self._make_orbit(sah="880", is_hz=True, temp_zone="temperate")
        system = self._make_system([in_hz])
        # In-HZ world: bio (2) + biocomplexity (2) + sophont check (2) = 6 calls.
        # bc=14≥8 → sophont check with (6,6 → current_roll=14≥13 → 2 dice only).
        # If a group roll were wrongly made it would consume 2 extra calls.
        with patch("traveller_world_detail.random.randint",
                   side_effect=[6, 6, 6, 6, 6, 6]) as mock_roll:
            _apply_biomass(system, optional_inhospitable_rule=True)
        assert mock_roll.call_count == 6
        # SAH "880" temperate: net DM=0, dice 6+6=12 → biomass 12
        assert in_hz.detail.biomass_rating == 12

    # ---- attach_detail flag pass-through ----

    def test_attach_detail_passes_inhospitable_flag(self):
        """attach_detail() forwards optional_inhospitable_rule to _apply_biomass."""
        from traveller_system_gen import generate_full_system  # pylint: disable=import-outside-toplevel
        system = generate_full_system(seed=0)
        with patch("traveller_world_detail._apply_biomass") as mock_apply:
            attach_detail(system, optional_inhospitable_rule=True)
        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs.get("optional_inhospitable_rule") is True
