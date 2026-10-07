import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.invoice_agent import build_invoice_agent
from src.agents.music_agent import build_music_agent, music_system_prompt
from src.agents.supervisor import build_supervisor
from src.graph.prompts import (
    GROUNDING_RULES,
    INVOICE_AGENT_PROMPT,
    MUSIC_AGENT_PROMPT,
    SUPERVISOR_PROMPT,
)
from src.tools import _common


def tool_call(name, args=None, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])


# --- music prompt ----------------------------------------------------------------


def test_music_prompt_includes_saved_preferences():
    prompt = music_system_prompt("Music Preferences: rock, jazz")
    assert prompt.startswith(MUSIC_AGENT_PROMPT)
    assert "Music Preferences: rock, jazz" in prompt


def test_music_prompt_without_memory_is_the_base_prompt():
    assert music_system_prompt(None) == MUSIC_AGENT_PROMPT
    assert music_system_prompt("") == MUSIC_AGENT_PROMPT


def test_music_agent_sends_memory_to_the_model(scripted_model):
    model = scripted_model(AIMessage(content="Try Miles Davis."))
    agent = build_music_agent(model)
    agent.invoke(
        {"messages": [HumanMessage(content="Suggest something")],
         "customer_id": 1, "memory": "Music Preferences: jazz"}
    )
    system = model.calls[0][0]
    assert "Music Preferences: jazz" in system.content
    assert model.calls[0][-1].content == "Suggest something"


def test_music_agent_without_memory_has_no_preferences_section(scripted_model):
    model = scripted_model(AIMessage(content="Sure."))
    build_music_agent(model).invoke(
        {"messages": [HumanMessage(content="hi")], "customer_id": 1, "memory": None}
    )
    assert "What we know about this customer" not in model.calls[0][0].content


# --- factories need no API key ---------------------------------------------------


def test_agents_build_without_an_api_key(scripted_model, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    model = scripted_model()
    assert build_music_agent(model) and build_invoice_agent(model) and build_supervisor(model)


# --- supervisor routing and customer scoping ---------------------------------------


def test_supervisor_routes_to_invoice_agent_and_uses_the_verified_customer(scripted_model):
    model = scripted_model(
        tool_call("transfer_to_invoice_agent", call_id="h1"),
        # the model tries to read customer 2's invoices by passing an extra argument
        tool_call("get_my_invoices", {"customer_id": "2"}, call_id="t1"),
        AIMessage(content="You have invoices."),
        AIMessage(content="Here are your invoices."),
    )
    result = build_supervisor(model).invoke(
        {"messages": [HumanMessage(content="show my invoices")], "customer_id": 1}
    )
    # output_mode="last_message" hides tool traffic from the result, so read what the
    # invoice agent's model was shown after the tool ran.
    tool_outputs = [
        json.loads(m.content)
        for call in model.calls
        for m in call
        if isinstance(m, ToolMessage) and m.name == "get_my_invoices"
    ]
    assert tool_outputs, "the invoice tool never ran"
    expected = _common._query(
        "SELECT COUNT(*) AS n FROM Invoice WHERE CustomerId = 1", {}
    )[0]["n"]
    assert {o["total"] for o in tool_outputs} == {expected}
    assert result["messages"][-1].content == "Here are your invoices."


def test_supervisor_can_answer_small_talk_itself(scripted_model):
    model = scripted_model(AIMessage(content="You're welcome!"))
    result = build_supervisor(model).invoke(
        {"messages": [HumanMessage(content="thanks!")], "customer_id": 1}
    )
    assert result["messages"][-1].content == "You're welcome!"
    assert not any(isinstance(m, ToolMessage) for m in result["messages"])


# --- grounding rules in every prompt ----------------------------------------------

RULE_KEYWORDS = [
    "Tool-only responses",
    "Exact numbers",
    "Honest failures",
    "Scope boundaries",
    "No memory-based answers",
    "Truncation transparency",
]


@pytest.mark.parametrize(
    "prompt", [MUSIC_AGENT_PROMPT, INVOICE_AGENT_PROMPT, SUPERVISOR_PROMPT],
    ids=["music", "invoice", "supervisor"],
)
def test_every_prompt_carries_all_six_grounding_rules(prompt):
    assert GROUNDING_RULES in prompt
    for keyword in RULE_KEYWORDS:
        assert keyword in prompt


def test_memory_is_described_as_not_a_source_of_facts():
    assert "not a source of facts" in music_system_prompt("Music Preferences: rock")


def test_invoice_prompt_points_to_the_system_message_not_user_text():
    assert "SystemMessage" in INVOICE_AGENT_PROMPT
    assert "Never take a customer ID" in INVOICE_AGENT_PROMPT


def test_supervisor_prompt_states_the_routing_rules():
    assert "invoice_agent FIRST, then music_catalog_agent" in SUPERVISOR_PROMPT
    assert "call NO specialist" in SUPERVISOR_PROMPT
    assert "complete answer" in SUPERVISOR_PROMPT
    assert "may not use your own knowledge of music" in SUPERVISOR_PROMPT


def test_music_prompt_admits_albums_cannot_be_searched_by_title():
    assert "CANNOT search by album title" in MUSIC_AGENT_PROMPT
    assert "never as" in MUSIC_AGENT_PROMPT


def test_music_prompt_says_the_catalog_has_no_descriptions():
    assert "no\ndescriptions, reviews or stories" in MUSIC_AGENT_PROMPT


# --- the hand-built music ReAct loop ------------------------------------------------


def test_music_agent_is_a_two_node_loop():
    agent = build_music_agent(object.__new__(type("M", (), {"bind_tools": lambda self, t: self})))
    graph = agent.get_graph()
    assert {"assistant", "tools"} <= set(graph.nodes)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("tools", "assistant") in edges  # results go back to the assistant
    assert ("assistant", "tools") in edges  # tool calls go to the tool node
    assert agent.name == "music_catalog_agent"


def test_music_agent_loops_until_there_are_no_tool_calls(scripted_model):
    model = scripted_model(
        tool_call("get_albums_by_artist", {"artist_name": "AC/DC"}, "t1"),
        tool_call("get_tracks_by_artist", {"artist_name": "AC/DC"}, "t2"),
        AIMessage(content="AC/DC has 2 albums."),
    )
    result = build_music_agent(model).invoke(
        {"messages": [HumanMessage(content="AC/DC?")], "customer_id": 1}
    )
    assert len(model.calls) == 3  # two tool rounds, then the final answer
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in tool_messages] == ["get_albums_by_artist", "get_tracks_by_artist"]
    assert json.loads(tool_messages[0].content)["total"] == 2  # real database data
    assert result["messages"][-1].content == "AC/DC has 2 albums."


def test_music_agent_prepends_the_grounding_prompt_every_turn_without_storing_it(scripted_model):
    model = scripted_model(
        tool_call("get_albums_by_artist", {"artist_name": "AC/DC"}),
        AIMessage(content="Done."),
    )
    result = build_music_agent(model).invoke(
        {"messages": [HumanMessage(content="AC/DC?")], "customer_id": 1}
    )
    for call in model.calls:
        assert isinstance(call[0], SystemMessage) and GROUNDING_RULES in call[0].content
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])


# --- supervisor routing ---------------------------------------------------------------


def agents_called(model):
    """Names of the specialists the supervisor handed off to, in order."""
    names = []
    for call in model.calls:
        for m in call:
            if isinstance(m, ToolMessage) and m.name.startswith("transfer_to_") and m.name not in names:
                names.append(m.name)
    return names


def test_mixed_query_calls_invoice_first_then_music(scripted_model):
    model = scripted_model(
        tool_call("transfer_to_invoice_agent", call_id="h1"),
        tool_call("get_my_invoices", call_id="t1"),
        AIMessage(content="You have 7 invoices."),
        tool_call("transfer_to_music_catalog_agent", call_id="h2"),
        tool_call("get_songs_by_genre", {"genre": "Jazz"}, call_id="t2"),
        AIMessage(content="Here is some jazz."),
        AIMessage(content="7 invoices, and some jazz."),
    )
    result = build_supervisor(model).invoke(
        {"messages": [HumanMessage(content="my invoices and some jazz")], "customer_id": 1}
    )
    assert agents_called(model) == ["transfer_to_invoice_agent", "transfer_to_music_catalog_agent"]
    assert result["messages"][-1].content == "7 invoices, and some jazz."


def test_off_topic_query_is_rejected_without_calling_any_specialist(scripted_model):
    model = scripted_model(AIMessage(content="Sorry, I can only help with music and your account."))
    result = build_supervisor(model).invoke(
        {"messages": [HumanMessage(content="What's the weather?")], "customer_id": 1}
    )
    assert len(model.calls) == 1  # only the supervisor's own model call
    assert agents_called(model) == []
    assert result["messages"][-1].content.startswith("Sorry")
