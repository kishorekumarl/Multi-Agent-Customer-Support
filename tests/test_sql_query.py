import json

import pytest

from src.tools import sql_query


@pytest.fixture(autouse=True)
def patch_engine(monkeypatch, seeded_engine):
    """Point the tool at an isolated, per-test engine instead of the global cached one."""
    monkeypatch.setattr(sql_query, "get_engine", lambda: seeded_engine)


def test_basic_select():
    result = sql_query.run_sql_query.invoke({"sql": "SELECT Name FROM Artist LIMIT 1"})
    rows = json.loads(result)
    assert len(rows) == 1
    assert "Name" in rows[0]


def test_parameterized_query():
    result = sql_query.run_sql_query.invoke(
        {"sql": "SELECT Name FROM Artist WHERE ArtistId = :id", "params": {"id": 1}}
    )
    rows = json.loads(result)
    assert rows == [{"Name": "AC/DC"}]


def test_empty_results():
    result = sql_query.run_sql_query.invoke(
        {"sql": "SELECT Name FROM Artist WHERE ArtistId = :id", "params": {"id": -1}}
    )
    assert json.loads(result) == []


def test_valid_json_output():
    result = sql_query.run_sql_query.invoke({"sql": "SELECT Name FROM Artist LIMIT 3"})
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert all(isinstance(row, dict) for row in parsed)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE Artist",
        "DELETE FROM Artist",
        "UPDATE Artist SET Name = 'x'",
        "SELECT 1; DROP TABLE Artist",
        "/* hi */ INSERT INTO Artist (Name) VALUES ('x')",
    ],
)
def test_write_and_stacked_statements_rejected(sql, seeded_engine):
    data = json.loads(sql_query.run_sql_query.invoke({"sql": sql}))
    assert "error" in data
    count = seeded_engine.connect().exec_driver_sql("SELECT COUNT(*) FROM Artist").scalar()
    assert count > 0


def test_writes_blocked_by_connection_even_inside_cte(seeded_engine):
    sql = "WITH x AS (SELECT 1) DELETE FROM Artist"
    data = json.loads(sql_query.run_sql_query.invoke({"sql": sql}))
    assert "error" in data
    assert seeded_engine.connect().exec_driver_sql("SELECT COUNT(*) FROM Artist").scalar() > 0


def test_bad_column_returns_error_json_not_exception():
    data = json.loads(sql_query.run_sql_query.invoke({"sql": "SELECT Nope FROM Artist"}))
    assert "error" in data


def test_row_cap():
    rows = json.loads(sql_query.run_sql_query.invoke({"sql": "SELECT * FROM Track"}))
    assert len(rows) == sql_query.MAX_ROWS
