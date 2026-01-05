import asyncio
from datetime import datetime
from pathlib import Path

import duckdb
import pyatv
from pyatv import exceptions
from pyatv.const import DeviceState
from pyatv.storage.file_storage import FileStorage

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"


def init_duckdb():
    """Create DB and table if they don't already exist."""
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            ts TIMESTAMP,
            device_name TEXT,
            address TEXT,
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
    return con


def enum_to_text(value):
    """Convert enum-like objects to something DuckDB can store."""
    if value is None:
        return None
    name = getattr(value, "name", None)
    if name is not None:
        return name
    return str(value)


def get_last_row(con, device_name):
    """Fetch the most recent row for this device, or None."""
    result = con.execute(
        f"""
        SELECT
            ts,
            state,
            app,
            title,
            series_name,
            season,
            episode,
            media_type
        FROM {TABLE_NAME}
        WHERE device_name = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        [device_name],
    ).fetchone()
    return result  # either a tuple or None


async def log_device_now_playing(config, loop, storage):
    """Log now playing info for a single Apple TV device."""
    con = init_duckdb()

    try:
        atv = await pyatv.connect(config, loop, storage=storage)

        try:
            playing = await atv.metadata.playing()

            # Normalize state enum → text
            state = enum_to_text(playing.device_state)

            # Only log when actually watching something
            if state not in ("Playing", "Paused"):
                return

            # Normalize media_type enum → text
            media_type = enum_to_text(getattr(playing, "media_type", None))

            ts = datetime.now()

            app = getattr(playing, "app", None)
            title = playing.title
            artist = getattr(playing, "artist", None)
            album = getattr(playing, "album", None)
            series_name = getattr(playing, "series_name", None)
            season = getattr(playing, "season_number", None)
            episode = getattr(playing, "episode_number", None)
            position = playing.position
            duration = playing.total_time

            # Check last row to avoid repeated Paused spam
            last = get_last_row(con, config.name)
            if last is not None:
                (
                    last_ts,
                    last_state,
                    last_app,
                    last_title,
                    last_series_name,
                    last_season,
                    last_episode,
                    last_media_type,
                ) = last

                same_show = (
                    last_app == app
                    and last_title == title
                    and last_series_name == series_name
                    and last_season == season
                    and last_episode == episode
                    and last_media_type == media_type
                )

                # If we are still Paused on the same thing, skip logging
                if state == "Paused" and last_state == "Paused" and same_show:
                    return

            # Build row and insert
            row = (
                ts,
                config.name,
                str(config.address),
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
                    duration
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )

            # Human-readable debug line
            summary_parts = [
                f"[{ts.isoformat()}]",
                f"device={config.name}",
                f"state={state}",
            ]
            if app:
                summary_parts.append(f"app={app}")
            if title:
                summary_parts.append(f"title={title}")
            print(" ".join(summary_parts))

        except exceptions.AuthenticationError:
            print(
                f"Authentication error for {config.name} – try re-pairing via atvremote."
            )
        except Exception as exc:
            print(f"Error while logging now playing for {config.name}: {exc}")
        finally:
            atv.close()

    except Exception as exc:
        print(f"Error connecting to {config.name}: {exc}")
    finally:
        con.close()


async def log_all_devices(loop):
    """Scan for all Apple TVs and log their now playing info concurrently."""
    storage = FileStorage.default_storage(loop)
    await storage.load()

    # Scan for all devices on the network
    print("Scanning for Apple TVs and HomePods...")
    all_devices = await pyatv.scan(loop, storage=storage)

    # Filter to include Apple TVs and HomePods (exclude Macs and Unknown devices)
    devices = [
        config
        for config in all_devices
        if config.device_info
        and config.device_info.model
        and str(config.device_info.model) != "DeviceModel.Unknown"
    ]

    if not devices:
        print("No Apple TVs or HomePods found on the network")
        print(
            f"Found {len(all_devices)} other devices: {', '.join([config.name for config in all_devices])}"
        )
        return

    print(
        f"Found {len(devices)} device(s): {', '.join([config.name for config in devices])}"
    )

    # Process all devices concurrently
    tasks = [log_device_now_playing(config, loop, storage) for config in devices]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(log_all_devices(loop))
