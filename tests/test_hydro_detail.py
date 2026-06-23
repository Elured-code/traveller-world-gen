"""Tests for traveller_hydro_detail.py — hydrographic detail (Phases 1 and 2)."""

import pytest
from traveller_gen.traveller_hydro_detail import (
    HydrographicDetail,
    generate_hydrographic_detail,
    _HYDRO_PCT_RANGE,
    _FLUID_TYPE_BY_TEMP,
    _AMMONIA_ELIGIBLE_ATMS,
    _fluid_type,
)


# ---------------------------------------------------------------------------
# _HYDRO_PCT_RANGE table sanity
# ---------------------------------------------------------------------------

def test_range_table_has_all_codes():
    assert set(_HYDRO_PCT_RANGE) == set(range(11))

def test_range_table_code0():
    assert _HYDRO_PCT_RANGE[0] == (0, 5)

def test_range_table_code10():
    assert _HYDRO_PCT_RANGE[10] == (96, 100)

def test_range_bounds_contiguous():
    """Each code's low is one above the previous code's high (codes 1-10)."""
    for code in range(1, 11):
        prev_low, prev_high = _HYDRO_PCT_RANGE[code - 1]
        this_low, _ = _HYDRO_PCT_RANGE[code]
        assert this_low == prev_high + 1, f"gap between code {code-1} and {code}"


# ---------------------------------------------------------------------------
# generate_hydrographic_detail — return None cases
# ---------------------------------------------------------------------------

def test_returns_none_for_size_0():
    result = generate_hydrographic_detail(hydrographics=5, size=0)
    assert result is None

def test_returns_none_for_hydro_negative():
    result = generate_hydrographic_detail(hydrographics=-1, size=5)
    assert result is None

def test_returns_none_for_hydro_above_10():
    result = generate_hydrographic_detail(hydrographics=11, size=5)
    assert result is None


# ---------------------------------------------------------------------------
# generate_hydrographic_detail — always-100 special case
# ---------------------------------------------------------------------------

def test_size_gt9_hydro10_always_100():
    for size in (10, 11, 15):
        result = generate_hydrographic_detail(hydrographics=10, size=size)
        assert result is not None
        assert result.surface_liquid_pct == 100, f"size={size}"

def test_size_9_hydro10_not_forced_100(monkeypatch):
    """Size exactly 9 with Hydro 10 should use the random range, not always 100."""
    monkeypatch.setattr("traveller_gen.traveller_hydro_detail.random.randint", lambda lo, hi: lo)
    result = generate_hydrographic_detail(hydrographics=10, size=9)
    assert result is not None
    assert result.surface_liquid_pct == 96


# ---------------------------------------------------------------------------
# generate_hydrographic_detail — range correctness for each code
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hydro,size", [
    (code, 5) for code in range(11)
])
def test_pct_within_range_100_samples(hydro, size):
    if size == 0:
        return
    low, high = _HYDRO_PCT_RANGE[hydro]
    for _ in range(100):
        result = generate_hydrographic_detail(hydro, size)
        assert result is not None
        assert low <= result.surface_liquid_pct <= high, (
            f"hydro={hydro}: {result.surface_liquid_pct} not in [{low},{high}]"
        )

def test_hydro0_pct_min(monkeypatch):
    monkeypatch.setattr("traveller_gen.traveller_hydro_detail.random.randint", lambda lo, hi: lo)
    r = generate_hydrographic_detail(0, 5)
    assert r is not None
    assert r.surface_liquid_pct == 0

def test_hydro0_pct_max(monkeypatch):
    monkeypatch.setattr("traveller_gen.traveller_hydro_detail.random.randint", lambda lo, hi: hi)
    r = generate_hydrographic_detail(0, 5)
    assert r is not None
    assert r.surface_liquid_pct == 5

def test_hydro5_pct_midrange(monkeypatch):
    monkeypatch.setattr("traveller_gen.traveller_hydro_detail.random.randint", lambda lo, hi: (lo + hi) // 2)
    r = generate_hydrographic_detail(5, 5)
    assert r is not None
    assert r.surface_liquid_pct == 50  # (46+55)//2

def test_hydro10_size1_uses_range(monkeypatch):
    monkeypatch.setattr("traveller_gen.traveller_hydro_detail.random.randint", lambda lo, hi: hi)
    r = generate_hydrographic_detail(10, 1)
    assert r is not None
    assert r.surface_liquid_pct == 100


# ---------------------------------------------------------------------------
# HydrographicDetail dataclass
# ---------------------------------------------------------------------------

def test_to_dict_has_surface_liquid_pct():
    hd = HydrographicDetail(surface_liquid_pct=42)
    d = hd.to_dict()
    assert d == {"surface_liquid_pct": 42}

def test_to_dict_keys_only():
    hd = HydrographicDetail(surface_liquid_pct=0)
    assert set(hd.to_dict().keys()) == {"surface_liquid_pct"}


# ---------------------------------------------------------------------------
# World integration — to_dict includes surface_liquid_pct
# ---------------------------------------------------------------------------

def test_world_to_dict_includes_detail_nested():
    from traveller_gen.traveller_world_gen import generate_world
    from traveller_gen.traveller_hydro_detail import generate_hydrographic_detail as ghd
    import random
    random.seed(42)
    world = generate_world()
    world.hydrographic_detail = ghd(world.hydrographics, world.size)
    d = world.to_dict()
    if world.size > 0:
        assert "detail" in d["hydrographics"]
        detail = d["hydrographics"]["detail"]
        assert "surface_liquid_pct" in detail
        pct = detail["surface_liquid_pct"]
        assert isinstance(pct, int)
        low, high = _HYDRO_PCT_RANGE[world.hydrographics]
        assert low <= pct <= high

def test_world_to_dict_no_detail_when_absent():
    from traveller_gen.traveller_world_gen import generate_world
    import random
    random.seed(1)
    world = generate_world()
    world.hydrographic_detail = None
    d = world.to_dict()
    assert "detail" not in d["hydrographics"]
    assert "surface_liquid_pct" not in d["hydrographics"]


# ---------------------------------------------------------------------------
# HydrographicDetail is importable from the module
# ---------------------------------------------------------------------------

def test_exports():
    from traveller_gen import traveller_hydro_detail as m
    assert hasattr(m, "HydrographicDetail")
    assert hasattr(m, "generate_hydrographic_detail")


# ---------------------------------------------------------------------------
# Phase 2 — _fluid_type() helper (WBH pp.91-92)
# ---------------------------------------------------------------------------

class TestFluidTypeHelper:
    """Unit tests for the _fluid_type() pure function."""

    def test_temperate_is_water(self):
        assert _fluid_type(0, "Temperate") == "Water"

    def test_hot_is_water(self):
        assert _fluid_type(0, "Hot") == "Water"

    def test_boiling_is_sulfuric_acid(self):
        assert _fluid_type(0, "Boiling") == "Sulfuric Acid"

    def test_cold_standard_atm_is_water(self):
        # Standard breathable atmosphere (code 0–9) + Cold → Water, not Ammonia
        for atm in range(10):
            assert _fluid_type(atm, "Cold") == "Water", f"atm={atm}"

    def test_cold_exotic_atm_is_ammonia(self):
        # Exotic/corrosive/insidious atmospheres (10–15) + Cold → Ammonia
        for atm in _AMMONIA_ELIGIBLE_ATMS:
            assert _fluid_type(atm, "Cold") == "Ammonia", f"atm={atm}"

    def test_frozen_is_liquid_hydrocarbons(self):
        assert _fluid_type(0, "Frozen") == "Liquid Hydrocarbons"

    def test_gas_atmosphere_16_returns_none(self):
        assert _fluid_type(16, "Temperate") is None

    def test_gas_atmosphere_17_returns_none(self):
        assert _fluid_type(17, "Cold") is None

    def test_normal_atmosphere_not_overridden(self):
        assert _fluid_type(6, "Temperate") == "Water"

    def test_fluid_table_covers_all_temperature_zones(self):
        zones = {"Boiling", "Hot", "Temperate", "Cold", "Frozen"}
        assert set(_FLUID_TYPE_BY_TEMP.keys()) == zones

    def test_unknown_temperature_returns_none(self):
        assert _fluid_type(0, "Unknown") is None


# ---------------------------------------------------------------------------
# Phase 2 — generate_hydrographic_detail() with atmosphere/temperature
# ---------------------------------------------------------------------------

class TestFluidTypeIntegration:
    """Integration tests for fluid type via generate_hydrographic_detail()."""

    def test_fluid_type_absent_for_desert_world(self):
        result = generate_hydrographic_detail(0, 5, temperature="Temperate")
        assert result is not None
        assert result.fluid_type is None

    def test_fluid_type_water_for_temperate(self):
        result = generate_hydrographic_detail(5, 5, temperature="Temperate")
        assert result is not None
        assert result.fluid_type == "Water"

    def test_fluid_type_water_for_cold_standard_atm(self):
        # Standard atmosphere (code 5) + Cold → Water (not Ammonia)
        result = generate_hydrographic_detail(5, 5, atmosphere=5, temperature="Cold")
        assert result is not None
        assert result.fluid_type == "Water"

    def test_fluid_type_ammonia_for_cold_exotic_atm(self):
        # Exotic atmosphere (code 10) + Cold → Ammonia
        result = generate_hydrographic_detail(5, 5, atmosphere=10, temperature="Cold")
        assert result is not None
        assert result.fluid_type == "Ammonia"

    def test_fluid_type_liquid_hydrocarbons_for_frozen(self):
        result = generate_hydrographic_detail(5, 5, temperature="Frozen")
        assert result is not None
        assert result.fluid_type == "Liquid Hydrocarbons"

    def test_fluid_type_none_for_gas_atmosphere(self):
        result = generate_hydrographic_detail(5, 5, atmosphere=16, temperature="Temperate")
        assert result is not None
        assert result.fluid_type is None

    def test_fluid_type_absent_for_size_0(self):
        result = generate_hydrographic_detail(5, 0, temperature="Temperate")
        assert result is None

    def test_backward_compat_no_kwargs(self):
        result = generate_hydrographic_detail(5, 5)
        assert result is not None
        assert result.surface_liquid_pct >= 0
        assert result.fluid_type == "Water"  # default temperature="Temperate"

    def test_to_dict_includes_fluid_type_when_set(self):
        # Use exotic atmosphere so fluid_type is Ammonia and present in dict
        result = generate_hydrographic_detail(5, 5, atmosphere=10, temperature="Cold")
        assert result is not None
        d = result.to_dict()
        assert "fluid_type" in d
        assert d["fluid_type"] == "Ammonia"

    def test_to_dict_omits_fluid_type_for_desert_world(self):
        result = generate_hydrographic_detail(0, 5, temperature="Temperate")
        assert result is not None
        d = result.to_dict()
        assert "fluid_type" not in d

    def test_surface_liquid_pct_unchanged_by_new_params(self):
        import random
        random.seed(99)
        result = generate_hydrographic_detail(5, 5, atmosphere=6, temperature="Temperate")
        assert result is not None
        assert 46 <= result.surface_liquid_pct <= 55
