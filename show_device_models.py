import asyncio
from pathlib import Path

import pyatv
from pyatv.storage.file_storage import FileStorage


async def show_all_device_models(loop):
    """Scan for all devices and show their models."""
    storage = FileStorage.default_storage(loop)
    await storage.load()

    print("Scanning for all devices on the network...")
    all_devices = await pyatv.scan(loop, storage=storage)

    if not all_devices:
        print("No devices found on the network")
        return

    print(f"\nFound {len(all_devices)} device(s):\n")
    print(f"{'Device Name':<30} {'Model':<30} {'Model String':<30}")
    print("=" * 90)

    for config in all_devices:
        name = config.name or "Unknown"
        model = config.device_info.model if config.device_info else None
        model_str = str(model) if model else "None"
        model_repr = repr(model) if model else "None"

        print(f"{name:<30} {model_repr:<30} {model_str:<30}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(show_all_device_models(loop))
