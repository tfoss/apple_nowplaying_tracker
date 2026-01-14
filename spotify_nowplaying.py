#!/usr/bin/env python3
"""
Track currently playing Spotify across all devices for multiple users.

Uses the Spotify Web API to get currently playing track information
and stores it in the same database as Apple TV tracking.

Supports multiple Spotify accounts (e.g., family members) by allowing
multiple sets of credentials, each with their own cache file.

Requires:
- spotipy library: pip install spotipy
- Spotify API credentials (Client ID & Secret) for each user
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

# Scopes needed for playback information
SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"


def get_spotify_users():
    """
    Load Spotify user configurations from environment variables.

    Supports multiple users sharing one app with format:
    SPOTIFY_CLIENT_ID=xxx (shared app credentials)
    SPOTIFY_CLIENT_SECRET=yyy (shared app credentials)
    SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback (optional)
    SPOTIFY_USERS=Mom,Dad,Kid (comma-separated list of user names)

    Or legacy format with separate credentials per user:
    SPOTIFY_USER_1_NAME=Mom
    SPOTIFY_USER_1_CLIENT_ID=xxx
    SPOTIFY_USER_1_CLIENT_SECRET=yyy

    Returns list of user configs: [
        {
            "name": "Mom",
            "client_id": "xxx",
            "client_secret": "yyy",
            "redirect_uri": "http://127.0.0.1:8888/callback"
        },
        ...
    ]
    """
    users = []

    # New simplified format: one app, multiple users
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
    )
    users_list = os.environ.get("SPOTIFY_USERS", "").strip()

    if client_id and client_secret and users_list:
        # Parse comma-separated user names
        for user_name in users_list.split(","):
            user_name = user_name.strip()
            if user_name:
                users.append(
                    {
                        "name": user_name,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                    }
                )
        return users

    # Legacy format: separate credentials per user (backwards compatibility)
    i = 1
    while True:
        name_key = f"SPOTIFY_USER_{i}_NAME"
        client_id_key = f"SPOTIFY_USER_{i}_CLIENT_ID"
        client_secret_key = f"SPOTIFY_USER_{i}_CLIENT_SECRET"
        redirect_uri_key = f"SPOTIFY_USER_{i}_REDIRECT_URI"

        name = os.environ.get(name_key)
        client_id = os.environ.get(client_id_key)
        client_secret = os.environ.get(client_secret_key)

        # If we don't find a user config, we've reached the end
        if not name or not client_id or not client_secret:
            break

        redirect_uri = os.environ.get(
            redirect_uri_key, "http://127.0.0.1:8888/callback"
        )

        users.append(
            {
                "name": name,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }
        )

        i += 1

    if users:
        return users

    # Single user fallback (no SPOTIFY_USERS specified)
    if client_id and client_secret:
        users.append(
            {
                "name": "Default",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }
        )

    return users


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


def log_spotify_playback_for_user(user_config, con):
    """
    Get currently playing Spotify track for one user and log it to database.

    Args:
        user_config: Dict with keys 'name', 'client_id', 'client_secret', 'redirect_uri'
        con: DuckDB connection (shared across users)
    """
    user_name = user_config["name"]

    # Create unique cache file for this user
    cache_path = str(
        Path(__file__).parent / f".spotify_cache_{user_name.lower().replace(' ', '_')}"
    )

    # Initialize Spotify client for this user
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=user_config["client_id"],
            client_secret=user_config["client_secret"],
            redirect_uri=user_config["redirect_uri"],
            scope=SPOTIFY_SCOPES,
            cache_path=cache_path,
        )
    )

    # Get currently playing track
    try:
        current = sp.current_playback()
    except Exception as e:
        print(f"[{user_name}] Error getting Spotify playback: {e}")
        return

    if not current or not current.get("item"):
        print(f"[{user_name}] Nothing currently playing")
        return

    # Extract playback information
    item = current["item"]
    device = current.get("device", {})

    ts = datetime.now()
    # Clean device info
    raw_device_name = device.get("name", "Unknown Device")
    device_type = device.get("type", "Unknown")
    device_model = device_type  # Just the type, not "Spotify-Type"

    # For generic device names like "iPhone", append user name for disambiguation
    if raw_device_name in ("iPhone", "iPad"):
        device_name = f"{raw_device_name} ({user_name})"
    else:
        device_name = raw_device_name

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
        current.get("progress_ms", 0) / 1000.0 if current.get("progress_ms") else None
    )
    duration = item.get("duration_ms", 0) / 1000.0 if item.get("duration_ms") else None

    # Check last row to avoid repeated Paused spam
    # For Spotify, need to match on both device_name and user_name
    last = con.execute(
        f"""
        SELECT ts, state, title, artist, album
        FROM {TABLE_NAME}
        WHERE device_name = ? AND user_name = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        [device_name, user_name],
    ).fetchone()
    if last is not None:
        (last_ts, last_state, last_title, last_artist, last_album) = last

        same_track = (
            last_title == title and last_artist == artist and last_album == album
        )

        # If we are still Paused on the same track, skip logging
        if state == "Paused" and last_state == "Paused" and same_track:
            print(f"[{user_name}] Still paused on same track, skipping")
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
        user_name,  # Add user_name
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
            device_model,
            user_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        row,
    )

    # Human-readable debug line
    print(
        f"[{ts.isoformat()}] user={user_name} device={device.get('name')} state={state} title={title} artist={artist}"
    )


def main():
    """Main function - poll all configured Spotify users."""

    # Load user configurations
    users = get_spotify_users()

    if not users:
        print("ERROR: No Spotify users configured!")
        print("\nFor multiple users, set environment variables:")
        print("  SPOTIFY_USER_1_NAME=Mom")
        print("  SPOTIFY_USER_1_CLIENT_ID=xxx")
        print("  SPOTIFY_USER_1_CLIENT_SECRET=yyy")
        print("")
        print("  SPOTIFY_USER_2_NAME=Dad")
        print("  SPOTIFY_USER_2_CLIENT_ID=xxx")
        print("  SPOTIFY_USER_2_CLIENT_SECRET=yyy")
        print("\nOr for single user (backwards compatible):")
        print("  SPOTIFY_CLIENT_ID=xxx")
        print("  SPOTIFY_CLIENT_SECRET=yyy")
        print("\nGet credentials at: https://developer.spotify.com/dashboard")
        return

    print(
        f"Tracking {len(users)} Spotify user(s): {', '.join([u['name'] for u in users])}"
    )

    # Initialize database once
    con = init_duckdb()

    try:
        # Poll each user
        for user in users:
            log_spotify_playback_for_user(user, con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
