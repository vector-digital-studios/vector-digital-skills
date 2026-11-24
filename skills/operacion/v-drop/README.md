# V Drop

**AirDrop-style file sharing over your own WiFi — no cloud, no accounts, no cables.**

V Drop is a tiny, dependency-free LAN file transfer hub. Run it on any computer in
your home, open a URL from your phone, and send files straight to the laptop — or
between any devices on the same network, with an accept/decline flow. Files never
leave your house.

Built with Python's standard library only (`http.server`) and vanilla JavaScript.
Zero dependencies, zero installs for the phone, works on iPhone and Android.

![V Drop](docs/screenshot-desktop.png)

*V Drop en el celular:* ![V Drop móvil](docs/screenshot-mobile.png)

## Features

- **Phone → laptop in one tap** — drag & drop or pick a file; lands on the server's `uploads/` folder, uncut and uncompressed.
- **Device-to-device** — send a file to any other device on the network: the receiver gets a live "Accept / Decline" prompt, then downloads.
- **Live device discovery** — a presence bar shows who's online; devices are auto-named from their model ("iPhone", "Pixel 8", "PC Windows") and can be renamed once (names persist per device).
- **Re-send or re-download** — history lets you push a file to another device (➦) or download it back to the current device (⬇).
- **No size limit in practice** — 10 GB cap, streams big files, resumes by design (HTTP).
- **PWA installable** — "Add to Home Screen" turns it into an app; works offline of the internet.
- **Zero dependencies** — pure Python stdlib + vanilla JS. Runs on Windows, macOS, Linux.

## How it works

V Drop is a **hub-and-spoke** server: one machine (usually the laptop) runs `server.py`
and becomes the hub. Every device connects to it over your WiFi (LAN) and exchanges
files through it. Nothing goes to the internet.

```
        ┌──────────────┐
        │   Your WiFi  │
        │              │
  iPhone │              │ Android
    ─────┼─── laptop ──┼─────
   (hub: server.py     │
     on port 8080)     │
                       │
                 Another laptop
```

## Quick start (Windows)

1. **Install Python 3.8+** from [python.org](https://python.org) (check "Add to PATH").
2. **Download** this repo (Code → Download ZIP) and unzip it.
3. **Run `start.bat`** — the server starts in the background on port 8080.
4. **Firewall (once):** right-click `firewall-admin.bat` → *Run as administrator*.
   Without this, Windows blocks phones from connecting.
5. **Get the URL:** open `data\last_url.txt` — it looks like
   `http://192.168.x.x:8080/?k=<token>`. The `?k=` token is your private access key.
6. On your phone (same WiFi), open that URL in a browser and drop a file.

> **Tip — a link that never changes:** the router may reassign the laptop's IP.
> Set a static IP for the computer (Windows: Settings → Network → your adapter →
> IP assignment → Edit → Manual) or reserve the address in your router's DHCP
> settings. Then bookmark the URL once and it always works.

### Sending between devices

1. Open V Drop on **both** devices (same WiFi).
2. Pick a file on one device. A sheet appears: **"Enviar a…"** with the list of
   devices online. Choose a destination — or "Solo a la laptop" to just save it.
3. The receiver gets **«Name» quiere enviarte…** with **Aceptar / Rechazar**.
4. On accept, the file downloads to the receiver.

## macOS / Linux

```bash
python3 server.py            # or: python server.py
```

- The server prints the URL with its token. Open it from any device on the network.
- **Firewall (macOS):** allow incoming connections for Python when prompted, or
  `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add python3`.
- **Firewall (Linux):** if using ufw, `sudo ufw allow 8080/tcp`.

## CLI options

| Flag | Meaning |
|---|---|
| `--port 9000` | Use a different port (default 8080) |
| `--no-token` | Disable the access token (only on trusted networks!) |

## Security model

V Drop is designed for **trusted home networks** — read this before exposing it anywhere else.

- **Token access:** the page URL carries a random token (`?k=...`). Anyone on the
  network who has the URL can upload/download. Treat the URL like a password.
- **Public shell, private API:** the HTML/CSS/JS shell and PWA manifest are served
  without auth (they contain no data and never reveal the token); every API call is
  token-gated. The app stores the token in the browser and sends it as a header.
- **LAN only:** the server binds to all interfaces but is meant to stay behind
  your router's NAT. **Do not** port-forward 8080 or expose it to the internet —
  there is no TLS and no user accounts.
- **Download control:** transfers between devices require the receiver to accept
  first; only the recipient (verified by IP) can download a transfer.
- **Hardened by default:** streaming uploads (no 10 GB RAM bombs), host validation
  against DNS-rebinding, connection/device/transfer limits, symlink guard, CSP.
- **Files stay home:** uploads never leave your network.
- See [SECURITY.md](SECURITY.md) for the full threat model, controls and limitations.

## API (for tinkerers)

All endpoints accept `?k=<token>` or the `X-Alfred-Token` header.

| Method | Path | Purpose |
|---|---|---|
| POST | `/upload` | Multipart upload; optional `to` field = target device cid |
| GET | `/api/health` | Server status + version |
| GET | `/api/history` | Recent uploads |
| GET | `/api/download?name=<file>` | Download an uploaded file to the current device |
| POST | `/api/device` | Register/ping/rename this device `{cid, name, model, platform}` |
| GET | `/api/devices` | List devices online |
| GET | `/api/events?cid=<id>` | SSE stream: `devices`, `transfer_request`, `transfer_accepted`, `transfer_declined` |
| POST | `/api/transfer` | Re-send an existing uploaded file `{to, name, from}` |
| GET | `/api/transfers?cid=<id>` | Pending + recent transfers |
| PUT | `/api/transfers/<tid>/accept` | Accept (recipient only) |
| DELETE | `/api/transfers/<tid>/decline` | Decline (recipient only) |
| GET | `/api/transfers/<tid>/download` | Download an accepted transfer (recipient only) |

## Development

```bash
# run a test instance on port 8090 (does not touch a running 8080)
python server.py --port 8090

# smoke test: 23 checks covering the full flow (register, SSE, accept, decline, download)
# IMPORTANT: run it against a token-mode server on 8090 (not --no-token)
python test/v2_smoke.py
# expected: RESULTADO: 23 OK / 0 FAIL
```

The server is a single `server.py` file — no build step, no package manager.
`python server.py --port 8090 && python test/v2_smoke.py` is the one-command
verification that the clone works.

## API examples

```bash
TOKEN=$(cat data/token.txt)

# upload a file
curl -F "files=@photo.jpg" "http://<ip>:8080/upload?k=$TOKEN"

# list recent uploads
curl "http://<ip>:8080/api/history?k=$TOKEN"

# download an uploaded file back to this device
curl -OJ "http://<ip>:8080/api/download?name=photo.jpg&k=$TOKEN"

# register this device (so others can send to it)
curl -X POST -H "Content-Type: application/json" \
     -d '{"cid":"mi-cel","name":"Mi Celular","model":"Pixel 8","platform":"phone"}' \
     "http://<ip>:8080/api/device?k=$TOKEN"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Phone can't connect | Run `firewall-admin.bat` as admin once; check both devices are on the same WiFi; disable AP isolation on the router if enabled |
| URL says `127.0.0.1` | No default route detected — get the LAN IP with `ipconfig` (Windows) / `ifconfig` (Mac/Linux) and use it manually |
| Link stops working after router restart | The DHCP IP changed — set a static IP on the computer or a DHCP reservation in the router |
| Port 8080 busy | Use `python server.py --port 9000` and open the new URL |
| Page shows "Enlace sin acceso" | The URL is missing `?k=...` — use the full URL you were given, or the token was cleared (clear site data and open the full URL again) |
| Upload fails with 503 | Too many simultaneous uploads — wait and retry (max 3 at once) |

## Project structure

```
v-drop/
├─ server.py            # the whole server (Python stdlib only)
├─ start.bat            # Windows launcher
├─ firewall-admin.bat   # one-time Windows firewall rule (run as admin)
├─ public/
│  ├─ index.html        # the web app (vanilla JS, PWA)
│  └─ static/           # icons + artwork
├─ test/
│  └─ v2_smoke.py       # end-to-end smoke test
├─ uploads/             # received files (created at runtime)
└─ data/                # token, history, devices, transfers (created at runtime)
```

## License

MIT — see [LICENSE](LICENSE). Built by [Juan Pareja](https://github.com/JuanParejaGutierrez)
with Alfred Protocol.
