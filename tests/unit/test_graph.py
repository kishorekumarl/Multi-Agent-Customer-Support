import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")  # the node builds its LLM client on import

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from src.graph import builder
from src.graph.memory_store import load_profile, save_profile
from src.graph.nodes import create_memory as memory_node
from src.graph.nodes import verify_identity as node
from src.graph.prompts import FALLBACK_MESSAGE
from src.schemas.UserInput import UserInput
from src.schemas.UserProfile import UserProfile


class FakeLLM:
    """Stands in for ChatOpenAI; each extraction pops the next queued UserInput."""

    def __init__(self):
        self.queue = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.queue.pop(0)


class FakeMemoryLLM:
    """Stands in for the memory extraction model; returns `result` and records its input."""

    def __init__(self):
        self.result = UserProfile(customer_id=1, music_preferences=[])
        self.calls = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self.result


@pytest.fixture
def memory_llm(monkeypatch):
    fake = FakeMemoryLLM()
    monkeypatch.setattr(memory_node, "get_llm", lambda: fake)
    return fake


@pytest.fixture
def llm(monkeypatch, memory_llm):
    """Fake extraction for verification. Requesting it also stubs the memory model,
    so no graph test ever reaches the real API."""
    fake = FakeLLM()
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    return fake


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def graph(store, scripted_model):
    """The real graph, with a scripted model for the supervisor so nothing reaches the API."""
    return builder.build_graph(MemorySaver(), store, agent_llm=scripted_model())


@pytest.fixture
def config():
    return {"configurable": {"thread_id": "t1"}}


def start(graph, config, text):
    return graph.invoke({"messages": [HumanMessage(content=text)], "customer_id": None}, config)


def interrupt_text(result):
    return result["__interrupt__"][0].value


NO_ID = UserInput()
ID_1 = UserInput(identifier="1", identifier_type="customer_id")
ID_2 = UserInput(identifier="2", identifier_type="customer_id")
UNKNOWN = UserInput(identifier="99999", identifier_type="customer_id")


# --- routing ---------------------------------------------------------------------


def test_router_loads_memory_when_verified():
    assert builder.router_after_verify({"messages": [], "customer_id": 7}) == "load_memory"


@pytest.mark.parametrize("state", [{"messages": []}, {"messages": [], "customer_id": None}])
def test_router_asks_again_when_not_verified(state):
    assert builder.router_after_verify(state) == "human_input"


# --- the graph -------------------------------------------------------------------


def test_valid_identifier_verifies_without_interrupt(graph, config, llm):
    llm.queue = [ID_1]
    result = start(graph, config, "my id is 1")
    assert "__interrupt__" not in result
    assert result["customer_id"] == 1


def test_customer_id_reaches_agents_only_via_system_message(graph, config, llm):
    llm.queue = [ID_1]
    result = start(graph, config, "my id is 1")
    system = [m for m in result["messages"] if isinstance(m, SystemMessage)]
    assert len(system) == 1
    assert "1" in system[0].content


def test_missing_identifier_interrupts_with_fallback_message(graph, config, llm):
    llm.queue = [NO_ID]
    result = start(graph, config, "hi there")
    assert interrupt_text(result) == FALLBACK_MESSAGE
    assert not result.get("customer_id")


def test_unknown_identifier_interrupts_and_adds_no_system_message(graph, config, llm):
    llm.queue = [UNKNOWN]
    result = start(graph, config, "my id is 99999")
    assert interrupt_text(result) == FALLBACK_MESSAGE
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])


def test_resume_with_valid_identifier_verifies(graph, config, llm):
    llm.queue = [NO_ID, ID_1]
    start(graph, config, "hi there")
    result = graph.invoke(Command(resume="my id is 1"), config)
    assert "__interrupt__" not in result
    assert result["customer_id"] == 1


def test_resumed_reply_is_added_as_a_human_message(graph, config, llm):
    llm.queue = [NO_ID, ID_1]
    start(graph, config, "hi there")
    result = graph.invoke(Command(resume="my id is 1"), config)
    humans = [m.content for m in result["messages"] if isinstance(m, HumanMessage)]
    assert humans == ["hi there", "my id is 1"]


def test_failed_retry_interrupts_again_then_succeeds(graph, config, llm):
    llm.queue = [NO_ID, UNKNOWN, ID_1]
    start(graph, config, "hi there")

    second = graph.invoke(Command(resume="99999"), config)
    assert interrupt_text(second) == FALLBACK_MESSAGE
    assert not second.get("customer_id")

    third = graph.invoke(Command(resume="1"), config)
    assert "__interrupt__" not in third
    assert third["customer_id"] == 1


def test_interrupted_run_is_paused_at_human_input(graph, config, llm):
    llm.queue = [NO_ID]
    start(graph, config, "hi there")
    assert graph.get_state(config).next == ("human_input",)


def test_threads_are_isolated(graph, llm):
    llm.queue = [ID_1, NO_ID]
    verified = start(graph, {"configurable": {"thread_id": "a"}}, "my id is 1")
    other = start(graph, {"configurable": {"thread_id": "b"}}, "hi there")
    assert verified["customer_id"] == 1
    assert not other.get("customer_id")


# --- memory ----------------------------------------------------------------------


def prefs(*items, customer_id=1):
    return UserProfile(customer_id=customer_id, music_preferences=list(items))


def saved(store, cid=1):
    profile = load_profile(store, cid)
    return profile.music_preferences if profile else None


def test_saved_preferences_are_loaded_into_state(graph, config, llm, store):
    save_profile(store, prefs("rock", "AC/DC", "jazz"))
    llm.queue = [ID_1]
    result = start(graph, config, "my id is 1")
    assert result["memory"] == "Music Preferences: rock, AC/DC, jazz"


def test_customer_without_saved_preferences_has_no_memory(graph, config, llm):
    llm.queue = [ID_1]
    result = start(graph, config, "my id is 1")
    assert result.get("memory") is None


def test_stated_preference_is_saved_after_the_response(graph, config, llm, memory_llm, store):
    memory_llm.result = prefs("rock")
    llm.queue = [ID_1]
    start(graph, config, "my id is 1, and I love rock")
    assert saved(store) == ["rock"]


def test_new_preferences_are_merged_not_overwritten(graph, config, llm, memory_llm, store):
    save_profile(store, prefs("rock"))
    memory_llm.result = prefs("jazz")
    llm.queue = [ID_1]
    start(graph, config, "my id is 1, and I like jazz")
    assert saved(store) == ["rock", "jazz"]


def test_empty_extraction_keeps_saved_preferences(graph, config, llm, memory_llm, store):
    save_profile(store, prefs("rock", "AC/DC"))
    memory_llm.result = prefs()
    llm.queue = [ID_1]
    start(graph, config, "my id is 1, do you have any blues?")
    assert saved(store) == ["rock", "AC/DC"]


def test_memory_carries_over_to_a_new_conversation(graph, llm, memory_llm, store):
    memory_llm.result = prefs("rock")
    llm.queue = [ID_1, ID_1]
    start(graph, {"configurable": {"thread_id": "first"}}, "my id is 1, I love rock")

    memory_llm.result = prefs()
    second = start(graph, {"configurable": {"thread_id": "second"}}, "my id is 1")
    assert second["memory"] == "Music Preferences: rock"


def test_customers_do_not_see_each_others_preferences(graph, config, llm, store):
    save_profile(store, prefs("rock", customer_id=1))
    llm.queue = [ID_2]
    result = start(graph, config, "my id is 2")
    assert result["customer_id"] == 2
    assert result.get("memory") is None


def test_unverified_customer_gets_no_memory_and_nothing_is_saved(
    graph, config, llm, memory_llm, store
):
    save_profile(store, prefs("rock"))
    memory_llm.result = prefs("metal")
    llm.queue = [NO_ID]
    result = start(graph, config, "I love metal")
    assert "__interrupt__" in result
    assert result.get("memory") is None
    assert memory_llm.calls == []
    assert saved(store) == ["rock"]


def test_memory_extraction_sees_the_customers_words_but_not_the_id_message(
    graph, config, llm, memory_llm
):
    llm.queue = [ID_1]
    start(graph, config, "my id is 1, I love rock")
    (system, human), = memory_llm.calls
    assert "Customer: my id is 1, I love rock" in human.content
    assert "Verified customer ID" not in human.content


# --- supervisor and agents -------------------------------------------------------


def test_graph_order_is_verify_memory_supervisor_save_memory(graph):
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("load_memory", "supervisor") in edges
    assert ("supervisor", "create_memory") in edges
    assert ("create_memory", "__end__") in edges
    assert "next_node" not in graph.get_graph().nodes


def test_supervisor_reply_is_the_last_message(config, llm, store, scripted_model):
    model = scripted_model(AIMessage(content="Hello, how can I help?"))
    graph = builder.build_graph(MemorySaver(), store, agent_llm=model)
    llm.queue = [ID_1]
    result = start(graph, config, "my id is 1")
    assert result["messages"][-1].content == "Hello, how can I help?"


def test_music_agent_sees_saved_preferences_through_the_whole_graph(
    config, llm, store, scripted_model
):
    save_profile(store, prefs("jazz"))
    model = scripted_model(
        AIMessage(content="", tool_calls=[{"name": "transfer_to_music_catalog_agent",
                                           "args": {}, "id": "h1"}]),
        AIMessage(content="Try Miles Davis."),
        AIMessage(content="Try Miles Davis."),
    )
    graph = builder.build_graph(MemorySaver(), store, agent_llm=model)
    llm.queue = [ID_1]
    start(graph, config, "my id is 1, suggest something")
    agent_system_prompts = [call[0].content for call in model.calls if "music catalog" in call[0].content]
    assert agent_system_prompts, "the music agent never ran"
    assert "Music Preferences: jazz" in agent_system_prompts[0]


def test_agents_never_run_for_an_unverified_customer(config, llm, store, scripted_model):
    model = scripted_model()
    graph = builder.build_graph(MemorySaver(), store, agent_llm=model)
    llm.queue = [NO_ID]
    result = start(graph, config, "show me all invoices")
    assert "__interrupt__" in result
    assert model.calls == []
