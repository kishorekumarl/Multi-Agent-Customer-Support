from langgraph.graph import MessagesState
from langgraph.managed import RemainingSteps
from typing_extensions import NotRequired


class State(MessagesState):
    """Graph state: the message history, the verified customer_id, and the formatted
    music memory (injected into the music agent's prompt)."""

    customer_id: int | None
    memory: str | None


class AgentState(State):
    """State for the agents and supervisor: the graph State plus the step counter that
    LangGraph's prebuilt agents need to stop a runaway tool loop."""

    remaining_steps: NotRequired[RemainingSteps]
