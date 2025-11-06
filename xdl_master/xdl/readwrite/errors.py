from xdl_master.xdl.errors import XDLError


class XDLReadError(XDLError):
    """Base error class for errors occurring while reading XDL files/strings."""

    pass


class XDLInvalidStepTypeError(XDLReadError):
    """Invalid step type used."""

    def __init__(self, step_name):
        self.step_name = step_name

    def __str__(self):
        return f'"{self.step_name}" is not a valid step type.'


class XDLInvalidPropError(XDLReadError):
    """Invalid prop used."""

    def __init__(self, step_name, prop):
        self.step_name = step_name
        self.prop = prop

    def __str__(self):
        return f'"{self.prop}" is an invalid prop for {self.step_name}.'


########
# JSON #
########


class XDLInvalidJSONError(XDLReadError):
    """Base error class for when XDL JSON supplied is invalid."""

    pass


class XDLBlueprintNoID(XDLReadError):
    """XDL JSON Blueprints need to have an id."""

    def __init__(self, xdl_blueprint) -> None:
        self.xdl_blueprint = xdl_blueprint

    def __str__(self):
        return f'"id" missing from blueprint: {self.xdl_blueprint}'


class XDLJSONNotBlueprintsAndSynthesis(XDLInvalidJSONError):
    """Both Blueprints and Synthesis sections were not provided"""

    def __init__(self, provided) -> None:
        self.p = provided

    def __str__(self):
        return f"Blueprints AND Synthesis sections needed. Only {self.p} given."


class XDLJSONBlueprintsNotListError(XDLInvalidJSONError):
    """XDL JSON Blueprints section is not an array."""

    def __str__(self):
        return "Blueprints section should be an array."


class XDLJSONBlueprintsSynthesisNotDictError(XDLInvalidJSONError):
    """XDL JSON Synthesis section is not a dictionary."""

    def __str__(self):
        return "Synthesis section should be a dictionary."


class XDLJSONMissingHardwareError(XDLInvalidJSONError):
    """XDL JSON is missing hardware section."""

    def __str__(self):
        return 'XDL JSON is missing "hardware" section.'


class XDLJSONMissingReagentsError(XDLInvalidJSONError):
    """XDL JSON is missing reagents section."""

    def __str__(self):
        return 'XDL JSON is missing "reagents" section.'


class XDLJSONMissingStepsError(XDLInvalidJSONError):
    """XDL JSON is missing steps section."""

    def __str__(self):
        return 'XDL JSON is missing "steps" section.'


class XDLJSONHardwareNotArrayError(XDLInvalidJSONError):
    """XDL JSON hardware section is not an array."""

    def __str__(self):
        return "Hardware section should be an array."


class XDLJSONReagentsNotArrayError(XDLInvalidJSONError):
    """XDL JSON reagents section is not an array."""

    def __str__(self):
        return "Reagents section should be an array."


class XDLJSONStepsNotArrayError(XDLInvalidJSONError):
    """XDL JSON steps section is not an array."""

    def __str__(self):
        return "Steps section should be an array."


class XDLJSONInvalidSectionError(XDLInvalidJSONError):
    """Invalid section included in XDL JSON."""

    def __init__(self, section_name):
        self.section_name = section_name

    def __str__(self):
        return f'{self.section_name} is an invalid section for XDL JSON.\
 Valid section keys: "steps", "reagents", "hardware".'


class XDLJSONMissingStepNameError(XDLInvalidJSONError):
    """Step missing "name" parameter in XDL JSON."""

    def __str__(self):
        return 'Step missing "name" parameter in XDL JSON.'


class XDLJSONMissingPropertiesError(XDLInvalidJSONError):
    """Step missing "properties" object in XDL JSON."""

    def __str__(self):
        return 'XDL element must have "properties" object in XDL JSON.'
