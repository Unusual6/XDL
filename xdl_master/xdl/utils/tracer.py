from typing import Any, Dict, List, Tuple

from xdl_master.xdl.constants import JSON_PROP_TYPE, REAGENT_PROP_TYPE, VESSEL_PROP_TYPE
from xdl_master.xdl.errors import XDLError, XDLTracerError
from xdl_master.xdl.utils.sanitisation import convert_val_to_std_units

STRING_PROP_TYPES = [
    str,
    REAGENT_PROP_TYPE,
    JSON_PROP_TYPE,
    VESSEL_PROP_TYPE,
]

PRECISION_MAX_VALUE = 0.000001


def try_unit_conversion(step, item: Any) -> Any:

    PROP_TYPE = step.PROP_TYPES[item[0]]
    # only attempt conversions if the prop type is not string based
    if PROP_TYPE not in STRING_PROP_TYPES:
        try:
            return convert_val_to_std_units(item[1])
        except KeyError:
            return item[1]
    else:
        return item[1]


def tracer_tester(
    tracer: List[Tuple[type, Dict]],
    step_list: List[Tuple[type, Dict]],
    precision: float = None,
) -> None:
    """Tests to see if every element from the Step list appears in the Tracer
    in order.
    Every entry from the list of required steps (step_list) needs to have
    (at least) one entry in the tracer with the required properties,
    i.e. the dict of the list step must be a sub-dict of the tracer step,
    and they have to be in the right order. We iterate through both the list
    and the tracer, but need to advance the index of each based on
    their position. We therefore need the length of both lists.

    Args:
        tracer (List[(str, Dict)]): Tracer with all steps that have been
    executed.
        step_list (List[(str, Dict)]): List of steps with properties that is
    tested to be a sub-list of tracer.
        precision (float): if specified, the given tolerace for floats, e.g.
    the volume in the step list cannot deviate more than {precision} from the
    volume in the tracer.

    Returns: Nothing."""
    # Imagine a bus driving along the street. Every possible stop is in the
    # tracer, and the passengers are standing in line in order at the exit,
    # that's the step list. Only the passenger in the front can tell the bus
    # driver "this is my stop".

    if precision and precision < PRECISION_MAX_VALUE:
        raise XDLError(
            f"precision level too small, must be at least {PRECISION_MAX_VALUE}"
        )

    trace_length = len(tracer)
    list_length = len(step_list)
    if list_length == 0:
        return

    # Sanitizing empty steps turns string into required tuple
    for i in range(list_length):
        if type(step_list[i]) == str:
            step_list[i] = (step_list[i], {})

    # We also need individual pointers for each list, starting at 0.
    list_pointer = 0
    trace_pointer = 0
    # We're done when the trace is exhausted, meaning we keep going
    # while we haven't reached the end
    while trace_pointer <= trace_length:
        # Check that we haven't exhausted the tracer
        if trace_pointer == trace_length:
            raise XDLTracerError(
                step_list[list_pointer][0], step_list[list_pointer][1], list_pointer
            )
        # We compare the step name
        if tracer[trace_pointer][0].__name__ == step_list[list_pointer][0]:
            # if the step name matches, we check if all requried properties
            # from the list step are in the trace step.

            # If a precision tolerace has been given, check individually
            if precision:
                step_has_all_properties = True

                for searched_item in step_list[list_pointer][1].items():
                    step_has_all_properties = test_item(
                        searched_item, tracer[trace_pointer], precision
                    )
                    if not step_has_all_properties:
                        break
                if step_has_all_properties:
                    # if that is the case, the list step has been found,
                    # and we move on to the next list step.
                    list_pointer += 1
                    # if we reach the end of the list, we're done
                    if list_pointer == list_length:
                        break
            # No precision given: check actual values
            else:
                if all(
                    (item[0], try_unit_conversion(tracer[trace_pointer][0], item))
                    in tracer[trace_pointer][1].items()
                    for item in step_list[list_pointer][1].items()
                ):
                    # if that is the case, the list step has been found,
                    # and we move on to the next list step.
                    list_pointer += 1
                    # if we reach the end of the list, we're done
                    if list_pointer == list_length:
                        break

        # if the step doesn't match, move to the next entry of the tracer.
        trace_pointer += 1
    # finally, assert that we have exhausted the list.
    if list_pointer != list_length:
        raise AssertionError("Step list exhaused without reaching its end")


def test_item(item: Tuple, step: Any, precision: float) -> bool:
    """Tests whether an item from the step list is a prop of the step.
    First, converting to standard units. Floats need to be within 0.1% accurate
    everything else must match exactly.
    """
    converted_item = try_unit_conversion(step[0], item)
    given_item = step[1][item[0]]
    if type(converted_item) == float and type(given_item) == float:
        # too close to zero for division: compare absolute difference
        if abs(converted_item) < 0.001:
            if abs(given_item - converted_item) < precision:
                return True
        # otherwise: relative difference
        else:
            if abs(given_item / converted_item - 1) < precision:
                return True
    if converted_item == given_item:
        return True
    return False


def update_tracer(tracer: List[Tuple[type, Dict]], step) -> None:
    """Adds the current step with all properties as a dictionary to the end
    of the tracer.

    Args:
        tracer (List[(str, Dict)]): Tracer with all steps that have been
    executed to this point.
        step (Step): Step that will be added to the tracer.

    Returns: Nothing.

    """
    if tracer is not None:
        # We want to add all props that are in PROP TYPES and INTERNAL PROPS
        # We do so by getting the list of keys, and iterating through them.
        iteration_list = list(step.PROP_TYPES.keys())
        iteration_list += step.INTERNAL_PROPS
        # Start with an empty dict and use update()
        tracing_dict = {}
        for key in iteration_list:
            tracing_dict.update({key: step.properties[key]})
        # If it has children, append those as well.
        if hasattr(step, "steps"):
            tracing_children_dict = {"children": step.steps}
            tracing_dict.update(tracing_children_dict)
        # The entries of the trace are a 2-tuple consisting of the step name,
        # and the dict.
        tracer.append((type(step), tracing_dict))
