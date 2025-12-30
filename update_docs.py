import os
import re

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
doc_files = ["README.md", "INSTALL.md", "CONTRIBUTING.md", "DEVELOPER.md", "PUBLISHING.md"]

replacements = [
    (r"poetry install", "uv sync"),
    (r"poetry run", "uv run"),
    (r"poetry build", "uv build"),
    (r"poetry publish", "uv publish"),
    (r"poetry shell", "source .venv/bin/activate # or uv run <command>"),
    (r"poetry add", "uv add"),
    (r"poetry remove", "uv remove"),
    (r"poetry lock", "uv lock"),
    (r"pip install", "uv pip install"), # Be careful with this one, maybe context matters
]

# Refined replacements to avoid over-matching "pip install" inside generic instructions
# We will focus on "poetry" replacements primarily as requested.
# For "pip install", if it's "pip install kryten-robot", that's fine for end users.
# If it's "pip install -e .", uv handles that with sync.
# Let's stick to poetry replacements first.

poetry_replacements = [
    (r"poetry install", "uv sync"),
    (r"poetry run", "uv run"),
    (r"poetry build", "uv build"),
    (r"poetry publish", "uv publish"),
    (r"poetry add", "uv add"),
    (r"poetry remove", "uv remove"),
    (r"poetry lock", "uv lock"),
    (r"poetry check", "uv pip check"),
    (r"poetry version", "# Use pyproject.toml to manage version"),
]

def update_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = content
        for pattern, replacement in poetry_replacements:
            new_content = re.sub(pattern, replacement, new_content)
            
        # Specific fix for pip install in dev context if found near poetry
        # new_content = new_content.replace("pip install -e .", "uv pip install -e .")

        if content != new_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path}")
            return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
    return False

total_updated = 0
for directory in directories:
    dir_path = os.path.join(base_dir, directory)
    if not os.path.exists(dir_path):
        continue
        
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file in doc_files:
                full_path = os.path.join(root, file)
                if update_file(full_path):
                    total_updated += 1

print(f"Total files updated: {total_updated}")
