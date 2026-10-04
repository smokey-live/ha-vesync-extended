# Contributing

Make one behavior change per pull request. Describe the triggering device/model,
the changed behavior, the protocol evidence and the checks performed.

Before submitting:

1. Run the protocol tests, Ruff checks and the Home Assistant smoke test.
2. Add a regression test for new response shapes, error handling or command ranges.
   Use synthetic, non-identifying fixture data and label its provenance.
3. For device commands, compare the app and a fresh status read before and after
   each test, and restore the original settings.
4. Update `docs/PROTOCOL.md`, `docs/VALIDATION.md` and `CHANGELOG.md` with the final behavior.
5. Keep unsupported features unavailable until their protocol and valid range are verified.

Do not include account credentials, tokens, device names, MAC addresses, cloud IDs,
network captures or raw authentication/device-list responses in a public issue or commit.

The package uses an independent integration domain. Do not patch the globally installed
pyvesync package or rename this component to `vesync`. Keep pyvesync's dependency pin
compatible with the Home Assistant version targeted by the official integration.

For releases, verify the final commit's CI result, bump the manifest and project version,
update the changelog, and publish a development prerelease until live-device testing
supports a stable release. Keep a rollback path for every installed test version.

