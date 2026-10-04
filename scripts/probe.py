"""Read-only live probe. Output is a whitelist of model and status fields.

Run with a hidden password prompt, or inside Home Assistant using an existing
VeSync config entry. Never supply credentials as command-line arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from aiohttp import ClientSession
from pyvesync import VeSync

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.vesync_extended.api import ApiError, ExtendedClient  # noqa: E402


def credentials(config_dir: Path | None):
    if config_dir is None:
        return input("VeSync email: ").strip(), getpass.getpass("VeSync password: "), "US"
    data = json.loads((config_dir / ".storage/core.config_entries").read_text())
    entries = [entry for entry in data["data"]["entries"] if entry["domain"] == "vesync"]
    if len(entries) != 1:
        raise ValueError("Expected exactly one existing official VeSync account")
    entry = entries[0]["data"]
    return entry["username"], entry["password"], entry.get("country", "US")


async def probe(config_dir: Path | None):
    email, password, country = credentials(config_dir)
    async with ClientSession() as session:
        manager = VeSync(email, password, country_code=country, session=session, redact=True)
        client = ExtendedClient(manager, session, read_only=True)
        await client.login()
        devices = await client.discover()
        results = []
        for device in devices.values():
            try:
                state = await client.get_state(device)
                results.append({"model": device.model, "state": asdict(state)})
            except ApiError as err:
                results.append(
                    {
                        "model": device.model,
                        "error": type(err).__name__,
                        "code": err.code,
                        "error_reason": str(err),
                    }
                )
            except TimeoutError:
                results.append({"model": device.model, "error": "TimeoutError"})
        return {"read_only": True, "device_count": len(devices), "devices": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ha-config", type=Path, help="Use the local HA VeSync entry without printing it"
    )
    parser.add_argument(
        "--output", type=Path, help="Optional local file for the safe status report"
    )
    args = parser.parse_args()
    # Do not emit authentication debug logs or raw exception details.
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(probe(args.ha_config))
    except (ApiError, ValueError, KeyError, OSError, TimeoutError) as err:
        print(json.dumps({"error": type(err).__name__}))
        return 1
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if result["devices"] and all("state" in d for d in result["devices"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
