from typing import Dict, List, Optional

from networkx import MultiDiGraph

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.misc import SanityCheck
from xdl_master.xdl.utils.prop_limits import (
    MASS_PROP_LIMIT,
    MOL_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TIME_PROP_LIMIT,
    PropLimit,
)
from xdl_master.xdl.utils.sanitisation import amount_str_to_units, amount_to_float
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractAddSolidStep(AbstractXDLElementTemplate, AbstractStep):
    """Add solid reagent.

    Name: AddSolid

    Mandatory props:
        vessel (vessel): Vessel to add reagent to.
        reagent (reagent): Reagent to add.
        mass (float): Mass of reagent to add.
        time (float): Time to add reagent over.
        portions (int): Number of portions to add reagent in.
        stir (bool): If ``True``, stir vessel while adding reagent.
        stir_speed (float): Speed in RPM at which to stir at if stir is
            ``True``.
    """

    MANDATORY_NAME = "AddSolid"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "reagent": REAGENT_PROP_TYPE,
        "mass": float,
        "amount": str,
        "mol": float,
        "time": float,
        "portions": int,
        "stir": bool,
        "stir_speed": float,
    }

    MANDATORY_DEFAULT_PROPS = {
        "mol": None,
        "stir": False,
        "time": None,
        "portions": 1,
        "stir_speed": None,
        "amount": None,
        "mass": None,
    }

    MANDATORY_PROP_LIMITS = {
        "mol": MOL_PROP_LIMIT,
        "mass": MASS_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    def sanity_checks(self, graph: MultiDiGraph) -> List[SanityCheck]:

        return [
            SanityCheck(
                condition=self.mass is not None,
                error_msg="Amount or mass must be given",
            ),
            SanityCheck(
                condition=(
                    self.amount_units in ["mol", "g", "equivalents"]
                    if self.amount
                    else True
                ),
                error_msg="Amount for AddSolid step must be expressed in units\
convertible to moles or grams",
            ),
        ]

    def on_prepare_for_execution(self, graph: MultiDiGraph):
        """Prepares the current step for execution.
        Gets/sets/cleans up appropriate items in preparation for exection.

        Args:
            graph (MultiDiGraph): Chemputer Graph to check
        """
        #  if mass has not been specified directly, work it out from 'amount'
        if self.mass is None:
            self.mass = self.amount_to_mass()

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {"vessel": VesselSpec(stir=self.stir)}

    @property
    def final_amount(self) -> Optional[float]:
        """Return float value of amount in arbitrary units - standard
        sanitisation is not used for this prop due to the potential for it to
        be converted to several different standard units.
        'amount' is ultimately converted to mass (in grams).

        Returns:
            float: amount value (float) in appropriate units (units specified
                in self.amount_units)
        """
        if self.amount is not None:
            return amount_to_float(self.amount)

        return None

    @property
    def amount_units(self) -> Optional[str]:
        """Keeps track of final amount units for final mass calculations.

        Returns:
            str: amount units should return 'mass' (g) or 'moles' (mol)
        """
        if self.amount is not None:
            return amount_str_to_units(self.amount)
        return None

    @property
    def _reagent_object(self):
        if hasattr(self.context, "reagents"):
            return [r for r in self.context.reagents if r.name == self.reagent][0]
        return None

    def amount_to_mass(self) -> float:
        """Convert amount to final mass.

        Returns:
            float: final mass to use (in g).
        """

        if self.amount is not None:

            #  moles to mass
            if self.amount_units == "mol":

                return self._reagent_object.molecular_weight * self.final_amount

            #  mass to mass
            elif self.amount_units == "g":
                return self.final_amount

            #  equivalents to mass
            elif self.amount_units == "equivalents":

                #  get equivalent amount - convert
                return self.equivalents_to_mass()

        return None

    def moles_to_mass(self, n_mols: float = None) -> float:
        """Convert moles to final mass.

        Args:
            n_mols (float, optional): number of moles of target reagent. If
                None, self.final_amount is used. Defaults to None.

        Returns:
            float: final mass to use (in g).
        """

        #  get n_moles from 'amount'
        if n_mols is None:
            if self.amount_units == "mol":
                n_mols = self.final_amount
            else:
                return None

        #  if available, get concentration of reagent to add (in mol / L)
        concentration = self._reagent_object.concentration

        if concentration:
            return n_mols / (concentration / 1000)

        mol_weight = self._reagent_object.molecular_weight

        mass = mol_weight * n_mols

        return mass

    def equivalents_to_mass(self) -> float:
        """Convert number of equivalents to final mass. This is calculated
        using the ```equiv_amount``` and ```equiv_reference``` parameters
        specified on call of the XDL object's ```prepare_for_execution```
        method.

        Returns:
            float: final mass to use in Add step (in mL).
        """
        n_moles = self.context._equiv_moles

        return self.moles_to_mass(n_mols=self.final_amount * n_moles)


class AbstractAddSolidFromDispenser(AbstractXDLElementTemplate, AbstractStep):
    """Add solid reagent from a Solid Dispenser

    Mandatory Props:
        vessel (vessel): Vessel to add reagent to
        stir (bool): Stir the vessel on addition
        stir_speed (float): Stir speed in RPM for the stirring
        turns (int): Number of turns for the Solid Dispenser to move
        speed (int): Speed of the solid dispenser movement in RPM
        driver (int): Driver used to turn the motor dependent on board used.
    """

    MANDATORY_NAME = "AddSolidFromDispenser"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "stir": bool,
        "stir_speed": float,
        "turns": int,
        "speed": int,
        "driver": int,
    }

    MANDATORY_DEFAULT_PROPS = {
        "speed": 100,
        "driver": 1,
        "stir_speed": None,
        "stir": False,
    }

    MANDATORY_PROP_LIMITS = {
        "driver": PropLimit(enum=["1", "2"], default="1"),
        "speed": PropLimit(enum=[str(i) for i in range(1, 601)]),
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
    }

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {"vessel": VesselSpec(stir=self.stir)}
