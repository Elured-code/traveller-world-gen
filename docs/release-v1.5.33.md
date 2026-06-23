# Traveller World Generator — v1.5.33 Release Notes

**2629 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds `cultural_extension` field to `culture_detail`
for T5 Cultural Extension (Cx) compatibility, and fixes App Insights request
telemetry timestamp precision.

---

## T5 Cultural Extension (Cx) Forward Conversion (Issue #141)

WBH p.254 defines the T5 Cx HASS format for expressing cultural traits as a
4-character eHex string, enabling compatibility with T5 and TravellerMap. This
release implements the forward conversion: when a world's cultural profile is
rolled or read from TravellerMap, the Cx value is now computed and stored on the
`CultureDetail` object.

**Conversion rules:**
- H (Heterogeneity) ← Diversity clamped to [max(1, Pop−5), Pop+5]
- A (Acceptance) ← Xenophilia clamped to [max(1, Imp+Pop−5), Imp+Pop+5]
- S (Strangeness) ← round(Uniqueness × 2/3)
- S2 (Symbols) ← Symbology clamped to [max(1, TL−5), TL+5]

Uninhabited worlds (Pop code 0) yield Cx "0000".

**API changes:**
- `generate_culture_detail()` gains an `importance: int = 0` parameter
- Both standard generation and TravellerMap read-back paths compute Cx
- World card displays "Cultural Extension (T5)" row when non-empty

---

## App Insights Request Timestamp Precision (Issue #153)

The `_ai_post_request()` telemetry function in `fastapi/app.py` previously
hardcoded milliseconds as `.000Z`, causing all requests within the same
wall-clock second to receive identical timestamps. This made it impossible to
reconstruct request order in burst scenarios (e.g., parallel UI requests).

Fixed to use microsecond precision:
```python
datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
```

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `cultural_extension` | `culture_detail` | string | Added — T5 Cx HASS eHex code (4 chars, e.g. "7567") |

---

## Backward Compatibility

`CultureDetail.from_dict()` defaults `cultural_extension` to `""` (empty string)
when the key is absent, so world JSON saved before v1.5.33 loads without error.
The `generate_culture_detail()` signature change (`importance` parameter added)
is safe because `importance` has a default value of 0; existing callers are
unaffected.

---

## Tests

17 new tests in `TestComputeCx` and `TestCulturalExtensionField` covering:
- Known-good Cx conversions (fixed traits → expected HASS)
- Clamping bounds for all four components
- Strangeness rounding
- Uninhabited world handling
- `to_dict()` / `from_dict()` round-trip
- Consistency between field and `_compute_cx()` helper

2629 tests pass (16 new in culture detail, 1 existing API test updated).
