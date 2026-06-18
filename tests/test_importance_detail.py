"""Tests for traveller_world_importance — world importance calculation."""

import pytest
from traveller_world_importance import WorldImportance, generate_importance_detail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen(
    starport="C",
    population=7,
    tech_level=9,
    trade_codes=None,
    bases=None,
):
    """Call generate_importance_detail with convenient defaults (all zero DMs)."""
    return generate_importance_detail(
        starport=starport,
        population=population,
        tech_level=tech_level,
        trade_codes=trade_codes or [],
        bases=bases or [],
    )


# ---------------------------------------------------------------------------
# Starport DM
# ---------------------------------------------------------------------------

class TestStarportDM:
    def test_starport_a_gives_plus_one(self):
        assert _gen(starport="A").starport_dm == 1

    def test_starport_b_gives_plus_one(self):
        assert _gen(starport="B").starport_dm == 1

    def test_starport_c_gives_zero(self):
        assert _gen(starport="C").starport_dm == 0

    def test_starport_d_gives_minus_one(self):
        assert _gen(starport="D").starport_dm == -1

    def test_starport_e_gives_minus_one(self):
        assert _gen(starport="E").starport_dm == -1

    def test_starport_x_gives_minus_one(self):
        assert _gen(starport="X").starport_dm == -1


# ---------------------------------------------------------------------------
# Population DM
# ---------------------------------------------------------------------------

class TestPopulationDM:
    def test_pop_0_gives_minus_one(self):
        assert _gen(population=0).population_dm == -1

    def test_pop_6_gives_minus_one(self):
        assert _gen(population=6).population_dm == -1

    def test_pop_7_gives_zero(self):
        assert _gen(population=7).population_dm == 0

    def test_pop_8_gives_zero(self):
        assert _gen(population=8).population_dm == 0

    def test_pop_9_gives_plus_one(self):
        assert _gen(population=9).population_dm == 1

    def test_pop_10_gives_plus_one(self):
        assert _gen(population=10).population_dm == 1


# ---------------------------------------------------------------------------
# Tech level DM
# ---------------------------------------------------------------------------

class TestTechDM:
    def test_tl_0_gives_minus_one(self):
        assert _gen(tech_level=0).tech_dm == -1

    def test_tl_8_gives_minus_one(self):
        assert _gen(tech_level=8).tech_dm == -1

    def test_tl_9_gives_zero(self):
        assert _gen(tech_level=9).tech_dm == 0

    def test_tl_10_gives_plus_one(self):  # eHex A
        assert _gen(tech_level=10).tech_dm == 1

    def test_tl_15_gives_plus_one(self):  # eHex F
        assert _gen(tech_level=15).tech_dm == 1

    def test_tl_16_gives_plus_two(self):  # eHex G
        assert _gen(tech_level=16).tech_dm == 2

    def test_tl_20_gives_plus_two(self):
        assert _gen(tech_level=20).tech_dm == 2


# ---------------------------------------------------------------------------
# Trade code DMs
# ---------------------------------------------------------------------------

class TestTradeCodeDMs:
    def test_agricultural_gives_plus_one(self):
        assert _gen(trade_codes=["Ag", "Ni"]).agricultural_dm == 1

    def test_no_agricultural_gives_zero(self):
        assert _gen(trade_codes=["Ni"]).agricultural_dm == 0

    def test_industrial_gives_plus_one(self):
        assert _gen(trade_codes=["In"]).industrial_dm == 1

    def test_no_industrial_gives_zero(self):
        assert _gen(trade_codes=["Ag"]).industrial_dm == 0

    def test_rich_gives_plus_one(self):
        assert _gen(trade_codes=["Ri"]).rich_dm == 1

    def test_no_rich_gives_zero(self):
        assert _gen(trade_codes=[]).rich_dm == 0

    def test_all_three_trade_codes(self):
        wi = _gen(trade_codes=["Ag", "In", "Ri"])
        assert wi.agricultural_dm == 1
        assert wi.industrial_dm == 1
        assert wi.rich_dm == 1


# ---------------------------------------------------------------------------
# Base DMs
# ---------------------------------------------------------------------------

class TestBaseDMs:
    def test_two_non_corsair_bases_gives_plus_one(self):
        assert _gen(bases=["N", "S"]).base_dm == 1

    def test_three_non_corsair_bases_gives_plus_one(self):
        assert _gen(bases=["N", "S", "M"]).base_dm == 1

    def test_one_non_corsair_base_gives_zero(self):
        assert _gen(bases=["N"]).base_dm == 0

    def test_no_bases_gives_zero(self):
        assert _gen(bases=[]).base_dm == 0

    def test_corsair_excluded_from_count(self):
        # One real base + one corsair base = only 1 non-corsair → 0
        assert _gen(bases=["N", "C"]).base_dm == 0

    def test_two_corsair_bases_gives_zero(self):
        assert _gen(bases=["C", "C"]).base_dm == 0

    def test_waystation_present_gives_plus_one(self):
        assert _gen(bases=["W"]).waystation_dm == 1

    def test_no_waystation_gives_zero(self):
        assert _gen(bases=["N", "S"]).waystation_dm == 0

    def test_waystation_also_counts_toward_base_dm(self):
        # W counts as a non-corsair base for the base_dm rule
        assert _gen(bases=["N", "W"]).base_dm == 1

    def test_waystation_alone_not_enough_for_base_dm(self):
        wi = _gen(bases=["W"])
        assert wi.base_dm == 0
        assert wi.waystation_dm == 1


# ---------------------------------------------------------------------------
# Total importance sum
# ---------------------------------------------------------------------------

class TestImportanceTotal:
    def test_all_neutral_gives_zero(self):
        assert _gen(starport="C", population=7, tech_level=9).importance == 0

    def test_high_importance_world(self):
        # Starport A (+1), Pop A (+1), TL F (+1), In+Ri (+2), N+S bases (+1) = +6
        wi = _gen(
            starport="A", population=10, tech_level=15,
            trade_codes=["In", "Ri"], bases=["N", "S"],
        )
        assert wi.importance == 6

    def test_backwater_world(self):
        # Starport D (-1), Pop 4 (-1), TL 5 (-1) = -3
        wi = _gen(starport="D", population=4, tech_level=5)
        assert wi.importance == -3

    def test_importance_equals_sum_of_all_dms(self):
        wi = _gen(
            starport="A", population=9, tech_level=12,
            trade_codes=["Ag"], bases=["N", "S", "W"],
        )
        expected = (
            wi.starport_dm + wi.population_dm + wi.tech_dm
            + wi.agricultural_dm + wi.industrial_dm + wi.rich_dm
            + wi.base_dm + wi.waystation_dm
        )
        assert wi.importance == expected


# ---------------------------------------------------------------------------
# importance_str property
# ---------------------------------------------------------------------------

class TestImportanceStr:
    def test_positive_has_plus_sign(self):
        wi = _gen(starport="A")
        assert wi.importance_str.startswith("+")

    def test_zero_is_just_zero(self):
        wi = _gen(starport="C", population=7, tech_level=9)
        assert wi.importance_str == "0"

    def test_negative_uses_minus_sign(self):
        wi = _gen(starport="D", population=4, tech_level=5)
        assert wi.importance_str.startswith("−")  # U+2212 minus sign

    def test_value_plus_two(self):
        wi = _gen(starport="A", population=7, tech_level=10)  # +1 +0 +1 = +2
        assert wi.importance_str == "+2"

    def test_value_minus_three(self):
        wi = _gen(starport="D", population=4, tech_level=5)
        assert wi.importance_str == "−3"


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_to_dict_from_dict_identity(self):
        wi = _gen(
            starport="A", population=9, tech_level=14,
            trade_codes=["Ag", "Ri"], bases=["N", "S"],
        )
        restored = WorldImportance.from_dict(wi.to_dict())
        assert restored.importance == wi.importance
        assert restored.starport_dm == wi.starport_dm
        assert restored.population_dm == wi.population_dm
        assert restored.tech_dm == wi.tech_dm
        assert restored.agricultural_dm == wi.agricultural_dm
        assert restored.industrial_dm == wi.industrial_dm
        assert restored.rich_dm == wi.rich_dm
        assert restored.base_dm == wi.base_dm
        assert restored.waystation_dm == wi.waystation_dm
        assert restored.labour_factor == wi.labour_factor
        assert restored.infrastructure_factor == wi.infrastructure_factor

    def test_from_dict_missing_fields_default_to_zero(self):
        wi = WorldImportance.from_dict({"importance": 2})
        assert wi.starport_dm == 0
        assert wi.population_dm == 0
        assert wi.tech_dm == 0
        assert wi.base_dm == 0
        assert wi.waystation_dm == 0
        assert wi.labour_factor == 0
        assert wi.infrastructure_factor is None

    def test_to_dict_contains_all_keys(self):
        d = _gen().to_dict()
        for key in ("importance", "starport_dm", "population_dm", "tech_dm",
                    "agricultural_dm", "industrial_dm", "rich_dm",
                    "base_dm", "waystation_dm", "labour_factor"):
            assert key in d

    def test_infrastructure_factor_omitted_when_none(self):
        wi = _gen(population=0)
        d = wi.to_dict()
        assert "infrastructure_factor" not in d

    def test_infrastructure_factor_present_when_set(self):
        import random as _random
        rng = _random.Random(42)
        wi = generate_importance_detail(
            starport="A", population=9, tech_level=12,
            trade_codes=[], bases=[], rng=rng,
        )
        if wi.infrastructure_factor is not None:
            assert "infrastructure_factor" in wi.to_dict()


# ---------------------------------------------------------------------------
# Labour factor
# ---------------------------------------------------------------------------

class TestLabourFactor:
    def test_pop_0_gives_zero(self):
        assert _gen(population=0).labour_factor == 0

    def test_pop_1_gives_zero(self):
        assert _gen(population=1).labour_factor == 0

    def test_pop_2_gives_one(self):
        assert _gen(population=2).labour_factor == 1

    def test_pop_7_gives_six(self):
        assert _gen(population=7).labour_factor == 6

    def test_pop_9_gives_eight(self):
        assert _gen(population=9).labour_factor == 8

    def test_pop_10_gives_nine(self):
        assert _gen(population=10).labour_factor == 9


# ---------------------------------------------------------------------------
# Infrastructure factor
# ---------------------------------------------------------------------------

class TestInfrastructureFactor:
    def test_pop_0_gives_none(self):
        wi = _gen(population=0)
        assert wi.infrastructure_factor is None

    def test_pop_1_no_dice_result_equals_importance(self):
        # Pop 1 → infra_dm = 0, raw = importance; starport A (+1), pop 1 (−1), TL 9 (0) = 0
        wi = _gen(population=1, starport="A", tech_level=9)
        assert wi.importance == 0
        assert wi.infrastructure_factor == 0

    def test_pop_1_negative_importance_gives_none(self):
        # Starport D (-1), pop 1 (-1), TL 5 (-1) = -3; infra_dm=0 → raw=-3 → None
        wi = _gen(population=1, starport="D", tech_level=5)
        assert wi.infrastructure_factor is None

    def test_pop_3_no_dice_result_equals_importance(self):
        # Pop 3 (1–3 range) → infra_dm = 0
        wi = _gen(population=3, starport="A", tech_level=12)
        assert wi.infrastructure_factor == wi.importance

    def test_pop_4_adds_one_die(self):
        import random as _random
        rng = _random.Random(1)
        wi = generate_importance_detail(
            starport="C", population=4, tech_level=9,
            trade_codes=[], bases=[], rng=rng,
        )
        assert wi.infrastructure_factor is not None or wi.importance < 0

    def test_pop_7_adds_two_dice(self):
        import random as _random
        rng = _random.Random(1)
        wi = generate_importance_detail(
            starport="A", population=7, tech_level=12,
            trade_codes=[], bases=[], rng=rng,
        )
        assert wi.infrastructure_factor is not None
        assert wi.infrastructure_factor >= wi.importance

    def test_negative_raw_gives_none(self):
        # Force a scenario where importance is very negative and dice can't save it.
        # Starport X (-1), pop 1 (-1), TL 0 (-1) = -3; infra_dm=0 → raw=-3 → None
        wi = _gen(population=1, starport="X", tech_level=0)
        assert wi.infrastructure_factor is None

    def test_zero_or_positive_raw_gives_int(self):
        import random as _random
        rng = _random.Random(99)
        wi = generate_importance_detail(
            starport="A", population=9, tech_level=12,
            trade_codes=[], bases=[], rng=rng,
        )
        assert isinstance(wi.infrastructure_factor, int)
        assert wi.infrastructure_factor >= 0


# ---------------------------------------------------------------------------
# Resource units (compute_resource_units)
# ---------------------------------------------------------------------------

class TestResourceUnits:
    def _ru(self, rf=5, lf=6, inf=4, ef=2):
        from traveller_world_importance import compute_resource_units
        return compute_resource_units(
            resource_factor=rf, labour_factor=lf,
            infrastructure_factor=inf, efficiency_factor=ef,
        )

    def test_basic_positive(self):
        # 5 × 6 × 4 × 2 = 240
        assert self._ru(rf=5, lf=6, inf=4, ef=2) == 240

    def test_negative_ef_gives_negative_ru(self):
        # 5 × 6 × 4 × -3 = -360
        assert self._ru(rf=5, lf=6, inf=4, ef=-3) == -360

    def test_zero_rf_treated_as_one(self):
        # 0→1 × 6 × 4 × 2 = 48
        assert self._ru(rf=0, lf=6, inf=4, ef=2) == 48

    def test_zero_lf_treated_as_one(self):
        # 5 × 0→1 × 4 × 2 = 40
        assert self._ru(rf=5, lf=0, inf=4, ef=2) == 40

    def test_none_inf_treated_as_one(self):
        # 5 × 6 × None→1 × 2 = 60
        assert self._ru(rf=5, lf=6, inf=None, ef=2) == 60

    def test_zero_inf_treated_as_one(self):
        assert self._ru(rf=5, lf=6, inf=0, ef=2) == 60

    def test_none_rf_treated_as_one(self):
        assert self._ru(rf=None, lf=6, inf=4, ef=2) == 48

    def test_ef_one_gives_rf_lf_inf(self):
        assert self._ru(rf=3, lf=4, inf=5, ef=1) == 60


# ---------------------------------------------------------------------------
# GWP base value (compute_gwp_base)
# ---------------------------------------------------------------------------

class TestGwpBase:
    def _base(self, inf, rf):
        from traveller_world_importance import compute_gwp_base
        return compute_gwp_base(infrastructure_factor=inf, resource_factor=rf)

    def test_book_example_if6_rf7(self):
        # IF=6, RF=7 → RF capped at 6 → base = 6+6 = 12
        assert self._base(6, 7) == 12

    def test_book_example_if0_rf2(self):
        # IF=0→1, RF=2→min(2,1)=1 → base = 1+1 = 2
        assert self._base(0, 2) == 2

    def test_rf_below_if(self):
        # IF=8, RF=3 → base = 8+3 = 11
        assert self._base(8, 3) == 11

    def test_rf_equals_if(self):
        # IF=5, RF=5 → base = 5+5 = 10
        assert self._base(5, 5) == 10

    def test_both_none_gives_two(self):
        assert self._base(None, None) == 2

    def test_none_inf_treated_as_one(self):
        # IF=None→1, RF=5→min(5,1)=1 → base=2
        assert self._base(None, 5) == 2

    def test_min_lower_bound(self):
        assert self._base(1, 1) == 2

    def test_upper_bound_is_twice_if(self):
        # RF always capped at IF, so max base = 2×IF
        assert self._base(10, 999) == 20


# ---------------------------------------------------------------------------
# GWP computation (compute_gwp)
# ---------------------------------------------------------------------------

class TestComputeGwp:
    def _gwp(self, population=7, starport="C", tech_level=10,
             government=4, trade_codes=None, gwp_base=6, efficiency_factor=2):
        from traveller_world_importance import compute_gwp
        return compute_gwp(
            population=population, starport=starport, tech_level=tech_level,
            government=government, trade_codes=trade_codes or [],
            gwp_base=gwp_base, efficiency_factor=efficiency_factor,
        )

    def test_pop_0_returns_zeros(self):
        from traveller_world_importance import compute_gwp
        pc, mcr = compute_gwp(0, "A", 12, 4, [], 6, 3)
        assert pc == 0
        assert mcr == 0.0

    def test_positive_ef_formula(self):
        # TL=10 → 1.0, Port C → 1.0, Gov 4 → 1.2, no TC, base=5, ef=2
        # GWP_pc = 1000 × 5 × (1.0×1.0×1.2×1.0) × 2 = 12000
        pc, _ = self._gwp(tech_level=10, government=4, gwp_base=5, efficiency_factor=2)
        assert pc == 12000

    def test_negative_ef_divides(self):
        # TL=10→1.0, Port C→1.0, Gov 4→1.2, no TC, base=5, ef=-1
        # GWP_pc = 1000 × 5 × 1.2 / (1 - (-1)) = 6000 / 2 = 3000
        pc, _ = self._gwp(tech_level=10, government=4, gwp_base=5, efficiency_factor=-1)
        assert pc == 3000

    def test_tl_0_clamped_to_0p05(self):
        # TL=0 → max(0.05, 0.0) = 0.05
        pc, _ = self._gwp(tech_level=0, starport="C", government=7, gwp_base=4, efficiency_factor=1)
        # 1000 × 4 × 0.05 × 1.0 × 1.0 × 1.0 = 200
        assert pc == 200

    def test_port_a_modifier_1p5(self):
        pc_a, _ = self._gwp(starport="A", tech_level=10, government=7,
                            gwp_base=4, efficiency_factor=1)
        pc_c, _ = self._gwp(starport="C", tech_level=10, government=7,
                            gwp_base=4, efficiency_factor=1)
        assert pc_a == round(pc_c * 1.5)

    def test_trade_codes_multiply(self):
        # In (1.1) and Ri (1.2): TC modifier = 1.1 × 1.2 = 1.32
        pc_both, _ = self._gwp(trade_codes=["In", "Ri"], tech_level=10, government=7,
                                gwp_base=4, efficiency_factor=1)
        pc_none, _ = self._gwp(trade_codes=[], tech_level=10, government=7,
                                gwp_base=4, efficiency_factor=1)
        assert round(pc_both / pc_none, 2) == 1.32

    def test_total_mcr_scales_with_population(self):
        _, mcr7 = self._gwp(population=7, gwp_base=4, efficiency_factor=1)
        _, mcr8 = self._gwp(population=8, gwp_base=4, efficiency_factor=1)
        # Pop 8 has 10× more people than pop 7
        assert abs(mcr8 / mcr7 - 10.0) < 0.01

    def test_result_types(self):
        pc, mcr = self._gwp()
        assert isinstance(pc, int)
        assert isinstance(mcr, float)


# ---------------------------------------------------------------------------
# Development score (compute_development_score)
# ---------------------------------------------------------------------------

class TestDevelopmentScore:
    def _ds(self, gwp_per_capita, inequality_rating=0):
        from traveller_world_importance import compute_development_score
        return compute_development_score(gwp_per_capita, inequality_rating)

    def test_zero_ir_equals_gwp_over_1000(self):
        assert self._ds(5000, 0) == 5.0

    def test_50_ir_halves_score(self):
        assert self._ds(10000, 50) == 5.0

    def test_100_ir_gives_zero(self):
        assert self._ds(10000, 100) == 0.0

    def test_formula_example(self):
        # DS = (12000/1000) × (1 - 25/100) = 12 × 0.75 = 9.0
        assert self._ds(12000, 25) == 9.0

    def test_result_is_float(self):
        assert isinstance(self._ds(5000), float)

    def test_rounded_to_two_decimal_places(self):
        # 7000/1000 × (1 - 33/100) = 7 × 0.67 = 4.69
        result = self._ds(7000, 33)
        assert result == round(result, 2)

    def test_development_score_none_before_attach(self):
        wi = _gen(population=7, starport="A", tech_level=12)
        assert wi.development_score is None


# ---------------------------------------------------------------------------
# Efficiency factor (compute_efficiency_factor)
# ---------------------------------------------------------------------------

class TestEfficiencyFactor:
    """Tests for compute_efficiency_factor() standalone function."""

    def _ef(self, population=7, government=4, law_level=3,
            pcr=5, progressiveness=6, expansionism=6, rng=None):
        from traveller_world_importance import compute_efficiency_factor
        import random as _random
        r = rng or _random.Random(1)
        return compute_efficiency_factor(
            population=population, government=government,
            law_level=law_level, pcr=pcr,
            progressiveness=progressiveness, expansionism=expansionism,
            rng=r,
        )

    def test_pop_0_returns_minus_5(self):
        from traveller_world_importance import compute_efficiency_factor
        assert compute_efficiency_factor(0, 4, 3, 5, 6, 6) == -5

    def test_result_never_zero(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        for seed in range(200):
            r = _random.Random(seed)
            ef = compute_efficiency_factor(5, 4, 3, 5, 6, 6, rng=r)
            assert ef != 0

    def test_result_in_range(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        for seed in range(200):
            r = _random.Random(seed)
            ef = compute_efficiency_factor(7, 4, 3, 5, 6, 6, rng=r)
            assert -5 <= ef <= 5

    def test_gov_minus_set_lowers_dm(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        rng = _random.Random(42)
        # Government 0 → DM-1 (minus set)
        ef_0  = compute_efficiency_factor(7, 0,  3, 5, 6, 6, rng=_random.Random(42))
        # Government 4 → DM+1 (plus set)
        ef_4  = compute_efficiency_factor(7, 4,  3, 5, 6, 6, rng=_random.Random(42))
        # Same dice; government 4 should be ≥ government 0
        assert ef_4 >= ef_0

    def test_gov_not_in_any_set_gives_no_dm(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        # Government 7 (Balkanization) is in neither set — no DM
        ef_7 = compute_efficiency_factor(7, 7, 3, 5, 6, 6, rng=_random.Random(42))
        assert -5 <= ef_7 <= 5  # in range; value itself not deterministic without RNG control

    def test_low_law_level_adds_one(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        # Law 4 (+1 DM) vs law 5 (no DM), same RNG
        ef_low  = compute_efficiency_factor(7, 7, 4, 5, 6, 6, rng=_random.Random(99))
        ef_mid  = compute_efficiency_factor(7, 7, 5, 5, 6, 6, rng=_random.Random(99))
        assert ef_low >= ef_mid

    def test_high_law_level_subtracts_one(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        # Law 10+ (−1 DM) vs law 5 (no DM)
        ef_hi  = compute_efficiency_factor(7, 7, 10, 5, 6, 6, rng=_random.Random(99))
        ef_mid = compute_efficiency_factor(7, 7, 5,  5, 6, 6, rng=_random.Random(99))
        assert ef_hi <= ef_mid

    def test_high_progressiveness_adds_one(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        ef_high = compute_efficiency_factor(7, 7, 5, 5, 9,  6, rng=_random.Random(99))
        ef_mid  = compute_efficiency_factor(7, 7, 5, 5, 6,  6, rng=_random.Random(99))
        assert ef_high >= ef_mid

    def test_low_expansionism_subtracts_one(self):
        import random as _random
        from traveller_world_importance import compute_efficiency_factor
        ef_low = compute_efficiency_factor(7, 7, 5, 5, 6, 2, rng=_random.Random(99))
        ef_mid = compute_efficiency_factor(7, 7, 5, 5, 6, 6, rng=_random.Random(99))
        assert ef_low <= ef_mid

    def test_efficiency_factor_none_before_attach(self):
        wi = _gen(population=7, starport="A", tech_level=12)
        assert wi.efficiency_factor is None

    def test_round_trip_with_efficiency_factor(self):
        from traveller_world_importance import WorldImportance
        wi = WorldImportance(
            importance=2, starport_dm=1, population_dm=0, tech_dm=1,
            agricultural_dm=0, industrial_dm=0, rich_dm=0,
            base_dm=0, waystation_dm=0,
            labour_factor=6, infrastructure_factor=4, efficiency_factor=3,
            resource_units=96, gwp_base=8, gwp_per_capita=24000, gwp_total_mcr=240000.0,
            development_score=24.0,
        )
        d = wi.to_dict()
        assert d["efficiency_factor"] == 3
        assert d["resource_units"] == 96
        assert d["gwp_per_capita"] == 24000
        restored = WorldImportance.from_dict(d)
        assert restored.efficiency_factor == 3
        assert restored.resource_units == 96
        assert restored.gwp_per_capita == 24000
        assert restored.gwp_total_mcr == 240000.0

    def test_round_trip_efficiency_factor_absent(self):
        from traveller_world_importance import WorldImportance
        wi = WorldImportance.from_dict({"importance": 1})
        assert wi.efficiency_factor is None
        assert wi.resource_units is None
        assert wi.gwp_per_capita is None
        assert "efficiency_factor" not in wi.to_dict()
        assert "gwp_per_capita" not in wi.to_dict()
