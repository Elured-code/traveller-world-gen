"""
pytest unit tests for generate_habitability_rating() (WBH p.131).
"""
import pytest
from traveller_gen.traveller_world_detail import generate_habitability_rating


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hab(
    size=6, atmosphere=6, hydrographics=7,
    gravity=1.0, tidal_status="none",
    has_low_oxygen_taint=False,
    advanced_mean_temperature_k=None,
    high_temperature_k=None,
    low_temperature_k=None,
    temperature_category=None,
) -> int:
    return generate_habitability_rating(
        size=size,
        atmosphere=atmosphere,
        hydrographics=hydrographics,
        gravity=gravity,
        tidal_status=tidal_status,
        has_low_oxygen_taint=has_low_oxygen_taint,
        advanced_mean_temperature_k=advanced_mean_temperature_k,
        high_temperature_k=high_temperature_k,
        low_temperature_k=low_temperature_k,
        temperature_category=temperature_category,
    )


# ---------------------------------------------------------------------------
# Base value
# ---------------------------------------------------------------------------

class TestBaseValue:
    def test_ideal_world_is_10(self):
        """Size 6, atm 6, hydro 7, gravity 1.0, temperate: no DMs → 10."""
        assert _hab() == 10


# ---------------------------------------------------------------------------
# Size DMs
# ---------------------------------------------------------------------------

class TestSizeDMs:
    def test_size_0_dm_minus1(self):
        assert _hab(size=0) == 9   # size 0 ≤ 4 → DM-1

    def test_size_4_dm_minus1(self):
        assert _hab(size=4) == 9

    def test_size_5_no_dm(self):
        assert _hab(size=5) == 10

    def test_size_8_no_dm(self):
        assert _hab(size=8) == 10

    def test_size_9_dm_plus1(self):
        assert _hab(size=9) == 11

    def test_size_15_dm_plus1(self):
        assert _hab(size=15) == 11


# ---------------------------------------------------------------------------
# Atmosphere DMs
# ---------------------------------------------------------------------------

class TestAtmosphereDMs:
    def test_atm_6_no_dm(self):
        assert _hab(atmosphere=6) == 10

    def test_atm_0_dm_minus8(self):
        assert _hab(atmosphere=0) == 2      # 10 - 8

    def test_atm_1_dm_minus8(self):
        assert _hab(atmosphere=1) == 2

    def test_atm_A_dm_minus8(self):
        assert _hab(atmosphere=10) == 2     # A = exotic

    def test_atm_2_dm_minus4(self):
        assert _hab(atmosphere=2) == 6

    def test_atm_E_dm_minus4(self):
        assert _hab(atmosphere=14) == 6     # E = low

    def test_atm_3_dm_minus3(self):
        assert _hab(atmosphere=3) == 7

    def test_atm_D_dm_minus3(self):
        assert _hab(atmosphere=13) == 7     # D = very dense

    def test_atm_4_dm_minus2(self):
        assert _hab(atmosphere=4) == 8

    def test_atm_9_dm_minus2(self):
        assert _hab(atmosphere=9) == 8

    def test_atm_5_dm_minus1(self):
        assert _hab(atmosphere=5) == 9

    def test_atm_7_dm_minus1(self):
        assert _hab(atmosphere=7) == 9

    def test_atm_8_dm_minus1(self):
        assert _hab(atmosphere=8) == 9

    def test_atm_B_dm_minus10(self):
        assert _hab(atmosphere=11) == 0     # 10 - 10 = 0

    def test_atm_C_dm_minus12(self):
        assert _hab(atmosphere=12) == 0     # clamped at 0

    def test_atm_F_dm_minus12(self):
        assert _hab(atmosphere=15) == 0

    def test_atm_G_dm_minus12(self):
        assert _hab(atmosphere=16) == 0     # NHZ helium gas

    def test_atm_H_dm_minus12(self):
        assert _hab(atmosphere=17) == 0     # NHZ hydrogen gas

    def test_low_oxygen_taint_adds_dm_minus2(self):
        # Atm 8 (DM-1) + low oxygen (DM-2) = DM-3 → 7
        assert _hab(atmosphere=8, has_low_oxygen_taint=True) == 7

    def test_low_oxygen_on_standard_atm(self):
        # Atm 6 (DM 0) + low oxygen (DM-2) → 8
        assert _hab(atmosphere=6, has_low_oxygen_taint=True) == 8


# ---------------------------------------------------------------------------
# Hydrographics DMs
# ---------------------------------------------------------------------------

class TestHydrographicsDMs:
    def test_hydro_0_dm_minus4(self):
        assert _hab(hydrographics=0) == 6

    def test_hydro_1_dm_minus2(self):
        assert _hab(hydrographics=1) == 8

    def test_hydro_3_dm_minus2(self):
        assert _hab(hydrographics=3) == 8

    def test_hydro_4_no_dm(self):
        assert _hab(hydrographics=4) == 10

    def test_hydro_8_no_dm(self):
        assert _hab(hydrographics=8) == 10

    def test_hydro_9_dm_minus1(self):
        assert _hab(hydrographics=9) == 9

    def test_hydro_A_dm_minus2(self):
        assert _hab(hydrographics=10) == 8


# ---------------------------------------------------------------------------
# Tidal lock DM
# ---------------------------------------------------------------------------

class TestTidalLockDM:
    def test_1_1_lock_dm_minus2(self):
        assert _hab(tidal_status="1:1_lock") == 8

    def test_no_lock_no_dm(self):
        assert _hab(tidal_status="none") == 10

    def test_prograde_no_dm(self):
        assert _hab(tidal_status="prograde") == 10


# ---------------------------------------------------------------------------
# Temperature DMs — full path
# ---------------------------------------------------------------------------

class TestTemperatureDMsFullPath:
    def test_high_temp_above_323_dm_minus2(self):
        # mean 290K (no DM), high 330K (>323) → DM-2
        assert _hab(advanced_mean_temperature_k=290, high_temperature_k=330) == 8

    def test_high_temp_below_279_dm_minus2(self):
        # mean 250K (<273 → DM-2), high 270K (<279 → DM-2) → DM-4
        assert _hab(advanced_mean_temperature_k=250, high_temperature_k=270) == 6

    def test_mean_above_323_dm_minus4(self):
        assert _hab(advanced_mean_temperature_k=330) == 6

    def test_mean_304_to_323_dm_minus2(self):
        assert _hab(advanced_mean_temperature_k=310) == 8

    def test_mean_304_boundary_dm_minus2(self):
        assert _hab(advanced_mean_temperature_k=304) == 8

    def test_mean_323_boundary_dm_minus2(self):
        # 323 is ≥ 304 and ≤ 323: DM-2 (not >323 DM-4)
        assert _hab(advanced_mean_temperature_k=323) == 8

    def test_mean_above_323_not_also_304_band(self):
        # >323 gives DM-4 only (the elif prevents double-counting)
        assert _hab(advanced_mean_temperature_k=350) == 6

    def test_mean_below_273_dm_minus2(self):
        assert _hab(advanced_mean_temperature_k=260) == 8

    def test_low_temp_below_200_dm_minus2(self):
        # mean 280K (no DM), low 190K (<200) → DM-2
        assert _hab(advanced_mean_temperature_k=280, low_temperature_k=190) == 8

    def test_multiple_temp_dms_stack(self):
        # mean 330K (>323 → DM-4), high 340K (>323 → DM-2), low 150K (<200 → DM-2)
        # total temp DM = -8, base 10 → 2
        assert _hab(
            advanced_mean_temperature_k=330,
            high_temperature_k=340,
            low_temperature_k=150,
        ) == 2

    def test_temperate_no_temp_dm(self):
        # all temps in comfortable range
        assert _hab(
            advanced_mean_temperature_k=288,
            high_temperature_k=300,
            low_temperature_k=270,
        ) == 10


# ---------------------------------------------------------------------------
# Temperature DMs — fallback path
# ---------------------------------------------------------------------------

class TestTemperatureDMsFallback:
    def test_frozen_dm_minus6(self):
        assert _hab(temperature_category="Frozen") == 4

    def test_boiling_dm_minus6(self):
        assert _hab(temperature_category="Boiling") == 4

    def test_cold_dm_minus2(self):
        assert _hab(temperature_category="Cold") == 8

    def test_hot_dm_minus2(self):
        assert _hab(temperature_category="Hot") == 8

    def test_temperate_no_dm(self):
        assert _hab(temperature_category="Temperate") == 10

    def test_category_case_insensitive(self):
        assert _hab(temperature_category="frozen") == 4
        assert _hab(temperature_category="BOILING") == 4

    def test_advanced_temp_takes_precedence_over_category(self):
        # Both provided: advanced_mean_temperature_k used, category ignored.
        # mean=288 → no DM, "Frozen" would give DM-6 but is ignored.
        assert _hab(
            advanced_mean_temperature_k=288,
            temperature_category="Frozen",
        ) == 10


# ---------------------------------------------------------------------------
# Gravity DMs
# ---------------------------------------------------------------------------

class TestGravityDMs:
    def test_gravity_1_0_no_dm(self):
        assert _hab(gravity=1.0) == 10

    def test_gravity_1_05_no_dm(self):
        assert _hab(gravity=1.05) == 10

    # Below 0.2 → DM-4
    def test_gravity_0_1_dm_minus4(self):
        assert _hab(gravity=0.1) == 6

    def test_gravity_0_2_boundary_dm_minus4(self):
        # At 0.2: worst DM is DM-4 (from the <0.2 range)
        assert _hab(gravity=0.2) == 6

    # 0.2 < g ≤ 0.4 → DM-2
    def test_gravity_0_3_dm_minus2(self):
        assert _hab(gravity=0.3) == 8

    def test_gravity_0_4_boundary_dm_minus2(self):
        # At 0.4: worst DM is DM-2
        assert _hab(gravity=0.4) == 8

    # 0.4 < g ≤ 0.7 → DM-1
    def test_gravity_0_5_dm_minus1(self):
        assert _hab(gravity=0.5) == 9

    def test_gravity_0_7_boundary_dm_minus1(self):
        # At 0.7: worst DM between DM-1 and DM+1 is DM-1
        assert _hab(gravity=0.7) == 9

    # 0.7 < g < 0.9 → DM+1
    def test_gravity_0_8_dm_plus1(self):
        assert _hab(gravity=0.8) == 11

    def test_gravity_0_9_boundary_no_dm(self):
        # At 0.9: worst DM between DM+1 and DM 0 is DM 0
        assert _hab(gravity=0.9) == 10

    # 0.9 ≤ g < 1.1 → DM 0
    def test_gravity_1_0_no_dm_range(self):
        assert _hab(gravity=1.0) == 10

    def test_gravity_1_1_boundary_dm_minus1(self):
        # At 1.1: worst DM between DM 0 and DM-1 is DM-1
        assert _hab(gravity=1.1) == 9

    # 1.1 < g < 1.4 → DM-1
    def test_gravity_1_2_dm_minus1(self):
        assert _hab(gravity=1.2) == 9

    def test_gravity_1_4_boundary_dm_minus3(self):
        # At 1.4: worst DM between DM-1 and DM-3 is DM-3
        assert _hab(gravity=1.4) == 7

    # 1.4 ≤ g < 2.0 → DM-3
    def test_gravity_1_8_dm_minus3(self):
        assert _hab(gravity=1.8) == 7

    def test_gravity_2_0_boundary_dm_minus6(self):
        # At 2.0: worst DM between DM-3 and DM-6 is DM-6
        assert _hab(gravity=2.0) == 4

    # g ≥ 2.0 → DM-6
    def test_gravity_3_0_dm_minus6(self):
        assert _hab(gravity=3.0) == 4


# ---------------------------------------------------------------------------
# Undefined gravity (gravity=None)
# ---------------------------------------------------------------------------

class TestUndefinedGravity:
    def test_size_6_undefined_gravity(self):
        # DM = 1 - |6 - 6| = 1 → 11
        assert _hab(gravity=None, size=6) == 11

    def test_size_5_undefined_gravity(self):
        # DM = 1 - |6 - 5| = 0 → 10
        assert _hab(gravity=None, size=5) == 10

    def test_size_7_undefined_gravity(self):
        # DM = 1 - |6 - 7| = 0 → 10
        assert _hab(gravity=None, size=7) == 10

    def test_size_0_undefined_gravity(self):
        # DM = 1 - |6 - 0| = -5; also size ≤ 4 → DM-1; total DM-6 → 4
        assert _hab(gravity=None, size=0) == 4

    def test_size_9_undefined_gravity(self):
        # DM = 1 - |6 - 9| = -2; size ≥ 9 → DM+1; total DM-1 → 9
        assert _hab(gravity=None, size=9) == 9


# ---------------------------------------------------------------------------
# Minimum clamp
# ---------------------------------------------------------------------------

class TestMinimumClamp:
    def test_result_never_below_zero(self):
        # Atm B (DM-10) + hydro 0 (DM-4) → 10 - 14 = -4 → clamped to 0
        assert _hab(atmosphere=11, hydrographics=0) == 0

    def test_heavily_penalised_world_is_zero(self):
        # Atm C (DM-12) + all other bad factors
        assert _hab(atmosphere=12, hydrographics=0, gravity=3.0) == 0


# ---------------------------------------------------------------------------
# Integration: DMs stack correctly
# ---------------------------------------------------------------------------

class TestDMsStack:
    def test_composite_standard_world(self):
        # size 6 (0), atm 6 (0), hydro 6 (0), gravity 1.0 (0),
        # mean 288K (0) → 10
        assert _hab(
            size=6, atmosphere=6, hydrographics=6, gravity=1.0,
            advanced_mean_temperature_k=288,
        ) == 10

    def test_thin_atm_dry_low_gravity(self):
        # atm 5 (DM-1), hydro 0 (DM-4), gravity 0.3 (DM-2) → 10 - 7 = 3
        assert _hab(atmosphere=5, hydrographics=0, gravity=0.3) == 3
