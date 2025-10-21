from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    PRESSURE_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractHydrogenateStep(AbstractXDLElementTemplate, AbstractStep):
    """Hydrogenate a reaction mixture in a given vessel at a given temperature
    for a set time.

    Name: Hydrogenate

    Mandatory Props:
        vessel (vessel): Vessel to hydrogenate.
        time (float): Time to hydrogenate for.
        temp (float): Temperature to hydrogenate at.
        pressure (float): Pressure of the vessel in mBar.
        stir (bool): If `True`, stir the vessel.
        stir_speed (float): Stirring speed in RPM.
    """

    MANDATORY_NAME = "Hydrogenate"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "time": float,
        "temp": float,
        "pressure": float,
        "stir": bool,
        "stir_speed": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "pressure": None,
        "stir": True,
        "stir_speed": None,
    }

    MANDATORY_PROP_LIMITS = {
        "time": TIME_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
        "pressure": PRESSURE_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "vessel": VesselSpec(
                stir=self.stir, hydrogenate=True, min_temp=self.temp, max_temp=self.temp
            )
        }
