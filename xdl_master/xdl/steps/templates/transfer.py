# relative
from typing import Dict

#  other
from networkx import MultiDiGraph

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.prop_limits import TIME_PROP_LIMIT, VOLUME_PROP_LIMIT
from xdl_master.xdl.utils.sanitisation import amount_str_to_units, amount_to_float
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractTransferStep(AbstractXDLElementTemplate, AbstractStep):
    """Transfer liquid from one vessel to another.

    The quantity to transfer can be specified using either volume (liquid units)
    or amount (all accepted units e.g. 'g', 'mL', 'eq', 'mmol').

    Name: Transfer

    Mandatory props:
        from_vessel (vessel): Vessel to transfer liquid from.
        to_vessel (vessel): Vessel to transfer liquid to.
        volume (float): Volume of liquid to transfer from from_vessel to
            to_vessel.
        amount (str): amount of reagent to add in moles, grams or equivalents.
        time (float): Time over which to transfer liquid.
        viscous (bool): If ``True``, adapt process to handle viscous liquid,
            e.g. use slower move speed.
        rinsing_solvent (reagent): Solvent to rinse from_vessel with, and
            transfer rinsings to ``to_vessel``.
        rinsing_volume (float): Volume of ``rinsing_solvent`` to rinse
            ``from_vessel`` with.
        rinsing_repeats (int): Number of rinses to perform.
        solid (bool): Behaves like AddSolid if true. Default False.
    """

    MANDATORY_NAME = "Transfer"

    MANDATORY_PROP_TYPES = {
        "from_vessel": VESSEL_PROP_TYPE,
        "to_vessel": VESSEL_PROP_TYPE,
        "volume": float,
        "amount": str,
        "time": float,
        "viscous": bool,
        "rinsing_solvent": REAGENT_PROP_TYPE,
        "rinsing_volume": float,
        "rinsing_repeats": int,
        "solid": bool,
    }

    MANDATORY_DEFAULT_PROPS = {
        "viscous": False,
        "time": None,
        "volume": None,
        "amount": None,
        "rinsing_solvent": None,
        "rinsing_volume": None,
        "rinsing_repeats": None,
        "solid": False,
    }

    MANDATORY_PROP_LIMITS = {
        "volume": VOLUME_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "rinsing_volume": VOLUME_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {
            "from_vessel": VesselSpec(),
            "to_vessel": VesselSpec(),
        }

    def on_prepare_for_execution(self, graph: MultiDiGraph):
        if not self.solid:
            if self.volume is None and self.amount:
                self.volume = self.context.calculate_volume(
                    volume=self.volume,
                    amount=self.amount,
                    amount_units=self.amount_units,
                    final_amount=self.final_amount,
                    reagent_concentration=None,
                    reagent_molecular_weight=None,
                    reagent_density=None,
                    reagent_solid=None,
                )

    @property
    def final_amount(self) -> float:
        """Return float value of amount in arbitrary units - standard
        sanitisation is not used for this prop due to the potential for it to
        be converted to several different standard units.
        'amount' is ultimately converted to volume (in mL).

        Returns:
            float: amount value (float) in appropriate units (units specified
                in self.amount_units)
        """
        if self.amount is not None:
            return amount_to_float(self.amount)

        return None

    @property
    def amount_units(self) -> str:
        """Keeps track of final amount units for final mass calculations.

        Returns:
            str: amount units should return 'mass' (g), 'moles' (mol) or
                'volume' (mL)
        """
        if self.amount is not None:
            return amount_str_to_units(self.amount)
        return None
