import logging

from src.utils.phone import normalize_phone


def test_international_format():
    logging.info("Testing international phone number normalization...")
    assert normalize_phone("+1 (555) 123-4567") == "+15551234567"


def test_domestic_digits():
    logging.info("test_domestic_digits.")
    assert normalize_phone("5551234567") == "5551234567"


def test_dashes():
    logging.info("test_dashes.")
    assert normalize_phone("555-123-4567") == "5551234567"


def test_empty_string():
    logging.info("test_empty_string.")
    assert normalize_phone("") == ""


def test_none_input():
    logging.info("test_none_input.")
    assert normalize_phone(None) == ""


def test_plus_prefix_preservation():
    logging.info("test_plus_prefix_preservation.")
    assert normalize_phone("+44 20 7946 0958").startswith("+")
    assert normalize_phone("+44 20 7946 0958") == "+442079460958"


def test_no_plus_prefix_not_added():
    logging.info("test_no_plus_prefix_not_added.")
    assert not normalize_phone("020 7946 0958").startswith("+")
