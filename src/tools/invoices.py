import json

from langchain_core.tools import tool

from src.tools._common import _json_errors, _not_found, _parse_id, _query


@tool
@_json_errors
def get_invoices_by_customer(customer_id: str) -> str:
    """Get all invoices for a customer, most recent first. customer_id is the
    CustomerId given as a number in a string."""
    cid = _parse_id(customer_id, "customer_id")
    rows = _query(
        """
        SELECT i.InvoiceId, i.InvoiceDate, i.BillingAddress, i.BillingCity,
               i.BillingState, i.BillingCountry, i.BillingPostalCode, i.Total
        FROM Invoice i
        WHERE i.CustomerId = :customer_id
        ORDER BY i.InvoiceDate DESC, i.InvoiceId DESC
        """,
        {"customer_id": cid},
    )
    if not rows:
        return _not_found(f"No invoices found for customer ID: {cid}", total=0)
    return json.dumps({"total": len(rows), "results": rows}, default=str)


@tool
@_json_errors
def get_purchased_tracks_by_customer(customer_id: str) -> str:
    """Get every track a customer has purchased, most expensive first. Each row is
    one purchased track (an invoice line), not a whole invoice. customer_id is the
    CustomerId given as a number in a string."""
    cid = _parse_id(customer_id, "customer_id")
    rows = _query(
        """
        SELECT t.TrackId, t.Name AS Track, ar.Name AS Artist, al.Title AS Album,
               g.Name AS Genre, il.UnitPrice, il.InvoiceId, i.InvoiceDate
        FROM InvoiceLine il
        JOIN Invoice i ON i.InvoiceId = il.InvoiceId
        JOIN Track t ON t.TrackId = il.TrackId
        JOIN Album al ON al.AlbumId = t.AlbumId
        JOIN Artist ar ON ar.ArtistId = al.ArtistId
        LEFT JOIN Genre g ON g.GenreId = t.GenreId
        WHERE i.CustomerId = :customer_id
        ORDER BY il.UnitPrice DESC, t.Name, il.InvoiceLineId
        """,
        {"customer_id": cid},
    )
    if not rows:
        return _not_found(f"No purchased tracks found for customer ID: {cid}", total=0)
    return json.dumps({"total": len(rows), "results": rows}, default=str)


@tool
@_json_errors
def get_support_rep_for_invoice(invoice_id: str) -> str:
    """Find the support rep (employee) assigned to the customer of a given invoice.
    invoice_id is the InvoiceId given as a number in a string."""
    iid = _parse_id(invoice_id, "invoice_id")
    rows = _query(
        """
        SELECT i.InvoiceId, e.EmployeeId, e.FirstName, e.LastName, e.Title,
               e.Email, e.Phone
        FROM Invoice i
        JOIN Customer c ON c.CustomerId = i.CustomerId
        LEFT JOIN Employee e ON e.EmployeeId = c.SupportRepId
        WHERE i.InvoiceId = :invoice_id
        """,
        {"invoice_id": iid},
    )
    if not rows:
        return json.dumps({"message": f"No invoice found with ID: {iid}"})
    if rows[0]["EmployeeId"] is None:
        return json.dumps({"message": f"No support rep is assigned for invoice ID: {iid}"})
    return json.dumps(rows[0], default=str)


@tool
@_json_errors
def get_invoice_line_items(invoice_id: str) -> str:
    """Get the detailed line items of one invoice (track, artist, unit price,
    quantity, line total). invoice_id is the InvoiceId given as a number in a string."""
    iid = _parse_id(invoice_id, "invoice_id")
    rows = _query(
        """
        SELECT il.InvoiceLineId, t.TrackId, t.Name AS Track, ar.Name AS Artist,
               al.Title AS Album, g.Name AS Genre, il.UnitPrice, il.Quantity,
               ROUND(il.UnitPrice * il.Quantity, 2) AS LineTotal
        FROM InvoiceLine il
        JOIN Track t ON t.TrackId = il.TrackId
        JOIN Album al ON al.AlbumId = t.AlbumId
        JOIN Artist ar ON ar.ArtistId = al.ArtistId
        LEFT JOIN Genre g ON g.GenreId = t.GenreId
        WHERE il.InvoiceId = :invoice_id
        ORDER BY il.InvoiceLineId
        """,
        {"invoice_id": iid},
    )
    if not rows:
        return _not_found(f"No line items found for invoice ID: {iid}", total=0)
    return json.dumps({"total": len(rows), "results": rows}, default=str)


INVOICE_TOOLS = [
    get_invoices_by_customer,
    get_purchased_tracks_by_customer,
    get_support_rep_for_invoice,
    get_invoice_line_items,
]
