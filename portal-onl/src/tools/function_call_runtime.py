import json
from collections.abc import Callable
from typing import Protocol

from agents.state import AgentState


class FunctionCallLike(Protocol):
    call_id: str
    name: str


type FunctionCallExtractor = Callable[[dict[str, object]], list[FunctionCallLike]]
type FunctionCallExecutor = Callable[[AgentState, FunctionCallLike], dict[str, object]]
type StateEventBuilder = Callable[[AgentState], dict[str, object]]


def resolve_output_item_function_call(
    *,
    item: dict[str, object],
    working_state: AgentState,
    extract_function_calls: FunctionCallExtractor,
    execute_function_call: FunctionCallExecutor,
    build_state_event: StateEventBuilder,
    last_state_fingerprint: str | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None, str | None]:
    function_calls = extract_function_calls({"output": [item]})
    if not function_calls:
        return None, None, last_state_fingerprint

    function_call = function_calls[0]
    tool_result = execute_function_call(working_state, function_call)
    function_call_output = {
        "type": "function_call_output",
        "call_id": function_call.call_id,
        "output": json.dumps(tool_result, ensure_ascii=False),
    }

    state_event = build_state_event(working_state)
    fingerprint = json.dumps(state_event["state"], ensure_ascii=False, sort_keys=True)
    state_payload = None
    if fingerprint != last_state_fingerprint:
        last_state_fingerprint = fingerprint
        state_payload = state_event["state"]

    stream_event = {
        "type": "agent.function_call_output",
        "call_id": function_call.call_id,
        "name": function_call.name,
        "output": tool_result,
        "state": state_payload,
    }
    return function_call_output, stream_event, last_state_fingerprint
