from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractSonicateStep(AbstractXDLElementTemplate, AbstractStep):
    """Sonicate a reaction mixture.

    Name: Sonicate

    Mandatory Props:
        vessel (vessel): Vessel to sonicate.
        temp (float): Temperature to sonicate at.
        time (float): Time to sonicate for.
        stir (bool): If `True`, stir the vessel
        stir_speed (float): Stirring speed in RPM.
    """

    MANDATORY_NAME = "Sonicate"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "temp": float,
        "time": float,
        "stir": bool,
        "stir_speed": float,
    }

    MANDATORY_DEFAULT_PROPS = {"stir": True, "stir_speed": None}

    MANDATORY_PROP_LIMITS = {
        "temp": TEMP_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "vessel": VesselSpec(
                stir=self.stir, sonicate=True, min_temp=self.temp, max_temp=self.temp
            )
        }
