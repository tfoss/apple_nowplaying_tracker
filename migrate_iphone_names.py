#!/usr/bin/env python3
"""
Migrate iPhone/iPad device names to include user_name for disambiguation.
e.g., 'iPhone' -> 'iPhone (Ted)'
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"


def main():
    con = duckdb.connect(str(DB_PATH))

    # Check what we're about to update
    print("=== Before migration ===")
    results = con.execute("""
        SELECT device_name, user_name, COUNT(*) as cnt
        FROM now_playing
        WHERE device_name IN ('iPhone', 'iPad') AND user_name IS NOT NULL
        GROUP BY device_name, user_name
    """).fetchall()
    for r in results:
        print(r)

    if not results:
        print("No iPhone/iPad entries to migrate.")
        con.close()
        return

    # Migrate historical data
    con.execute("""
        UPDATE now_playing
        SET device_name = device_name || ' (' || user_name || ')'
        WHERE device_name IN ('iPhone', 'iPad') AND user_name IS NOT NULL
    """)

    print()
    print("=== After migration ===")
    results = con.execute("""
        SELECT device_name, user_name, COUNT(*) as cnt
        FROM now_playing
        WHERE device_name LIKE 'iPhone%' OR device_name LIKE 'iPad%'
        GROUP BY device_name, user_name
    """).fetchall()
    for r in results:
        print(r)

    con.close()
    print()
    print("Migration complete!")


if __name__ == "__main__":
    main()
