#!/usr/bin/env python3
"""
Discover and log state of all HomeKit devices (lights, outlets, switches, sensors, etc.)

Uses aiohomekit to discover and read state from HomeKit accessories.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import duckdb
from aiohomekit.controller import Controller

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
            service_type TEXT,
            characteristic TEXT,
            value TEXT,
            unit TEXT
        )
    """)
    return con


async def discover_and_log_homekit_devices():
    """
    Discover HomeKit devices and log their state.

    Note: This requires devices to be in pairing mode or already paired.
    For already-configured HomeKit devices in your home, you typically need
    to access them through the Home app's sharing or use the Home Assistant
    integration which has persistent pairing.
    """

    controller = Controller()

    print("Discovering HomeKit accessories...")
    print("Note: This discovers devices advertising via Bonjour/mDNS")
    print()

    # Start the controller to begin discovery
    await controller.async_start()

    # Wait for discovery to complete
    print("Scanning for 10 seconds...")
    await asyncio.sleep(10)

    # Get discovered devices
    discoveries = controller.discoveries

    print(f"\nFound {len(discoveries)} HomeKit accessories:")
    print()

    for device_id, discovery in discoveries.items():
        print(f"Device: {discovery.name}")
        print(f"  Device ID: {device_id}")
        print(f"  Address: {discovery.address}:{discovery.port}")
        print(f"  Category: {discovery.category}")
        print(f"  Config: {discovery.config_num}")
        print(f"  Status: {discovery.status_flags}")
        print()

    # Clean up
    await controller.async_stop()

    if not discoveries:
        print("No unpaired HomeKit devices found.")
        print()
        print("This is expected if all your HomeKit devices are already")
        print("paired with your Home app. To access paired devices, you need:")
        print("  1. Export pairing data from the Home app (not straightforward)")
        print("  2. Use Home Assistant which maintains persistent pairings")
        print("  3. Temporarily unpair a device to test discovery")
        print()
        print("Alternative: Use the Home app's shortcuts/automations to log")
        print("device states, or integrate with Home Assistant.")

    return discoveries


async def main():
    """Main function."""

    print("=" * 60)
    print("HomeKit Device State Logger")
    print("=" * 60)
    print()

    discoveries = await discover_and_log_homekit_devices()

    # Note: To actually read device state from paired devices, we would need:
    # 1. Load existing pairing credentials
    # 2. Connect to each paired device
    # 3. List accessories and characteristics
    # 4. Read characteristic values and log to database

    # Example workflow for already-paired devices:
    # controller.load_pairing('pairing_data.json')
    # for alias, pairing in controller.pairings.items():
    #     accessories = await pairing.list_accessories_and_characteristics()
    #     for accessory in accessories['accessories']:
    #         for service in accessory['services']:
    #             for char in service['characteristics']:
    #                 if char.get('perms') and 'pr' in char['perms']:
    #                     value = await pairing.get_characteristics([(aid, iid)])


if __name__ == "__main__":
    asyncio.run(main())
