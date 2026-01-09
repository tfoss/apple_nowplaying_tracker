#!/usr/bin/env python3
"""
Discover and log state of all HomeKit devices (lights, outlets, switches, sensors, etc.)

Uses pyatv's ability to discover HomeKit accessories on the local network.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "homekit_state.duckdb"
TABLE_NAME = "device_state"


def init_duckdb():
    """Create DB and table if they don't already exist."""
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            ts TIMESTAMP,
            device_name TEXT,
            device_type TEXT,
            room TEXT,
            characteristic TEXT,
            value TEXT,
            unit TEXT
        )
    """)
    return con


async def discover_homekit_devices():
    """
    Discover HomeKit devices on the network.

    Note: This uses pyatv's scan which primarily finds Apple TV/HomePod devices.
    For full HomeKit device discovery, we'd need a dedicated HomeKit library like
    'homekit' (https://github.com/jlusiardi/homekit_python) which can discover
    and control all HomeKit accessories.
    """
    import pyatv

    print("Scanning for HomeKit-enabled devices...")
    devices = await pyatv.scan(asyncio.get_event_loop(), timeout=5)

    print(f"\nFound {len(devices)} devices:")
    for device in devices:
        print(f"\nDevice: {device.name}")
        print(f"  Address: {device.address}")
        print(f"  Device Info: {device.device_info}")
        print(f"  Services: {[s.protocol.name for s in device.services]}")

    return devices


async def main():
    """Main function."""

    print("=" * 60)
    print("HomeKit Device State Logger")
    print("=" * 60)
    print()
    print("NOTE: This initial version uses pyatv which primarily discovers")
    print("Apple TV and HomePod devices. For comprehensive HomeKit device")
    print("discovery (lights, outlets, sensors, etc.), we would need to")
    print("install the 'homekit' Python library.")
    print()
    print("To get full HomeKit support, run:")
    print("  pip install homekit")
    print()
    print("=" * 60)
    print()

    devices = await discover_homekit_devices()

    # Future: Use homekit library to discover all accessories
    # from homekit.controller import Controller
    # controller = Controller()
    # devices = controller.discover(max_seconds=10)


if __name__ == "__main__":
    asyncio.run(main())
