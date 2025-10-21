from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps.base_steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    POWER_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractMicrowaveStep(AbstractXDLElementTemplate, AbstractStep):
    """Microwave reaction mass.


    Args:
        vessel (str): Vessel containing mixture to microwave.
        power (float): Power of microwave generator at which
            irradiation is carried out
        time (float): Time to stir vessel at given power.
        stir (bool): If ``True`` then stir vessel.
        stir_speed (float): Speed in RPM at which to stir.
        RP_limit (float): reflected power limit for generator
    """

    MANDATORY_NAME = "Microwave"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "power": float,
        "time": float,
        "temp": float,
        "stir": bool,
        "stir_speed": float,
        "RP_limit": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "stir": True,
        "stir_speed": "250 RPM",
        "power": None,
        "temp": None,
        "RP_limit": "50 W",  # it should be 0,1*power
    }

    MANDATORY_PROP_LIMITS = {
        "time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
        "power": POWER_PROP_LIMIT,  # needs to be implemented
        "temp": TEMP_PROP_LIMIT,
        "RP_limit": POWER_PROP_LIMIT,  # needs to be implemented
    }


class AbstractStartMicrowaveStep(AbstractXDLElementTemplate, AbstractStep):
    """Start the microwave.

    Name: StartMicrowave

    Mandatory props:
        vessel (vessel): Vessel to stop stirring.
    """

    MANDATORY_NAME = "StartMicrowave"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
    }


class AbstractStopMicrowaveStep(AbstractXDLElementTemplate, AbstractStep):
    """Stop the microwave.

    Name: StopMicrowave

    Mandatory props:
        vessel (vessel): Vessel to stop stirring.
    """

    MANDATORY_NAME = "StopMicrowave"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
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
