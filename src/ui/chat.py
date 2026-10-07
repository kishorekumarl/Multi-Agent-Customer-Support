"""Chat logic for the UI, kept free of Gradio so it can be tested without a browser."""

import time
import uuid
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

GREETING = (
    "Hi! I'm the music store support assistant. To get started, please share your "
    "Customer ID, the email on your account, or your phone number."
)
ERROR_REPLY = "Sorry, something went wrong on my side. Please try again in a moment."

# What the status line says once each graph node has finished (i.e. what runs next).
NEXT_STEP = {
    "verify_info": "Loading your preferences...",
    "load_memory": "Finding an answer...",
    "supervisor": "Saving your preferences...",
}


@dataclass
class TurnResult:
    reply: str
    waiting: bool  # True when the graph is paused, waiting for the customer's next message
    seconds: float


def new_thread_id() -> str:
    """One per browser session; the checkpointer keeps each thread's history separate."""
    return str(uuid.uuid4())


def graph_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


# --- status line -----------------------------------------------------------------


def status_idle() -> str:
    return "Ready"


def status_processing(step: str = "Processing...") -> str:
    return f"⏳ **{step}**"


def status_success(seconds: float) -> str:
    return f"✅ **Done** in {seconds:.1f}s"


def status_waiting() -> str:
    return "🔐 **Waiting for your input**"


def status_error() -> str:
    return "⚠️ **Error** - something went wrong, please try again"


# --- running a turn --------------------------------------------------------------


def _text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return " ".join(p if isinstance(p, str) else p.get("text", "") for p in content)


def last_ai_text(messages) -> str:
    """The most recent assistant message that has text (tool-call turns have none)."""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and _text(message).strip():
            return _text(message).strip()
    return ""


def stream_turn(graph, thread_id: str, text: str):
    """Run one customer message through the graph.

    Yields ("progress", status_text) as graph nodes finish, then one
    ("final", TurnResult). If the graph is paused at an interrupt (waiting for the
    customer to answer), the message resumes it; otherwise it starts a new run.
    """
    config = graph_config(thread_id)
    started = time.perf_counter()

    paused = bool(graph.get_state(config).next)
    payload = Command(resume=text) if paused else {"messages": [HumanMessage(content=text)]}

    for update in graph.stream(payload, config, stream_mode="updates"):
        for node in update:
            if node in NEXT_STEP:
                yield ("progress", status_processing(NEXT_STEP[node]))

    snapshot = graph.get_state(config)
    waiting = bool(snapshot.next)
    if waiting:
        reply = str(snapshot.tasks[0].interrupts[0].value)
    else:
        reply = last_ai_text(snapshot.values.get("messages", []))
    yield ("final", TurnResult(reply or ERROR_REPLY, waiting, time.perf_counter() - started))
