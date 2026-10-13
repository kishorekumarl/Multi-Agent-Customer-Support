import json
import re

from langchain_core.tools import tool
from src.tools._common import _json_errors, _like, _not_found, _parse_id, _query

_TRACK_FROM = """
    FROM Track t
    JOIN Album al ON al.AlbumId = t.AlbumId
    JOIN Artist ar ON ar.ArtistId = al.ArtistId
    LEFT JOIN Genre g ON g.GenreId = t.GenreId
"""
_TRACK_COLS = (
    "t.TrackId, t.Name AS Track, ar.Name AS Artist, "
    "al.Title AS Album, g.Name AS Genre, t.UnitPrice"
)
_ESCAPE = "ESCAPE '!'"
_ALBUM_LIMIT = 50


def _genre_name(genre: str) -> str:
    """Drop a trailing "album(s)", "song(s)", "track(s)" or "music" the model may add
    ("Rock albums" -> "Rock"), keeping the original text if nothing would be left."""
    stripped = re.sub(r"(?i)[\s,]+(albums?|songs?|tracks?|music)\s*$", "", (genre or "").strip())
    return stripped or genre


@tool
@_json_errors
def get_albums_by_artist(artist_name: str) -> str:
    """Find albums by artist name (fuzzy LIKE match, partial names work). Returns the
    total number of matching albums plus up to 50 of them."""
    params = {"artist_name": _like(artist_name)}
    where = f"WHERE ar.Name LIKE :artist_name {_ESCAPE}"
    total = _query(
        f"SELECT COUNT(*) AS n FROM Album al JOIN Artist ar ON ar.ArtistId = al.ArtistId {where}",
        params,
    )[0]["n"]
    if total == 0:
        return _not_found(f"No albums found for artist: {artist_name}", total=0)
    rows = _query(
        "SELECT al.AlbumId, al.Title AS Album, ar.Name AS Artist FROM Album al "
        f"JOIN Artist ar ON ar.ArtistId = al.ArtistId {where} "
        f"ORDER BY ar.Name, al.Title LIMIT {_ALBUM_LIMIT}",
        params,
    )
    return json.dumps({"total": total, "results": rows}, default=str)


@tool
@_json_errors
def get_tracks_by_artist(artist_name: str) -> str:
    """Find tracks by artist name (fuzzy LIKE match). Returns the total number of
    matching tracks plus a sample of up to 20."""
    params = {"artist_name": _like(artist_name)}
    where = f"WHERE ar.Name LIKE :artist_name {_ESCAPE}"
    total = _query(f"SELECT COUNT(*) AS n {_TRACK_FROM} {where}", params)[0]["n"]
    if total == 0:
        return _not_found(f"No tracks found for artist: {artist_name}", total=0)
    sample = _query(
        f"SELECT {_TRACK_COLS} {_TRACK_FROM} {where} ORDER BY ar.Name, t.Name LIMIT 20",
        params,
    )
    return json.dumps({"total": total, "results": sample}, default=str)


@tool
@_json_errors
def get_songs_by_genre(genre: str) -> str:
    """Browse songs in a genre. Pass only the genre name, e.g. "Rock" (not "rock albums").
    Returns "total" (all tracks in the genre) and up to 10 tracks, one per artist, as a
    sample covering a variety of artists; each track includes its Album. Results are the
    same on every call."""
    genre = _genre_name(genre)
    rows = _query(
        f"""
        SELECT * FROM (
            SELECT {_TRACK_COLS},
                   ROW_NUMBER() OVER (PARTITION BY ar.ArtistId ORDER BY t.TrackId) AS rn
            {_TRACK_FROM}
            WHERE g.Name LIKE :genre {_ESCAPE}
        )
        WHERE rn = 1
        ORDER BY Artist, TrackId
        LIMIT 10
        """,
        {"genre": _like(genre)},
    )
    if not rows:
        return _not_found(f"No songs found for genre: {genre}")
    for r in rows:
        r.pop("rn")
    total = _query(
        f"SELECT COUNT(*) AS n {_TRACK_FROM} WHERE g.Name LIKE :genre {_ESCAPE}",
        {"genre": _like(genre)},
    )[0]["n"]
    return json.dumps({"total": total, "results": rows}, default=str)


@tool
@_json_errors
def search_songs_by_title(title: str) -> str:
    """Search songs by title (fuzzy LIKE match). Returns "total" (all matches) and up to
    10 of them."""
    rows = _query(
        f"SELECT {_TRACK_COLS} {_TRACK_FROM} WHERE t.Name LIKE :title {_ESCAPE} "
        "ORDER BY t.Name, t.TrackId LIMIT 10",
        {"title": _like(title)},
    )
    if not rows:
        return _not_found(f"No songs found with title: {title}")
    total = _query(
        f"SELECT COUNT(*) AS n {_TRACK_FROM} WHERE t.Name LIKE :title {_ESCAPE}",
        {"title": _like(title)},
    )[0]["n"]
    return json.dumps({"total": total, "results": rows}, default=str)


@tool
@_json_errors
def get_track_details(track_id: str) -> str:
    """Get full details for one track by its TrackId, given as a number in a string
    (album, artist, genre, media type, composer, length, size, price)."""
    track_id_int = _parse_id(track_id, "track_id")
    rows = _query(
        """
        SELECT t.TrackId, t.Name AS Track, ar.Name AS Artist, al.Title AS Album,
               g.Name AS Genre, mt.Name AS MediaType, t.Composer,
               t.Milliseconds, t.Bytes, t.UnitPrice
        FROM Track t
        JOIN Album al ON al.AlbumId = t.AlbumId
        JOIN Artist ar ON ar.ArtistId = al.ArtistId
        JOIN MediaType mt ON mt.MediaTypeId = t.MediaTypeId
        LEFT JOIN Genre g ON g.GenreId = t.GenreId
        WHERE t.TrackId = :id
        """,
        {"id": track_id_int},
    )
    if not rows:
        return json.dumps({"message": f"No track found with ID: {track_id_int}"})
    return json.dumps(rows[0], default=str)


MUSIC_CATALOG_TOOLS = [
    get_albums_by_artist,
    get_tracks_by_artist,
    get_songs_by_genre,
    search_songs_by_title,
    get_track_details,
]
