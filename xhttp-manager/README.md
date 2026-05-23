# xhttp-manager

User management addon for [XHTTP-Installer](https://github.com/avacocloud/XHTTP-Installer).  
Adds multi‑user support, bandwidth/time/device limits, and a full REST API to your VLESS+XHTTP proxy.

## Features

- **Multi‑user VLESS** – dynamically add/remove Xray clients without downtime.
- **Resource limits** – expiry dates, data caps, device concurrency limits.
- **REST API** – Bearer‑token‑secured API on `localhost:7171`.
- **CLI** – scriptable management via `xhttp-mgr` command.
- **Auto‑enforcement** – systemd timer checks limits every 60 seconds.
- **Single‑command install** – non‑destructive, works on top of an existing XHTTP‑Installer deployment.

## Quick Install

Run this on a server that already has XHTTP-Installer fully deployed:

```bash
curl -fsSL https://raw.githubusercontent.com/Massie382/xhttp-manager/main/install.sh | sudo bash