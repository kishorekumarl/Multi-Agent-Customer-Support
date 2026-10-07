from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config.settings import settings
from src.graph.prompts import EXTRACTION_PROMPT
from src.graph.state import State
from src.schemas.UserInput import UserInput
from src.tools.customer_lookup import find_customer_id
from src.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Build the extraction model on first use, so importing this module needs no API key."""
    return ChatOpenAI(
        model=settings.model_name,
        temperature=settings.temperature,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )


def verify_identity(state: State) -> dict:
    """Verify the customer from the latest HumanMessage.

    On success, inject the verified customer_id into the state together with a
    SystemMessage. That message is the only way downstream agents receive the
    ID; it is never parsed from free-text user messages. On failure, return no
    update so the route function sends the user to the human-input node.

    A conversation is verified once: if customer_id is already set (every turn after
    the first starts here too), nothing is extracted, so a later message can never
    switch the session to another customer.
    """
    if state.get("customer_id") is not None:
        return {}

    human_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if human_message is None:
        return {}

    extractor = get_llm().with_structured_output(UserInput)
    result: UserInput = extractor.invoke(
        [SystemMessage(content=EXTRACTION_PROMPT), HumanMessage(content=human_message.content)]
    )

    if result.identifier is None:
        logger.info("No identifier found in user message.")
        return {}

    cid = find_customer_id(result.identifier, result.identifier_type)
    if cid is None:
        logger.info("No customer found for the given identifier.")
        return {}

    logger.info("Verified customer %s.", cid)
    return {
        "customer_id": cid,
        "messages": [SystemMessage(content=f"Verified customer ID: {cid}")],
    }
