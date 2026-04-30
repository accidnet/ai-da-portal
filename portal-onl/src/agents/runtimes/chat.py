from typing import cast

from agents.runtimes.base import BaseAgent
from agents.state import AgentState
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from infrastructure.ai.client import AiClient


class ChatAgent(BaseAgent):
    def invoke(self, state: AgentState) -> AgentState:
        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")

        max_iterations = 6
        iteration_count = 0
        next_input: list[dict[str, object]] = self._build_initial_input(working_state)

        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            response = self._read_response_payload(
                self._llm_client.create_response(
                    **self._response_kwargs(next_input),
                    stream=False,
                )
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            tool_outputs = self._execute_response_function_calls(working_state, response)
            if tool_outputs:
                next_input = self._extend_input_with_response(
                    next_input,
                    response,
                    tool_outputs=tool_outputs,
                )
                continue

            assistant_message = self._extract_assistant_text(response)
            if assistant_message:
                working_state["assistant_message"] = assistant_message
                working_state["status"] = "completed"
                working_state.setdefault("route", "conversation")
                break

            break

        working_state.setdefault("route", "conversation")
        return working_state


def build_chat_agent(
    *,
    llm_client: AiClient,
    dataset_service: DatasetService,
    analysis_service: AnalysisService,
) -> ChatAgent:
    return ChatAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
