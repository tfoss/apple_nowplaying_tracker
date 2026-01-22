import asyncio
import json
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pyatv
from pyatv import exceptions
from pyatv.const import DeviceState
from pyatv.storage.file_storage import FileStorage

from notify import notify_device_error, record_device_success

DB_PATH = Path(__file__).parent / "atv_usage.duckdb"
TABLE_NAME = "now_playing"
DEVICE_CACHE_PATH = Path(__file__).parent / "device_cache.json"
DEVICE_CONFIG_CACHE_PATH = Path(__file__).parent / "device_config_cache.pkl"
CACHE_EXPIRY_HOURS = 24  # Re-scan once per day


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
        # Column already exists
        pass

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
    device_start = time.time()
    con = init_duckdb()

    try:
        connect_start = time.time()
        atv = await pyatv.connect(config, loop, storage=storage)
        connect_time = time.time() - connect_start
        print(f"[TIMING] {config.name}: connect took {connect_time:.2f}s")

        try:
            metadata_start = time.time()
            playing = await atv.metadata.playing()
            metadata_time = time.time() - metadata_start
            print(
                f"[TIMING] {config.name}: metadata.playing() took {metadata_time:.2f}s"
            )

            # Record successful connection (resets failure counter)
            record_device_success(config.name)

            # Normalize state enum → text
            state = enum_to_text(playing.device_state)

            # Only log when actually watching something
            if state not in ("Playing", "Paused"):
                return

            ts = datetime.now()

            # Get app info from metadata (not from playing object)
            app_obj = atv.metadata.app
            app = app_obj.name if app_obj else None
            app_id = app_obj.identifier if app_obj else None
            title = playing.title
            artist = getattr(playing, "artist", None)
            album = getattr(playing, "album", None)
            series_name = getattr(playing, "series_name", None)
            season = getattr(playing, "season_number", None)
            episode = getattr(playing, "episode_number", None)
            position = playing.position
            duration = playing.total_time

            # Normalize media_type enum → text
            media_type = enum_to_text(getattr(playing, "media_type", None))

            # Get device model for better media_type inference
            device_model = None
            if config.device_info and config.device_info.model:
                device_model = enum_to_text(config.device_info.model)

            # Infer media_type if unknown based on device type
            if media_type == "Unknown" or media_type is None:
                if device_model and "HomePod" in device_model:
                    # HomePods are primarily music devices
                    media_type = "Music"
                elif device_model and "AppleTV" in device_model:
                    # Apple TVs are primarily video devices
                    media_type = "Video"

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
            error_msg = f"Authentication error for {config.name} – try re-pairing via atvremote."
            print(error_msg)
            notify_device_error(config.name, error_msg)
        except Exception as exc:
            error_msg = f"Error while logging now playing for {config.name}: {exc}"
            print(error_msg)
            notify_device_error(config.name, str(exc))
        finally:
            atv.close()

    except Exception as exc:
        error_msg = f"Error connecting to {config.name}: {exc}"
        print(error_msg)
        notify_device_error(config.name, str(exc))
    finally:
        con.close()


def load_cached_configs():
    """Load cached device configs (full pickled objects) and last scan time."""
    if not DEVICE_CONFIG_CACHE_PATH.exists():
        return None, None

    try:
        with open(DEVICE_CONFIG_CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
        last_scan = cache["last_scan"]
        configs = cache["configs"]
        return configs, last_scan
    except Exception as e:
        print(f"Failed to load cached configs: {e}")
        return None, None


def save_cached_configs(devices):
    """Save full device configs (pickled) and current timestamp to cache."""
    cache = {"last_scan": datetime.now(), "configs": devices}
    try:
        with open(DEVICE_CONFIG_CACHE_PATH, "wb") as f:
            pickle.dump(cache, f)
        print(f"Cached {len(devices)} device configs")
    except Exception as e:
        print(f"Failed to save cached configs: {e}")


async def log_all_devices(loop):
    """Scan for all Apple TVs and log their now playing info concurrently."""
    script_start = time.time()

    storage = FileStorage.default_storage(loop)
    await storage.load()

    # Check if we have cached configs
    cached_configs, last_scan = load_cached_configs()
    cache_valid = (
        cached_configs is not None
        and last_scan is not None
        and datetime.now() - last_scan < timedelta(hours=CACHE_EXPIRY_HOURS)
    )

    if cache_valid:
        # Use cached configs directly - no scanning needed!
        print(
            f"Using cached device configs (last scan: {last_scan.strftime('%Y-%m-%d %H:%M')})"
        )
        load_time = time.time() - script_start
        print(f"[TIMING] Loading cached configs took {load_time:.2f}s")
        devices = cached_configs
    else:
        # Perform full network scan
        print("Scanning for Apple TVs and HomePods...")
        scan_start = time.time()
        all_devices = await pyatv.scan(loop, storage=storage)
        scan_time = time.time() - scan_start
        print(f"[TIMING] Full network scan took {scan_time:.2f}s")

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

        # Cache the full device configs for next time
        save_cached_configs(devices)

    if not devices:
        print("No cached devices found on the network")
        return

    print(
        f"Found {len(devices)} device(s): {', '.join([config.name for config in devices])}"
    )

    # Process all devices concurrently
    gather_start = time.time()
    tasks = [log_device_now_playing(config, loop, storage) for config in devices]
    await asyncio.gather(*tasks)
    gather_time = time.time() - gather_start
    print(f"[TIMING] Processing all devices took {gather_time:.2f}s")

    total_time = time.time() - script_start
    print(f"[TIMING] Total script execution: {total_time:.2f}s")


if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Starting Apple TV nowplaying scan")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(log_all_devices(loop))
