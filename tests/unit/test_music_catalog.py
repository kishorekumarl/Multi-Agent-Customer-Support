import json

import pytest

from src.tools import _common, music_catalog


def call(tool, **kwargs):
    return json.loads(tool.invoke(kwargs))


# --- get_albums_by_artist ---------------------------------------------------


def test_albums_by_artist_exact():
    data = call(music_catalog.get_albums_by_artist, artist_name="AC/DC")
    titles = {r["Album"] for r in data["results"]}
    assert "Let There Be Rock" in titles
    assert all(r["Artist"] == "AC/DC" for r in data["results"])

def test_albums_by_artist_total_matches_the_results_returned():
    data = call(music_catalog.get_albums_by_artist, artist_name="AC/DC")
    assert {r["Artist"] for r in data["results"]} == {"AC/DC"}
    assert data["total"] == len(data["results"]) == 2


def test_albums_by_artist_fuzzy_and_case_insensitive():
    data = call(music_catalog.get_albums_by_artist, artist_name="ac/d")
    assert data["results"]
    assert all("AC/DC" == r["Artist"] for r in data["results"])


def test_albums_by_artist_no_match_returns_message():
    data = call(music_catalog.get_albums_by_artist, artist_name="XYZ")
    assert data["message"] == "No albums found for artist: XYZ"
    assert data["results"] == []
    assert data["total"] == 0


def test_albums_by_artist_capped_at_50_with_full_total():
    data = call(music_catalog.get_albums_by_artist, artist_name="a")
    assert data["total"] > 50
    assert len(data["results"]) == 50


def test_albums_by_artist_total_matches_results_when_small():
    data = call(music_catalog.get_albums_by_artist, artist_name="AC/DC")
    assert data["total"] == len(data["results"]) > 0


# --- get_tracks_by_artist ---------------------------------------------------


def test_tracks_by_artist_small_catalog_returns_everything():
    data = call(music_catalog.get_tracks_by_artist, artist_name="AC/DC")
    assert data["total"] > 0
    assert len(data["results"]) == data["total"]  # fewer than 20 tracks
    assert all(r["Artist"] == "AC/DC" for r in data["results"])


def test_tracks_by_artist_sample_capped_at_20_but_total_is_full_count():
    data = call(music_catalog.get_tracks_by_artist, artist_name="Iron Maiden")
    assert data["total"] > 20
    assert len(data["results"]) == 20


def test_tracks_by_artist_no_match_returns_message():
    data = call(music_catalog.get_tracks_by_artist, artist_name="XYZ")
    assert data["message"] == "No tracks found for artist: XYZ"
    assert data["total"] == 0
    assert data["results"] == []


# --- get_songs_by_genre -----------------------------------------------------


def test_songs_by_genre_max_10_one_track_per_artist():
    data = call(music_catalog.get_songs_by_genre, genre="Rock")
    results = data["results"]
    assert len(results) == 10
    artists = [r["Artist"] for r in results]
    assert len(set(artists)) == len(artists)  # diversity: no artist repeated
    assert all("Rock" in r["Genre"] for r in results)


def test_songs_by_genre_is_deterministic():
    first = music_catalog.get_songs_by_genre.invoke({"genre": "Rock"})
    assert all(music_catalog.get_songs_by_genre.invoke({"genre": "Rock"}) == first for _ in range(3))


def test_songs_by_genre_picks_lowest_track_id_per_artist():
    data = call(music_catalog.get_songs_by_genre, genre="Rock")
    for row in data["results"]:
        lowest = _common._query(
            "SELECT MIN(t.TrackId) AS m FROM Track t "
            "JOIN Album al ON al.AlbumId = t.AlbumId "
            "JOIN Artist ar ON ar.ArtistId = al.ArtistId "
            "JOIN Genre g ON g.GenreId = t.GenreId "
            "WHERE ar.Name = :artist AND g.Name LIKE '%Rock%'",
            {"artist": row["Artist"]},
        )[0]["m"]
        assert row["TrackId"] == lowest


def test_songs_by_genre_hides_internal_columns():
    data = call(music_catalog.get_songs_by_genre, genre="Rock")
    assert all("rn" not in r for r in data["results"])


def test_songs_by_genre_fewer_artists_than_limit():
    # A genre with only a handful of artists still yields one row per artist.
    data = call(music_catalog.get_songs_by_genre, genre="Opera")
    artists = [r["Artist"] for r in data["results"]]
    assert 0 < len(artists) <= 10
    assert len(set(artists)) == len(artists)


@pytest.mark.parametrize("phrase", ["Rock albums", "rock album", "Rock songs", "rock music", "Rock, albums"])
def test_songs_by_genre_ignores_trailing_album_or_song_words(phrase):
    data = call(music_catalog.get_songs_by_genre, genre=phrase)
    assert data["total"] == call(music_catalog.get_songs_by_genre, genre="Rock")["total"]
    assert data["results"]


def test_songs_by_genre_only_a_filler_word_is_not_stripped_to_nothing():
    assert call(music_catalog.get_songs_by_genre, genre="albums")["results"] == []


def test_songs_by_genre_no_match_returns_message():
    data = call(music_catalog.get_songs_by_genre, genre="XYZ")
    assert data["message"] == "No songs found for genre: XYZ"
    assert data["results"] == []


# --- search_songs_by_title --------------------------------------------------


def test_search_songs_by_title_fuzzy_capped_at_10():
    data = call(music_catalog.search_songs_by_title, title="love")
    assert 0 < len(data["results"]) <= 10
    assert all("love" in r["Track"].lower() for r in data["results"])


def test_search_songs_by_title_no_match_returns_message():
    data = call(music_catalog.search_songs_by_title, title="XYZ")
    assert data["message"] == "No songs found with title: XYZ"
    assert data["results"] == []


def test_search_songs_by_title_order_is_stable():
    data = call(music_catalog.search_songs_by_title, title="a")
    keys = [(r["Track"], r["TrackId"]) for r in data["results"]]
    assert keys == sorted(keys)


# --- get_track_details ------------------------------------------------------


def test_track_details_full_record():
    data = call(music_catalog.get_track_details, track_id="1")
    assert data["TrackId"] == 1
    assert data["Artist"] == "AC/DC"
    for key in ("Track", "Album", "Genre", "MediaType", "Composer", "Milliseconds", "Bytes", "UnitPrice"):
        assert key in data


def test_track_details_accepts_padded_string_id():
    assert call(music_catalog.get_track_details, track_id=" 1 ")["TrackId"] == 1


def test_track_details_unknown_id_returns_message():
    data = call(music_catalog.get_track_details, track_id="999999")
    assert data == {"message": "No track found with ID: 999999"}


@pytest.mark.parametrize("bad", ["abc", "1.5", "", "  ", "-3", "0", "1; DROP TABLE Track"])
def test_track_details_non_numeric_id_returns_error(bad):
    data = call(music_catalog.get_track_details, track_id=bad)
    assert "must be a positive whole number" in data["error"]


# --- input safety and failure handling --------------------------------------


@pytest.mark.parametrize(
    "tool, arg",
    [
        (music_catalog.get_albums_by_artist, "artist_name"),
        (music_catalog.get_tracks_by_artist, "artist_name"),
        (music_catalog.get_songs_by_genre, "genre"),
        (music_catalog.search_songs_by_title, "title"),
    ],
)
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_input_returns_error(tool, arg, blank):
    data = call(tool, **{arg: blank})
    assert "error" in data
    assert "results" not in data


def test_like_wildcards_in_input_are_literal():
    # Unescaped, "_" would match any character and "A_/DC" would find AC/DC.
    assert call(music_catalog.get_albums_by_artist, artist_name="A_/DC")["results"] == []
    # Unescaped, "%" would match every artist.
    assert call(music_catalog.get_albums_by_artist, artist_name="%")["results"] == []
    # Some track titles genuinely contain "%"; only those may match, not the whole catalog.
    results = call(music_catalog.search_songs_by_title, title="%")["results"]
    assert all("%" in r["Track"] for r in results)
    assert call(music_catalog.get_songs_by_genre, genre="%")["results"] == []
    assert call(music_catalog.get_tracks_by_artist, artist_name="%")["total"] == 0


def test_database_failure_returns_error_json_instead_of_raising(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(_common, "get_engine", boom)
    data = call(music_catalog.search_songs_by_title, title="love")
    assert "error" in data
    assert "db down" not in data["error"]  # internal details are not leaked


# --- module wiring ----------------------------------------------------------


def test_tool_list_exports_all_five_tools():
    assert len(music_catalog.MUSIC_CATALOG_TOOLS) == 5
    names = {t.name for t in music_catalog.MUSIC_CATALOG_TOOLS}
    assert names == {
        "get_albums_by_artist",
        "get_tracks_by_artist",
        "get_songs_by_genre",
        "search_songs_by_title",
        "get_track_details",
    }


def test_songs_by_genre_reports_the_total_beyond_the_sample():
    data = call(music_catalog.get_songs_by_genre, genre="Rock")
    assert len(data["results"]) == 10
    assert data["total"] > len(data["results"])


def test_search_songs_by_title_reports_the_total_beyond_the_cap():
    data = call(music_catalog.search_songs_by_title, title="love")
    assert len(data["results"]) == 10
    assert data["total"] > 10
