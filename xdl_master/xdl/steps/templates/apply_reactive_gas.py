from typing import Dict

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    PRESSURE_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractApplyReactiveGasStep(AbstractXDLElementTemplate, AbstractStep):
    """Apply a reactive gas to a vessel.

    Name: ApplyReactiveGas

    Mandatory Props:
        vessel (str): Vessel containing the reagent/product to apply gas to.
        gas (str): Reactive gas to be applied.
        time (float): Amount of time to run the application for.
        temp (float): Temperature to perform the application at.
        pressure (float): Pressure to set the reaction vessel at in mBar.
        stir (bool): If True, stir the reaction vessel during the process.
        stir_speed (float): Stirring speed in RPM.
    """

    MANDATORY_NAME = "ApplyReactiveGas"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "time": float,
        "temp": float,
        "gas": REAGENT_PROP_TYPE,
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
