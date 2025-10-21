#  std
from typing import Dict, List, Optional

#  other
from networkx import MultiDiGraph

from xdl_master.xdl.constants import REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.steps import AbstractStep

#  relative
from xdl_master.xdl.steps.templates.abstract_template import AbstractXDLElementTemplate
from xdl_master.xdl.utils.misc import SanityCheck
from xdl_master.xdl.utils.prop_limits import (
    ADD_PURPOSE_PROP_LIMIT,
    ROTATION_SPEED_PROP_LIMIT,
    TIME_PROP_LIMIT,
    VOLUME_PROP_LIMIT,
)
from xdl_master.xdl.utils.sanitisation import amount_str_to_units, amount_to_float
from xdl_master.xdl.utils.vessels import VesselSpec


class AbstractAddStep(AbstractXDLElementTemplate, AbstractStep):
    """Add liquid or solid reagent. Reagent identity (ie liquid or solid) is
    determined by the ``solid`` property of a reagent in the ``Reagent``
    section.

    The quantity of the reagent can be specified using either volume (liquid
    units) or amount (all accepted units e.g. 'g', 'mL', 'eq', 'mmol').

    Name: Add

    Mandatory props:
        vessel (vessel): Vessel to add reagent to.
        reagent (reagent): Reagent to add.
        volume (float): Volume of reagent to add.
        mass (float): Mass of reagent to add.
        amount (str): amount of reagent to add in moles, grams or equivalents.
            Sanitisation occurs on call of ``on_prepare_for_execution`` for this
            prop. This will change in future.
        dropwise (bool): If ``True``, use dropwise addition speed.
        time (float): Time to add reagent over.
        stir (bool): If ``True``, stir vessel while adding reagent.
        stir_speed (float): Speed in RPM at which to stir at if stir is
            ``True``.
        viscous (bool): If ``True``, adapt process to handle viscous reagent,
            e.g. use slower addition speeds.
        purpose (str): Purpose of addition. If ``None`` assume that simply a
            reagent is being added. Roles of reagents can be specified in
            ``<Reagent>`` tag. Possible values: ``"precipitate"``,
            ``"neutralize"``, ``"basify"``, ``"acidify"`` or ``"dissolve"``.
    """

    MANDATORY_NAME = "Add"

    MANDATORY_PROP_TYPES = {
        "vessel": VESSEL_PROP_TYPE,
        "reagent": REAGENT_PROP_TYPE,
        "volume": float,
        "mass": float,
        "dropwise": bool,
        "speed": float,
        "time": float,
        "stir": bool,
        "stir_speed": float,
        "viscous": bool,
        "purpose": str,
        "amount": str,
    }

    MANDATORY_DEFAULT_PROPS = {
        "stir": False,
        "dropwise": False,
        "speed": None,
        "viscous": False,
        "time": None,
        "stir_speed": None,
        "purpose": None,
        "amount": None,
        "volume": None,
        "mass": None,
    }

    MANDATORY_PROP_LIMITS = {
        "volume": VOLUME_PROP_LIMIT,
        "time": TIME_PROP_LIMIT,
        "stir_speed": ROTATION_SPEED_PROP_LIMIT,
        "purpose": ADD_PURPOSE_PROP_LIMIT,
    }

    def sanity_checks(self, graph: MultiDiGraph) -> List[SanityCheck]:
        """Gets a list of Sanity checks to perform for the step

        Args:
            graph (MultiDiGraph): Chemputer graph to check

        Returns:
            List[SanityCheck]: List of checks to perform
        """
        # if context exists, make variable for mass_to_volume and
        # amount_to_volume conversions for sanity tests to make things neater
        if self.context is not None:
            mass_to_vol = self.context.mass_to_volume(
                mass=self.mass, reagent_density=self.reagent_density
            )
            amount_to_vol = self.context.amount_to_volume(
                amount=self.amount,
                amount_units=self.amount_units,
                reagent_solid=self.reagent_solid,
                final_amount=self.final_amount,
                reagent_density=self.reagent_density,
                reagent_concentration=self.reagent_concentration,
                reagent_molecular_weight=self.reagent_molecular_weight,
            )

        else:
            mass_to_vol = None
            amount_to_vol = None

        # check the amount units, if specified in 'unit/eq', perform a
        # unit sanity check
        if self.amount_units:
            amount_unit_check = "/" in self.amount

        else:
            amount_unit_check = False

        return [
            SanityCheck(
                condition=self.mass is not None or not self.reagent_solid,
                error_msg='Mass must be specified for addition of solid \
reagents. This can be specified directly, or indirectly via "amount" in units \
convertible to mass units.',
            ),
            SanityCheck(
                condition=hasattr(self, "context") or not self.amount,
                error_msg='For use of new Add features such "amount" prop, a \
Context object must be provided with access to Reagent objects.',
            ),
            SanityCheck(
                condition=hasattr(self, "context") or not self.reagent_solid,
                error_msg="In order to use the Add step for addition of \
solids, a Context object is required with access to Reagent objects. This is \
to confirm the state of the target reagent is correct (i.e. a solid)",
            ),
            SanityCheck(
                condition=self.reagent_solid
                or self.volume is not None
                or self.amount is not None,
                error_msg='Volume must not be None for addition of a liquid \
reagent. Volume can be declared directly or indirectly via \
"mass" and / or "amount" properties.',
            ),
            SanityCheck(
                condition=(
                    self.amount_units in ["g", "mol", "equivalents", "mL"]
                    if self.amount
                    else True
                ),
                error_msg='Check amounts prop: must be specified in units \
convertible to "mol", "g" or "mL".',
            ),
            SanityCheck(
                condition=(
                    (
                        self.volume is None
                        or (mass_to_vol == amount_to_vol == self.volume)
                    )
                    if self.amount and self.mass
                    else True
                ),
                error_msg="Amount and mass must be equivalent.",
            ),
            SanityCheck(
                condition=(
                    not self.reagent_solid or self.volume == mass_to_vol
                    if (self.mass is not None and self.amount_units != "mL")
                    else True
                ),
                error_msg="Values for volume and mass must not be in conflict.",
            ),
            SanityCheck(
                condition=(
                    self.volume == amount_to_vol
                    if (
                        self.amount
                        and not self.reagent_solid
                        and "/" not in self.amount
                    )
                    else True
                ),
                error_msg=(
                    f"{self.volume}, {amount_to_vol}. Values for \
                    volume and amount must not be in conflict."
                ),
            ),
            SanityCheck(
                condition=(
                    self.reagent_concentration is not None
                    or (
                        self.reagent_density is not None
                        and self.reagent_molecular_weight is not None
                    )
                    if self.amount_units == "moles"
                    else True
                ),
                error_msg=f"Density and molecular weight or concentration \
are required for {self.reagent} to work out volume from moles.",
            ),
            SanityCheck(
                condition=(
                    not self.reagent_concentration if (self.reagent_solid) else True
                ),
                error_msg=f"{self.reagent} is a solid and therefore cannot \
have a concentration.",
            ),
            SanityCheck(
                condition=(
                    self.reagent in [r.name for r in self.context.reagents]
                    if self.context.reagents
                    else True
                ),
                error_msg=f"{self.reagent} does not map to any reagents.",
            ),
            SanityCheck(
                condition=(
                    self.context._base_scale is not None if amount_unit_check else True
                ),
                error_msg=f"Amount units are {self.amount} but no \
                base_scale specified for the procedure",
            ),
            SanityCheck(
                condition=(
                    self.context._equiv_moles is not None if amount_unit_check else True
                ),
                error_msg=f"Amount units for {self.amount} require an \
                equivalence reference and amount but one or both were not \
                provided",
            ),
            SanityCheck(
                condition=(
                    self.reagent_density
                    or (self.reagent_molecular_weight and self.reagent_concentration)
                    if (
                        self.amount_units == "g"
                        and "/" not in self.amount
                        and not self.reagent_solid
                    )
                    else True
                ),
                error_msg=f"To add {self.amount} of {self.reagent}, specify \
either density or both concentration and molecular weight for {self.reagent}",
            ),
        ]

    def on_prepare_for_execution(self, graph: MultiDiGraph):
        """Prepares the current step for execution.
        Gets/sets/cleans up appropriate items in preparation for exection.

        Args:
            graph (MultiDiGraph): Chemputer Graph to check
        """
        #  volume is not specified, so work out volume to add using desired
        #  mass / amount and concentration of reagent
        if self.reagent_solid is True:
            self.mass = self.context.amount_to_mass(
                amount=self.amount,
                amount_units=self.amount_units,
                reagent_mw=self.reagent_molecular_weight,
                final_amount=self.final_amount,
            )

        elif self.volume is None:
            if self.reagent_solid is False:
                self.volume = self.context.calculate_volume(
                    volume=self.volume,
                    mass=self.mass,
                    amount=self.amount,
                    amount_units=self.amount_units,
                    final_amount=self.final_amount,
                    reagent_concentration=self.reagent_concentration,
                    reagent_molecular_weight=self.reagent_molecular_weight,
                    reagent_density=self.reagent_density,
                    reagent_solid=self.reagent_solid,
                )

    @property
    def vessel_specs(self) -> Dict[str, VesselSpec]:
        return {"vessel": VesselSpec(stir=self.stir)}

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

    @property
    def _reagent_object(self):
        """Fetch appropriate Reagent object for self.reagent.

        Returns:
            Reagent, optional: Reagent object. This is the Reagent object
                associated with the reagent to be added. Returns None if
                Reagent object cannot be fetched.
        """
        if hasattr(self, "context"):
            if self.context and self.context.reagents:
                reagents = [r for r in self.context.reagents if r.name == self.reagent]
                if reagents:
                    return reagents[0]

        return None

    @property
    def reagent_solid(self) -> bool:
        """State of target reagent. True if solid, False if not (or if Reagent
        object cannot be retrieved for target reagent).
        Returns:
            bool: True if solid, False if not.
        """
        if self._reagent_object:
            return self._reagent_object.solid
        return False

    @property
    def reagent_concentration(self) -> Optional[float]:
        """Concentration of target reagent from Reagent object.

        Returns:
            Optional[float]: target reagent concentration in mol / L. If Reagent
                object cannot be fetched, return None.
        """
        if self._reagent_object:
            return self._reagent_object.concentration
        return None

    @property
    def reagent_density(self) -> Optional[float]:
        """Density of target reagent from Reagent object.

        Returns:
            Optional[float]: target reagent density in g / mL. If Reagent object
                cannot be fetched, return None.
        """
        if self._reagent_object:
            return self._reagent_object.density
        return None

    @property
    def reagent_molecular_weight(self) -> Optional[float]:
        """Molecular weight of target reagent from Reagent object.

        Returns:
            Optional[float]: target reagent molecular weight in g / mol. If
                Reagent object cannot be fetched, return None.
        """
        if self._reagent_object:
            return self._reagent_object.molecular_weight
        return None
