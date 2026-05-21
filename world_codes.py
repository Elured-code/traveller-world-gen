from enum import IntEnum, StrEnum


class StarportCode(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    X = "X"


class TemperatureCategory(StrEnum):
    FROZEN    = "Frozen"
    COLD      = "Cold"
    TEMPERATE = "Temperate"
    HOT       = "Hot"
    BOILING   = "Boiling"


class TradeCode(StrEnum):
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
    GREEN = "Green"
    AMBER = "Amber"
    RED   = "Red"


class AtmosphereCode(IntEnum):
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
