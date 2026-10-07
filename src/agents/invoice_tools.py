"""Invoice tools scoped to the verified customer.

The model never supplies a customer ID: each tool reads it from the graph state
(injected by LangGraph, hidden from the tool schema) and delegates to the
existing tools in src/tools/invoices.py. Invoice-ID tools also check that the
invoice belongs to that customer, and answer exactly as for a missing invoice.
"""

import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.tools import invoices
from src.tools._common import _BadInput, _json_errors, _not_found, _parse_id, _query


def _run(tool, **arguments) -> str:
    """Run the existing tool's own function. Skipping its logging/error wrapper means each
    call is logged once (by the scoped tool); the scoped tool turns errors into JSON too."""
    return tool.func.__wrapped__(**arguments)


def _verified_id(state: dict) -> int:
    cid = (state or {}).get("customer_id")
    if cid is None:
        raise _BadInput("The customer is not verified.")
    return int(cid)


def _owns_invoice(customer_id: int, invoice_id: int) -> bool:
    rows = _query("SELECT CustomerId FROM Invoice WHERE InvoiceId = :id", {"id": invoice_id})
    return bool(rows) and rows[0]["CustomerId"] == customer_id


@tool
@_json_errors
def get_my_invoices(state: Annotated[dict, InjectedState]) -> str:
    """Get all of the customer's invoices, most recent first."""
    return _run(invoices.get_invoices_by_customer, customer_id=str(_verified_id(state)))


@tool
@_json_errors
def get_my_purchased_tracks(state: Annotated[dict, InjectedState]) -> str:
    """Get every track the customer has purchased, most expensive first. Each row is
    one purchased track (an invoice line), not a whole invoice."""
    return _run(invoices.get_purchased_tracks_by_customer, customer_id=str(_verified_id(state)))


@tool
@_json_errors
def get_support_rep_for_my_invoice(invoice_id: str, state: Annotated[dict, InjectedState]) -> str:
    """Find the support rep (employee) assigned to the customer, for one of their invoices.
    invoice_id is the InvoiceId given as a number in a string."""
    cid = _verified_id(state)
    iid = _parse_id(invoice_id, "invoice_id")
    if not _owns_invoice(cid, iid):
        return json.dumps({"message": f"No invoice found with ID: {iid}"})
    return _run(invoices.get_support_rep_for_invoice, invoice_id=str(iid))


@tool
@_json_errors
def get_my_invoice_line_items(invoice_id: str, state: Annotated[dict, InjectedState]) -> str:
    """Get the detailed line items of one of the customer's invoices (track, artist,
    unit price, quantity, line total). invoice_id is the InvoiceId given as a number
    in a string."""
    cid = _verified_id(state)
    iid = _parse_id(invoice_id, "invoice_id")
    if not _owns_invoice(cid, iid):
        return _not_found(f"No line items found for invoice ID: {iid}", total=0)
    return _run(invoices.get_invoice_line_items, invoice_id=str(iid))


SCOPED_INVOICE_TOOLS = [
    get_my_invoices,
    get_my_purchased_tracks,
    get_support_rep_for_my_invoice,
    get_my_invoice_line_items,
]
