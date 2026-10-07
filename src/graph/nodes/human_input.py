from src.graph.state import State

from langgraph.types import interrupt
from langchain_core.messages import HumanMessage
from src.graph.prompts import FALLBACK_MESSAGE

def human_input(state: State)-> dict:
    """Ask the user for a valid identifier and add their reply to the history."""
    reply=interrupt(FALLBACK_MESSAGE)
    return{"messages":[HumanMessage(content=str(reply))]}

    