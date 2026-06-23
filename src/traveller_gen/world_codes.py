"""Shared constants and code enumerations for the Traveller world generator."""

from enum import IntEnum, StrEnum


class StarportCode(StrEnum):
    """UWP starport quality codes (Mongoose Traveller 2e, p.205)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    X = "X"


class TemperatureCategory(StrEnum):
    """World temperature categories derived from orbital position."""

    FROZEN    = "Frozen"
    COLD      = "Cold"
    TEMPERATE = "Temperate"
    HOT       = "Hot"
    BOILING   = "Boiling"


class TradeCode(StrEnum):
    """Standard Traveller trade classification codes."""

    AG = "Ag"
    AS = "As"
    BA = "Ba"
    DE = "De"
    FL = "Fl"
    GA = "Ga"
    HI = "Hi"
    HT = "Ht"
    IC = "Ic"
    IN = "In"
    LO = "Lo"
    LT = "Lt"
    NA = "Na"
    NI = "Ni"
    PO = "Po"
    RI = "Ri"
    VA = "Va"
    WA = "Wa"


class TravelZone(StrEnum):
    """Traveller travel zone classifications."""

    GREEN = "Green"
    AMBER = "Amber"
    RED   = "Red"


class AtmosphereCode(IntEnum):
    """UWP atmosphere codes (WBH pp.78-95)."""

    NONE              = 0
    TRACE             = 1
    VERY_THIN_TAINTED = 2
    VERY_THIN         = 3
    THIN_TAINTED      = 4
    THIN              = 5
    STANDARD          = 6
    STANDARD_TAINTED  = 7
    DENSE             = 8
    DENSE_TAINTED     = 9
    EXOTIC            = 10
    CORROSIVE         = 11
    INSIDIOUS         = 12
    DENSE_HIGH        = 13
    ELLIPSOIDAL       = 14
    UNUSUAL           = 15
    GAS_GIANT_H       = 16
    GAS_GIANT_I       = 17


try:
    from . import _version as _v  # type: ignore[import]
    APP_VERSION = ".".join(str(x) for x in _v.__version_tuple__)
except ImportError:
    APP_VERSION = "1.5.33"

_EHEX = "0123456789ABCDEFGHIJ"


def gg_diameter_from_sah(gg_sah: str) -> int:
    """Return the numeric diameter (Terran diameters) from a gas giant SAH string.

    E.g. 'GM9' → 9, 'GLE' → 14.  Returns 8 (mid-range default) on parse failure.
    """
    if len(gg_sah) >= 3:
        idx = _EHEX.find(gg_sah[2].upper())
        if idx >= 0:
            return idx
    return 8
