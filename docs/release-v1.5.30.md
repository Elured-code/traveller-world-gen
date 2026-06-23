# Traveller World Generator — v1.5.30 Release Notes

**2486 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds `tl_novelty` field to `tech_detail` and
extends the technology profile string format from `H-L-QQQQQ-TTTT-MM` to
`H-L-QQQQQ-TTTT-MM-N`.

---

## Novelty TL Placeholder (Issue #154)

The WBH §5 Social Characteristics procedure includes a Novelty TL sub-category
that captures per-nation variance in cutting-edge technology. The full procedure
has not yet been transcribed. This release adds the `tl_novelty` field as a
placeholder seeded to `tl_high_common` (the UWP TL — the ceiling all other
sub-TLs are bounded by) so the schema and profile string are complete and
forward-compatible.

The actual WBH §5 Novelty procedure will replace the placeholder in a future
session.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `tl_novelty` | `tech_detail` | integer, min 0 | Added — placeholder equals `tl_high_common` |
| `technology_profile` | `tech_detail` | string | Format extended: `H-L-QQQQQ-TTTT-MM` → `H-L-QQQQQ-TTTT-MM-N` |

---

## Backward Compatibility

`TechDetail.from_dict()` defaults `tl_novelty` to `0` when the key is absent,
so world JSON saved before v1.5.30 loads without error. The technology profile
string format change (adding the `-N` segment) is visible to any API consumer
that parses the string directly.

---

## Tests

8 new tests in `TestNoveltyTL` covering placeholder value, non-negative bound,
`to_dict` inclusion, profile format (6 dash-separated segments), and eHex
encoding. 3 additional tests in `TestRoundTrip` cover `tl_novelty` round-trip
and backward-compat `from_dict` with missing key. 2486 tests pass.
