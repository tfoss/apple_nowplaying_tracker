#!/usr/bin/env python3
"""
Track currently playing Spotify across all devices.

Uses the Spotify Web API to get currently playing track information
and stores it in the same database as Apple TV tracking.

Requires:
- spotipy library: pip install spotipy
- Spotify API credentials (Client ID & Secret)
- User authentication (uses OAuth with local redirect)
"""

import os
from datetime import datetime
from pathlib import Path

import duckdb

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "WARNING: python-dotenv not installed. Install with: pip install python-dotenv"
    )
    print("Will try to use environment variables directly")

# Import spotipy - will need to be installed
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("ERROR: spotipy not installed. Install with: pip install spotipy")
    exit(1)

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"

# Spotify API credentials - load from .env or environment variables
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"
)

# Scopes needed for playback information
SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"


def init_duckdb():
    """Create DB and table if they don't already exist."""
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            ts TIMESTAMP,
            device_name TEXT,
            address TEXT,
            device_model TEXT,
            state TEXT,
            app TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            series_name TEXT,
            season INTEGER,
            episode INTEGER,
            media_type TEXT,
            position DOUBLE,
            duration DOUBLE
        )
    """)

    # Add device_model column if it doesn't exist (migration for existing tables)
    try:
        con.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN device_model TEXT")
    except:
        pass

    return con


def get_last_row(con, device_name):
    """Fetch the most recent row for this device, or None."""
    result = con.execute(
        f"""
        SELECT
            ts,
            state,
            title,
            artist,
            album
        FROM {TABLE_NAME}
        WHERE device_name = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        [device_name],
    ).fetchone()
    return result


def log_spotify_playback():
    """Get currently playing Spotify track and log it to database."""

    # Check for credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("ERROR: Spotify credentials not set!")
        print("Set environment variables:")
        print("  export SPOTIFY_CLIENT_ID='your_client_id'")
        print("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
        print("\nGet credentials at: https://developer.spotify.com/dashboard")
        return

    # Initialize Spotify client
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SPOTIFY_SCOPES,
            cache_path=str(Path(__file__).parent / ".spotify_cache"),
        )
    )

    # Get currently playing track
    try:
        current = sp.current_playback()
    except Exception as e:
        print(f"Error getting Spotify playback: {e}")
        return

    if not current or not current.get("item"):
        print("Nothing currently playing on Spotify")
        return

    con = init_duckdb()

    try:
        # Extract playback information
        item = current["item"]
        device = current.get("device", {})

        ts = datetime.now()
        device_name = f"Spotify: {device.get('name', 'Unknown Device')}"
        device_type = device.get("type", "Unknown")
        device_model = f"Spotify-{device_type}"

        # Map Spotify states to our format
        is_playing = current.get("is_playing", False)
        state = "Playing" if is_playing else "Paused"

        app = "Spotify"
        title = item.get("name")

        # Get artists (can be multiple)
        artists = item.get("artists", [])
        artist = ", ".join([a.get("name") for a in artists]) if artists else None

        album_obj = item.get("album", {})
        album = album_obj.get("name")

        # Spotify doesn't have series info
        series_name = None
        season = None
        episode = None

        # Always Music for Spotify
        media_type = "Music"

        # Position and duration in seconds
        position = (
            current.get("progress_ms", 0) / 1000.0
            if current.get("progress_ms")
            else None
        )
        duration = (
            item.get("duration_ms", 0) / 1000.0 if item.get("duration_ms") else None
        )

        # Check last row to avoid repeated Paused spam
        last = get_last_row(con, device_name)
        if last is not None:
            (last_ts, last_state, last_title, last_artist, last_album) = last

            same_track = (
                last_title == title and last_artist == artist and last_album == album
            )

            # If we are still Paused on the same track, skip logging
            if state == "Paused" and last_state == "Paused" and same_track:
                print(f"[{device_name}] Still paused on same track, skipping")
                return

        # Build row and insert
        row = (
            ts,
            device_name,
            None,  # address (not applicable for Spotify)
            state,
            app,
            title,
            artist,
            album,
            series_name,
            season,
            episode,
            media_type,
            position,
            duration,
            device_model,
        )

        con.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                ts,
                device_name,
                address,
                state,
                app,
                title,
                artist,
                album,
                series_name,
                season,
                episode,
                media_type,
                position,
                duration,
                device_model
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

        # Human-readable debug line
        print(
            f"[{ts.isoformat()}] device={device_name} state={state} app={app} title={title} artist={artist}"
        )

    finally:
        con.close()


def main():
    """Main function."""
    log_spotify_playback()


if __name__ == "__main__":
    main()
