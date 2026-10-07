from langgraph.prebuilt import create_react_agent

from src.agents.invoice_tools import SCOPED_INVOICE_TOOLS
from src.graph.nodes.verify_identity import get_llm
from src.graph.prompts import INVOICE_AGENT_PROMPT
from src.graph.state import AgentState


def build_invoice_agent(llm=None):
    """The invoice specialist; its tools take the customer ID from state, never from the model."""
    return create_react_agent(
        model=llm or get_llm(),
        tools=SCOPED_INVOICE_TOOLS,
        prompt=INVOICE_AGENT_PROMPT,
        state_schema=AgentState,
        name="invoice_agent",
    )
