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


class AbstractEvaporateStep(AbstractXDLElementTemplate, AbstractStep):
    """Evaporate solvent.

    Name: Evaporate

    Mandatory props:
        vessel (vessel): Vessel to evaporate solvent from.
        pressure (float): Vacuum pressure to use for evaporation.
        temp (float): Temperature to heat contents of vessel to for evaporation.
        time (float): Time to evaporate for.
        stir_speed (float): Speed at which to stir mixture during
            evaporation. If using traditional rotavap, speed in RPM at
            which to rotate evaporation flask.
    """

    MANDATORY_NAME = "Evaporate"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "pressure": float,
        "time": float,
        "temp": float,
        "stir_speed": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "time": None,
        "temp": None,
        "pressure": None,
        "stir_speed": None,
    }

    MANDATORY_PROP_LIMITS = {
        "time": TIME_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
        "pressure": PRESSURE_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "vessel": VesselSpec(
                evaporate=True,
                min_temp=self.temp,
                max_temp=self.temp,
            ),
        }
