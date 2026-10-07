import json

import pytest

from src.agents import invoice_tools as tools
from src.tools import _common


def call(tool, state, **args):
    return json.loads(tool.invoke({**args, "state": state}))


def invoice_of(customer_id):
    return _common._query(
        "SELECT InvoiceId FROM Invoice WHERE CustomerId = :c ORDER BY InvoiceId LIMIT 1",
        {"c": customer_id},
    )[0]["InvoiceId"]


def other_customer_with_invoices(not_id):
    return _common._query(
        "SELECT DISTINCT CustomerId FROM Invoice WHERE CustomerId != :c ORDER BY CustomerId LIMIT 1",
        {"c": not_id},
    )[0]["CustomerId"]


STATE = {"messages": [], "customer_id": 1}


def test_customer_id_is_not_part_of_any_tool_schema():
    for tool in tools.SCOPED_INVOICE_TOOLS:
        assert "customer_id" not in tool.args
        assert "state" not in tool.args  # injected by LangGraph, hidden from the model


def test_my_invoices_uses_the_customer_from_state():
    data = call(tools.get_my_invoices, STATE)
    assert data["total"] > 0
    assert all(r["InvoiceId"] for r in data["results"])
    ids = {r["InvoiceId"] for r in data["results"]}
    assert invoice_of(1) in ids


def test_other_customers_invoices_are_not_returned():
    other = other_customer_with_invoices(1)
    mine = {r["InvoiceId"] for r in call(tools.get_my_invoices, STATE)["results"]}
    theirs = {r["InvoiceId"] for r in call(tools.get_my_invoices, {"customer_id": other})["results"]}
    assert mine.isdisjoint(theirs)


def test_a_customer_id_smuggled_in_by_the_model_is_ignored():
    # The model has no customer_id argument; extras must not change whose data is returned.
    other = other_customer_with_invoices(1)
    expected = call(tools.get_my_invoices, STATE)
    smuggled = call(tools.get_my_invoices, STATE, customer_id=str(other))
    assert smuggled == expected


def test_purchased_tracks_come_from_the_state_customer():
    data = call(tools.get_my_purchased_tracks, STATE)
    assert data["total"] > 0


def test_line_items_of_my_invoice():
    data = call(tools.get_my_invoice_line_items, STATE, invoice_id=str(invoice_of(1)))
    assert data["total"] > 0


def test_line_items_of_someone_elses_invoice_look_like_a_missing_invoice():
    other_invoice = invoice_of(other_customer_with_invoices(1))
    foreign = call(tools.get_my_invoice_line_items, STATE, invoice_id=str(other_invoice))
    missing = call(tools.get_my_invoice_line_items, STATE, invoice_id="999999")
    assert foreign["results"] == [] and foreign["total"] == 0
    assert foreign["message"].replace(str(other_invoice), "N") == missing["message"].replace(
        "999999", "N"
    )


def test_support_rep_for_my_invoice():
    data = call(tools.get_support_rep_for_my_invoice, STATE, invoice_id=str(invoice_of(1)))
    assert data["InvoiceId"] == invoice_of(1)
    assert "EmployeeId" in data


def test_support_rep_for_someone_elses_invoice_is_refused_like_a_missing_one():
    other_invoice = invoice_of(other_customer_with_invoices(1))
    foreign = call(tools.get_support_rep_for_my_invoice, STATE, invoice_id=str(other_invoice))
    missing = call(tools.get_support_rep_for_my_invoice, STATE, invoice_id="999999")
    assert "EmployeeId" not in foreign
    assert foreign["message"].replace(str(other_invoice), "N") == missing["message"].replace(
        "999999", "N"
    )


@pytest.mark.parametrize("state", [{"messages": []}, {"messages": [], "customer_id": None}])
def test_unverified_state_returns_an_error_and_no_data(state):
    for tool, args in [
        (tools.get_my_invoices, {}),
        (tools.get_my_purchased_tracks, {}),
        (tools.get_my_invoice_line_items, {"invoice_id": "1"}),
        (tools.get_support_rep_for_my_invoice, {"invoice_id": "1"}),
    ]:
        data = call(tool, state, **args)
        assert "error" in data and "results" not in data


@pytest.mark.parametrize("bad", ["abc", "-1", "0", "1 OR 1=1"])
def test_bad_invoice_ids_return_an_error(bad):
    data = call(tools.get_my_invoice_line_items, STATE, invoice_id=bad)
    assert "error" in data
