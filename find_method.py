
file_path = r"d:\Devel\kryten-py\src\kryten\client.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

if "def _send_command" in content:
    print("Found definition of _send_command")
    # Print context
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "def _send_command" in line:
            print(f"Line {i+1}: {line}")
            # Print next few lines
            for j in range(1, 20):
                if i+j < len(lines):
                    print(f"Line {i+1+j}: {lines[i+j]}")
            break
else:
    print("Definition of _send_command NOT found")

if "def __send_command" in content:
    print("Found definition of __send_command")
