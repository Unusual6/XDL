from typing import Dict

from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import (
    TEMP_PROP_LIMIT,
    TIME_PROP_LIMIT,
    VOLUME_PROP_LIMIT,
)
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractDecantStep(AbstractXDLElementTemplate, AbstractStep):
    """Decanting reaction.


    Args:
        vessel (str): Filter vessel.
        wait_time (float): Time to leave vacuum on filter vessel after contents
            have been moved. (optional)
        aspiration_speed (float): Speed in mL / min to draw liquid from
            vessel.
        filtrate_vessel (str): Optional. Vessel to send filtrate to. Defaults to
            waste_vessel.
        vacuum (str): Given internally. Name of vacuum flask.
        vacuum_device (str): Given internally. Name of vacuum device attached to
            vacuum flask. Can be None if vacuum is just from fumehood vacuum
            line.
        vacuum_valve (str): Given internally. Name of valve connecting filter
            bottom to vacuum.
        valve_unused_port (str): Given internally. Random unused position on
            valve.
    """

    MANDATORY_NAME = "Decant"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "wait_time": float,
        "aspiration_speed": float,
        "filtrate_vessel": VESSEL_PROP_TYPE,
        "anticlogging": bool,
        "waste_vessel": str,
        "filter_top_volume": float,
        "inline_filter": bool,
        "vacuum_attached": bool,
        "temp": float,
        "volume": float,
        "continue_heatchill": bool,
    }

    MANDATORY_DEFAULT_PROPS = {
        "wait_time": "2 minutes",
        "aspiration_speed": 5,  # mL / min
        "anticlogging": False,
        "filtrate_vessel": None,
        "volume": None,
        "temp": None,
        "continue_heatchill": False,
    }

    MANDATORY_PROP_LIMITS = {
        "wait_time": TIME_PROP_LIMIT,
        "filter_top_volume": VOLUME_PROP_LIMIT,
        "temp": TEMP_PROP_LIMIT,
        "volume": VOLUME_PROP_LIMIT,
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
