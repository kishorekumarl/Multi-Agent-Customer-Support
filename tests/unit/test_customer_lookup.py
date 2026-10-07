import pytest

from src.tools import _common
from src.tools.customer_lookup import find_customer_id, verify_customer


def a_customer():
    return _common._query(
        "SELECT CustomerId, Email, Phone FROM Customer WHERE Phone IS NOT NULL LIMIT 1", {}
    )[0]


def test_matching_email_and_phone_verifies():
    c = a_customer()
    assert verify_customer(c["Email"], c["Phone"]) == c["CustomerId"]


def test_email_case_and_phone_formatting_ignored():
    c = a_customer()
    digits = "".join(ch for ch in c["Phone"] if ch.isdigit() or ch == "+")
    assert verify_customer(f"  {c['Email'].upper()} ", digits) == c["CustomerId"]


def test_wrong_phone_fails():
    assert verify_customer(a_customer()["Email"], "000") is None


def test_unknown_email_fails():
    assert verify_customer("nobody@example.com", a_customer()["Phone"]) is None


def test_missing_phone_on_file_cannot_verify(seeded_engine):
    c = a_customer()
    with seeded_engine.begin() as conn:
        conn.exec_driver_sql("UPDATE Customer SET Phone = NULL")
    assert verify_customer(c["Email"], c["Phone"]) is None


@pytest.mark.parametrize("email, phone", [("", "123"), ("a@b.com", ""), ("a@b.com", "abc")])
def test_blank_inputs_return_none(email, phone):
    assert verify_customer(email, phone) is None


def test_injection_string_does_not_match():
    assert verify_customer("' OR '1'='1", "1") is None


# --- find_customer_id: look up by one identifier -------------------------------------


def test_find_by_customer_id():
    c = a_customer()
    assert find_customer_id(str(c["CustomerId"]), "customer_id") == c["CustomerId"]


def test_find_by_customer_id_with_spaces():
    c = a_customer()
    assert find_customer_id(f" {c['CustomerId']} ", "customer_id") == c["CustomerId"]


@pytest.mark.parametrize("bad", ["99999", "abc", "SW-12", "-1", "0", "3.5", "1 OR 1=1"])
def test_find_by_customer_id_miss_or_garbage_returns_none(bad):
    assert find_customer_id(bad, "customer_id") is None


def test_find_by_email_case_insensitive_and_trimmed():
    c = a_customer()
    assert find_customer_id(f"  {c['Email'].upper()} ", "email") == c["CustomerId"]


def test_find_by_unknown_email_returns_none():
    assert find_customer_id("nobody@example.com", "email") is None


def test_find_by_phone_exact_stored_format():
    c = a_customer()
    assert find_customer_id(c["Phone"], "phone") == c["CustomerId"]


def test_find_by_phone_different_formatting():
    c = a_customer()
    compact = "".join(ch for ch in c["Phone"] if ch.isdigit() or ch == "+")
    assert find_customer_id(compact, "phone") == c["CustomerId"]


def test_find_by_unknown_phone_returns_none():
    # Must not fall back to "the first customer with a phone".
    assert find_customer_id("+999 000 000 0000", "phone") is None


@pytest.mark.parametrize("bad", ["abc", "", "   ", "()-"])
def test_find_by_unusable_phone_returns_none(bad):
    assert find_customer_id(bad, "phone") is None


def test_find_by_phone_shared_by_two_customers_returns_none(seeded_engine):
    c = a_customer()
    with seeded_engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE Customer SET Phone = ? WHERE CustomerId != ?", (c["Phone"], c["CustomerId"])
        )
    assert find_customer_id(c["Phone"], "phone") is None


@pytest.mark.parametrize(
    "identifier, identifier_type",
    [("", "email"), (None, "email"), ("a@b.com", ""), ("a@b.com", None), ("1", "fax")],
)
def test_find_with_missing_input_or_unknown_type_returns_none(identifier, identifier_type):
    assert find_customer_id(identifier, identifier_type) is None


def test_find_injection_string_does_not_match():
    assert find_customer_id("' OR '1'='1", "email") is None


def test_find_by_phone_with_empty_stored_phone_does_not_match_unusable_input(seeded_engine):
    # A stored "" normalizes to "", so unusable input like "()-" must not match it.
    with seeded_engine.begin() as conn:
        conn.exec_driver_sql("UPDATE Customer SET Phone = '' WHERE CustomerId = 1")
    assert find_customer_id("()-", "phone") is None
