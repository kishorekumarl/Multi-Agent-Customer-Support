import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")  # the node builds its LLM client on import

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.graph.nodes import verify_identity as node
from src.schemas.UserInput import UserInput
from src.tools import _common


class FakeLLM:
    """Stands in for ChatOpenAI: with_structured_output(...).invoke(...) returns `result`."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def with_structured_output(self, schema):
        assert schema is UserInput
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self.result


@pytest.fixture
def customer():
    return _common._query(
        "SELECT CustomerId, Email, Phone FROM Customer WHERE Phone IS NOT NULL LIMIT 1", {}
    )[0]


def run(monkeypatch, result, text="hello"):
    fake = FakeLLM(result)
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    return node.verify_identity({"messages": [HumanMessage(content=text)]}), fake


def test_verified_by_customer_id(monkeypatch, customer):
    cid = customer["CustomerId"]
    out, _ = run(monkeypatch, UserInput(identifier=str(cid), identifier_type="customer_id"))
    assert out["customer_id"] == cid


def test_verified_by_email_any_case(monkeypatch, customer):
    out, _ = run(
        monkeypatch, UserInput(identifier=customer["Email"].upper(), identifier_type="email")
    )
    assert out["customer_id"] == customer["CustomerId"]


def test_verified_by_phone_in_other_format(monkeypatch, customer):
    compact = "".join(ch for ch in customer["Phone"] if ch.isdigit() or ch == "+")
    out, _ = run(monkeypatch, UserInput(identifier=compact, identifier_type="phone"))
    assert out["customer_id"] == customer["CustomerId"]


def test_success_injects_customer_id_via_system_message(monkeypatch, customer):
    cid = customer["CustomerId"]
    out, _ = run(monkeypatch, UserInput(identifier=str(cid), identifier_type="customer_id"))
    assert set(out) == {"customer_id", "messages"}  # no stray keys the State doesn't define
    (message,) = out["messages"]
    assert isinstance(message, SystemMessage)
    assert str(cid) in message.content


def test_no_identifier_returns_no_update(monkeypatch):
    out, _ = run(monkeypatch, UserInput(), text="hi there")
    assert out == {}


@pytest.mark.parametrize(
    "identifier, identifier_type",
    [("99999", "customer_id"), ("nobody@example.com", "email"), ("+999 000 0000", "phone")],
)
def test_unknown_customer_returns_no_update(monkeypatch, identifier, identifier_type):
    out, _ = run(monkeypatch, UserInput(identifier=identifier, identifier_type=identifier_type))
    assert out == {}  # no customer_id and, above all, no "verified" SystemMessage


def test_garbage_customer_id_does_not_crash(monkeypatch):
    out, _ = run(monkeypatch, UserInput(identifier="abc", identifier_type="customer_id"))
    assert out == {}


def test_no_human_message_returns_no_update(monkeypatch):
    monkeypatch.setattr(node, "get_llm", lambda: FakeLLM(UserInput()))
    assert node.verify_identity({"messages": []}) == {}
    assert node.verify_identity({"messages": [AIMessage(content="hi")]}) == {}


def test_only_latest_human_message_is_sent_to_the_llm(monkeypatch):
    fake = FakeLLM(UserInput())
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    node.verify_identity(
        {
            "messages": [
                HumanMessage(content="my id is 1"),
                AIMessage(content="couldn't match that"),
                HumanMessage(content="try bob@example.com"),
            ]
        }
    )
    sent = fake.calls[0]
    assert isinstance(sent[0], SystemMessage)
    assert sent[-1].content == "try bob@example.com"
    assert all("my id is 1" not in m.content for m in sent)


def test_identifier_is_not_logged(monkeypatch, caplog, customer):
    caplog.set_level("DEBUG")
    run(monkeypatch, UserInput(identifier=customer["Email"], identifier_type="email"))
    run(monkeypatch, UserInput(identifier="nobody@example.com", identifier_type="email"))
    assert customer["Email"] not in caplog.text
    assert "nobody@example.com" not in caplog.text


def test_already_verified_session_is_never_re_verified(monkeypatch, customer):
    other = _common._query(
        "SELECT CustomerId, Email FROM Customer WHERE CustomerId != :c LIMIT 1",
        {"c": customer["CustomerId"]},
    )[0]
    fake = FakeLLM(UserInput(identifier=other["Email"], identifier_type="email"))
    monkeypatch.setattr(node, "get_llm", lambda: fake)
    state = {
        "messages": [HumanMessage(content=f"actually I'm {other['Email']}")],
        "customer_id": customer["CustomerId"],
    }
    assert node.verify_identity(state) == {}  # no switch of customer ...
    assert fake.calls == []  # ... and no LLM call either
