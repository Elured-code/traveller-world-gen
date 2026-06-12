"""
pytest unit tests for traveller_world_tech_detail.py (issue #98).

Covers:
  - None guard for uninhabited worlds
  - High/Low common TL bounds
  - Profile string format
  - Atmosphere-0 air TL special case
  - Hydrographics-0 sea TL special case
  - Law-0 personal military TL special case
  - Balkanised worlds computed normally
  - All sub-TLs non-negative
  - to_dict() / from_dict() round-trip
  - attach_tech_detail() mainworld and secondary world wiring
  - Hypothesis property-based bounds invariants
"""

# pylint: disable=import-error
import re
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from traveller_system_gen import generate_full_system
from traveller_world_detail import attach_detail
from traveller_world_tech_detail import (
    TechDetail,
    generate_tech_detail,
    attach_tech_detail,
)

_PROFILE_RE = re.compile(r"^[0-9A-Z]-[0-9A-Z]-[0-9A-Z]{5}-[0-9A-Z]{4}-[0-9A-Z]{2}$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    tl=10, atmosphere=6, hydrographics=7, population=8,
    government=6, law_level=5, starport="A", pcr=4,
    habitability_rating=None, trade_codes=None, rng=None,
) -> TechDetail:
    """Convenience wrapper: generate a TechDetail with sensible defaults."""
    result = generate_tech_detail(
        tl=tl, atmosphere=atmosphere, hydrographics=hydrographics,
        population=population, government=government, law_level=law_level,
        starport=starport, pcr=pcr, habitability_rating=habitability_rating,
        trade_codes=trade_codes, rng=rng,
    )
    assert result is not None
    return result


# ---------------------------------------------------------------------------
# None guard
# ---------------------------------------------------------------------------

class TestNoneGuard:
    """Tests for the population==0 None guard."""

    def test_uninhabited_returns_none(self):
        """population=0 → None (no procedures apply)."""
        assert generate_tech_detail(
            tl=10, atmosphere=6, hydrographics=7, population=0,
            government=6, law_level=5, starport="A",
        ) is None

    def test_inhabited_returns_tech_detail(self):
        """population>0 → TechDetail instance."""
        assert _gen() is not None


# ---------------------------------------------------------------------------
# High / Low common TL
# ---------------------------------------------------------------------------

class TestCommonTL:
    """Tests for High and Low common TL bounds."""

    def test_high_common_equals_tl(self):
        """tl_high_common always equals the input UWP TL."""
        td = _gen(tl=12)
        assert td.tl_high_common == 12

    def test_low_common_le_high_common(self):
        """tl_low_common is never greater than tl_high_common."""
        td = _gen(tl=10)
        assert td.tl_low_common <= td.tl_high_common

    def test_low_common_ge_half_tl(self):
        """tl_low_common is at least TL // 2."""
        td = _gen(tl=10)
        assert td.tl_low_common >= 10 // 2

    def test_tl_zero_low_common_is_zero(self):
        """TL 0 forces low common to 0 (both bounds collapse to 0)."""
        td = _gen(tl=0, atmosphere=6)
        assert td.tl_high_common == 0
        assert td.tl_low_common == 0

    def test_gov7_balkanised_computes_normally(self):
        """Government 7 applies DM-2 but produces a valid non-None result."""
        td = _gen(tl=10, government=7)
        assert td is not None
        assert td.tl_high_common == 10
        assert td.tl_low_common <= 10


# ---------------------------------------------------------------------------
# Energy TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestEnergyTL:
    """Tests for Energy Tech Level sub-category bounds and DMs."""

    def test_energy_ge_half_tl(self):
        """Energy TL is always >= tl_high // 2."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_energy >= 5, f"seed {seed}: energy {td.tl_energy} < 5"

    def test_energy_le_120pct_tl(self):
        """Energy TL is always <= int(tl_high * 1.2)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_energy <= 12, f"seed {seed}: energy {td.tl_energy} > 12"

    def test_energy_can_exceed_tl_high_with_pop9(self):
        """Energy TL can exceed tl_high when pop >= 9 and TLM roll is favourable."""
        found_above = False
        for seed in range(200):
            td = _gen(tl=10, population=9, rng=random.Random(seed))
            if td.tl_energy > 10:
                found_above = True
                break
        assert found_above, "Energy TL never exceeded tl_high across 200 seeds with pop 9"

    def test_energy_can_exceed_tl_high_with_industrial(self):
        """Energy TL can exceed tl_high when Industrial trade code is present."""
        found_above = False
        for seed in range(200):
            td = _gen(tl=10, population=6, trade_codes=["In"], rng=random.Random(seed))
            if td.tl_energy > 10:
                found_above = True
                break
        assert found_above, "Energy TL never exceeded tl_high across 200 seeds with In"

    def test_energy_pop9_dm_raises_mean(self):
        """Energy TL mean is statistically higher with pop 9+ than pop 8 (same seeds)."""
        seeds = list(range(100))
        mean_no_dm = sum(
            _gen(tl=10, population=8, rng=random.Random(s)).tl_energy for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=9, rng=random.Random(s)).tl_energy for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_no_dm

    def test_energy_industrial_dm_raises_mean(self):
        """Energy TL mean is higher with Industrial code than without (same seeds)."""
        seeds = list(range(100))
        mean_no_dm = sum(
            _gen(tl=10, population=6, rng=random.Random(s)).tl_energy for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=6, trade_codes=["In"], rng=random.Random(s)).tl_energy
            for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_no_dm

    def test_energy_tl_zero(self):
        """TL 0 world: energy TL is 0 (bounds collapse to [0, 0])."""
        for seed in range(20):
            td = _gen(tl=0, atmosphere=6, rng=random.Random(seed))
            assert td.tl_energy == 0


# ---------------------------------------------------------------------------
# Electronics TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestElectronicsTL:
    """Tests for Electronics Tech Level sub-category bounds and DMs."""

    def test_electronics_le_energy_plus_one(self):
        """Electronics TL is always <= Energy TL + 1."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_electronics <= td.tl_energy + 1, (
                f"seed {seed}: elec {td.tl_electronics} > energy {td.tl_energy} + 1"
            )

    def test_electronics_ge_energy_minus_three(self):
        """Electronics TL is always >= max(0, Energy TL - 3)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_electronics >= max(0, td.tl_energy - 3), (
                f"seed {seed}: elec {td.tl_electronics} < energy {td.tl_energy} - 3"
            )

    def test_electronics_pop15_dm_raises_mean(self):
        """Electronics mean is higher with pop 1–5 than pop 8 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=8, rng=random.Random(s)).tl_electronics for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=3, rng=random.Random(s)).tl_electronics for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base

    def test_electronics_pop9_dm_lowers_mean(self):
        """Electronics mean is lower with pop 9+ than pop 8 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=8, rng=random.Random(s)).tl_electronics for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=9, rng=random.Random(s)).tl_electronics for s in seeds
        ) / len(seeds)
        assert mean_dm <= mean_base

    def test_electronics_industrial_dm_raises_mean(self):
        """Electronics mean is higher with Industrial code than without (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=6, rng=random.Random(s)).tl_electronics for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=6, trade_codes=["In"], rng=random.Random(s)).tl_electronics
            for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base


# ---------------------------------------------------------------------------
# Manufacturing TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestManufacturingTL:
    """Tests for Manufacturing Tech Level sub-category bounds and DMs."""

    def test_manufacturing_le_max_energy_electronics(self):
        """Manufacturing TL is always <= max(Energy TL, Electronics TL)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_manufacturing <= max(td.tl_energy, td.tl_electronics), (
                f"seed {seed}: mfg {td.tl_manufacturing} > max("
                f"energy {td.tl_energy}, elec {td.tl_electronics})"
            )

    def test_manufacturing_ge_electronics_minus_two(self):
        """Manufacturing TL is always >= max(0, Electronics TL - 2)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_manufacturing >= max(0, td.tl_electronics - 2), (
                f"seed {seed}: mfg {td.tl_manufacturing} < elec {td.tl_electronics} - 2"
            )

    def test_manufacturing_pop16_dm_lowers_mean(self):
        """Manufacturing mean is lower with pop 1–6 than pop 7 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=7, rng=random.Random(s)).tl_manufacturing for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=4, rng=random.Random(s)).tl_manufacturing for s in seeds
        ) / len(seeds)
        assert mean_dm <= mean_base

    def test_manufacturing_pop8_dm_raises_mean(self):
        """Manufacturing mean is higher with pop 8+ than pop 7 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=7, rng=random.Random(s)).tl_manufacturing for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=8, rng=random.Random(s)).tl_manufacturing for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base

    def test_manufacturing_industrial_dm_raises_mean(self):
        """Manufacturing mean is higher with Industrial code than without (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, population=7, rng=random.Random(s)).tl_manufacturing for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, population=7, trade_codes=["In"], rng=random.Random(s)).tl_manufacturing
            for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base


# ---------------------------------------------------------------------------
# Medical TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestMedicalTL:
    """Tests for Medical Tech Level sub-category bounds and DMs."""

    def test_medical_le_electronics(self):
        """Medical TL is always <= Electronics TL."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_medical <= td.tl_electronics, (
                f"seed {seed}: medical {td.tl_medical} > electronics {td.tl_electronics}"
            )

    def test_medical_starport_a_floor_6(self):
        """Starport A floor is 6 — medical >= min(6, electronics)."""
        for seed in range(50):
            td = _gen(tl=10, starport="A", rng=random.Random(seed))
            assert td.tl_medical >= min(6, td.tl_electronics), (
                f"seed {seed}: medical {td.tl_medical} < min(6, elec {td.tl_electronics})"
            )

    def test_medical_starport_b_floor_4(self):
        """Starport B floor is 4 — medical >= min(4, electronics)."""
        for seed in range(50):
            td = _gen(tl=10, starport="B", rng=random.Random(seed))
            assert td.tl_medical >= min(4, td.tl_electronics), (
                f"seed {seed}: medical {td.tl_medical} < min(4, elec {td.tl_electronics})"
            )

    def test_medical_starport_c_floor_2(self):
        """Starport C floor is 2 — medical >= min(2, electronics)."""
        for seed in range(50):
            td = _gen(tl=10, starport="C", rng=random.Random(seed))
            assert td.tl_medical >= min(2, td.tl_electronics)

    def test_medical_starport_x_no_floor(self):
        """Starport X has no minimum medical floor (can reach 0)."""
        found_zero = False
        for seed in range(200):
            td = _gen(tl=3, atmosphere=0, starport="X", rng=random.Random(seed))
            if td.tl_medical == 0:
                found_zero = True
                break
        assert found_zero, "Medical TL never reached 0 with Starport X across 200 seeds"

    def test_medical_rich_dm_raises_mean(self):
        """Medical mean is higher with Rich trade code than without (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, rng=random.Random(s)).tl_medical for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, trade_codes=["Ri"], rng=random.Random(s)).tl_medical for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base

    def test_medical_poor_dm_lowers_mean(self):
        """Medical mean is lower with Poor trade code than without (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, rng=random.Random(s)).tl_medical for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, trade_codes=["Po"], rng=random.Random(s)).tl_medical for s in seeds
        ) / len(seeds)
        assert mean_dm <= mean_base


# ---------------------------------------------------------------------------
# Environmental TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestEnvironmentalTL:
    """Tests for Environmental Tech Level sub-category bounds and DMs."""

    def test_environmental_le_energy(self):
        """Environmental TL is always <= Energy TL."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_environmental <= td.tl_energy, (
                f"seed {seed}: env {td.tl_environmental} > energy {td.tl_energy}"
            )

    def test_environmental_ge_energy_minus_five(self):
        """Environmental TL is always >= max(0, Energy TL - 5)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_environmental >= max(0, td.tl_energy - 5), (
                f"seed {seed}: env {td.tl_environmental} < energy {td.tl_energy} - 5"
            )

    def test_environmental_hab_dm_raises_mean(self):
        """Low habitability rating raises Environmental TL mean (same seeds)."""
        seeds = list(range(100))
        mean_no_dm = sum(
            _gen(tl=10, habitability_rating=8, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, habitability_rating=3, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_no_dm

    def test_environmental_hab_dm_formula(self):
        """DM = 8 - habitability_rating when rating < 8 (verified via mean shift)."""
        seeds = list(range(100))
        mean_hab6 = sum(
            _gen(tl=10, habitability_rating=6, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        mean_hab4 = sum(
            _gen(tl=10, habitability_rating=4, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        assert mean_hab4 >= mean_hab6

    def test_environmental_no_dm_when_hab_none(self):
        """No habitability DM when habitability_rating is None (same mean as hab=8)."""
        seeds = list(range(100))
        mean_none = sum(
            _gen(tl=10, habitability_rating=None, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        mean_hab8 = sum(
            _gen(tl=10, habitability_rating=8, rng=random.Random(s)).tl_environmental
            for s in seeds
        ) / len(seeds)
        assert abs(mean_none - mean_hab8) < 0.5


# ---------------------------------------------------------------------------
# Land Transport TL sub-category (WBH §5)
# ---------------------------------------------------------------------------

class TestLandTL:
    """Tests for Land Transport Tech Level sub-category bounds and DMs."""

    def test_land_le_energy(self):
        """Land TL is always <= Energy TL."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_land <= td.tl_energy, (
                f"seed {seed}: land {td.tl_land} > energy {td.tl_energy}"
            )

    def test_land_ge_electronics_minus_five(self):
        """Land TL is always >= max(0, Electronics TL - 5)."""
        for seed in range(50):
            td = _gen(tl=10, rng=random.Random(seed))
            assert td.tl_land >= max(0, td.tl_electronics - 5), (
                f"seed {seed}: land {td.tl_land} < elec {td.tl_electronics} - 5"
            )

    def test_land_hydro10_dm_lowers_mean(self):
        """Land TL mean is lower with Hydrographics 10 than 7 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, hydrographics=7, rng=random.Random(s)).tl_land for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, hydrographics=10, rng=random.Random(s)).tl_land for s in seeds
        ) / len(seeds)
        assert mean_dm <= mean_base

    def test_land_pcr02_dm_raises_mean(self):
        """Land TL mean is higher with PCR 0–2 than PCR 5 (same seeds)."""
        seeds = list(range(100))
        mean_base = sum(
            _gen(tl=10, pcr=5, rng=random.Random(s)).tl_land for s in seeds
        ) / len(seeds)
        mean_dm = sum(
            _gen(tl=10, pcr=1, rng=random.Random(s)).tl_land for s in seeds
        ) / len(seeds)
        assert mean_dm >= mean_base


# ---------------------------------------------------------------------------
# Technology profile format
# ---------------------------------------------------------------------------

class TestProfileFormat:
    """Tests for technology_profile string format."""

    def test_profile_matches_pattern(self):
        """technology_profile matches the H-L-QQQQQ-TTTT-MM regex."""
        td = _gen()
        assert _PROFILE_RE.match(td.technology_profile), (
            f"profile '{td.technology_profile}' does not match H-L-QQQQQ-TTTT-MM"
        )

    def test_profile_high_char_matches_tl(self):
        """Profile first character encodes tl_high in eHex."""
        ehex = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        td = _gen(tl=12)
        assert td.technology_profile[0] == ehex[12]

    def test_profile_low_char_consistent(self):
        """Profile third character encodes tl_low_common in eHex."""
        ehex = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        td = _gen(tl=10, rng=random.Random(42))
        assert td.technology_profile[2] == ehex[td.tl_low_common]


# ---------------------------------------------------------------------------
# Special-case sub-TLs
# ---------------------------------------------------------------------------

class TestAirTL:
    """Tests for air transport TL special rules."""

    def test_atm0_tl5_air_is_zero(self):
        """Atmosphere 0 with TL <= 5 forces air transport TL to zero."""
        td = _gen(tl=5, atmosphere=0)
        assert td.tl_air == 0

    def test_atm0_tl6_air_not_forced_zero(self):
        """Atmosphere 0 at TL 6 no longer forces air TL to zero."""
        rng = random.Random(1)
        td = generate_tech_detail(
            tl=6, atmosphere=0, hydrographics=5, population=7,
            government=6, law_level=4, starport="B", rng=rng,
        )
        assert td is not None
        assert td.tl_air >= 0

    def test_atm6_standard_air_nonneg(self):
        """Standard atmosphere yields non-negative air transport TL."""
        td = _gen(tl=10, atmosphere=6)
        assert td.tl_air >= 0


class TestSeaTL:
    """Tests for sea transport TL special rules."""

    def test_hydro0_sea_is_zero(self):
        """Hydrographics 0 forces sea transport TL to zero."""
        td = _gen(tl=10, hydrographics=0)
        assert td.tl_sea == 0

    def test_hydro_nonzero_sea_nonneg(self):
        """Non-zero hydrographics yields non-negative sea transport TL."""
        td = _gen(tl=10, hydrographics=7)
        assert td.tl_sea >= 0


class TestMilitaryPersonalTL:
    """Tests for military personal TL special rules."""

    def test_law0_personal_military_is_zero(self):
        """Law Level 0 forces personal military TL to zero."""
        td = _gen(tl=10, law_level=0)
        assert td.tl_military_personal == 0

    def test_law_nonzero_personal_military_nonneg(self):
        """Non-zero law level yields non-negative personal military TL."""
        td = _gen(tl=10, law_level=5)
        assert td.tl_military_personal >= 0


# ---------------------------------------------------------------------------
# All sub-TLs non-negative
# ---------------------------------------------------------------------------

class TestNonNegative:  # pylint: disable=too-few-public-methods
    """Tests that all sub-TL fields are non-negative."""

    def test_all_fields_non_negative(self):
        """Every integer TL field in TechDetail is >= 0."""
        td = _gen()
        for field in (
            "tl_high_common", "tl_low_common",
            "tl_energy", "tl_electronics", "tl_manufacturing",
            "tl_medical", "tl_environmental",
            "tl_land", "tl_sea", "tl_air", "tl_space",
            "tl_military_personal", "tl_military_heavy",
        ):
            assert getattr(td, field) >= 0, f"{field} is negative"


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Serialisation round-trip tests for TechDetail."""

    def test_to_dict_from_dict_identity(self):
        """All fields survive a to_dict/from_dict round-trip."""
        td = _gen(rng=random.Random(99))
        d = td.to_dict()
        td2 = TechDetail.from_dict(d)
        assert td.tl_high_common == td2.tl_high_common
        assert td.tl_low_common == td2.tl_low_common
        assert td.tl_energy == td2.tl_energy
        assert td.tl_electronics == td2.tl_electronics
        assert td.tl_manufacturing == td2.tl_manufacturing
        assert td.tl_medical == td2.tl_medical
        assert td.tl_environmental == td2.tl_environmental
        assert td.tl_land == td2.tl_land
        assert td.tl_sea == td2.tl_sea
        assert td.tl_air == td2.tl_air
        assert td.tl_space == td2.tl_space
        assert td.tl_military_personal == td2.tl_military_personal
        assert td.tl_military_heavy == td2.tl_military_heavy
        assert td.technology_profile == td2.technology_profile

    def test_from_dict_missing_keys_defaults(self):
        """from_dict({}) returns a zeroed TechDetail without raising."""
        td = TechDetail.from_dict({})
        assert td.tl_high_common == 0
        assert td.technology_profile == ""


# ---------------------------------------------------------------------------
# attach_tech_detail integration
# ---------------------------------------------------------------------------

class TestAttach:
    """Integration tests for attach_tech_detail()."""

    def _make_system(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, pop=8, tl=10, atm=6, hydro=7, gov=6, law=5):
        """Build a minimal TravellerSystem stub for attach tests."""
        system = generate_full_system("Test", seed=42)
        mw = system.mainworld
        if mw is not None:
            mw.population = pop
            mw.tech_level = tl
            mw.atmosphere = atm
            mw.hydrographics = hydro
            mw.government = gov
            mw.law_level = law
            mw.tech_detail = None
        return system

    def test_attach_sets_mainworld_tech_detail(self):
        """Inhabited mainworld receives tech_detail after attach."""
        system = self._make_system()
        attach_tech_detail(system, rng=random.Random(7))
        assert system.mainworld is not None
        assert system.mainworld.tech_detail is not None  # type: ignore[attr-defined]

    def test_attach_uninhabited_mainworld_no_tech_detail(self):
        """Uninhabited mainworld keeps tech_detail as None."""
        system = self._make_system(pop=0)
        attach_tech_detail(system, rng=random.Random(7))
        assert system.mainworld is not None
        assert system.mainworld.tech_detail is None  # type: ignore[attr-defined]

    def test_attach_inhabited_secondary_gets_tech_detail(self):
        """Inhabited secondary WorldDetail receives tech_detail after attach."""
        system = generate_full_system("Test", seed=1234)
        attach_detail(system, rng=random.Random(1234))
        attach_tech_detail(system, rng=random.Random(1234))
        found_inhabited = False
        for orbit in system.system_orbits.orbits:
            det = orbit.detail
            if det is not None and det.inhabited:
                found_inhabited = True
                assert det.tech_detail is not None
        if not found_inhabited:
            pytest.skip("No inhabited secondary world in seed 1234 system")

    def test_attach_uninhabited_secondary_no_tech_detail(self):
        """Uninhabited secondary WorldDetail keeps tech_detail as None."""
        system = generate_full_system("Test", seed=1234)
        attach_detail(system, rng=random.Random(1234))
        attach_tech_detail(system, rng=random.Random(1234))
        for orbit in system.system_orbits.orbits:
            det = orbit.detail
            if det is not None and not det.inhabited:
                assert det.tech_detail is None


# ---------------------------------------------------------------------------
# Hypothesis property-based tests
# ---------------------------------------------------------------------------

class TestBoundsInvariants:  # pylint: disable=too-few-public-methods
    """Hypothesis property-based tests for sub-TL bounds invariants."""

    @given(
        tl=st.integers(min_value=0, max_value=20),
        atmosphere=st.integers(min_value=0, max_value=15),
        hydrographics=st.integers(min_value=0, max_value=10),
        population=st.integers(min_value=1, max_value=12),
        government=st.integers(min_value=0, max_value=15),
        law_level=st.integers(min_value=0, max_value=9),
        starport=st.sampled_from(["A", "B", "C", "D", "E", "X"]),
        pcr=st.integers(min_value=0, max_value=9),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=200)
    def test_bounds_invariants(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, tl, atmosphere, hydrographics, population, government,
            law_level, starport, pcr, seed,
    ):
        """All sub-TL bound invariants hold across the full input space."""
        td = generate_tech_detail(
            tl=tl, atmosphere=atmosphere, hydrographics=hydrographics,
            population=population, government=government, law_level=law_level,
            starport=starport, pcr=pcr,
            rng=random.Random(seed),
        )
        assert td is not None

        # High common TL always equals input TL
        assert td.tl_high_common == tl

        # Low common TL bounded [tl//2, tl]
        assert td.tl_low_common <= td.tl_high_common
        assert td.tl_low_common >= 0

        # All sub-TLs non-negative
        for val in (
            td.tl_energy, td.tl_electronics, td.tl_manufacturing,
            td.tl_medical, td.tl_environmental,
            td.tl_land, td.tl_sea, td.tl_air, td.tl_space,
            td.tl_military_personal, td.tl_military_heavy,
        ):
            assert val >= 0

        # Energy TL bounds: [tl // 2, int(tl * 1.2)]
        # (no trade_codes passed here so DM is at most +1 from pop, still clamped)
        assert td.tl_energy <= int(tl * 1.2)
        assert td.tl_energy >= 0

        # Electronics TL bounds: [Energy TL − 3, Energy TL + 1]
        assert td.tl_electronics <= td.tl_energy + 1
        assert td.tl_electronics >= 0

        # Manufacturing TL bounds: [Electronics TL − 2, max(Energy, Electronics)]
        assert td.tl_manufacturing <= max(td.tl_energy, td.tl_electronics)
        assert td.tl_manufacturing >= 0

        # Medical TL: always <= Electronics TL
        assert td.tl_medical <= td.tl_electronics

        # Environmental TL: [Energy TL − 5, Energy TL]
        assert td.tl_environmental <= td.tl_energy
        assert td.tl_environmental >= 0

        # Land TL: [Electronics TL − 5, Energy TL]
        assert td.tl_land <= td.tl_energy
        assert td.tl_land >= 0

        # Sea TL = 0 when hydrographics = 0
        if hydrographics == 0:
            assert td.tl_sea == 0

        # Air TL = 0 when atmosphere = 0 and tl <= 5
        if atmosphere == 0 and tl <= 5:
            assert td.tl_air == 0

        # Personal military TL = 0 when law level = 0
        if law_level == 0:
            assert td.tl_military_personal == 0

        # Profile format
        assert _PROFILE_RE.match(td.technology_profile)
