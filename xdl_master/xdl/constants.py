from typing import Any, Dict, List

#: XDL version number. Used in header at top of outputted XDL files.
XDL_VERSION: str = "2.0.0"

########
# MISC #
########

#: Chemify API URL
CHEMIFY_API_URL: str = "https://api.chemification.com"

#: Chemicals that will be recognised as inert gas.
INERT_GAS_SYNONYMS: List[str] = ["nitrogen", "n2", "ar", "argon"]

#: Chemical name if found in graph to be used as air source.
AIR: str = "air"

#: Room temperature in °C
ROOM_TEMPERATURE: int = 25

#: Keywords that if found in reagent name signify that the reagent is aqueous.
AQUEOUS_KEYWORDS: List[str] = ["water", "aqueous", "acid", " m ", "hydroxide"]

#: Attributes of the ``<Synthesis>`` element. This is kind of a relic from when
#: there were multiple attributes that could be included in the ``Synthesis``
#: tag. Might be sensible to just handle ``graph_sha256`` attribute specifically
#: rather than have this one element list.
SYNTHESIS_ATTRS: List[Dict[str, Any]] = [
    {
        "name": "graph_sha256",
        "type": str,
        "default": "",
    },
    {
        "name": "id",
        "type": str,
        "default": "",
    },
]

#  tags used for root nodes in standard XDL1 XML and XDL2-exclusive XML
#  with blueprint compatibility
XDL_1_ROOT = "Synthesis"
XDL_2_ROOT = "XDL"

#: Prop type if property is reagent declared in Reagent section.
REAGENT_PROP_TYPE: str = "reagent"

#: Prop type if property is reaction mixture vessel.
VESSEL_PROP_TYPE: str = "vessel"

#: JSON string prop type.
JSON_PROP_TYPE: str = "json"

#  Sections used for organising steps. These MUST be kept in order
STEP_SECTIONS = ["Prep", "Reaction", "Purification", "Workup"]

#  Core attributes that must always be kept up-to-date in XDL Context
#  container class.
CORE_CONTEXT_ATTRS = ["reagents", "blueprints", "components", "hardware", "parameters"]

# used by Repeat as an indicator as when to stop


class XDLStatus:
    pass


DONE = XDLStatus()
