import json

import pytest

from src.tools import _common, invoices


def call(tool, **kwargs):
    return json.loads(tool.invoke(kwargs))


def a_customer_with_invoices():
    return _common._query(
        "SELECT CustomerId, COUNT(*) AS n FROM Invoice GROUP BY CustomerId "
        "ORDER BY n DESC, CustomerId LIMIT 1",
        {},
    )[0]


# --- get_invoices_by_customer -----------------------------------------------


def test_invoices_sorted_most_recent_first():
    cust = a_customer_with_invoices()
    data = call(invoices.get_invoices_by_customer, customer_id=str(cust["CustomerId"]))
    assert data["total"] == cust["n"] == len(data["results"])
    keys = [(r["InvoiceDate"], r["InvoiceId"]) for r in data["results"]]
    assert keys == sorted(keys, reverse=True)


def test_invoices_only_for_requested_customer():
    cust = a_customer_with_invoices()
    data = call(invoices.get_invoices_by_customer, customer_id=str(cust["CustomerId"]))
    ids = {r["InvoiceId"] for r in data["results"]}
    owned = {
        r["InvoiceId"]
        for r in _common._query(
            "SELECT InvoiceId FROM Invoice WHERE CustomerId = :c", {"c": cust["CustomerId"]}
        )
    }
    assert ids == owned


def test_invoices_unknown_customer_returns_message():
    data = call(invoices.get_invoices_by_customer, customer_id="99999")
    assert data["message"] == "No invoices found for customer ID: 99999"
    assert data["results"] == []
    assert data["total"] == 0


# --- get_purchased_tracks_by_customer ---------------------------------------


def test_purchased_tracks_sorted_by_price_highest_first():
    cust = a_customer_with_invoices()
    data = call(invoices.get_purchased_tracks_by_customer, customer_id=str(cust["CustomerId"]))
    prices = [r["UnitPrice"] for r in data["results"]]
    assert prices == sorted(prices, reverse=True)
    assert len(set(prices)) > 1  # the sort is actually exercised


def test_purchased_tracks_one_row_per_invoice_line():
    cust = a_customer_with_invoices()
    data = call(invoices.get_purchased_tracks_by_customer, customer_id=str(cust["CustomerId"]))
    expected = _common._query(
        "SELECT COUNT(*) AS n FROM InvoiceLine il JOIN Invoice i ON i.InvoiceId = il.InvoiceId "
        "WHERE i.CustomerId = :c",
        {"c": cust["CustomerId"]},
    )[0]["n"]
    assert data["total"] == len(data["results"]) == expected
    assert all("Track" in r and "Artist" in r for r in data["results"])


def test_purchased_tracks_unknown_customer_returns_message():
    data = call(invoices.get_purchased_tracks_by_customer, customer_id="99999")
    assert data["message"] == "No purchased tracks found for customer ID: 99999"
    assert data["results"] == []


# --- get_support_rep_for_invoice --------------------------------------------


def test_support_rep_matches_customers_rep():
    expected = _common._query(
        "SELECT i.InvoiceId, e.FirstName, e.LastName, e.EmployeeId "
        "FROM Invoice i JOIN Customer c ON c.CustomerId = i.CustomerId "
        "JOIN Employee e ON e.EmployeeId = c.SupportRepId LIMIT 1",
        {},
    )[0]
    data = call(invoices.get_support_rep_for_invoice, invoice_id=str(expected["InvoiceId"]))
    assert data["EmployeeId"] == expected["EmployeeId"]
    assert data["FirstName"] == expected["FirstName"]
    assert data["LastName"] == expected["LastName"]
    for key in ("Title", "Email", "Phone"):
        assert key in data


def test_support_rep_unknown_invoice_returns_message():
    data = call(invoices.get_support_rep_for_invoice, invoice_id="99999")
    assert data == {"message": "No invoice found with ID: 99999"}


def test_support_rep_missing_rep_returns_message(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.exec_driver_sql("UPDATE Customer SET SupportRepId = NULL")
    invoice_id = _common._query("SELECT InvoiceId FROM Invoice LIMIT 1", {})[0]["InvoiceId"]
    data = call(invoices.get_support_rep_for_invoice, invoice_id=str(invoice_id))
    assert data == {"message": f"No support rep is assigned for invoice ID: {invoice_id}"}


# --- get_invoice_line_items -------------------------------------------------


def test_line_items_belong_to_invoice_and_have_totals():
    invoice_id = _common._query(
        "SELECT InvoiceId FROM InvoiceLine GROUP BY InvoiceId HAVING COUNT(*) > 1 "
        "ORDER BY InvoiceId LIMIT 1",
        {},
    )[0]["InvoiceId"]
    data = call(invoices.get_invoice_line_items, invoice_id=str(invoice_id))
    expected = _common._query(
        "SELECT InvoiceLineId FROM InvoiceLine WHERE InvoiceId = :i ORDER BY InvoiceLineId",
        {"i": invoice_id},
    )
    assert [r["InvoiceLineId"] for r in data["results"]] == [r["InvoiceLineId"] for r in expected]
    assert data["total"] == len(expected)
    for r in data["results"]:
        assert r["LineTotal"] == pytest.approx(r["UnitPrice"] * r["Quantity"])
        for key in ("Track", "Artist", "Album", "Quantity"):
            assert key in r


def test_line_items_unknown_invoice_returns_message():
    data = call(invoices.get_invoice_line_items, invoice_id="99999")
    assert data["message"] == "No line items found for invoice ID: 99999"
    assert data["results"] == []


# --- string parameters and validation ---------------------------------------


ID_TOOLS = [
    (invoices.get_invoices_by_customer, "customer_id"),
    (invoices.get_purchased_tracks_by_customer, "customer_id"),
    (invoices.get_support_rep_for_invoice, "invoice_id"),
    (invoices.get_invoice_line_items, "invoice_id"),
]


@pytest.mark.parametrize("tool, arg", ID_TOOLS)
@pytest.mark.parametrize("bad", ["abc", "1.5", "", "  ", "-3", "0", "1 OR 1=1"])
def test_non_numeric_ids_return_clear_error(tool, arg, bad):
    data = call(tool, **{arg: bad})
    assert data["error"].startswith(f"{arg} must be a positive whole number")
    assert "results" not in data


@pytest.mark.parametrize("tool, arg", ID_TOOLS)
def test_padded_string_ids_are_accepted(tool, arg):
    data = call(tool, **{arg: " 1 "})
    assert "error" not in data


def test_database_failure_returns_error_json_instead_of_raising(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(_common, "get_engine", boom)
    data = call(invoices.get_invoices_by_customer, customer_id="1")
    assert "error" in data
    assert "db down" not in data["error"]  # internal details are not leaked


# --- module wiring ----------------------------------------------------------


def test_tool_list_exports_all_four_tools():
    assert {t.name for t in invoices.INVOICE_TOOLS} == {
        "get_invoices_by_customer",
        "get_purchased_tracks_by_customer",
        "get_support_rep_for_invoice",
        "get_invoice_line_items",
    }
