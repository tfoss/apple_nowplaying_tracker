#!/usr/bin/env python3
"""
Backfill device_model and fix media_type for existing database records.

This script:
1. Sets device_model based on device_name patterns
2. Updates Unknown media_type to Music for HomePods
3. Updates Unknown media_type to Music when artist field is present
4. Updates Unknown media_type to Video when series_name is present
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"


def backfill_device_models(con):
    """Backfill device_model based on device names."""
    print("Backfilling device_model based on device names...")

    # Get unique device names and their patterns
    device_mappings = {
        "AppleTV": "AppleTV",
        "Basement": "AppleTV",  # Assuming this is an Apple TV
    }

    # HomePods - check for "HomePod" in the name
    result = con.execute(f"""
        SELECT DISTINCT device_name
        FROM {TABLE_NAME}
        WHERE device_name LIKE '%HomePod%'
    """).fetchall()

    for (device_name,) in result:
        device_mappings[device_name] = (
            "HomePodMini"  # Default to Mini, adjust if needed
        )

    # Apply the mappings
    for device_name, model in device_mappings.items():
        count = con.execute(
            f"""
            UPDATE {TABLE_NAME}
            SET device_model = ?
            WHERE device_name = ? AND device_model IS NULL
        """,
            [model, device_name],
        ).fetchall()

        # Get count of updated rows
        updated = con.execute(
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            WHERE device_name = ? AND device_model = ?
        """,
            [device_name, model],
        ).fetchone()[0]

        print(f"  ✓ Set {device_name} -> {model} ({updated:,} rows)")


def fix_media_types(con):
    """Fix Unknown media_types based on context."""
    print("\nFixing Unknown media_types...")

    # 1. HomePods playing Unknown -> Music
    count = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET media_type = 'Music'
        WHERE media_type = 'Unknown'
          AND device_model LIKE '%HomePod%'
    """).fetchall()

    updated = con.execute(f"""
        SELECT COUNT(*)
        FROM {TABLE_NAME}
        WHERE media_type = 'Music' AND device_model LIKE '%HomePod%'
    """).fetchone()[0]
    print(f"  ✓ HomePod Unknown -> Music ({updated:,} rows)")

    # 2. Has artist field -> Music
    count = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET media_type = 'Music'
        WHERE media_type = 'Unknown'
          AND artist IS NOT NULL
    """).fetchall()

    updated_artist = con.execute(f"""
        SELECT COUNT(*)
        FROM {TABLE_NAME}
        WHERE media_type = 'Music' AND artist IS NOT NULL
    """).fetchone()[0]
    print(f"  ✓ Has artist -> Music ({updated_artist:,} rows)")

    # 3. Has series_name -> Video
    count = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET media_type = 'Video'
        WHERE media_type = 'Unknown'
          AND series_name IS NOT NULL
    """).fetchall()

    updated_series = con.execute(f"""
        SELECT COUNT(*)
        FROM {TABLE_NAME}
        WHERE media_type = 'Video' AND series_name IS NOT NULL
    """).fetchone()[0]
    print(f"  ✓ Has series_name -> Video ({updated_series:,} rows)")


def show_summary(con):
    """Show summary of media types by device."""
    print("\n" + "=" * 80)
    print("MEDIA TYPE DISTRIBUTION BY DEVICE")
    print("=" * 80 + "\n")

    result = con.execute(f"""
        SELECT
            device_name,
            device_model,
            media_type,
            COUNT(*) as count
        FROM {TABLE_NAME}
        GROUP BY device_name, device_model, media_type
        ORDER BY device_name, media_type
    """)

    print(result)

    print("\n" + "=" * 80)
    print("OVERALL MEDIA TYPE SUMMARY")
    print("=" * 80 + "\n")

    result = con.execute(f"""
        SELECT
            media_type,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
        FROM {TABLE_NAME}
        GROUP BY media_type
        ORDER BY count DESC
    """)

    print(result)


def main():
    print("Starting database backfill...\n")

    con = duckdb.connect(str(DB_PATH))

    # Backfill device models
    backfill_device_models(con)

    # Fix media types
    fix_media_types(con)

    # Show summary
    show_summary(con)

    con.close()

    print("\n" + "=" * 80)
    print("Backfill complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
