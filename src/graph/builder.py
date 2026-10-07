from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore

from src.agents.supervisor import build_supervisor
from src.graph.nodes.create_memory import create_memory
from src.graph.nodes.human_input import human_input
from src.graph.nodes.load_memory import load_memory
from src.graph.nodes.verify_identity import verify_identity
from src.graph.state import State


def router_after_verify(state: State) -> Literal["load_memory", "human_input"]:
    """Load the customer's memory once a customer_id is set; otherwise ask the user again."""
    return "load_memory" if state.get("customer_id") is not None else "human_input"


def build_graph(checkpointer=None, store=None, agent_llm=None):
    """Build the graph.The checkpointer keeps one conversation's state; the store keeps each
    customer's saved preferences across conversations. `agent_llm` is the chat model
    for the supervisor and specialists (default: get_llm(); tests pass a fake).
    """
    builder = StateGraph(State)
    builder.add_node("verify_info", verify_identity)
    builder.add_node("human_input", human_input)
    builder.add_node("load_memory", load_memory)
    builder.add_node("supervisor", build_supervisor(agent_llm))
    builder.add_node("create_memory", create_memory)

    builder.add_edge(START, "verify_info")
    builder.add_conditional_edges("verify_info", router_after_verify)
    builder.add_edge("human_input", "verify_info")
    builder.add_edge("load_memory", "supervisor")
    builder.add_edge("supervisor", "create_memory")
    builder.add_edge("create_memory", END)
    return builder.compile(
        checkpointer=checkpointer or MemorySaver(),
        store=store or InMemoryStore(),
    )
