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

from traveller_gen.traveller_world_cargo_gen import (
    CargoLot,
    CargoManifest,
    _PURCHASE_PCT,
    _TRADE_GOODS,
    _purchase_pct,
    generate_cargo_manifest,
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
