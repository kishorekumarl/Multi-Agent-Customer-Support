"""The UI's send handler, driven directly (no browser)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from src.ui import chat
from src.ui.app import make_respond, start_session


class StubSnapshot:
    def __init__(self, next_=(), values=None, tasks=()):
        self.next, self.values, self.tasks = next_, values or {}, tasks


class StubGraph:
    """Just enough graph for stream_turn: replays `updates`, then reports `final`."""

    def __init__(self, updates=(), final=None, fail=False):
        self.updates, self.final, self.fail, self.threads = updates, final, fail, []

    def get_state(self, config):
        return self.final if self.final is not None and getattr(self, "_done", False) else StubSnapshot()

    def stream(self, payload, config, stream_mode):
        self.threads.append(config["configurable"]["thread_id"])
        if self.fail:
            raise RuntimeError("model down")
        for update in self.updates:
            yield update
        self._done = True


def ai_snapshot(text):
    from langchain_core.messages import AIMessage

    return StubSnapshot(values={"messages": [AIMessage(content=text)]})


def run(respond, message, history=None, thread_id="t"):
    return list(respond(message, history or [], thread_id))


# Each yield is (chatbot history, textbox, status, send button, thread id).


def test_the_users_message_is_shown_first_before_any_model_call():
    graph = StubGraph(final=ai_snapshot("hi!"))
    first = run(make_respond(graph), "hello")[0]
    history, box, status, send, _ = first
    assert history[-1] == {"role": "user", "content": "hello"}
    assert box == ""  # input cleared right away
    assert "Processing" in status
    assert send["interactive"] is False  # no double sends while working


def test_successful_turn_ends_with_the_reply_and_a_done_status():
    graph = StubGraph(updates=[{"verify_info": {}}, {"supervisor": {}}], final=ai_snapshot("hi!"))
    steps = run(make_respond(graph), "hello")
    history, _, status, send, _ = steps[-1]
    assert history[-1] == {"role": "assistant", "content": "hi!"}
    assert "Done" in status and "s" in status
    assert send["interactive"] is True
    assert any("Finding an answer" in s[2] or "Loading" in s[2] for s in steps)  # progress shown


def test_a_waiting_graph_shows_the_waiting_status():
    class Task:
        interrupts = [type("I", (), {"value": chat.GREETING})()]

    graph = StubGraph(final=StubSnapshot(next_=("human_input",), tasks=[Task()]))
    steps = run(make_respond(graph), "hi")
    history, _, status, send, _ = steps[-1]
    assert "Waiting for your input" in status
    assert history[-1]["content"] == chat.GREETING
    assert send["interactive"] is True


def test_a_failure_shows_a_friendly_error_not_the_exception():
    steps = run(make_respond(StubGraph(fail=True)), "hello")
    history, _, status, send, _ = steps[-1]
    assert "Error" in status
    assert history[-1]["content"] == chat.ERROR_REPLY
    assert "model down" not in str(steps)
    assert send["interactive"] is True  # the customer can try again


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_messages_do_nothing(blank):
    graph = StubGraph(final=ai_snapshot("x"))
    steps = run(make_respond(graph), blank, history=[{"role": "assistant", "content": "hi"}])
    assert len(steps) == 1 and graph.threads == []  # the graph was never called
    assert steps[0][0] == [{"role": "assistant", "content": "hi"}]


def test_history_is_kept_across_turns():
    graph = StubGraph(final=ai_snapshot("ok"))
    past = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    history = run(make_respond(graph), "c", history=past)[-1][0]
    assert [m["content"] for m in history] == ["a", "b", "c", "ok"]


def test_a_missing_thread_id_gets_one_and_returns_it():
    graph = StubGraph(final=ai_snapshot("ok"))
    steps = run(make_respond(graph), "hello", thread_id=None)
    thread = steps[-1][4]
    assert thread and graph.threads == [thread]


def test_the_given_thread_id_is_used_unchanged():
    graph = StubGraph(final=ai_snapshot("ok"))
    run(make_respond(graph), "hello", thread_id="session-42")
    assert graph.threads == ["session-42"]


def test_new_conversation_resets_the_thread_chat_and_status():
    thread, history, status = start_session()
    assert history == [{"role": "assistant", "content": chat.GREETING}]
    assert status == chat.status_idle()
    other, _, _ = start_session()
    assert thread != other  # every New Conversation gets a different thread
