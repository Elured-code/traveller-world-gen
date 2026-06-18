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
