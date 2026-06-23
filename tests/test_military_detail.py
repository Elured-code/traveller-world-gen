"""Tests for traveller_world_military_detail.py (Issue #102).

Covers: state of readiness roll, Militancy DMs, enforcement always-exists,
branch existence/effect for each branch, military budget formula, profile
string format, serialisation, and attach no-op guards.
"""
import random
import unittest

from traveller_gen.traveller_world_military_detail import (
    MilitaryBranch,
    MilitaryDetail,
    generate_military_detail,
    attach_military_detail,
    _militancy_sor_dm,
    _militancy_branch_dm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detail(
    starport="A",
    has_highport=True,
    has_naval_base=True,
    has_military_base=False,
    population=7,
    government=3,
    law_level=5,
    tech_level=12,
    atmosphere=6,
    hydrographics=7,
    pcr=4,
    militancy=7,
    expansionism=7,
    efficiency_factor=1,
    gwp_total_mcr=500_000.0,
    risk=False,
    seed=42,
) -> MilitaryDetail:
    rng = random.Random(seed)
    return generate_military_detail(
        starport=starport,
        has_highport=has_highport,
        has_naval_base=has_naval_base,
        has_military_base=has_military_base,
        population=population,
        government=government,
        law_level=law_level,
        tech_level=tech_level,
        atmosphere=atmosphere,
        hydrographics=hydrographics,
        pcr=pcr,
        militancy=militancy,
        expansionism=expansionism,
        efficiency_factor=efficiency_factor,
        gwp_total_mcr=gwp_total_mcr,
        risk=risk,
        rng=rng,
    )


class TestMilitancyDMs(unittest.TestCase):

    def test_sor_dm_low_militancy(self):
        self.assertEqual(_militancy_sor_dm(1), -4)
        self.assertEqual(_militancy_sor_dm(2), -4)

    def test_sor_dm_mid_low(self):
        self.assertEqual(_militancy_sor_dm(3), -1)
        self.assertEqual(_militancy_sor_dm(5), -1)

    def test_sor_dm_mid(self):
        self.assertEqual(_militancy_sor_dm(6), 1)
        self.assertEqual(_militancy_sor_dm(8), 1)

    def test_sor_dm_high(self):
        self.assertEqual(_militancy_sor_dm(9), 2)
        self.assertEqual(_militancy_sor_dm(11), 2)

    def test_sor_dm_very_high(self):
        self.assertEqual(_militancy_sor_dm(12), 4)
        self.assertEqual(_militancy_sor_dm(35), 4)

    def test_branch_dm_matches_sor_dm(self):
        # Branch DM table is the same as SoR DM table
        for mil in range(1, 36):
            self.assertEqual(_militancy_branch_dm(mil), _militancy_sor_dm(mil))


class TestStateOfReadiness(unittest.TestCase):

    def test_sor_label_is_string(self):
        det = _make_detail()
        self.assertIsInstance(det.state_of_readiness, str)
        self.assertGreater(len(det.state_of_readiness), 0)

    def test_sor_modifier_is_valid(self):
        det = _make_detail()
        self.assertIn(det.state_of_readiness_modifier, (0.5, 0.75, 1.0, 1.2, 2.0, 5.0))

    def test_high_militancy_skews_toward_war(self):
        # With Militancy 35 (DM+4), Complacent peace is impossible
        results = set()
        for s in range(100):
            det = _make_detail(militancy=35, seed=s)
            results.add(det.state_of_readiness)
        self.assertNotIn("Complacent peace", results)

    def test_low_militancy_skews_toward_peace(self):
        # With Militancy 1 (DM-4), Total War is extremely unlikely
        results = set()
        for s in range(100):
            det = _make_detail(militancy=1, seed=s)
            results.add(det.state_of_readiness)
        self.assertNotIn("Total war: full mobilisation", results)

    def test_determinism_same_seed(self):
        d1 = _make_detail(seed=999)
        d2 = _make_detail(seed=999)
        self.assertEqual(d1.state_of_readiness, d2.state_of_readiness)
        self.assertEqual(d1.state_of_readiness_modifier, d2.state_of_readiness_modifier)


class TestEnforcement(unittest.TestCase):

    def test_enforcement_always_exists(self):
        # Enforcement always exists regardless of attributes
        for gov in (0, 3, 7, 11, 15):
            for law in (0, 3, 9, 12):
                det = _make_detail(government=gov, law_level=law, seed=1)
                self.assertTrue(det.enforcement.exists,
                                f"Enforcement must exist for gov={gov} law={law}")

    def test_enforcement_effect_minimum_1(self):
        # Even worst-case DMs, effect must be at least 1
        det = _make_detail(government=0, law_level=0, pcr=9, militancy=1, seed=5)
        self.assertGreaterEqual(det.enforcement.effect, 1)

    def test_enforcement_effect_maximum_18(self):
        det = _make_detail(government=11, law_level=15, pcr=0, militancy=35, seed=5)
        self.assertLessEqual(det.enforcement.effect, 18)

    def test_high_law_boosts_enforcement(self):
        low_law = _make_detail(law_level=2, seed=7)
        high_law = _make_detail(law_level=12, seed=7)
        self.assertGreater(high_law.enforcement.effect, low_law.enforcement.effect)


class TestMilitia(unittest.TestCase):

    def test_militia_may_not_exist_low_pop_world(self):
        # Gov 6 gives DM-6 on law level; low population; should sometimes fail
        results = [_make_detail(government=6, law_level=1, pcr=7,
                                militancy=3, seed=s).militia.exists
                   for s in range(50)]
        self.assertFalse(all(results), "Militia should not always exist for Gov 6")

    def test_militia_effect_zero_when_absent(self):
        for s in range(20):
            det = _make_detail(government=6, law_level=0, pcr=7, militancy=1, seed=s)
            if not det.militia.exists:
                self.assertEqual(det.militia.effect, 0)


class TestBranchTLGates(unittest.TestCase):

    def test_air_force_absent_below_tl4(self):
        det = _make_detail(tech_level=3, seed=1)
        self.assertFalse(det.air_force.exists)
        self.assertEqual(det.air_force.effect, 0)

    def test_system_defence_absent_below_tl7(self):
        det = _make_detail(tech_level=6, seed=1)
        self.assertFalse(det.system_defence.exists)
        self.assertEqual(det.system_defence.effect, 0)

    def test_navy_absent_below_tl8(self):
        det = _make_detail(tech_level=7, seed=1)
        self.assertFalse(det.navy.exists)

    def test_marines_absent_below_tl8(self):
        det = _make_detail(tech_level=7, seed=1)
        self.assertFalse(det.marines.exists)

    def test_surface_branches_possible_at_tl0(self):
        # Enforcement, Militia, Army, Wet Navy all TL 0+
        det = _make_detail(tech_level=4, atmosphere=6, hydrographics=7,
                           government=7, militancy=10, seed=2)
        self.assertTrue(det.enforcement.exists)


class TestWetNavy(unittest.TestCase):

    def test_wet_navy_absent_on_desert_world(self):
        # Hydrographics 0 → DM-20, should never exist
        results = [_make_detail(hydrographics=0, seed=s).wet_navy.exists
                   for s in range(30)]
        self.assertFalse(any(results), "Wet Navy must not exist on hydrographics 0")

    def test_wet_navy_likely_on_ocean_world(self):
        # Hydrographics A (10) → DM+8 plus militancy DM; should usually exist
        results = [_make_detail(hydrographics=10, militancy=9, seed=s).wet_navy.exists
                   for s in range(30)]
        self.assertTrue(any(results), "Wet Navy should exist on high-hydro worlds")


class TestMarinesDependencies(unittest.TestCase):

    def test_marines_penalised_without_navy(self):
        # Low-TL world: navy won't exist (TL<8), marines get No-Navy DM-6
        det_notl = _make_detail(tech_level=7, seed=3)
        self.assertFalse(det_notl.navy.exists)
        self.assertFalse(det_notl.marines.exists)

    def test_marines_possible_with_navy_and_military_base(self):
        # High-TL, naval base, military base, expansionist world
        results = [
            _make_detail(tech_level=14, has_naval_base=True, has_military_base=True,
                         expansionism=13, militancy=10, seed=s).marines.exists
            for s in range(30)
        ]
        self.assertTrue(any(results), "Marines should sometimes exist on expansionist worlds")


class TestMilitaryBudget(unittest.TestCase):

    def test_budget_pct_positive(self):
        det = _make_detail(gwp_total_mcr=1_000_000.0)
        self.assertGreater(det.military_budget_pct, 0.0)

    def test_budget_total_scales_with_gwp(self):
        det_rich = _make_detail(gwp_total_mcr=10_000_000.0, seed=10)
        det_poor = _make_detail(gwp_total_mcr=1.0, seed=10)
        # Rich world has higher absolute budget
        self.assertGreater(det_rich.military_budget_total_mcr,
                           det_poor.military_budget_total_mcr)

    def test_budget_reflects_readiness_multiplier(self):
        # Budget total = gwp * pct/100 * readiness_modifier; verify it's consistent
        det = _make_detail()
        expected = round(
            det.military_budget_pct / 100.0
            * 500_000.0
            * det.state_of_readiness_modifier, 2
        )
        self.assertAlmostEqual(det.military_budget_total_mcr, expected, places=1)


class TestMilitaryProfile(unittest.TestCase):

    def test_profile_format(self):
        # EMAWF-SNM:X.XX%
        det = _make_detail()
        parts = det.military_profile.split(":")
        self.assertEqual(len(parts), 2)
        body, pct = parts
        self.assertIn("-", body)
        halves = body.split("-")
        self.assertEqual(len(halves), 2)
        self.assertEqual(len(halves[0]), 5)   # EMAWF
        self.assertEqual(len(halves[1]), 3)   # SNM
        self.assertTrue(pct.endswith("%"))

    def test_enforcement_always_nonzero_in_profile(self):
        det = _make_detail()
        # First character of profile is Enforcement Effect eHex (always ≥ 1)
        first_char = det.military_profile[0]
        self.assertNotEqual(first_char, "0")

    def test_absent_branch_shows_zero_in_profile(self):
        # TL 7: Navy (pos 6) must be 0
        det = _make_detail(tech_level=7)
        self.assertFalse(det.navy.exists)
        # Profile position 6 (0-indexed, after hyphen at pos 5): char at index 6
        profile_body = det.military_profile.split(":")[0]
        # EMAWF-SNM: S is index 6, N is index 7, M is index 8
        navy_char = profile_body[7]
        self.assertEqual(navy_char, "0")


class TestRoundtripSerialization(unittest.TestCase):

    def test_to_dict_from_dict_roundtrip(self):
        original = _make_detail(seed=55)
        restored = MilitaryDetail.from_dict(original.to_dict())
        self.assertEqual(original.military_profile, restored.military_profile)
        self.assertEqual(original.state_of_readiness, restored.state_of_readiness)
        self.assertAlmostEqual(original.military_budget_pct,
                               restored.military_budget_pct, places=4)
        self.assertEqual(original.enforcement.effect, restored.enforcement.effect)
        self.assertEqual(original.navy.exists, restored.navy.exists)

    def test_branch_roundtrip(self):
        b = MilitaryBranch(exists=True, effect=7)
        self.assertEqual(MilitaryBranch.from_dict(b.to_dict()), b)

    def test_absent_branch_roundtrip(self):
        b = MilitaryBranch(exists=False, effect=0)
        self.assertEqual(MilitaryBranch.from_dict(b.to_dict()), b)


class TestAttachNoOp(unittest.TestCase):

    def test_no_op_when_mainworld_is_none(self):
        class FakeSystem:
            mainworld = None
        attach_military_detail(FakeSystem())  # must not raise

    def test_no_op_when_population_zero(self):
        class FakeWorld:
            population = 0
            importance_detail = None
        class FakeSystem:
            mainworld = FakeWorld()
        attach_military_detail(FakeSystem())  # must not raise

    def test_no_op_when_importance_detail_none(self):
        class FakeWorld:
            population = 7
            importance_detail = None
        class FakeSystem:
            mainworld = FakeWorld()
        attach_military_detail(FakeSystem())  # must not raise


if __name__ == "__main__":
    unittest.main()
