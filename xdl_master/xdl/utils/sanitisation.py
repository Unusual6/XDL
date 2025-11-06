"""This module provides functions for parsing strings to appropriate units,
and converting values to floats in standard units.
"""

import re
from typing import Callable, Dict, Type, Union

from xdl_master.xdl.utils.prop_limits import (
    BOOL_PROP_LIMIT,
    POSITIVE_FLOAT_PROP_LIMIT,
    POSITIVE_INT_PROP_LIMIT,
    PropLimit,
)

#############
# Constants #
#############

#: Default prop limits to use for types if no prop limit is given.
DEFAULT_PROP_LIMITS: Dict[Type, PropLimit] = {
    float: POSITIVE_FLOAT_PROP_LIMIT,
    int: POSITIVE_INT_PROP_LIMIT,
    bool: BOOL_PROP_LIMIT,
}

#: Regex pattern to match all of '1', '-1', '1.0', '-1.0' etc.
FLOAT_REGEX_PATTERN: str = r"([-]?[0-9]+(?:[.][0-9]+)?)"

#: Regex pattern to match optional units in quantity strings
#: e.g. match 'mL' in '5 mL'. The 3 is there to match 'cm3'.
UNITS_REGEX_PATTERN: str = r"[a-zA-Zμ°]+[3]?"

#########
# Utils #
#########


def parse_bool(s: str) -> Union[bool, None]:
    """Parse bool from string.

    Args:
        s (str): String representing bool.

    Returns:
        bool: ``True`` if ``s`` lower case is ``'true'``, ``False`` if ``s``
            lower case is ``'false'``, otherwise ``None``.
    """
    if isinstance(s, bool):
        return s
    elif type(s) == str:
        if s.lower() == "true":
            return True
        elif s.lower() == "false":
            return False
    else:
        return None


########################
# Unit Standardisation #
########################


def no_conversion(x: float) -> float:
    """Leave value unchanged."""
    return x


def days_to_seconds(x: float) -> float:
    """Convert time in days to seconds.

    Args:
        x (float): Time in days.

    Returns:
        float: Time in seconds.
    """
    return x * 60 * 60 * 24


def minutes_to_seconds(x: float) -> float:
    """Convert time in minutes to seconds.

    Args:
        x (float): Time in minutes.

    Returns:
        float: Time in seconds.
    """
    return x * 60


def hours_to_seconds(x: float) -> float:
    """Convert time in hours to seconds.

    Args:
        x (float): Time in hours.

    Returns:
        float: Time in seconds.
    """
    return x * 60 * 60


def cl_to_ml(x: float) -> float:
    """Convert volume in cL to mL.

    Args:
        x (float): Volume in cL.

    Returns:
        float: Volume in mL
    """
    return x * 10


def dl_to_ml(x: float) -> float:
    """Convert volume in dL to mL.

    Args:
        x (float): Volume in dL.

    Returns:
        float: Volume in mL
    """
    return x * 10**2


def l_to_ml(x: float) -> float:
    """Convert volume in L to mL.

    Args:
        x (float): Volume in L.

    Returns:
        float: Volume in mL
    """
    return x * 10**3


def ul_to_ml(x: float) -> float:
    """Convert volume in uL to mL.

    Args:
        x (float): Volume in uL.

    Returns:
        float: Volume in mL
    """
    return x * 10**-3


def kilogram_to_grams(x: float) -> float:
    """Convert mass in kg to g.

    Args:
        x (float): Mass in kg.

    Returns:
        float: Mass in g
    """
    return x * 10**3


def milligram_to_grams(x: float) -> float:
    """Convert mass in mg to g.

    Args:
        x (float): Mass in mg.

    Returns:
        float: Mass in g
    """
    return x * 10**-3


def microgram_to_grams(x: float) -> float:
    """Convert mass in ug to g.

    Args:
        x (float): Mass in ug.

    Returns:
        float: Mass in g
    """
    return x * 10**-6


def mmol_to_mol(x: float) -> float:
    """Converts mmol to mol

    Args:
        x (float): Value in mmol

    Returns:
        float: Value in mol
    """
    return x * 10**-3


def nmol_to_mol(x: float) -> float:
    """Converts nmol to mol

    Args:
        x (float): Value in nmol

    Returns:
        float: Value in mol
    """
    return x * 10**-9


def kilowatt_to_watt(x: float) -> float:
    """Convert power in kW to W.

    Args:
        x (float): Power in kW.

    Returns:
        float: Power in Watt
    """
    return x * 10**3


def megawatt_to_watt(x: float) -> float:
    """Convert power in MW to W.

    Args:
        x (float): Power in MW.

    Returns:
        float: Power in Watt
    """
    return x * 10**6


#: Dict of units and functions to convert them to standard units. The majority
#  of units are not case-sensitive. In the event that a unit is present in
#  more than one case, this unit must be expressed in proper case.
#: Standard units are mL (volume), grams (mass), mbar (pressure),
#: seconds (time), °C (temperature), RPM (rotation speed) and nm (length).
UNIT_CONVERTERS: Dict[str, Callable] = {
    "ml": no_conversion,
    "millilitre": no_conversion,
    "milliliter": no_conversion,
    "milliliters": no_conversion,
    "millilitres": no_conversion,
    "cm3": no_conversion,
    "cc": no_conversion,
    "cl": cl_to_ml,
    "centilitre": cl_to_ml,
    "centiliter": cl_to_ml,
    "centilitres": cl_to_ml,
    "centiliters": cl_to_ml,
    "dl": dl_to_ml,
    "decilitre": dl_to_ml,
    "deciliter": dl_to_ml,
    "decilitres": dl_to_ml,
    "deciliters": dl_to_ml,
    "l": l_to_ml,
    "liter": l_to_ml,
    "litre": l_to_ml,
    "liters": l_to_ml,
    "litres": l_to_ml,
    "μl": ul_to_ml,
    "ul": ul_to_ml,
    "microlitre": ul_to_ml,
    "microliter": ul_to_ml,
    "microlitres": ul_to_ml,
    "microliters": ul_to_ml,
    "kg": kilogram_to_grams,
    "kilogram": kilogram_to_grams,
    "kilograms": kilogram_to_grams,
    "g": no_conversion,
    "gram": no_conversion,
    "grams": no_conversion,
    "mg": milligram_to_grams,
    "milligram": milligram_to_grams,
    "milligrams": milligram_to_grams,
    "ug": microgram_to_grams,
    "μg": microgram_to_grams,
    "microgram": microgram_to_grams,
    "micrograms": microgram_to_grams,
    "°c": lambda x: x,
    "k": lambda x: x - 273.15,
    "f": lambda x: (x - 32) / 1.8,
    "days": days_to_seconds,
    "day": days_to_seconds,
    "h": hours_to_seconds,
    "hour": hours_to_seconds,
    "hours": hours_to_seconds,
    "hr": hours_to_seconds,
    "hrs": hours_to_seconds,
    "m": minutes_to_seconds,
    "min": minutes_to_seconds,
    "mins": minutes_to_seconds,
    "minute": minutes_to_seconds,
    "minutes": minutes_to_seconds,
    "s": no_conversion,
    "sec": no_conversion,
    "secs": no_conversion,
    "second": no_conversion,
    "seconds": no_conversion,
    "mbar": no_conversion,
    "bar": lambda x: x * 10**3,
    "torr": lambda x: x * 1.33322,
    "mmhg": lambda x: x * 1.33322,
    "atm": lambda x: x * 1013.25,
    "pa": lambda x: x * 0.01,
    "rpm": lambda x: x,
    "nm": lambda x: x,
    "mol": no_conversion,
    "mmol": mmol_to_mol,
    "nmol": nmol_to_mol,
    "g/mol": no_conversion,
    "mg/mol": milligram_to_grams,
    "ug/mol": microgram_to_grams,
    "g/mL": no_conversion,
    "mg/mL": milligram_to_grams,
    "ug/mL": microgram_to_grams,
    "g/cm3": no_conversion,
    "mg/cm3": milligram_to_grams,
    "ug/cm3": microgram_to_grams,
    "mol/L": no_conversion,
    "mmol/L": mmol_to_mol,
    "mmol/mL": no_conversion,
    "M": no_conversion,
    "mM": mmol_to_mol,
    "nM": nmol_to_mol,
    "equivalent": no_conversion,
    "equivalents": no_conversion,
    "equiv": no_conversion,
    "equivs": no_conversion,
    "eq": no_conversion,
    "mol/eq": no_conversion,
    "mmol/eq": mmol_to_mol,
    "W": no_conversion,
    "kW": kilowatt_to_watt,
    "MW": megawatt_to_watt,
}


def convert_val_to_std_units(
    val: Union[str, float],
    case_sensitive: bool = False,
) -> float:
    """Given str of value with/without units, convert it into standard unit and
    return float value. If given value is float, return unchanged.

    Standard units:

    time      seconds
    volume    mL
    pressure  mbar
    temp      °c
    mass      g

    Arguments:
        val (Union[str, float]): Value (and units) as str, or float. If no units
            are specified it is assumed value is already in default units. If
            value if float it is returned unchanged.
    Returns:
        float: Value in default units.
    """
    # Val is already float, just return it.
    if type(val) != str:
        return val

    # Get number from string
    number_search = re.search(FLOAT_REGEX_PATTERN, val)
    if number_search:
        number = float(number_search[0])

        # Get unit from string
        unit_search = re.search(UNITS_REGEX_PATTERN, val)
        if unit_search:
            unit = unit_search[0]

            #  some units are case-sensitive with uppercase characters ('M',
            #  'mM')
            if unit not in UNIT_CONVERTERS:
                unit = unit.lower()

            # Convert number to standard units
            return UNIT_CONVERTERS[unit](number)

        # No unit found, just return number
        else:
            return number

    # Can't even find number in string, return val unchanged.
    return val


def amount_str_to_units(amount: str) -> Union[str, None]:
    """'amount' prop can be in any one of several sets of units (g, mol,
    equivs). To keep track of these units when performing calculations, this
    prop is not sanitised directly in XDLBase. Instead, the units are parsed
    here so units can be tracked easily in steps.

    Returns:
        str: standardised units
    """
    # Get unit from string
    if amount:
        unit_search = re.search(UNITS_REGEX_PATTERN, amount)
        if unit_search:
            unit = unit_search[0]

            if unit.lower() in VOLUME_UNITS:
                return "mL"
            elif unit.lower() in MASS_UNITS:
                return "g"
            elif unit.lower() in MOLE_UNITS:
                return "mol"
            elif unit.lower() in EQUIV_UNITS:
                return "equivalents"

    return None


def amount_to_float(amount: str) -> float:
    """'amount' prop can be in any one of several sets of units (g, mol,
    equivs). To keep track of these units when performing calculations, this
    prop is not sanitised directly in XDLBase. Instead, the final float value of
    amount is parsed here so it can be tracked easily in steps.
    """
    return convert_val_to_std_units(amount)


#  full list of acceptable volume units - these can be converted to mL
VOLUME_UNITS = [
    "ml",
    "millilitre",
    "milliliter",
    "milliliters",
    "millilitres",
    "cm3",
    "cc",
    "cl",
    "centilitre",
    "centiliter",
    "centilitres",
    "centiliters",
    "dl",
    "decilitre",
    "deciliter",
    "decilitres",
    "deciliters",
    "l",
    "liter",
    "litre",
    "liters",
    "litres",
    "μl",
    "ul",
    "microlitre",
    "microliter",
    "microlitres",
    "microliters",
]

# full list of acceptable mass units - these can be converted to g
MASS_UNITS = [
    "kg",
    "kilogram",
    "kilograms",
    "g",
    "gram",
    "grams",
    "mg",
    "milligram",
    "milligrams",
    "ug",
    "μg",
    "microgram",
    "micrograms",
]

#  full list of mol units - these can be converted to mol
MOLE_UNITS = ["mol", "mmol"]

#  full list of equivalent units - these can all be used to refer to
#  'equivalents'
EQUIV_UNITS = ["eq", "eqs", "equiv", "equivs", "equivalent", "equivalents"]
