import json
from pathlib import Path

state_file = Path("extraction_state.json")

if state_file.exists():
    with open(state_file) as f:
        data = json.load(f)

    print(f"Current state: {len(data.get('processed_sources', []))} sources processed.")

    # Backup
    with open("extraction_state.json.bak", "w") as f:
        json.dump(data, f, indent=2)
    print("Backup saved to 'extraction_state.json.bak'")

    # Reset
    data["processed_sources"] = []
    data["current_source"] = None
    # We keep images_count or reset it?
    # Resetting it makes sense if we are re-doing it, but maybe we want to track total?
    # Let's keep it to see how many NEW ones we add, or just reset.
    # Actually, let's reset it to start fresh tracking for this run.
    data["images_count"] = 0

    with open(state_file, "w") as f:
        json.dump(data, f, indent=2)

    print("✅ State reset! You can now run the pipeline to re-process everything.")
else:
    print("No state file found.")
