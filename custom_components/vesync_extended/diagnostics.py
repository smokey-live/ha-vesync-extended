"""Diagnostics from an explicit safe-field list, without account or device identifiers."""

from dataclasses import asdict


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "version": "0.1.4",
        "read_only": coordinator.client.read_only,
        "devices": [
            {"model": device.model, "state": asdict(coordinator.data[cid])}
            for cid, device in coordinator.client.devices.items()
            if cid in coordinator.data
        ],
    }
