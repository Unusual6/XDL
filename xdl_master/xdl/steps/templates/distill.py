from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    DISTILL_MODE_PROP_TYPE,
    PRESSURE_PROP_LIMIT,
    TEMP_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractDistillStep(AbstractXDLElementTemplate, AbstractStep):
    """Distill a reaction mixture at a given temperature to retrieve a product.

    Name: Distill

    Mandatory Props:
        vessel (str): Vessel contianing the reaction mixture to be distilled.
        temp (float): Temperature to heat the reaction vessel to.
            This _should_ be higher tha nthe `vapour_temp`.
        vapour_temp (float): Boiling point of the desired product.
        pressure (float): Pressure to put the reaction vessel to in mBar or atm.
        mode (str): Mode of distillation. Either 'standard' or 'kugelrohr'.
    """

    MANDATORY_NAME = "Distill"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "temp": float,
        "vapour_temp": float,
        "pressure": float,
        "mode": str,
    }

    MANDATORY_DEFAULT_PROPS = {
        "pressure": "1 atm",
        "mode": "standard",
        "vapour_temp": None,
        "temp": None,
    }

    MANDATORY_PROP_LIMITS = {
        "temp": TEMP_PROP_LIMIT,
        "vapour_temp": TEMP_PROP_LIMIT,
        "pressure": PRESSURE_PROP_LIMIT,
        "mode": DISTILL_MODE_PROP_TYPE,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {"vessel": VesselSpec(evaporate=True, max_temp=self.temp)}
