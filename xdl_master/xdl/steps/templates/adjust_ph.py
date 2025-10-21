from typing import Dict

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    PH_RANGE_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractAdjustPHStep(AbstractXDLElementTemplate, AbstractStep):
    """Adjust the pH of a reaction mixture with a given reagent.

    Name: AdjustPH

    Mandatory Props:
        vessel (vessel): Vessel to adjust the pH of.
        reagent (reagent): Reagent to use to adjust the pH.
        pH (float): Target pH of the adjustment.
        volume_increment (float): Volume to add to adjust the pH.
        stir (bool): If `True` then stir the vessel.
        stir_time (float): Time to stir for.
        stir_speed (float): Stirring speed in RPM.
    """

    MANDATORY_NAME = "AdjustPH"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "reagent": REAGENT_PROP_TYPE,
        "pH": float,
        "volume_increment": float,
        "stir": bool,
        "stir_time": float,
        "stir_speed": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "pH": None,
        "volume_increment": "1 mL",
        "stir": True,
        "stir_speed": None,
    }

    MANDATORY_PROP_LIMITS = {
        "pH": PH_RANGE_PROP_LIMIT,
        "stir_time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {"vessel": VesselSpec(stir=self.stir)}
