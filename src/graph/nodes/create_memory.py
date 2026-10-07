from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.store.base import BaseStore

from src.graph.memory_store import load_profile, save_profile
from src.graph.nodes.verify_identity import get_llm
from src.graph.prompts import MEMORY_EXTRACTION_PROMPT
from src.graph.state import State
from src.schemas.UserProfile import UserProfile
from src.utils.logger import get_logger

logger = get_logger(__name__)

WINDOW = 10  # how many recent messages the extraction sees


def _text(message) -> str:
    """Plain text of a message; content can be a string or a list of parts."""
    content = message.content
    if isinstance(content, str):
        return content
    return " ".join(
        part if isinstance(part, str) else part.get("text", "") for part in content
    )


def _transcript(messages) -> str:
    """Label the last WINDOW messages Customer/Assistant, leaving out system messages."""
    lines = []
    for message in messages[-WINDOW:]:
        text = _text(message).strip()
        if not text:
            continue  # e.g. an AI turn that only carries a tool or handoff call
        if isinstance(message, HumanMessage):
            lines.append(f"Customer: {text}")
        elif isinstance(message, AIMessage):
            lines.append(f"Assistant: {text}")
    return "\n".join(lines)


def create_memory(state: State, *, store: BaseStore) -> dict:
    """Save music preferences the customer stated, merged into what is already saved.

    Existing preferences are never removed or overwritten. If nothing new was
    extracted, the store is not written at all.
    """
    cid = state.get("customer_id")
    if cid is None:
        return {}

    transcript = _transcript(state["messages"])
    if not transcript:
        return {}

    try:
        extractor = get_llm().with_structured_output(UserProfile)
        extracted: UserProfile = extractor.invoke(
            [SystemMessage(content=MEMORY_EXTRACTION_PROMPT), HumanMessage(content=transcript)]
        )
        # The model's customer_id is ignored: only extracted.music_preferences is used.
        if not extracted.music_preferences:
            return {}  # nothing stated: keep whatever is saved untouched

        existing = load_profile(store, cid)
        saved = existing.music_preferences if existing else []
        known = {p.casefold() for p in saved}
        new = [p for p in extracted.music_preferences if p.casefold() not in known]
        if not new:
            return {}  # nothing new: skip the write

        save_profile(store, UserProfile(customer_id=cid, music_preferences=saved + new))
    except Exception:
        logger.exception("Could not update memory for customer %s.", cid)
        return {}

    logger.info("Saved %d new preferences for customer %s.", len(new), cid)
    return {}
