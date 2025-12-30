import os
import subprocess

directories = [
    "Kryten-Robot",
    "kryten-bingo",
    "kryten-cli",
    "kryten-clock",
    "kryten-games",
    "kryten-llm",
    "kryten-misc",
    "kryten-moderator",
    "kryten-playlist",
    "kryten-py",
    "kryten-shell",
    "kryten-userstats",
    "kryten-webui"
]

base_dir = r"d:\Devel"
commit_message = "Update documentation for UV migration"

for directory in directories:
    full_path = os.path.join(base_dir, directory)
    
    if not os.path.isdir(full_path):
        continue

    if not os.path.isdir(os.path.join(full_path, ".git")):
        continue

    print(f"Processing {directory}...")
    
    try:
        # Check if there are changes
        status = subprocess.run(["git", "status", "--porcelain"], cwd=full_path, capture_output=True, text=True)
        
        if status.stdout.strip():
            subprocess.run(["git", "add", "."], cwd=full_path, check=True)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=full_path, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=full_path, check=True)
            print(f"  Updated {directory}")
        else:
            print(f"  No changes in {directory}")

    except Exception as e:
        print(f"  Error processing {directory}: {e}")

print("Done.")
