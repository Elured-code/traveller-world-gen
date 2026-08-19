"""Tests for issue #44 Stages 2+3: gas escape table and retention filter.

Covers:
- _world_escape_value() formula correctness
- _GAS_ESCAPE_VALUES keys match _GAS_CODES keys (completeness check)
- apply_gas_retention_filter() removes non-retained gases
- apply_gas_retention_filter() keeps heavy gases
- gas_retention_applied flag set only when removal occurs
- No-op cases: empty gas_mix, temperature <= 0
- Unknown gas_name is conservatively retained
- Percentages of remaining components are unchanged
- AtmosphereDetail.to_dict() emits gas_retention_applied only when True
- AtmosphereDetail.from_dict() roundtrips gas_retention_applied
"""
import pytest

from traveller_gen.traveller_world_atmosphere_gen import (
    _world_escape_value,       # pylint: disable=protected-access
    _GAS_ESCAPE_VALUES,        # pylint: disable=protected-access
    _GAS_CODES,                # pylint: disable=protected-access
    apply_gas_retention_filter,
    AtmosphereDetail,
    GasMixComponent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _component(gas_name: str, percentage: int = 50) -> GasMixComponent:
    return GasMixComponent(
        gas_name=gas_name,
        gas_code=_GAS_CODES.get(gas_name, "XX"),
        percentage=percentage,
    )


def _detail(components: list) -> AtmosphereDetail:
    detail = AtmosphereDetail()
    detail.gas_mix = list(components)
    return detail


# ---------------------------------------------------------------------------
# _world_escape_value
# ---------------------------------------------------------------------------

class TestWorldEscapeValue:
    """_world_escape_value returns v_e² × 8 / T_K."""

    def test_earth_like(self):
        # v_e=11.2 km/s, T=280 K → 11.2² × 8 / 280
        expected = 11.2 ** 2 * 8.0 / 280
        assert abs(_world_escape_value(11.2, 280) - expected) < 1e-9

    def test_proportional_to_ve_squared(self):
        wev1 = _world_escape_value(5.0, 300)
        wev2 = _world_escape_value(10.0, 300)
        assert abs(wev2 / wev1 - 4.0) < 1e-9

    def test_inversely_proportional_to_temperature(self):
        wev_cold = _world_escape_value(8.0, 100)
        wev_warm = _world_escape_value(8.0, 400)
        assert abs(wev_cold / wev_warm - 4.0) < 1e-9


# ---------------------------------------------------------------------------
# _GAS_ESCAPE_VALUES completeness
# ---------------------------------------------------------------------------

class TestGasEscapeValuesCompleteness:
    """Every gas in _GAS_CODES should have an entry in _GAS_ESCAPE_VALUES."""

    def test_all_gas_codes_covered(self):
        missing = set(_GAS_CODES.keys()) - set(_GAS_ESCAPE_VALUES.keys())
        assert not missing, f"Missing escape values for: {missing}"

    def test_all_values_positive(self):
        for name, val in _GAS_ESCAPE_VALUES.items():
            assert val > 0, f"{name} has non-positive escape value {val}"

    def test_hydrogen_heaviest_to_escape(self):
        # H₂ should have the highest escape value (lightest molecule)
        assert _GAS_ESCAPE_VALUES["Hydrogen"] == max(_GAS_ESCAPE_VALUES.values())

    def test_sulphuric_acid_easiest_to_retain(self):
        # H₂SO₄ should have one of the lowest escape values (among non-particulate gases)
        # Silicates and Metal Vapours are particulate categories, may be lower
        heavy_molecular = {
            k: v for k, v in _GAS_ESCAPE_VALUES.items()
            if k not in ("Silicates", "Metal Vapours")
        }
        assert _GAS_ESCAPE_VALUES["Sulphuric Acid"] == min(heavy_molecular.values())


# ---------------------------------------------------------------------------
# apply_gas_retention_filter — no-op cases
# ---------------------------------------------------------------------------

class TestRetentionFilterNoOp:
    """Filter leaves detail unchanged in degenerate cases."""

    def test_empty_gas_mix(self):
        detail = _detail([])
        apply_gas_retention_filter(detail, escape_velocity_km_s=5.0, temperature_k=300)
        assert detail.gas_mix == []
        assert not detail.gas_retention_applied

    def test_zero_temperature(self):
        detail = _detail([_component("Hydrogen")])
        apply_gas_retention_filter(detail, escape_velocity_km_s=5.0, temperature_k=0)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied

    def test_all_gases_retained(self):
        # Earth-like: v_e=11.2, T=280 → world_escape≈3.59; CO₂ (0.91) kept
        detail = _detail([_component("Carbon Dioxide", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=11.2, temperature_k=280)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied


# ---------------------------------------------------------------------------
# apply_gas_retention_filter — light gases removed
# ---------------------------------------------------------------------------

class TestRetentionFilterRemovesLightGases:
    """Hydrogen and Helium are removed on small/hot worlds."""

    def test_hydrogen_removed_on_small_warm_world(self):
        # Size 4 ≈ v_e=5 km/s, T=250 K → world_escape = 5²×8/250 = 0.8
        # H₂ escape_value=20.0 > 0.8 → should be removed
        detail = _detail([_component("Hydrogen", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=5.0, temperature_k=250)
        assert detail.gas_mix == []
        assert detail.gas_retention_applied

    def test_helium_removed_on_small_world(self):
        # v_e=6, T=200 → world_escape = 6²×8/200 = 1.44; He=10.0 → removed
        detail = _detail([_component("Helium", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=6.0, temperature_k=200)
        assert detail.gas_mix == []
        assert detail.gas_retention_applied

    def test_mixed_mix_partial_removal(self):
        # H₂ (escape 20.0) removed, CO₂ (escape 0.91) kept
        # v_e=8, T=300 → world_escape = 8²×8/300 = 1.707
        detail = _detail([_component("Hydrogen", 20), _component("Carbon Dioxide", 80)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=8.0, temperature_k=300)
        assert len(detail.gas_mix) == 1
        assert detail.gas_mix[0].gas_name == "Carbon Dioxide"
        assert detail.gas_mix[0].percentage == 80  # unchanged
        assert detail.gas_retention_applied


# ---------------------------------------------------------------------------
# apply_gas_retention_filter — heavy gases kept
# ---------------------------------------------------------------------------

class TestRetentionFilterKeepsHeavyGases:
    """CO₂ and heavier gases are retained even on small worlds."""

    def test_co2_kept_on_small_world(self):
        # v_e=4, T=200 → world_escape = 4²×8/200 = 0.64; CO₂=0.91 → removed
        # Wait, 0.91 > 0.64 → CO₂ would also be removed here. Let me use higher v_e.
        # v_e=5, T=200 → world_escape = 5²×8/200 = 1.0; CO₂=0.91 ≤ 1.0 → kept
        detail = _detail([_component("Carbon Dioxide", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=5.0, temperature_k=200)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied

    def test_krypton_kept_on_moderate_world(self):
        # v_e=6, T=300 → world_escape = 6²×8/300 = 0.96; Kr=0.48 ≤ 0.96 → kept
        detail = _detail([_component("Krypton", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=6.0, temperature_k=300)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied

    def test_nitrogen_retained_on_earth_like(self):
        # v_e=11.2, T=280 → world_escape≈3.59; N₂=1.43 ≤ 3.59 → kept
        detail = _detail([_component("Nitrogen", 100)])
        apply_gas_retention_filter(detail, escape_velocity_km_s=11.2, temperature_k=280)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied


# ---------------------------------------------------------------------------
# apply_gas_retention_filter — unknown gas name
# ---------------------------------------------------------------------------

class TestRetentionFilterUnknownGas:
    """Gas names not in _GAS_ESCAPE_VALUES are conservatively kept."""

    def test_unknown_gas_retained(self):
        component = GasMixComponent(gas_name="Unobtanium", gas_code="UO", percentage=100)
        detail = _detail([component])
        apply_gas_retention_filter(detail, escape_velocity_km_s=1.0, temperature_k=10000)
        assert len(detail.gas_mix) == 1
        assert not detail.gas_retention_applied


# ---------------------------------------------------------------------------
# gas_retention_applied serialisation
# ---------------------------------------------------------------------------

class TestGasRetentionAppliedSerialisation:
    """gas_retention_applied is emitted in to_dict() only when True."""

    def test_not_emitted_by_default(self):
        detail = AtmosphereDetail()
        d = detail.to_dict()
        assert "gas_retention_applied" not in d

    def test_emitted_when_true(self):
        detail = AtmosphereDetail()
        detail.gas_retention_applied = True
        d = detail.to_dict()
        assert d.get("gas_retention_applied") is True

    def test_roundtrip_true(self):
        detail = AtmosphereDetail()
        detail.gas_retention_applied = True
        restored = AtmosphereDetail.from_dict(detail.to_dict())
        assert restored.gas_retention_applied is True

    def test_roundtrip_false(self):
        detail = AtmosphereDetail()
        restored = AtmosphereDetail.from_dict(detail.to_dict())
        assert restored.gas_retention_applied is False
