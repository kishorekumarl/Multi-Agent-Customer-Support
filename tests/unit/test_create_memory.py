import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")  # the node imports the LLM factory

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.store.memory import InMemoryStore

from src.graph.memory_store import load_profile, save_profile
from src.graph.nodes import create_memory as node
from src.graph.prompts import MEMORY_EXTRACTION_PROMPT
from src.schemas.UserProfile import UserProfile


class FakeLLM:
    """Stands in for ChatOpenAI: returns `result` and records what it was sent."""

    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def with_structured_output(self, schema):
        assert schema is UserProfile
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.result


class SpyStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.puts = 0

    def put(self, *args, **kwargs):
        self.puts += 1
        return super().put(*args, **kwargs)


@pytest.fixture
def store():
    return SpyStore()


def extracted(*prefs, customer_id=1):
    return UserProfile(customer_id=customer_id, music_preferences=list(prefs))


def run(monkeypatch, store, result, messages=None, customer_id=1, error=None):
    fake = FakeLLM(result, error)
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    state = {"messages": messages or [HumanMessage(content="I love rock")]}
    if customer_id is not None:
        state["customer_id"] = customer_id
    return node.create_memory(state, store=store), fake


def saved(store, cid=1):
    profile = load_profile(store, cid)
    return profile.music_preferences if profile else None


def test_saves_new_preference(monkeypatch, store):
    out, _ = run(monkeypatch, store, extracted("rock"))
    assert out == {}
    assert saved(store) == ["rock"]
    assert store.get(("memory_profile", "1"), "user_memory") is not None


def test_merge_is_a_union_and_keeps_existing_first(monkeypatch, store):
    save_profile(store, extracted("rock"))
    run(monkeypatch, store, extracted("jazz"))
    assert saved(store) == ["rock", "jazz"]


def test_duplicates_are_skipped_case_insensitively(monkeypatch, store):
    save_profile(store, extracted("rock"))
    run(monkeypatch, store, extracted("Rock", "jazz"))
    assert saved(store) == ["rock", "jazz"]


def test_empty_extraction_never_touches_saved_preferences(monkeypatch, store):
    save_profile(store, extracted("rock", "AC/DC"))
    store.puts = 0
    run(monkeypatch, store, extracted())
    assert store.puts == 0
    assert saved(store) == ["rock", "AC/DC"]


def test_nothing_new_skips_the_write(monkeypatch, store):
    save_profile(store, extracted("rock"))
    store.puts = 0
    run(monkeypatch, store, extracted("ROCK"))
    assert store.puts == 0


def test_empty_extraction_for_new_customer_writes_nothing(monkeypatch, store):
    run(monkeypatch, store, extracted())
    assert store.puts == 0
    assert saved(store) is None


def test_no_customer_id_does_nothing(monkeypatch, store):
    out, fake = run(monkeypatch, store, extracted("rock"), customer_id=None)
    assert out == {} and fake.calls == [] and store.puts == 0


def test_model_supplied_customer_id_is_ignored(monkeypatch, store):
    run(monkeypatch, store, extracted("rock", customer_id=999), customer_id=1)
    assert saved(store, 1) == ["rock"]
    assert saved(store, 999) is None


def test_customers_do_not_share_memory(monkeypatch, store):
    run(monkeypatch, store, extracted("rock"), customer_id=1)
    run(monkeypatch, store, extracted("jazz"), customer_id=2)
    assert saved(store, 1) == ["rock"]
    assert saved(store, 2) == ["jazz"]


def test_llm_failure_is_swallowed_and_store_untouched(monkeypatch, store):
    save_profile(store, extracted("rock"))
    store.puts = 0
    out, _ = run(monkeypatch, store, None, error=RuntimeError("boom"))
    assert out == {} and store.puts == 0
    assert saved(store) == ["rock"]


def test_transcript_is_labelled_windowed_and_has_no_system_messages(monkeypatch, store):
    messages = [SystemMessage(content="Verified customer ID: 1")]
    for i in range(8):
        messages += [HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}")]
    _, fake = run(monkeypatch, store, extracted(), messages=messages)
    system, human = fake.calls[0]
    assert system.content == MEMORY_EXTRACTION_PROMPT
    lines = human.content.splitlines()
    assert len(lines) == 10
    assert lines[-1] == "Assistant: a7"
    assert all(line.startswith(("Customer: ", "Assistant: ")) for line in lines)
    assert "Verified customer ID" not in human.content


def test_no_conversation_text_means_no_llm_call(monkeypatch, store):
    _, fake = run(monkeypatch, store, extracted("rock"), messages=[SystemMessage(content="x")])
    assert fake.calls == []


def test_preferences_are_not_logged(monkeypatch, store, caplog):
    caplog.set_level("DEBUG")
    run(monkeypatch, store, extracted("Secret Band"))
    assert "Secret Band" not in caplog.text
