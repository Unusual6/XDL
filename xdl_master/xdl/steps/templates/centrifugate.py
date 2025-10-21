from typing import Dict

from xdl_master.xdl.constants import ROOM_TEMPERATURE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractCentrifugateStep(AbstractXDLElementTemplate, AbstractStep):
    """Centrifugation reaction.


    Args:
         vessel (str): Vessel containing mixture to microwave.
        time (float): Time to stir vessel at given power.
        rotation_speed (float): speed of the centrifuge
        temp (float): centrifuge temperature.
    """

    MANDATORY_NAME = "Centrifugate"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "rotation_speed": float,
        "time": float,
        "temp": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "rotation_speed": "4000 RPM",
        "time": "5 min",
        "temp": ROOM_TEMPERATURE,
    }

    MANDATORY_PROP_LIMITS = {
        "rotation_speed": ROTATION_SPEED_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "vessel": VesselSpec(
                irradiate=True,
                stir=self.stir,
                min_temp=self.temp,
                max_temp=self.temp,
            ),
        }
