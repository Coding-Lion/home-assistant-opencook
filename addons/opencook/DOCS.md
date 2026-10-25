# openCook Server configuration

1. Set an `admin_password` before the first start, then start the add-on.
2. Open `http://YOUR_HA_IP:8000/admin` (Open Web UI).
3. Select the discovered server in the Android app, or enter
   `http://YOUR_HA_IP:8000`, then create/join your household.
4. Install the companion HACS integration from
   `https://github.com/coding-lion/home-assistant-opencook` and enter the same
   server URL and the household invite code.

## Options

| Option | Purpose |
| --- | --- |
| `server_name` | Friendly name announced to openCook clients using mDNS. |
| `admin_password` | Sets the server's initial admin password only. Later changes use the admin console. |
| `vision_base_url` | OpenAI-compatible vision API base URL. Default is an unused local Ollama endpoint. |
| `vision_model` | Vision model name; unused until a photo scan is requested. |
| `vision_api_key` | Leave blank for sync without AI. Remote authenticated endpoints require HTTPS. |
| `backup_keep` | Number of openCook server-created backup archives to retain. This does not schedule backups. |
| `log_level` | Uvicorn HTTP server logging level. |

With no vision server configured, scanning photos fails but household and shopping
sync remain available. The add-on never downloads an AI model or starts Ollama.
If you later run Ollama on another machine, use, for example,
`http://192.168.1.50:11434/v1` and pull a compatible vision model there.

## Network and storage

The add-on listens on host TCP port **8000** and advertises `_opencook._tcp` over
mDNS. This requires host networking; port 8000 must be unused by other services.
It has no Home Assistant ingress proxy. Open its direct LAN URL.

Keep it on a trusted LAN/VPN. The upstream server is mostly unauthenticated; its
admin password protects admin actions, not the full server.

The server runs as uid/gid 10001 after preparing `/data/opencook`. Supervisor
preserves this private add-on directory on upgrades and includes it in backups
when this add-on is selected. It stores `opencook.db`, `images/` and `backups/`.
openCook's archive creation/restore UI remains available in `/admin`.

After restoring a server backup, restart the add-on as recommended by upstream.
After restoring an HA backup, confirm the Android app is using the same household.

## Troubleshooting

- **Start fails with address already in use:** free host port 8000.
- **Phone does not discover server:** manually enter the Yellow's LAN IP/port;
  multicast may be blocked between networks.
- **Scanning fails:** expected without a vision backend; shopping sync does not need one.
- **Integration rejects credentials:** use the household invite code, not the PIN
  or admin password, and make sure the household has been attached to this server.
- **Changing `admin_password` has no effect:** it only bootstraps the password on
  first start. Use the admin console's change-password function afterwards.
