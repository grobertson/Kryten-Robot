import os
import subprocess

# List of directories to process
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
commit_message = "Migrate to UV package management"

for directory in directories:
    full_path = os.path.join(base_dir, directory)
    
    if not os.path.isdir(full_path):
        print(f"Skipping {directory}: Not a directory")
        continue

    # Check if it's a git repository
    if not os.path.isdir(os.path.join(full_path, ".git")):
        print(f"Skipping {directory}: Not a git repository")
        continue

    print(f"Processing {directory}...")
    
    try:
        # Git Add
        subprocess.run(["git", "add", "."], cwd=full_path, check=True)
        
        # Git Commit
        # Check if there are changes to commit first
        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=full_path, capture_output=True, text=True)
        if status_result.stdout.strip():
            subprocess.run(["git", "commit", "-m", commit_message], cwd=full_path, check=True)
            print(f"  Committed changes in {directory}")
        else:
            print(f"  No changes to commit in {directory}")

        # Git Push
        subprocess.run(["git", "push", "origin", "main"], cwd=full_path, check=True)
        print(f"  Pushed {directory} to origin/main")

    except subprocess.CalledProcessError as e:
        print(f"  Error processing {directory}: {e}")
    except Exception as e:
        print(f"  Unexpected error in {directory}: {e}")

print("Done processing all directories.")
