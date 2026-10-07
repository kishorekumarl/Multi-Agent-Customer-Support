"""Customer identity verification (plain code, deliberately not an LLM tool)."""



from src.tools._common import _BadInput, _parse_id, _query
from src.utils.logger import get_logger
from src.utils.phone import normalize_phone

logger = get_logger(__name__)

def verify_customer(email: str, phone: str) -> int | None:
    """Return the CustomerId when `email` and `phone` both match one customer, else None.

    Email is matched case-insensitively and phone by digits only, so formatting
    differences don't matter. A customer with no phone on file can't be verified.
    """
    email = (email or "").strip()
    given_phone = normalize_phone(phone)
    if not email or not given_phone:
        return None

    rows = _query(
        "SELECT CustomerId, Phone FROM Customer WHERE LOWER(Email) = LOWER(:email)",
        {"email": email},
    )
    for row in rows:
        stored = normalize_phone(row["Phone"])
        if stored and stored == given_phone:
            return row["CustomerId"]
    logger.info("Identity verification failed")
    return None


def find_customer_id(identifier, identifier_type)->int| None:
    """Return the CustomerId when `identifier` matches one customer, else None.

    Email is matched case-insensitively and phone by digits only, so formatting
    differences don't matter. A customer with no phone on file can't be verified.
    """
        
    if not identifier or not identifier_type:
        return None
    identifier=identifier.strip() 
    if not identifier:
        return None 
    if identifier_type == "email":
        rows = _query(
            "SELECT CustomerId FROM Customer WHERE LOWER(Email) = LOWER(:email)",
            {"email": identifier},
        )
        if rows:
            return rows[0]["CustomerId"]
    elif identifier_type == "phone":
        given = normalize_phone(identifier)
        if not given:
            return None
        rows = _query(
            "SELECT CustomerId, Phone FROM Customer WHERE Phone IS NOT NULL",{})
        matches=[r["CustomerId"] for r in rows if normalize_phone(r["Phone"]) == given]
        if len(matches) == 1:
            return matches[0]
    elif identifier_type == "customer_id":
        try:
            cid = _parse_id(identifier, "CustomerId")
        except _BadInput:
            return None
        rows = _query("SELECT CustomerId FROM Customer WHERE CustomerId = :id", {"id": cid})
        if rows:
            return rows[0]["CustomerId"]
    logger.info("No matching customer found.")
    return None
