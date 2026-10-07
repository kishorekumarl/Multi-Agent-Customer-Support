import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.graph import builder
from src.graph.nodes import create_memory as memory_node
from src.graph.nodes import verify_identity as node
from src.graph.prompts import FALLBACK_MESSAGE
from src.schemas.UserInput import UserInput
from src.schemas.UserProfile import UserProfile
from src.ui import chat


class FakeExtractor:
    """Stands in for the identifier-extraction model; an empty queue means "no identifier"."""

    def __init__(self):
        self.queue = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.queue.pop(0) if self.queue else UserInput()


class FakeMemoryModel:
    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return UserProfile(customer_id=1, music_preferences=[])


ID_1 = UserInput(identifier="1", identifier_type="customer_id")


@pytest.fixture
def extractor(monkeypatch):
    fake = FakeExtractor()
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    monkeypatch.setattr(memory_node, "get_llm", lambda: FakeMemoryModel())
    return fake


@pytest.fixture
def graph(scripted_model):
    model = scripted_model(*[AIMessage(content=f"answer {i}") for i in range(20)])
    return builder.build_graph(MemorySaver(), InMemoryStore(), agent_llm=model)


def run(graph, thread, text):
    events = list(chat.stream_turn(graph, thread, text))
    assert events[-1][0] == "final"
    return events[:-1], events[-1][1]


# --- sessions ----------------------------------------------------------------------


def test_every_session_gets_a_unique_thread_id():
    ids = {chat.new_thread_id() for _ in range(50)}
    assert len(ids) == 50


def test_graph_config_scopes_by_thread():
    assert chat.graph_config("abc") == {"configurable": {"thread_id": "abc"}}


# --- status line -----------------------------------------------------------------------


def test_status_texts_cover_processing_success_waiting_and_error():
    assert "Processing" in chat.status_processing()
    assert "Finding an answer" in chat.status_processing("Finding an answer...")
    assert "Done" in chat.status_success(2.34) and "2.3s" in chat.status_success(2.34)
    assert "Waiting for your input" in chat.status_waiting()
    assert "Error" in chat.status_error()


# --- a turn through the real graph -------------------------------------------------------


def test_verification_interrupt_waits_then_resumes(graph, extractor):
    extractor.queue = [UserInput(), ID_1]
    _, first = run(graph, "t", "hello")
    assert first.waiting and first.reply == FALLBACK_MESSAGE

    _, second = run(graph, "t", "my id is 1")  # resumes the paused graph
    assert not second.waiting
    assert second.reply == "answer 0"
    assert second.seconds >= 0


def test_wrong_identifier_keeps_waiting(graph, extractor):
    extractor.queue = [UserInput(identifier="99999", identifier_type="customer_id")]
    _, result = run(graph, "t", "my id is 99999")
    assert result.waiting and result.reply == FALLBACK_MESSAGE


def test_progress_events_follow_the_graph_stages(graph, extractor):
    extractor.queue = [ID_1]
    progress, _ = run(graph, "t", "my id is 1")
    assert [p[1] for p in progress] == [
        chat.status_processing("Loading your preferences..."),
        chat.status_processing("Finding an answer..."),
        chat.status_processing("Saving your preferences..."),
    ]


def test_later_turns_do_not_verify_again(graph, extractor):
    extractor.queue = [ID_1]
    run(graph, "t", "my id is 1")
    _, second = run(graph, "t", "show my invoices")  # extractor queue is empty: no 2nd call
    assert not second.waiting and second.reply == "answer 1"


def test_new_thread_starts_unverified(graph, extractor):
    extractor.queue = [ID_1]
    run(graph, "old", "my id is 1")
    _, fresh = run(graph, "new", "show my invoices")
    assert fresh.waiting  # the new conversation must verify again


def test_two_sessions_do_not_cross_talk(graph, extractor):
    extractor.queue = [ID_1]
    run(graph, "tab-a", "my id is 1")
    _, other = run(graph, "tab-b", "show my invoices")
    assert other.waiting
    a = graph.get_state(chat.graph_config("tab-a")).values
    b = graph.get_state(chat.graph_config("tab-b")).values
    assert a["customer_id"] == 1 and not b.get("customer_id")
    assert all("my id is 1" not in m.content for m in b["messages"] if isinstance(m, HumanMessage))


def test_last_ai_text_skips_tool_call_turns():
    messages = [
        AIMessage(content="first"),
        AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
    ]
    assert chat.last_ai_text(messages) == "first"
    assert chat.last_ai_text([]) == ""


# --- the UI object ---------------------------------------------------------------------------


def test_ui_builds_without_an_api_key_when_given_a_graph(graph, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from src.ui.app import build_ui

    ui = build_ui(graph)
    labels = {str(b.value) for b in ui.blocks.values() if type(b).__name__ == "Button"}
    assert {"Send", "New Conversation"} <= labels
