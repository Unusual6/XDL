from xdl_master.xdl.constants import VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate


class AbstractRunColumnStep(AbstractXDLElementTemplate, AbstractStep):
    """Placeholder. Needs done properly in future.

    Name: RunColumn

    Mandatory props:
        from_vessel (vessel): Vessel to take sample from.
        to_vessel (vessel): Time to elute to.
        column (str): Name of the column.
    """

    MANDATORY_NAME = "RunColumn"

    MANDATORY_PROP_TYPES = {
        "from_vessel": VESSEL_PROP_TYPE,
        "to_vessel": VESSEL_PROP_TYPE,
        "column": str,
    }
