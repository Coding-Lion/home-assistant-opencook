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

The add-on image has **not yet been built or run locally**: this machine has no
working Docker engine. The repository includes CI builds and container smoke tests
for `linux/amd64` and `linux/arm64`; those results are pending publication/running
the workflow. Local schema checks validate option mapping, not Supervisor itself.

A first install on the Home Assistant Yellow is still required. GitHub publishing
needs authentication, and HA installation needs the instance URL and access.
Until publication, use the local ZIP packages and the README's local-install steps.

Compatibility before Core 2026.10.3 is based on the documented APIs and the
Voluptuous fallback; the full suite has not been run on every older HA release.
