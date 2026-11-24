# Security Policy

## Threat model

V Drop is a **local-network file transfer hub**. It is designed for trusted home
and office LANs and makes no attempt to be a hardened internet service.

- **Trusted network assumption:** anyone who can reach the server on your LAN and
  knows the token can upload and download files. The token is the only gate.
- **No TLS:** traffic is plain HTTP. Do not expose the server to the internet
  (no port forwarding, no reverse proxy without adding TLS yourself).
- **No user accounts:** there is no multi-user authorization beyond the shared token.

## Hardening built-in

| Control | Detail |
|---|---|
| Access token | Random 72-bit token (`os.urandom(9)`), compared with `hmac.compare_digest`. Accepted via `?k=` query or `X-Alfred-Token` header. |
| Public shell only | `/`, `/manifest.json` and `/static/*` are public (HTML/CSS/JS needed by the PWA, no data). **The token never appears in the manifest.** Every API endpoint is token-gated. |
| Token storage | The web app keeps the token in `localStorage` (saved on first visit) and sends it as a header; the installed PWA opens `/` and works from storage. Clear site data to remove it. |
| Host validation | Requests with an unexpected `Host` header are rejected (403) — mitigates DNS-rebinding. Allowed: the LAN IP, `localhost`, the machine hostname and `*.local`. |
| Streaming uploads | Multipart bodies are parsed incrementally (bounded memory ~1 MB) and written straight to disk — a 10 GB file does not load into RAM. |
| Upload limits | Max 10 GB per file/request, max 3 concurrent uploads (503 beyond), socket read timeout 30 s. |
| Connection limits | Max 64 concurrent connections, max 3 SSE streams per device (429 beyond). |
| Device limits | Max 100 registered devices; `devices.json` is only written when a device actually changes. |
| Transfer limits | Max 10 pending transfers per recipient (429 beyond); pendings expire (declined) after 6 h; records removed after 24 h. |
| Recipient binding | A transfer records the recipient's IP at creation; accept/decline/download verify the caller's IP matches the registered device (prevents cid spoofing). |
| Download control | Transfers require the receiver to accept first; only the recipient can download. |
| Symlink guard | File serving resolves `realpath` and refuses paths outside `uploads/`. |
| Path traversal | Filenames are basename-sanitized; `../` and path separators are stripped. |
| XSS | All network-derived strings (device/file names) are rendered with `esc()` (textContent); a Content-Security-Policy meta tag restricts resources to same-origin. |
| No info leakage | Errors are generic; responses never expose server paths. |

## Known limitations (by design)

| Item | Detail |
|---|---|
| Token in URL | The token can travel in the query string (`?k=...`) when shared as a link. It can appear in browser history and local server logs. Acceptable on a private LAN; treat the URL as a password. The API also accepts the token as a header. |
| No encryption at rest | Files in `uploads/` are stored as-is, readable by any local user of the host machine. |
| Shared-token access | Any device with the URL can upload. There is no per-device ACL. |
| HTTP plaintext | No TLS. On an open or compromised WiFi, another host could sniff traffic. WPA2 encrypts the radio link, not host-to-host traffic. |
| Global history delete | Any token holder can clear the global delivery history (intentional: single-household tool). |
| DoS residual | A malicious peer on the LAN can still fill the disk (each file capped at 10 GB) — acceptable for home use; do not expose publicly. |

## Safe deployment checklist

1. Keep the server **behind your router's NAT** — never port-forward 8080.
2. Share the URL only with people/devices you trust.
3. Run on a machine you control (the laptop is fine).
4. If you need access from outside your home, use a **VPN** (Tailscale/WireGuard)
   instead of exposing the port.
5. Set a static IP / DHCP reservation so the URL stays stable.
6. If you ever delete `data/token.txt`, a new token is generated — share the new URL.

## Reporting a vulnerability

If you find a security issue, please **open a GitHub issue** with the details
(do not include real files or tokens). Include:

- The endpoint / file involved
- A minimal reproduction (concept only, no live exploit data)
- Suggested fix, if you have one

Issues are reviewed by the maintainer. Please give reasonable time before any
public disclosure.
