import pytest
from langgraph.store.memory import InMemoryStore

from src.graph.memory_store import save_profile
from src.graph.nodes import load_memory as module
from src.graph.nodes.load_memory import load_memory
from src.schemas.UserProfile import UserProfile


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


def state(customer_id=1):
    return {"messages": [], "customer_id": customer_id}


def test_no_customer_id_changes_nothing(store):
    assert load_memory({"messages": []}, store=store) == {}
    assert load_memory({"messages": [], "customer_id": None}, store=store) == {}


def test_customer_without_saved_preferences_gets_no_memory(store):
    assert load_memory(state(), store=store) == {"memory": None}


def test_empty_preference_list_gets_no_memory(store):
    save_profile(store, UserProfile(customer_id=1, music_preferences=[]))
    assert load_memory(state(), store=store) == {"memory": None}


def test_saved_preferences_are_formatted_for_the_prompt(store):
    save_profile(store, UserProfile(customer_id=1, music_preferences=["rock", "AC/DC", "jazz"]))
    assert load_memory(state(), store=store) == {
        "memory": "Music Preferences: rock, AC/DC, jazz"
    }


def test_customers_only_see_their_own_preferences(store):
    save_profile(store, UserProfile(customer_id=1, music_preferences=["rock"]))
    save_profile(store, UserProfile(customer_id=2, music_preferences=["jazz"]))
    assert load_memory(state(2), store=store)["memory"] == "Music Preferences: jazz"
    assert load_memory(state(3), store=store) == {"memory": None}


def test_loading_never_writes_to_the_store(store):
    save_profile(store, UserProfile(customer_id=1, music_preferences=["rock"]))
    store.puts = 0
    load_memory(state(), store=store)
    assert store.puts == 0


def test_a_failing_store_means_no_memory_not_a_crash(monkeypatch, store):
    def boom(*args, **kwargs):
        raise RuntimeError("store down")

    monkeypatch.setattr(module, "load_profile", boom)
    assert load_memory(state(), store=store) == {"memory": None}


def test_preferences_are_not_logged(store, caplog):
    caplog.set_level("DEBUG")
    save_profile(store, UserProfile(customer_id=1, music_preferences=["Secret Band"]))
    load_memory(state(), store=store)
    assert "Secret Band" not in caplog.text
