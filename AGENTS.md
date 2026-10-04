# Project guidance

- Read README.md and docs/PROTOCOL.md before changing a handler.
- Keep this custom integration separate from the official `vesync` domain and device map.
- Default to read-only mode. Enforce it at the API boundary, not only in UI feature flags.
- Match exact cloud model identifiers and reject unverified commands and ranges.
- Check both cloud and nested device response codes. Do not invent values for missing fields.
- Confirm writes with a fresh device status read. Keep failures local to the affected device.
- Never commit account credentials, tokens, names, MAC addresses, cloud IDs or captures.
- Use synthetic fixtures for unit tests and clearly distinguish them from live evidence.
- Run pytest, ruff check, ruff format --check and the target Home Assistant smoke test.
- Update CHANGELOG.md and the protocol/validation documents when behavior changes.
- Keep the dependency pin compatible with the target Home Assistant version.
