from langgraph.store.base import BaseStore

from src.graph.memory_store import load_profile
from src.graph.state import State
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_memory(state: State, *, store: BaseStore) -> dict:
    """Put the verified customer's saved music preferences into state["memory"]."""
    cid = state.get("customer_id")
    if cid is None:
        return {}

    try:
        profile = load_profile(store, cid)
    except Exception:
        logger.exception("Could not load memory for customer %s.", cid)
        return {"memory": None}

    if profile is None or not profile.music_preferences:
        return {"memory": None}

    logger.info("Loaded %d preferences for customer %s.", len(profile.music_preferences), cid)
    return {"memory": "Music Preferences: " + ", ".join(profile.music_preferences)}
