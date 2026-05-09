"""Quick script to find and print the IGT server port and public URL."""
import os
import json
import urllib.request
import sys

out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "port_info.txt")
result = None

for line in os.popen("netstat -ano | findstr LISTENING"):
    if "0.0.0.0:" in line:
        parts = line.strip().split()
        addr = parts[1]  # e.g. "0.0.0.0:57311"
        port = int(addr.split(":")[-1])
        if 10000 < port < 65000:
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/network/info", timeout=2
                )
                data = json.loads(resp.read())
                if "cloudflared_url" in data:
                    result = f"Port: {port}\nLocal: http://localhost:{port}\nPublic: {data['cloudflared_url']}"
                    break
            except Exception:
                pass

if result:
    with open(out_file, "w") as f:
        f.write(result)
    sys.__stdout__.write(result + "\n")
    sys.__stdout__.flush()
else:
    with open(out_file, "w") as f:
        f.write("No IGT server found")
    sys.__stdout__.write("No IGT server found\n")
    sys.__stdout__.flush()
