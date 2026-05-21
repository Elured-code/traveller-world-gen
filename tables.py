# Display-layer lookup tables — single source of truth for all label/mapping data
# used across to_dict(), summary(), to_html_context(), gen-ui, and JSON rendering.
#
# Physics constants (e.g. _DIAMETER_BASE_KM, SIZE_GRAVITY_G) live beside the code
# that uses them for calculations and are NOT duplicated here.

# Size → diameter display label (no " km" suffix — callers append when needed)
SIZE_DIAMETER_LABEL: dict[int, str] = {
    0: "<1,000", 1: "1,600",  2: "3,200",  3: "4,800",
    4: "6,400",  5: "8,000",  6: "9,600",  7: "11,200",
    8: "12,800", 9: "14,400", 10: "16,000",
}

# Size → surface gravity display label
SIZE_GRAVITY_LABEL: dict[int, str] = {
    0: "negligible", 1: "0.05G", 2: "0.15G", 3: "0.25G",
    4: "0.35G",      5: "0.45G", 6: "0.70G", 7: "0.90G",
    8: "1.00G",      9: "1.25G", 10: "1.40G",
}

# Population code → range description
POPULATION_RANGE: dict[int, str] = {
    0: "None",              1: "Few (1+)",              2: "Hundreds",
    3: "Thousands",         4: "Tens of thousands",     5: "Hundreds of thousands",
    6: "Millions",          7: "Tens of millions",      8: "Hundreds of millions",
    9: "Billions",          10: "Tens of billions",
}

# Trade code → full display label  (canonical: "Ag — Agricultural")
TRADE_CODE_FULL: dict[str, str] = {
    "Ag": "Ag — Agricultural",     "As": "As — Asteroid",
    "Ba": "Ba — Barren",           "De": "De — Desert",
    "Fl": "Fl — Fluid Oceans",     "Ga": "Ga — Garden",
    "Hi": "Hi — High Population",  "Ht": "Ht — High Tech",
    "Ic": "Ic — Ice-Capped",       "In": "In — Industrial",
    "Lo": "Lo — Low Population",   "Lt": "Lt — Low Tech",
    "Na": "Na — Non-Agricultural", "Ni": "Ni — Non-Industrial",
    "Po": "Po — Poor",             "Ri": "Ri — Rich",
    "Va": "Va — Vacuum",           "Wa": "Wa — Waterworld",
}

# Base facility code → full display label  (canonical: "N — Naval")
# To obtain a bare name (e.g. for JSON), use: BASE_FULL[code].split(" — ", 1)[-1]
BASE_FULL: dict[str, str] = {
    "N": "N — Naval",      "S": "S — Scout",    "W": "W — Way Station",
    "D": "D — Depot",      "M": "M — Military", "H": "H — Highport",
    "C": "C — Corsair",
}

# Travel zone → CSS class name
ZONE_CSS_CLASS: dict[str, str] = {
    "Green": "zone-green", "Amber": "zone-amber", "Red": "zone-red",
}

# Tidal lock status → human-readable label
TIDAL_STATUS_LABELS: dict[str, str] = {
    "braking":    "Tidal braking",
    "prograde":   "Prograde (tidally slowed)",
    "retrograde": "Retrograde (tidally induced)",
    "3:2_lock":   "3:2 resonance lock",
    "1:1_lock":   "1:1 tidal lock (synchronous)",
}
