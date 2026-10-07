import pytest

from src.tools import _common


@pytest.fixture(autouse=True)
def patch_engine(monkeypatch, seeded_engine):
    """Point the tools at an isolated, per-test engine instead of the global cached one."""
    monkeypatch.setattr(_common, "get_engine", lambda: seeded_engine)


from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChatModel(BaseChatModel):
    """A chat model that plays back `replies` in order (then says "OK"); no network.

    bind_tools returns the model itself, so it can drive agents and the supervisor.
    `calls` records every list of messages the model was sent.
    """

    replies: list = []
    calls: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        reply = self.replies.pop(0) if self.replies else AIMessage(content="OK")
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture
def scripted_model():
    """Factory: scripted_model(AIMessage(...), AIMessage(...)) -> ScriptedChatModel."""

    def make(*replies):
        return ScriptedChatModel(replies=list(replies), calls=[])

    return make
