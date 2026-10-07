from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.graph.nodes.verify_identity import get_llm
from src.graph.prompts import MUSIC_AGENT_PROMPT, MUSIC_MEMORY_PROMPT
from src.graph.state import State
from src.tools.music_catalog import MUSIC_CATALOG_TOOLS


def music_system_prompt(memory: str | None) -> str:
    """The agent's system prompt, with the customer's saved preferences when there are any."""
    if not memory:
        return MUSIC_AGENT_PROMPT
    return MUSIC_AGENT_PROMPT + MUSIC_MEMORY_PROMPT.format(memory=memory)


def build_music_agent(llm=None):
    """The music catalog specialist, as a hand-built ReAct loop.

        START -> assistant --(tool calls)--> tools -> assistant ... --(no tool calls)--> END

    The assistant node prepends the grounding system prompt on every call (it is never
    stored in the message history); the tools node runs whatever tools were requested.
    """
    model = (llm or get_llm()).bind_tools(MUSIC_CATALOG_TOOLS)

    def assistant(state: State) -> dict:
        prompt = SystemMessage(content=music_system_prompt(state.get("memory")))
        return {"messages": [model.invoke([prompt] + list(state["messages"]))]}

    graph = StateGraph(State)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(MUSIC_CATALOG_TOOLS))
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")
    return graph.compile(name="music_catalog_agent")
