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


class AbstractSublimateStep(AbstractXDLElementTemplate, AbstractStep):
    """Sublimate a reaction mixture in a given vessel.

    Name: Sublimate

    Mandatory Props:
        vessel (vessel): Vessel to sublimate.
        temp (float): Temperature of the sublimation.
        time (float): Time to sublimate for.
        stir (bool): If `True`, stir the vessel.
        stir_speed (float): Stirring speed in RPM.
    """

    MANDATORY_NAME = "Sublimate"

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
                stir=self.stir, sublimate=True, min_temp=self.temp, max_temp=self.temp
            )
        }
