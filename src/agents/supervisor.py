from langgraph_supervisor import create_supervisor

from src.agents.invoice_agent import build_invoice_agent
from src.agents.music_agent import build_music_agent
from src.graph.nodes.verify_identity import get_llm
from src.graph.prompts import SUPERVISOR_PROMPT
from src.graph.state import AgentState


def build_supervisor(llm=None, output_mode="last_message"):
    """Compile the supervisor with its two specialists. Models are created here, not at import.

    output_mode="full_history" also returns the specialists' tool calls (useful for debugging).
    """
    llm = llm or get_llm()
    return create_supervisor(
        [build_music_agent(llm), build_invoice_agent(llm)],
        model=llm,
        prompt=SUPERVISOR_PROMPT,
        state_schema=AgentState,
        output_mode=output_mode,
    ).compile()
