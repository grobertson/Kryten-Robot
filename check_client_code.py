
file_path = r"D:\Devel\kryten-py\src\kryten\client.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "def send_pm" in content:
    print("Found 'def send_pm'")
    # Print context
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "def send_pm" in line:
            print(f"Line {i+1}: {line}")
else:
    print("Did not find 'def send_pm'")

if "def send_chat" in content:
    print("Found 'def send_chat'")
else:
    print("Did not find 'def send_chat'")
