from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    COLOR_PROP_LIMIT,
    POWER_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
    WAVELENGTH_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractIrradiateStep(AbstractXDLElementTemplate, AbstractStep):
    """Irradiate reaction mixture with light of given wavelength.

    Name: Irradiate

    Mandatory props:
        vessel (str): Vessel containing reaction mixture to irradiate.
        time (float): Time to irradiate the vessel for.
        wavelength (float): Wavelength of the irradiation in nm. Supply either
            this or color.
        color (str): color of the light. Possible values: red, green, blue,
            white, UV365, UV395. Supply either this or wavelength.
        LED_power (float): Power of LED. Accepts W, kW, mW
        temp (float): Temperature to perform the irradiation at.
        stir (bool): If True, stir the reaction vessel during the process.
        stir_speed (float): Stirring speed in RPM.
        LED_intensity (float): LED output power in percentages derived based
            on LED_power.
        cooling_power (float): cooling fan output power in percentages
        derived based on temp.
    """

    MANDATORY_NAME = "Irradiate"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "time": float,
        "wavelength": float,
        "color": str,
        "LED_power": float,
        "temp": float,
        "stir": bool,
        "stir_speed": float,
        "LED_intensity": float,
        "cooling_power": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "wavelength": None,
        "color": None,
        "LED_power": None,
        "temp": None,
        "stir": True,
        "stir_speed": "250 RPM",
        "LED_intensity": None,
        "cooling_power": None,
    }

    MANDATORY_PROP_LIMITS = {
        "time": TIME_PROP_LIMIT,
        "wavelength": WAVELENGTH_PROP_LIMIT,
        "color": COLOR_PROP_LIMIT,
        "LED_power": POWER_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
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
