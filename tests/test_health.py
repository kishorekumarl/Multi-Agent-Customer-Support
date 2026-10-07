from src.database.health import REQUIRED_TABLES, check_database_health


def test_healthy_database(seeded_engine):
    result = check_database_health(seeded_engine)
    assert result["healthy"] is True
    assert result["missing_tables"] == []
    assert result["track_count"] == 3503
    assert result["error"] is None


def test_missing_tables_reported(empty_engine):
    result = check_database_health(empty_engine)
    assert result["healthy"] is False
    assert set(result["missing_tables"]) == set(REQUIRED_TABLES)
    assert result["track_count"] is None
