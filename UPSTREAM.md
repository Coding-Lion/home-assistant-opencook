# Upstream provenance and license

This project is distributed under GPL-3.0-or-later; see [LICENSE](LICENSE).

- Server: [oliexdev/openCook](https://github.com/oliexdev/openCook), pinned at
  `a60375d0d73f275ec1f70b687ce89ff389c553d9`.
- Corresponding server source:
  <https://github.com/oliexdev/openCook/tree/a60375d0d73f275ec1f70b687ce89ff389c553d9/server>.
  The Dockerfile installs this source unmodified. Runtime configuration is in
  `addons/opencook/rootfs/opt/opencook/launch.py`.
- `custom_components/opencook/protocol.py` is copied from upstream
  `server/app/sync.py`, with attribution and formatting changes. Copyright (C) 2026
  olie.xdev <olie.xdeveloper@googlemail.com>.
- `tests/fixtures/sync-vectors.json` is copied from the same revision's
  `server/tests/fixtures/sync-vectors.json`.
- Brand icons are copied from upstream `fastlane/metadata/android/en-US/images/icon.png`.
- Shopping field mapping follows upstream `ShoppingMessageEncoder.kt` and
  `MessageApplier.kt` at that revision.
- Add-on structure was informed by
  [hassio-addons/app-example](https://github.com/hassio-addons/app-example).
  This project uses the Python image's standard container init and a Python launcher;
  it does not copy the example's S6/Bashio implementation.

To update the server, review its API/field changes, update `OPENCOOK_REF` in the
Dockerfile and this document, then run the protocol, HTTP contract and HA tests,
and build/smoke-test both container architectures. Increment the add-on version
so Supervisor rebuilds it. Upstream's API currently has no version-negotiation
mechanism, so compatibility with arbitrary future revisions is not guaranteed.
