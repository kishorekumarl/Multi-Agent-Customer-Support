import json
import logging

import pytest

from src.agents import invoice_tools
from src.config.settings import settings
from src.tools import _common, invoices, music_catalog


@pytest.fixture(autouse=True)
def tool_logs(caplog):
    caplog.set_level(logging.INFO, logger="src.tools._common")
    return caplog


def lines(caplog, kind):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(kind)]


def test_request_and_response_are_logged_with_the_json_body(tool_logs):
    music_catalog.get_albums_by_artist.invoke({"artist_name": "AC/DC"})
    (request,) = lines(tool_logs, "TOOL_REQUEST")
    (response,) = lines(tool_logs, "TOOL_RESPONSE")
    assert "get_albums_by_artist" in request and json.dumps({"artist_name": "AC/DC"}) in request
    assert "Let There Be Rock" in response  # the JSON the model received
    assert " ms," in response and " chars)" in response


@pytest.mark.parametrize(
    "tool, args",
    [
        (music_catalog.get_tracks_by_artist, {"artist_name": "AC/DC"}),
        (music_catalog.get_songs_by_genre, {"genre": "Rock"}),
        (music_catalog.search_songs_by_title, {"title": "love"}),
        (music_catalog.get_track_details, {"track_id": "1"}),
        (invoices.get_invoices_by_customer, {"customer_id": "1"}),
        (invoices.get_invoice_line_items, {"invoice_id": "98"}),
    ],
)
def test_every_tool_logs_without_a_logger_of_its_own(tool_logs, tool, args):
    tool.invoke(args)
    assert len(lines(tool_logs, "TOOL_REQUEST")) == 1
    assert len(lines(tool_logs, "TOOL_RESPONSE")) == 1


def test_the_injected_state_is_not_logged_only_the_customer_id(tool_logs):
    state = {"messages": ["SECRET CONVERSATION TEXT"], "customer_id": 1}
    invoice_tools.get_my_invoices.invoke({"state": state})
    (request,) = lines(tool_logs, "TOOL_REQUEST")
    assert "SECRET CONVERSATION TEXT" not in request and "messages" not in request
    assert '"customer_id": 1' in request


def test_long_responses_are_truncated(tool_logs):
    music_catalog.get_albums_by_artist.invoke({"artist_name": "a"})  # large result set
    (response,) = lines(tool_logs, "TOOL_RESPONSE")
    assert "[truncated," in response
    assert len(response) < _common._PAYLOAD_LIMIT + 200


def test_failures_are_logged_and_the_error_json_is_returned(tool_logs):
    result = json.loads(invoices.get_invoice_line_items.invoke({"invoice_id": "abc"}))
    assert "error" in result
    (response,) = lines(tool_logs, "TOOL_RESPONSE")
    assert "error" in response


def test_payload_logging_can_be_switched_off(tool_logs, monkeypatch):
    monkeypatch.setattr(settings, "log_tool_payloads", False)
    music_catalog.get_albums_by_artist.invoke({"artist_name": "AC/DC"})
    (response,) = lines(tool_logs, "TOOL_RESPONSE")
    assert "Let There Be Rock" not in response  # no body, no customer data
    assert '"total": 2' in response and "2 rows" in response  # just the shape
