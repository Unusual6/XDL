from typing import Dict

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
    VOLUME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractDissolveStep(AbstractXDLElementTemplate, AbstractStep):
    """Dissolve solid in solvent.

    Name: Dissolve

    Mandatory props:
        vessel (vessel): Vessel containing solid to dissolve.
        solvent (reagent): Solvent to dissolve solid in.
        volume (float): Volume of solvent to use.
        amount (str): amount of reagent to add in moles, grams or equivalents.
        temp (float): Temperature to heat vessel to while dissolving solid.
        time (float): Time to stir/heat for in order to dissolve solid.
        stir_speed (float): Speed in RPM at which to stir while dissolving
            solid.
    """

    MANDATORY_NAME = "Dissolve"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "solvent": REAGENT_PROP_TYPE,
        "volume": float,
        "temp": float,
        "time": float,
        "stir_speed": float,
        "amount": str,
    }

    MANDATORY_DEFAULT_PROPS = {
        "time": None,
        "temp": None,
        "stir_speed": None,
        "volume": None,
        "amount": None,
    }

    MANDATORY_PROP_LIMITS = {
        "volume": VOLUME_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "vessel": VesselSpec(stir=True, min_temp=self.temp, max_temp=self.temp),
        }
