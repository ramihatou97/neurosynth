import sys
import os
from pathlib import Path
import subprocess

# Paths
current_dir = Path(__file__).resolve().parent    # neurosynth/
ref_lib_dir = current_dir / "reference-library"  # neurosynth/reference-library/
deep_dx_src = current_dir / "src"                # neurosynth/src/

# Verify paths
if not ref_lib_dir.exists():
    print(f"Error: Could not find reference-library at {ref_lib_dir}")
    sys.exit(1)

# Entry point is main.py
main_py = ref_lib_dir / "main.py"
if not main_py.exists():
    print(f"Error: Could not find main.py at {main_py}")
    sys.exit(1)

print("🚀 Launching Deep-DX UI Integration...")
print(f"Working Directory: {current_dir}")
print(f"Deep-DX Libraries: {deep_dx_src}")
print(f"UI Entry Point:    {main_py}")

# Prepare Environment
env = os.environ.copy()

# Critical: Add neurosynth/src to PYTHONPATH so 'deep_dx', 'index', 'ai' can be imported directly
# We do NOT add 'neurosynth' root, to avoid 'src' naming conflict.
# By adding 'neurosynth/src', we expose its children (deep_dx) as top-level modules.
current_python_path = env.get("PYTHONPATH", "")
env["PYTHONPATH"] = f"{deep_dx_src}:{current_python_path}"

# Launch
try:
    # Run python with the main.py script
    subprocess.run([sys.executable, str(main_py)], env=env, cwd=str(ref_lib_dir), check=True)
except subprocess.CalledProcessError as e:
    print(f"Application exited with code: {e.returncode}")
except KeyboardInterrupt:
    print("\nStopped.")
