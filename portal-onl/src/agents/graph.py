from agents.state import AgentState


class AgentGraph:
    def invoke(self, state: AgentState) -> AgentState:
        return state


def build_agent_graph() -> AgentGraph:
    return AgentGraph()
