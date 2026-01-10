#!/usr/bin/env python3
"""
Analyze Apple TV usage data and create viewing/listening sessions.

Groups consecutive plays of the same media into sessions with:
- Start/end timestamps
- Total watch/listen duration
- Completion percentage
- Device used
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"

# Maximum gap between entries to consider them part of the same session
SESSION_GAP_MINUTES = 10

# Minimum watch time in seconds to include a session (filters out brief pauses/skips)
MIN_WATCH_TIME_SECONDS = 30


def create_sessions_table(con):
    """
    Create a persistent table that groups consecutive plays into sessions.

    A session is defined as consecutive entries for the same media on the same device
    where the time gap between entries is less than SESSION_GAP_MINUTES.

    This replaces the entire table each time to ensure it's up-to-date.
    """

    # Create a sessions table with start/end times and duration
    # Split into multiple CTEs to avoid nested window functions
    # Drop both view and table if they exist (handles migration from view to table)
    try:
        con.execute("DROP VIEW IF EXISTS viewing_sessions")
    except:
        pass
    try:
        con.execute("DROP TABLE IF EXISTS viewing_sessions")
    except:
        pass
    con.execute(f"""
        CREATE TABLE viewing_sessions AS
        WITH ordered_plays AS (
            SELECT
                ts,
                device_name,
                title,
                artist,
                album,
                series_name,
                season,
                episode,
                media_type,
                position,
                duration,
                state,
                -- Calculate time difference from previous row for same media/device
                LAG(ts) OVER (
                    PARTITION BY device_name, title, series_name, season, episode, artist, album
                    ORDER BY ts
                ) as prev_ts
            FROM {TABLE_NAME}
            WHERE state IN ('Playing', 'Paused')
        ),
        with_session_breaks AS (
            SELECT
                *,
                -- Mark session breaks when gap > SESSION_GAP_MINUTES
                CASE
                    WHEN prev_ts IS NULL
                    OR EXTRACT(EPOCH FROM (ts - prev_ts)) > {SESSION_GAP_MINUTES * 60}
                    THEN 1
                    ELSE 0
                END as is_new_session
            FROM ordered_plays
        ),
        with_session_ids AS (
            SELECT
                *,
                -- Create session IDs by summing up the session breaks
                SUM(is_new_session) OVER (
                    PARTITION BY device_name, title, series_name, season, episode, artist, album
                    ORDER BY ts
                ) as session_id
            FROM with_session_breaks
        )
        SELECT
            device_name,
            title,
            artist,
            album,
            series_name,
            season,
            episode,
            media_type,
            MIN(ts) as session_start,
            MAX(ts) as session_end,
            MAX(position) as max_position_reached,
            MAX(duration) as media_duration,
            -- Calculate watch time based on position progress
            CASE
                WHEN MAX(position) IS NOT NULL AND MIN(position) IS NOT NULL
                THEN MAX(position) - MIN(position)
                ELSE EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts)))
            END as watch_time_seconds,
            -- Calculate completion percentage
            CASE
                WHEN MAX(duration) > 0 AND MAX(position) IS NOT NULL
                THEN ROUND((MAX(position) / MAX(duration)) * 100, 1)
                ELSE NULL
            END as completion_pct,
            COUNT(*) as num_entries,
            session_id
        FROM with_session_ids
        GROUP BY
            device_name,
            title,
            artist,
            album,
            series_name,
            season,
            episode,
            media_type,
            session_id
        HAVING COUNT(*) >= 1
            AND watch_time_seconds >= {MIN_WATCH_TIME_SECONDS}
        ORDER BY session_start DESC
    """)


def print_recent_sessions(con, limit=20):
    """Print the most recent viewing/listening sessions."""
    print(f"\n{'=' * 100}")
    print(f"RECENT VIEWING/LISTENING SESSIONS (Last {limit})")
    print(f"{'=' * 100}\n")

    result = con.sql(f"""
        SELECT
            session_start,
            session_end,
            device_name,
            CASE
                WHEN series_name IS NOT NULL THEN series_name || ' S' || season || 'E' || episode
                WHEN artist IS NOT NULL THEN artist || ' - ' || title
                ELSE title
            END as display_title,
            media_type,
            ROUND(watch_time_seconds / 60.0, 1) as watch_minutes,
            completion_pct,
            num_entries
        FROM viewing_sessions
        ORDER BY session_start DESC
        LIMIT {limit}
    """)
    print(result)


def print_session_stats(con):
    """Print aggregate statistics about viewing sessions."""
    print(f"\n{'=' * 100}")
    print("SESSION STATISTICS")
    print(f"{'=' * 100}\n")

    # Total watch time by device
    print("Total Watch Time by Device (hours):")
    result = con.sql("""
        SELECT
            device_name,
            ROUND(SUM(watch_time_seconds) / 3600.0, 2) as total_hours,
            COUNT(*) as num_sessions
        FROM viewing_sessions
        GROUP BY device_name
        ORDER BY total_hours DESC
    """)
    print(result)

    # Total watch time by media type
    print("\n\nTotal Watch Time by Media Type (hours):")
    result = con.sql("""
        SELECT
            media_type,
            ROUND(SUM(watch_time_seconds) / 3600.0, 2) as total_hours,
            COUNT(*) as num_sessions
        FROM viewing_sessions
        WHERE media_type IS NOT NULL
        GROUP BY media_type
        ORDER BY total_hours DESC
    """)
    print(result)

    # Most watched shows/movies
    print("\n\nMost Watched TV Shows (by total time):")
    result = con.sql("""
        SELECT
            series_name,
            COUNT(DISTINCT season || '-' || episode) as num_episodes,
            ROUND(SUM(watch_time_seconds) / 3600.0, 2) as total_hours,
            COUNT(*) as num_sessions
        FROM viewing_sessions
        WHERE series_name IS NOT NULL
        GROUP BY series_name
        ORDER BY total_hours DESC
        LIMIT 10
    """)
    print(result)

    # Most played music
    print("\n\nMost Played Songs (by session count):")
    result = con.sql("""
        SELECT
            artist,
            title,
            COUNT(*) as play_count,
            ROUND(SUM(watch_time_seconds) / 60.0, 1) as total_minutes
        FROM viewing_sessions
        WHERE artist IS NOT NULL AND media_type = 'Music'
        GROUP BY artist, title
        ORDER BY play_count DESC
        LIMIT 10
    """)
    print(result)


def print_daily_usage(con, days=7):
    """Print daily usage statistics."""
    print(f"\n{'=' * 100}")
    print(f"DAILY USAGE (Last {days} days)")
    print(f"{'=' * 100}\n")

    result = con.sql(f"""
        SELECT
            DATE(session_start) as date,
            COUNT(*) as num_sessions,
            ROUND(SUM(watch_time_seconds) / 3600.0, 2) as total_hours,
            COUNT(DISTINCT device_name) as num_devices_used
        FROM viewing_sessions
        WHERE session_start >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY DATE(session_start)
        ORDER BY date DESC
    """)
    print(result)


def export_sessions_to_csv(con, output_file="viewing_sessions.csv"):
    """Export the viewing sessions to a CSV file."""
    output_path = Path(__file__).parent / output_file

    con.execute(f"""
        COPY (
            SELECT * FROM viewing_sessions
            ORDER BY session_start DESC
        ) TO '{output_path}' (HEADER, DELIMITER ',')
    """)

    print(f"\n\nExported viewing sessions to: {output_path}")


def main():
    """Main analysis function."""
    try:
        con = duckdb.connect(str(DB_PATH))

        # Create/update the sessions table
        print("Creating/updating viewing_sessions table...")
        create_sessions_table(con)
        print("✓ Sessions table updated successfully\n")

        # Print various analyses
        print_recent_sessions(con, limit=20)
        print_session_stats(con)
        print_daily_usage(con, days=7)

        # Export to CSV
        export_sessions_to_csv(con)

        con.close()

        print(f"\n{'=' * 100}")
        print("Analysis complete!")
        print(f"{'=' * 100}\n")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
