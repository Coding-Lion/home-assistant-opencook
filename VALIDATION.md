# Validation status

Validated locally on 2026-10-25 using Linux/WSL, Python 3.14.9 and
Home Assistant Core 2026.10.3:

- **28 tests passed**, including the upstream sync vectors, actual upstream
  household/sync HTTP routes and HA config-entry setup/to-do services/unload.
- Tests cover stale HA fields versus concurrent phone edits, quantities and recipe
  provenance, household isolation, tombstones, reset recovery and offline failures.
- **Ruff lint and formatting passed.**
- **Official hassfest passed:** one integration, zero invalid integrations, using
  the Home Assistant Core 2026.10.3 validator.
- Installed the pinned upstream server package, started its full FastAPI app
  without a model server, and verified `/health` returned `{"status":"ok"}` and
  `/admin` returned HTTP 200. Stopped the temporary server after verification.

Published [release v0.1.0](https://github.com/Coding-Lion/home-assistant-opencook/releases/tag/v0.1.0).
The [release-code CI run](https://github.com/Coding-Lion/home-assistant-opencook/actions/runs/40199130184)
passed all five jobs: tests, hassfest, HACS validation, and container build/smoke
tests on both `linux/amd64` and `linux/arm64`. The container smoke tests verify
startup, health, household creation, the service UID and persistence across restart.

On Home Assistant Yellow / CM4 with Core 2026.10.2:

- Supervisor accepted the repository and built/installed the server app.
- The server started with the configured admin password and advertised its mDNS
  service. The health check returned HTTP 200, with no vision server running.
- A new household was created successfully.
- The integration was downloaded through HACS and all component files were verified.
- Home Assistant's configuration check completed successfully before restarting.
- After the restart, the integration configured successfully for the new household.
- The native To-do interface displayed the connected `todo.home_shopping_list`
  entity, ready for use with an empty list.

Compatibility before Core 2026.10.2 is based on the documented APIs and the
Voluptuous fallback; the full suite has not been run on every older HA release.
