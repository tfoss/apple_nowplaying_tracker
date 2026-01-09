#!/usr/bin/env python3
"""
Add user_name column to now_playing table and clean up concatenated Spotify fields.

Changes:
1. Add user_name column (TEXT, nullable)
2. Backfill user_name for existing Spotify entries by parsing device_name
3. Clean up device_name to remove "Spotify (User): " prefix
4. Clean up device_model to remove "Spotify-" prefix
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"


def migrate():
    """Run the migration."""
    con = duckdb.connect(str(DB_PATH))

    print("Starting migration...")

    # Step 1: Add user_name column
    print("\n1. Adding user_name column...")
    try:
        con.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN user_name TEXT")
        print("   ✓ Column added")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("   ✓ Column already exists")
        else:
            raise

    # Step 2: Backfill user_name from device_name for Spotify entries
    print("\n2. Backfilling user_name for Spotify entries...")
    result = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET user_name = CASE
            WHEN device_name LIKE 'Spotify (%):%%' THEN
                REGEXP_EXTRACT(device_name, 'Spotify \\(([^)]+)\\):', 1)
            ELSE NULL
        END
        WHERE app = 'Spotify' AND user_name IS NULL
    """)
    print(f"   ✓ Updated {result.fetchone()[0]} rows")

    # Step 3: Clean up device_name (remove "Spotify (User): " prefix)
    print("\n3. Cleaning up device_name...")
    result = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET device_name = REGEXP_REPLACE(device_name, '^Spotify \\([^)]+\\): ', '')
        WHERE device_name LIKE 'Spotify (%):%%'
    """)
    print(f"   ✓ Updated {result.fetchone()[0]} rows")

    # Step 4: Clean up device_model (remove "Spotify-" prefix)
    print("\n4. Cleaning up device_model...")
    result = con.execute(f"""
        UPDATE {TABLE_NAME}
        SET device_model = REGEXP_REPLACE(device_model, '^Spotify-', '')
        WHERE device_model LIKE 'Spotify-%%'
    """)
    print(f"   ✓ Updated {result.fetchone()[0]} rows")

    # Step 5: Show sample of cleaned data
    print("\n5. Sample of cleaned Spotify data:")
    result = con.execute(f"""
        SELECT
            user_name,
            device_name,
            device_model,
            app,
            title
        FROM {TABLE_NAME}
        WHERE app = 'Spotify'
        ORDER BY ts DESC
        LIMIT 5
    """).fetchall()

    for row in result:
        print(
            f"   User: {row[0]}, Device: {row[1]}, Model: {row[2]}, App: {row[3]}, Title: {row[4]}"
        )

    con.close()
    print("\n✓ Migration complete!")


if __name__ == "__main__":
    migrate()
