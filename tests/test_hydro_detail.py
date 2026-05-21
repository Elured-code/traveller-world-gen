"""Tests for traveller_hydro_detail.py — hydrographic percentage (Phase 1)."""

import pytest
from traveller_hydro_detail import (
    HydrographicDetail,
    generate_hydrographic_detail,
    _HYDRO_PCT_RANGE,
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
    monkeypatch.setattr("traveller_hydro_detail.random.randint", lambda lo, hi: lo)
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
    monkeypatch.setattr("traveller_hydro_detail.random.randint", lambda lo, hi: lo)
    r = generate_hydrographic_detail(0, 5)
    assert r is not None
    assert r.surface_liquid_pct == 0

def test_hydro0_pct_max(monkeypatch):
    monkeypatch.setattr("traveller_hydro_detail.random.randint", lambda lo, hi: hi)
    r = generate_hydrographic_detail(0, 5)
    assert r is not None
    assert r.surface_liquid_pct == 5

def test_hydro5_pct_midrange(monkeypatch):
    monkeypatch.setattr("traveller_hydro_detail.random.randint", lambda lo, hi: (lo + hi) // 2)
    r = generate_hydrographic_detail(5, 5)
    assert r is not None
    assert r.surface_liquid_pct == 50  # (46+55)//2

def test_hydro10_size1_uses_range(monkeypatch):
    monkeypatch.setattr("traveller_hydro_detail.random.randint", lambda lo, hi: hi)
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
    from traveller_world_gen import generate_world
    from traveller_hydro_detail import generate_hydrographic_detail as ghd
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
    from traveller_world_gen import generate_world
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
    import traveller_hydro_detail as m
    assert hasattr(m, "HydrographicDetail")
    assert hasattr(m, "generate_hydrographic_detail")
