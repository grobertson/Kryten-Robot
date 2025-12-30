
file_path = r"D:\Devel\kryten-py\src\kryten\client.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "def __send_command" in content:
    print("Found 'def __send_command'")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "def __send_command" in line:
            print(f"Line {i+1}: {line}")
else:
    print("Did not find 'def __send_command'")
