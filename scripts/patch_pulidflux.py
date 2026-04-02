"""Patch ComfyUI-PuLID-Flux to add missing timestep_zero_index parameter."""
import sys
from pathlib import Path

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/comfyui/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py")
text = target.read_text()

if "timestep_zero_index" in text:
    print("Already patched, skipping.")
    sys.exit(0)

old = "        control = None,"
new = "        control = None,\n        timestep_zero_index=None,"

if old not in text:
    print("ERROR: Could not find patch target in pulidflux.py", file=sys.stderr)
    sys.exit(1)

target.write_text(text.replace(old, new, 1))
print("Patched pulidflux.py: added timestep_zero_index parameter.")
