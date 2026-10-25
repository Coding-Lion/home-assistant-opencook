# openCook for Home Assistant

Run [openCook](https://github.com/oliexdev/openCook) on Home Assistant OS and use
the household shopping list in Home Assistant's native **To-do lists** interface.
This repository contains both a Supervisor add-on and a HACS custom integration.

Designed for **Home Assistant Yellow / CM4 (`aarch64`)**; the add-on also targets
`amd64`. No Ollama installation, GPU, cloud service, or AI API key is needed for
shopping-list sync. Recipe photo extraction is unavailable until you choose to
configure a compatible vision endpoint. The Android app remains the main recipe
and meal-planning interface; the server's web page is an administration console.

## Install the server add-on

Requires Home Assistant OS or another Supervisor installation with an add-on/app
store. Home Assistant Container installations cannot install Supervisor add-ons.

1. In **Settings → Add-ons → Add-on Store → ⋮ → Repositories**, add:
   `https://github.com/coding-lion/home-assistant-opencook`.
   Recent HA versions may label Add-ons as Apps.
2. Install **openCook Server**. The initial installation builds the server image
   on your Yellow and needs internet access; allow time for the build to finish.
3. On the Configuration tab set `admin_password` before the first start. Leave
   `vision_api_key` empty and keep the other defaults for use without AI.
4. Start the add-on and enable **Start on boot**. Open the web UI at
   `http://YOUR_YELLOW_IP:8000/admin` to confirm it is running. `/health` should
   return `{"status":"ok"}`.
5. In the openCook Android app, select the discovered server or enter
   `http://YOUR_YELLOW_IP:8000`. Create/join a household and let the phone sync.
   For an existing serverless household, use the app's attach-server flow to keep
   the existing household and invite code.

Port **8000** must be free. The add-on uses the host network for openCook's mDNS
discovery; no privileged mode, Docker socket, or Home Assistant API access is
requested. Keep port 8000 on your trusted LAN/VPN: the upstream server is designed
for a home network and most endpoints are unauthenticated. The admin password
does not add authentication to every endpoint.

If you access Home Assistant through a public hostname or reverse proxy, the
Open Web UI button may use that hostname. Use the Yellow's **LAN IP** with port
8000 for the openCook app; adding this repository does not publish that port.

Data lives in `/data/opencook` inside the add-on: SQLite database, recipe images
and server-created backups. It persists across add-on restarts and updates and is
included when you select this add-on in a Home Assistant backup. Make a backup
before an upgrade or reinstall. Uninstalling an add-on can remove its data.

## Install the shopping-list integration

Requires **Home Assistant Core 2025.3 or later** and an existing household on the
server. The integration can also connect to an openCook server running elsewhere.

1. In **HACS → ⋮ → Custom repositories**, add
   `https://github.com/coding-lion/home-assistant-opencook`, category **Integration**.
2. Download **openCook Shopping List**, then restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → openCook**.
4. Enter `http://YOUR_YELLOW_IP:8000` and your household's **invite code**. This is
   the shared sync credential, distinct from the join PIN and admin password.
   The app's household settings show the code so it can be copied. If necessary, joining the existing
   household via `POST /households/{household_id}/join` (with its join PIN) returns
   the `invite_code`; see the server API docs at `/docs`. Keep the code private.
5. Open **To-do lists** and select the household's shopping list. Add its entity
   to your dashboard with a To-do list card.

This creates a separate `todo` entity backed directly by openCook. It does not
copy items into Home Assistant's built-in `shopping_list` integration. You can
add, rename, check/uncheck, and delete items from the native to-do interface and
the standard `todo.*` actions. Changes from phones appear within about **30
seconds**, once those phones have synced with the server. HA writes are sent
immediately and report an error if the server is unreachable.

```yaml
type: todo-list
entity: todo.our_kitchen_shopping_list  # Replace with your actual entity ID.
title: Shopping
```

An automation can add an item using the standard action:

```yaml
action: todo.add_item
target:
  entity_id: todo.our_kitchen_shopping_list
data:
  item: Coffee
```

## Behavior and limits

- One config entry and one shopping-list entity per household. Repeat setup for
  additional households. Use **Reconfigure** to change an address or invite code.
- Quantities and units appear as read-only item descriptions. Editing the name
  or checked state preserves structured quantities and recipe references.
- New HA items are manual entries; numeric text such as `2 L milk` is kept as
  text. HA does not parse it into openCook quantity/unit fields or consolidate
  same-name items like the Android app does.
- HA shows all non-deleted shopping records. Android applies additional pantry
  coverage and language-specific ingredient matching, so it can hide records
  that HA still displays. The integration does not reproduce that matcher.
- Checking an item sets openCook's checked flag. HA's **clear completed** removes
  those records; it does not run Android's **checkout into pantry** workflow.
- Due dates, custom descriptions and reordering are not supported.
- Initial setup/reload reconstructs the list from the sync log. Later requests
  use openCook's Merkle delta sync. Server resets/restores rebuild the local
  projection without uploading old records. The integration retains only shopping
  fields and household timestamps in memory, not recipe contents or images.

## Local installation before publishing

If the GitHub repository has not yet been published, copy `addons/opencook` to
`/addons/opencook` on your HA host, reload the add-on store and install it under
**Local add-ons**. For the integration, copy `custom_components/opencook` into
`/config/custom_components/opencook` and restart HA. The configuration directory
may be exposed as `homeassistant` by the Samba app. These paths refer to the HA
host, not your Windows computer.

## Development and validation

On Linux/WSL, use Python 3.14 for the current Home Assistant test harness:

```bash
git clone https://github.com/oliexdev/openCook.git upstream/opencook
git -C upstream/opencook checkout a60375d0d73f275ec1f70b687ce89ff389c553d9
uv venv --python 3.14
uv pip install -r requirements-test.txt -r requirements-ha-test.txt
uv run --no-project pytest -q
uv run --no-project ruff check custom_components tests scripts addons/opencook/rootfs
uv run --no-project ruff format --check custom_components tests scripts addons/opencook/rootfs
```

Tests include upstream's shared HLC/merge/Merkle vectors, actual upstream
household/sync HTTP routes, multiple writers, field preservation, tombstones,
server resets, offline failures, HA setup/config flows and native to-do services.
CI also builds/smoke-tests amd64 and aarch64 images, runs hassfest and validates
HACS packaging. Tests are not a substitute for a first install on your Yellow.

The build installs upstream source pinned to a commit; upstream's Python
dependency ranges are resolved at build time. See [UPSTREAM.md](UPSTREAM.md) for
the exact revision, corresponding source, and GPL attribution.
