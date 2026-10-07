import io
import logging

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.supervisor import build_supervisor


def captured(run):
    """Everything the "langgraph" logger emits while `run()` executes."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    logger = logging.getLogger("langgraph")
    logger.addHandler(handler)
    try:
        run()
    finally:
        logger.removeHandler(handler)
    return buffer.getvalue()


def handoff(name, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": call_id}])


def test_a_supervisor_handoff_no_longer_logs_the_remaining_steps_notice(scripted_model):
    model = scripted_model(
        handoff("transfer_to_music_catalog_agent", "h1"),
        AIMessage(content="It is an album."),
        AIMessage(content="Final answer."),
    )
    supervisor = build_supervisor(model)
    log = captured(
        lambda: supervisor.invoke(
            {"messages": [HumanMessage(content="what is this album about")], "customer_id": 1}
        )
    )
    assert "remaining_steps" not in log


def test_other_langgraph_warnings_still_get_through():
    log = captured(lambda: logging.getLogger("langgraph").warning("a different problem"))
    assert "a different problem" in log


def test_a_notice_about_another_channel_still_gets_through():
    message = "Task x wrote to unknown channel customer_id, ignoring it."
    assert message in captured(lambda: logging.getLogger("langgraph").warning(message))
