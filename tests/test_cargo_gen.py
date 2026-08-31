"""
test_cargo_gen.py
=================
pytest unit tests for traveller_world_cargo_gen.py.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
"""
import json as _json
import random

import pytest

from fastapi.testclient import TestClient

from app import app as _fastapi_app  # noqa: E402  (fastapi/app.py)
from traveller_gen.traveller_world_cargo_gen import (
    CargoLot,
    CargoManifest,
    FreightLots,
    FreightManifest,
    _PURCHASE_PCT,
    _TRADE_GOODS,
    _freight_lots_count,
    _purchase_pct,
    generate_cargo_manifest,
    generate_freight_lots,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world(trade_codes=None, law_level=0, starport="A"):
    class _W:
        pass
    w = _W()
    w.name = "Test"
    w.trade_codes = trade_codes or []
    w.law_level = law_level
    w.starport = starport
    return w


# ---------------------------------------------------------------------------
# _purchase_pct — CRB p.244 Modified Price table
# ---------------------------------------------------------------------------

class TestPurchasePct:

    def test_roll_8_is_base(self):
        assert _purchase_pct(8) == 100

    def test_low_roll_clamped_to_table_min(self):
        assert _purchase_pct(-99) == _purchase_pct(-3) == _PURCHASE_PCT[-3]

    def test_high_roll_clamped_to_table_max(self):
        assert _purchase_pct(999) == _purchase_pct(25) == _PURCHASE_PCT[25]

    def test_low_roll_most_expensive(self):
        assert _purchase_pct(-3) > _purchase_pct(8)

    def test_high_roll_cheapest(self):
        assert _purchase_pct(25) < _purchase_pct(8)

    def test_monotone_decreasing(self):
        rolls = sorted(_PURCHASE_PCT)
        for a, b in zip(rolls, rolls[1:]):
            assert _PURCHASE_PCT[a] >= _PURCHASE_PCT[b], (
                f"Price table not monotone at roll {a}→{b}"
            )

    def test_min_pct_is_15(self):
        assert _PURCHASE_PCT[25] == 15

    def test_max_pct_is_300(self):
        assert _PURCHASE_PCT[-3] == 300


# ---------------------------------------------------------------------------
# _TRADE_GOODS table integrity
# ---------------------------------------------------------------------------

class TestTradeGoodsTable:

    def test_all_d66_keys_valid(self):
        for d66 in _TRADE_GOODS:
            tens, units = divmod(d66, 10)
            assert 1 <= tens <= 6, f"d66 {d66} tens digit out of range"
            assert 1 <= units <= 6, f"d66 {d66} units digit out of range"

    def test_36_entries(self):
        assert len(_TRADE_GOODS) == 36

    def test_base_prices_positive(self):
        for d66, g in _TRADE_GOODS.items():
            assert g.base_cr > 0, f"d66 {d66} base_cr not positive"

    def test_tons_params_positive(self):
        for d66, g in _TRADE_GOODS.items():
            assert g.tons_n >= 1, f"d66 {d66} tons_n < 1"
            assert g.tons_x >= 1, f"d66 {d66} tons_x < 1"

    def test_common_goods_always_available(self):
        """D66 11-16 are Common Goods with no trade code restriction."""
        for d66 in (11, 12, 13, 14, 15, 16):
            assert _TRADE_GOODS[d66].avail == (), (
                f"d66 {d66} should be always-available (empty avail)"
            )

    def test_illegal_goods_have_illegal_law_zero(self):
        """D66 61-65 are universally illegal; illegal_law=0 always excludes."""
        for d66 in (61, 62, 63, 64, 65):
            assert _TRADE_GOODS[d66].illegal_law == 0, (
                f"d66 {d66} should have illegal_law=0"
            )

    def test_common_goods_have_no_illegal_law(self):
        for d66 in (11, 12, 13, 14, 15, 16):
            assert _TRADE_GOODS[d66].illegal_law is None

    def test_purchase_dm_tuples_valid(self):
        for d66, g in _TRADE_GOODS.items():
            for code, dm in g.pdms:
                assert isinstance(code, str) and len(code) >= 2, (
                    f"d66 {d66} pdm code invalid: {code!r}"
                )
                assert isinstance(dm, int) and dm >= 0, (
                    f"d66 {d66} pdm dm invalid: {dm}"
                )


# ---------------------------------------------------------------------------
# generate_cargo_manifest — starport gating
# ---------------------------------------------------------------------------

class TestStarportGating:

    def test_starport_x_returns_empty_manifest(self):
        world = _make_world(trade_codes=["In", "Ht", "Ri"], starport="X")
        manifest = generate_cargo_manifest(world)
        assert manifest.lots == []
        assert manifest.total_tons == 0

    def test_starport_a_returns_lots(self):
        world = _make_world(trade_codes=["In", "Ht"], starport="A")
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        assert len(manifest.lots) > 0

    def test_starport_e_returns_common_goods(self):
        """Even a world with no trade codes gets Common Goods on non-X starport."""
        world = _make_world(trade_codes=[], starport="E")
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        assert len(manifest.lots) == 6   # D66 11-16 only (no trade codes match)


# ---------------------------------------------------------------------------
# generate_cargo_manifest — availability by trade code
# ---------------------------------------------------------------------------

class TestAvailability:

    def test_common_goods_always_present(self):
        """Common Electronics (D66 11) appears on any non-X world."""
        world = _make_world(trade_codes=[], starport="A")
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Common Electronics" in names

    def test_all_six_common_goods_present_on_bare_world(self):
        world = _make_world(trade_codes=[], starport="A")
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        assert len(manifest.lots) == 6

    def test_in_world_has_advanced_electronics(self):
        world = _make_world(trade_codes=["In"])
        manifest = generate_cargo_manifest(world, rng=random.Random(42))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Advanced Electronics" in names

    def test_ht_world_has_cybernetics(self):
        world = _make_world(trade_codes=["Ht"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Cybernetics" in names

    def test_ag_world_has_live_animals(self):
        world = _make_world(trade_codes=["Ag"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Live Animals" in names

    def test_non_matching_world_lacks_advanced_electronics(self):
        """A Ri-only world (not In, not Ht) has no Advanced Electronics."""
        world = _make_world(trade_codes=["Ri"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Advanced Electronics" not in names

    def test_as_world_has_crystals_and_gems(self):
        world = _make_world(trade_codes=["As"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Crystals & Gems" in names

    def test_wa_world_has_biochemicals(self):
        world = _make_world(trade_codes=["Wa"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Biochemicals" in names


# ---------------------------------------------------------------------------
# generate_cargo_manifest — illegal goods always excluded
# ---------------------------------------------------------------------------

class TestIllegalGoodsExcluded:

    def test_illegal_biochemicals_never_in_manifest(self):
        world = _make_world(trade_codes=["Ag", "Ic"], law_level=0)
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Illegal Biochemicals" not in names

    def test_illegal_weapons_never_in_manifest(self):
        world = _make_world(trade_codes=["In", "Ht"], law_level=0)
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Illegal Weapons" not in names

    def test_illegal_drugs_excluded_on_any_law_level(self):
        for ll in (0, 3, 9):
            world = _make_world(trade_codes=["Ga", "Hi", "Wa"], law_level=ll)
            manifest = generate_cargo_manifest(world, rng=random.Random(1))
            names = {lot.trade_good for lot in manifest.lots}
            assert "Illegal Drugs" not in names, f"law_level={ll}: Illegal Drugs appeared"

    def test_illegal_cybernetics_excluded(self):
        world = _make_world(trade_codes=["As", "Wa"], law_level=0)
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Illegal Cybernetics" not in names

    def test_legal_cybernetics_available_on_ht_world(self):
        """Legal Cybernetics (D66 32) is distinct from Illegal Cybernetics (D66 62)."""
        world = _make_world(trade_codes=["Ht"], law_level=0)
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        names = {lot.trade_good for lot in manifest.lots}
        assert "Cybernetics" in names


# ---------------------------------------------------------------------------
# generate_cargo_manifest — tonnage and price
# ---------------------------------------------------------------------------

class TestTonnageAndPrice:

    def test_tonnage_within_valid_range_common_electronics(self):
        """Common Electronics (2D×10): must be in [20, 120]."""
        world = _make_world(trade_codes=[])
        for seed in range(50):
            manifest = generate_cargo_manifest(world, rng=random.Random(seed))
            for lot in manifest.lots:
                if lot.trade_good == "Common Electronics":
                    assert 20 <= lot.tons <= 120, (
                        f"seed {seed}: tons={lot.tons} out of [20,120]"
                    )

    def test_tonnage_within_valid_range_cybernetics(self):
        """Cybernetics (1D×1): must be in [1, 6]."""
        world = _make_world(trade_codes=["Ht"])
        for seed in range(50):
            manifest = generate_cargo_manifest(world, rng=random.Random(seed))
            for lot in manifest.lots:
                if lot.trade_good == "Cybernetics":
                    assert 1 <= lot.tons <= 6, (
                        f"seed {seed}: tons={lot.tons} out of [1,6]"
                    )

    def test_purchase_price_within_table_bounds(self):
        """Purchase price must be in [base × 15%, base × 300%] for any 3D roll."""
        world = _make_world(trade_codes=[])   # Common Goods only; DMs vary
        for seed in range(100):
            manifest = generate_cargo_manifest(world, rng=random.Random(seed))
            for lot in manifest.lots:
                lo = round(lot.base_price_cr * 0.15)
                hi = round(lot.base_price_cr * 3.00)
                assert lo <= lot.purchase_price_cr <= hi, (
                    f"seed {seed} {lot.trade_good}: price {lot.purchase_price_cr} "
                    f"outside [{lo}, {hi}]"
                )

    def test_purchase_dm_is_max_not_sum(self):
        """In world with In+2 and Ht+3 for Advanced Electronics, DM = 3 (max), not 5."""
        world = _make_world(trade_codes=["In", "Ht"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        ae = next((l for l in manifest.lots if l.trade_good == "Advanced Electronics"), None)
        assert ae is not None
        assert ae.purchase_dm == 3    # Ht+3 wins over In+2

    def test_positive_dm_lowers_purchase_price_on_average(self):
        """An As world buying Common Ore (As+4) should typically pay less than
        a world with no matching purchase DM, over many seeds."""
        as_world = _make_world(trade_codes=["As"])
        no_world = _make_world(trade_codes=["Hi"])   # no ore purchase DM

        as_prices = []
        no_prices = []
        for seed in range(200):
            m_as = generate_cargo_manifest(as_world, rng=random.Random(seed))
            m_no = generate_cargo_manifest(no_world, rng=random.Random(seed))
            lot_as = next((l for l in m_as.lots if l.trade_good == "Common Ore"), None)
            lot_no = next((l for l in m_no.lots if l.trade_good == "Common Ore"), None)
            if lot_as and lot_no:
                as_prices.append(lot_as.purchase_price_cr)
                no_prices.append(lot_no.purchase_price_cr)

        assert as_prices and no_prices
        assert sum(as_prices) / len(as_prices) < sum(no_prices) / len(no_prices), (
            "Asteroid purchase DM did not lower average Common Ore price"
        )

    def test_total_tons_equals_sum_of_lots(self):
        world = _make_world(trade_codes=["In", "Ht"])
        manifest = generate_cargo_manifest(world, rng=random.Random(7))
        assert manifest.total_tons == sum(lot.tons for lot in manifest.lots)


# ---------------------------------------------------------------------------
# CargoManifest serialisation
# ---------------------------------------------------------------------------

class TestSerialisation:

    def test_to_dict_has_required_keys(self):
        world = _make_world(trade_codes=[])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        d = manifest.to_dict()
        assert "world_name" in d
        assert "lots" in d
        assert "total_tons" in d

    def test_lot_dict_has_required_keys(self):
        world = _make_world(trade_codes=[])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        assert manifest.lots
        lot = manifest.lots[0].to_dict()
        for key in ("d66", "trade_good", "tons", "base_price_cr",
                    "purchase_dm", "purchase_price_cr"):
            assert key in lot, f"Missing key: {key}"

    def test_to_json_roundtrip(self):
        world = _make_world(trade_codes=["As", "Ri"])
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        d = _json.loads(manifest.to_json())
        assert d["total_tons"] == manifest.total_tons
        assert len(d["lots"]) == len(manifest.lots)

    def test_empty_manifest_serialises_cleanly(self):
        world = _make_world(starport="X")
        manifest = generate_cargo_manifest(world)
        d = manifest.to_dict()
        assert d["lots"] == []
        assert d["total_tons"] == 0

    def test_world_name_in_manifest(self):
        world = _make_world(trade_codes=[])
        world.name = "Regina"
        manifest = generate_cargo_manifest(world, rng=random.Random(1))
        assert manifest.world_name == "Regina"
        assert manifest.to_dict()["world_name"] == "Regina"


# ---------------------------------------------------------------------------
# generate_freight_lots helpers
# ---------------------------------------------------------------------------

def _make_freight_world(
        population=5, starport="C", tech_level=8, travel_zone="Green",
        name="Freight Test"):
    class _W:
        pass
    w = _W()
    w.name = name
    w.population = population
    w.starport = starport
    w.tech_level = tech_level
    w.travel_zone = travel_zone
    w.trade_codes = []
    return w


_FREIGHT_CLIENT = TestClient(_fastapi_app)


def _freight_world_json(population=5, starport="C", tech_level=8,
                        travel_zone="Green"):
    """Minimal world JSON accepted by POST /api/freight."""
    return {
        "uwp": f"{starport}5{tech_level:X}0000-0",
        "name": "TestWorld",
        "population": population,
        "starport": {"code": starport},
        "tech_level": tech_level,
        "travel_zone": travel_zone,
        "trade_codes": [],
    }


# ---------------------------------------------------------------------------
# _freight_lots_count — Freight Traffic table
# ---------------------------------------------------------------------------

class TestFreightLotsCount:

    def test_roll_le_1_returns_zero(self):
        rng = random.Random(1)
        assert _freight_lots_count(1, rng) == 0
        assert _freight_lots_count(-5, rng) == 0

    def test_roll_2_rolls_1d(self):
        # 1D: result must be 1–6
        for seed in range(20):
            result = _freight_lots_count(2, random.Random(seed))
            assert 1 <= result <= 6, f"seed {seed}: got {result}"

    def test_roll_8_rolls_3d(self):
        # 3D: result must be 3–18
        for seed in range(20):
            result = _freight_lots_count(8, random.Random(seed))
            assert 3 <= result <= 18, f"seed {seed}: got {result}"

    def test_roll_20_rolls_10d(self):
        # 10D: result must be 10–60
        for seed in range(20):
            result = _freight_lots_count(20, random.Random(seed))
            assert 10 <= result <= 60, f"seed {seed}: got {result}"

    def test_roll_19_rolls_9d(self):
        for seed in range(20):
            result = _freight_lots_count(19, random.Random(seed))
            assert 9 <= result <= 54, f"seed {seed}: got {result}"


# ---------------------------------------------------------------------------
# generate_freight_lots — DMs
# ---------------------------------------------------------------------------

class TestFreightDMs:

    def test_population_1_dm_minus4(self):
        """Pop ≤ 1 → DM −4; should average fewer lots than pop 5."""
        low_pop = _make_freight_world(population=1)
        mid_pop = _make_freight_world(population=5)
        low_totals = [generate_freight_lots(low_pop, rng=random.Random(s)).lots.minor
                      for s in range(50)]
        mid_totals = [generate_freight_lots(mid_pop, rng=random.Random(s)).lots.minor
                      for s in range(50)]
        assert sum(low_totals) <= sum(mid_totals)

    def test_population_0_dm_minus4(self):
        w = _make_freight_world(population=0)
        # Pop DM -4: lots.minor should often be 0 with a neutral-starport world
        results = [generate_freight_lots(w, rng=random.Random(s)).lots.minor
                   for s in range(100)]
        assert sum(results) <= sum(
            generate_freight_lots(_make_freight_world(population=8),
                                  rng=random.Random(s)).lots.minor
            for s in range(100)
        )

    def test_population_6_7_dm_plus2(self):
        low = _make_freight_world(population=5)
        high = _make_freight_world(population=6)
        low_vals = [generate_freight_lots(low, rng=random.Random(s)).lots.minor
                    for s in range(100)]
        high_vals = [generate_freight_lots(high, rng=random.Random(s)).lots.minor
                     for s in range(100)]
        assert sum(high_vals) >= sum(low_vals)

    def test_population_8_dm_plus4(self):
        p5 = _make_freight_world(population=5)
        p8 = _make_freight_world(population=8)
        p5_vals = [generate_freight_lots(p5, rng=random.Random(s)).lots.minor
                   for s in range(100)]
        p8_vals = [generate_freight_lots(p8, rng=random.Random(s)).lots.minor
                   for s in range(100)]
        assert sum(p8_vals) > sum(p5_vals)

    def test_starport_a_more_than_x(self):
        wa = _make_freight_world(starport="A", population=8)
        wx = _make_freight_world(starport="X", population=8)
        a_vals = [generate_freight_lots(wa, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        x_vals = [generate_freight_lots(wx, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        assert sum(a_vals) > sum(x_vals)

    def test_starport_b_more_than_e(self):
        wb = _make_freight_world(starport="B")
        we = _make_freight_world(starport="E")
        b_vals = [generate_freight_lots(wb, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        e_vals = [generate_freight_lots(we, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        assert sum(b_vals) >= sum(e_vals)

    def test_tl_low_dm_minus1(self):
        lo = _make_freight_world(tech_level=6)
        mid = _make_freight_world(tech_level=7)
        lo_vals = [generate_freight_lots(lo, rng=random.Random(s)).lots.minor
                   for s in range(100)]
        mid_vals = [generate_freight_lots(mid, rng=random.Random(s)).lots.minor
                    for s in range(100)]
        assert sum(lo_vals) <= sum(mid_vals)

    def test_tl_high_dm_plus2(self):
        mid = _make_freight_world(tech_level=8)
        hi = _make_freight_world(tech_level=9)
        mid_vals = [generate_freight_lots(mid, rng=random.Random(s)).lots.minor
                    for s in range(100)]
        hi_vals = [generate_freight_lots(hi, rng=random.Random(s)).lots.minor
                   for s in range(100)]
        assert sum(hi_vals) >= sum(mid_vals)

    def test_amber_zone_dm_minus2(self):
        green = _make_freight_world(travel_zone="Green")
        amber = _make_freight_world(travel_zone="Amber")
        g_vals = [generate_freight_lots(green, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        a_vals = [generate_freight_lots(amber, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        assert sum(g_vals) >= sum(a_vals)

    def test_red_zone_dm_minus6(self):
        green = _make_freight_world(travel_zone="Green")
        red = _make_freight_world(travel_zone="Red")
        g_vals = [generate_freight_lots(green, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        r_vals = [generate_freight_lots(red, rng=random.Random(s)).lots.minor
                  for s in range(100)]
        assert sum(g_vals) > sum(r_vals)

    def test_major_tier_dm_minus4_yields_fewer_lots_than_minor(self):
        """The −4 major DM should produce fewer major lots than minor lots on average."""
        w = _make_freight_world(population=8, starport="A", tech_level=12)
        majors = [generate_freight_lots(w, rng=random.Random(s)).lots.major
                  for s in range(200)]
        minors = [generate_freight_lots(w, rng=random.Random(s)).lots.minor
                  for s in range(200)]
        assert sum(majors) < sum(minors)

    def test_incidental_tier_dm_plus2_yields_more_lots_than_minor(self):
        """The +2 incidental DM should produce more incidental lots than minor lots."""
        w = _make_freight_world(population=5, starport="C", tech_level=8)
        incidentals = [generate_freight_lots(w, rng=random.Random(s)).lots.incidental
                       for s in range(200)]
        minors = [generate_freight_lots(w, rng=random.Random(s)).lots.minor
                  for s in range(200)]
        assert sum(incidentals) >= sum(minors)


# ---------------------------------------------------------------------------
# generate_freight_lots — tonnage invariants
# ---------------------------------------------------------------------------

class TestFreightTonnage:

    def test_lot_counts_non_negative(self):
        w = _make_freight_world()
        for seed in range(50):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.lots.incidental >= 0
            assert m.lots.minor >= 0
            assert m.lots.major >= 0
            assert m.mail_containers >= 0

    def test_total_tons_matches_sum(self):
        w = _make_freight_world(population=8, starport="A", tech_level=12)
        for seed in range(30):
            m = generate_freight_lots(w, rng=random.Random(seed))
            expected = (m.total_incidental_tons + m.total_minor_tons
                        + m.total_major_tons + m.mail_containers * 5)
            assert m.total_tons == expected, (
                f"seed {seed}: total_tons {m.total_tons} != sum {expected}"
            )

    def test_incidental_tonnage_upper_bound(self):
        w = _make_freight_world()
        for seed in range(50):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.total_incidental_tons <= m.lots.incidental * 6

    def test_minor_tonnage_multiples_of_5(self):
        w = _make_freight_world()
        for seed in range(50):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.total_minor_tons % 5 == 0, (
                f"seed {seed}: minor tons {m.total_minor_tons} not divisible by 5"
            )

    def test_major_tonnage_multiples_of_10(self):
        w = _make_freight_world()
        for seed in range(50):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.total_major_tons % 10 == 0, (
                f"seed {seed}: major tons {m.total_major_tons} not divisible by 10"
            )

    def test_zero_lots_means_zero_tons(self):
        # If incidental count is 0, incidental tons must also be 0
        w = _make_freight_world(population=0, starport="X", travel_zone="Red")
        for seed in range(30):
            m = generate_freight_lots(w, rng=random.Random(seed))
            if m.lots.incidental == 0:
                assert m.total_incidental_tons == 0
            if m.lots.minor == 0:
                assert m.total_minor_tons == 0
            if m.lots.major == 0:
                assert m.total_major_tons == 0


# ---------------------------------------------------------------------------
# generate_freight_lots — mail
# ---------------------------------------------------------------------------

class TestFreightMail:

    def test_mail_containers_zero_or_positive(self):
        w = _make_freight_world()
        for seed in range(50):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.mail_containers >= 0

    def test_mail_containers_at_most_6(self):
        w = _make_freight_world(population=9, starport="A", tech_level=15)
        for seed in range(200):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.mail_containers <= 6, (
                f"seed {seed}: mail_containers {m.mail_containers} > 6"
            )

    def test_mail_appears_on_high_traffic_world(self):
        # High-pop starport-A world should produce mail on at least some seeds
        w = _make_freight_world(population=9, starport="A", tech_level=15)
        mail_counts = [generate_freight_lots(w, rng=random.Random(s)).mail_containers
                       for s in range(200)]
        assert any(c > 0 for c in mail_counts), (
            "No mail generated across 200 seeds for a high-traffic world"
        )

    def test_mail_included_in_total_tons(self):
        w = _make_freight_world(population=9, starport="A", tech_level=15)
        for seed in range(100):
            m = generate_freight_lots(w, rng=random.Random(seed))
            assert m.total_tons >= m.mail_containers * 5


# ---------------------------------------------------------------------------
# generate_freight_lots — determinism and serialisation
# ---------------------------------------------------------------------------

class TestFreightDeterminism:

    def test_seed_reproducibility(self):
        w = _make_freight_world(population=7, starport="B", tech_level=10)
        m1 = generate_freight_lots(w, rng=random.Random(999))
        m2 = generate_freight_lots(w, rng=random.Random(999))
        assert m1.to_dict() == m2.to_dict()

    def test_different_seeds_may_differ(self):
        w = _make_freight_world(population=7, starport="B", tech_level=10)
        results = [generate_freight_lots(w, rng=random.Random(s)).total_tons
                   for s in range(20)]
        assert len(set(results)) > 1, "All seeds produced identical total_tons"

    def test_no_rng_argument(self):
        w = _make_freight_world()
        m = generate_freight_lots(w)
        assert isinstance(m, FreightManifest)

    def test_to_dict_has_required_keys(self):
        w = _make_freight_world()
        m = generate_freight_lots(w, rng=random.Random(1))
        d = m.to_dict()
        for key in ("world_name", "lots", "total_incidental_tons",
                    "total_minor_tons", "total_major_tons",
                    "mail_containers", "total_tons"):
            assert key in d, f"Missing key: {key}"

    def test_lots_dict_has_tier_keys(self):
        w = _make_freight_world()
        m = generate_freight_lots(w, rng=random.Random(1))
        lots = m.to_dict()["lots"]
        for key in ("incidental", "minor", "major"):
            assert key in lots, f"Missing lots key: {key}"

    def test_to_json_roundtrip(self):
        import json as _j
        w = _make_freight_world(population=8, starport="A")
        m = generate_freight_lots(w, rng=random.Random(42))
        d = _j.loads(m.to_json())
        assert d["total_tons"] == m.total_tons
        assert d["lots"]["incidental"] == m.lots.incidental

    def test_world_name_in_manifest(self):
        w = _make_freight_world(name="Mora")
        m = generate_freight_lots(w, rng=random.Random(1))
        assert m.world_name == "Mora"
        assert m.to_dict()["world_name"] == "Mora"


# ---------------------------------------------------------------------------
# POST /api/freight — FastAPI endpoint
# ---------------------------------------------------------------------------

class TestFreightEndpoint:

    def _world_json(self, **kwargs):
        return _freight_world_json(**kwargs)

    def test_valid_request_returns_200(self):
        resp = _FREIGHT_CLIENT.post("/api/freight",
                                    json=self._world_json(), params={"seed": "1"})
        assert resp.status_code == 200

    def test_response_has_world_name(self):
        resp = _FREIGHT_CLIENT.post("/api/freight",
                                    json=self._world_json(), params={"seed": "1"})
        assert resp.json()["world_name"] == "TestWorld"

    def test_response_has_lots_keys(self):
        resp = _FREIGHT_CLIENT.post("/api/freight",
                                    json=self._world_json(), params={"seed": "1"})
        data = resp.json()
        for key in ("lots", "total_incidental_tons", "total_minor_tons",
                    "total_major_tons", "mail_containers", "total_tons"):
            assert key in data, f"Missing key: {key}"

    def test_lots_sub_dict_has_tier_keys(self):
        resp = _FREIGHT_CLIENT.post("/api/freight",
                                    json=self._world_json(), params={"seed": "1"})
        lots = resp.json()["lots"]
        for key in ("incidental", "minor", "major"):
            assert key in lots, f"Missing lots key: {key}"

    def test_seed_reproducibility(self):
        body = self._world_json(population=7, starport="B")
        r1 = _FREIGHT_CLIENT.post("/api/freight", json=body, params={"seed": "42"})
        r2 = _FREIGHT_CLIENT.post("/api/freight", json=body, params={"seed": "42"})
        assert r1.json() == r2.json()

    def test_missing_body_returns_400(self):
        resp = _FREIGHT_CLIENT.post("/api/freight")
        assert resp.status_code == 400

    def test_invalid_json_body_returns_400(self):
        resp = _FREIGHT_CLIENT.post(
            "/api/freight",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_invalid_seed_returns_400(self):
        resp = _FREIGHT_CLIENT.post("/api/freight",
                                    json=self._world_json(), params={"seed": "abc"})
        assert resp.status_code == 400
