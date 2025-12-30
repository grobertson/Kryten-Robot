
import os

file_path = r"d:\Devel\kryten-playlist\kryten_playlist\service.py"

# The duplicated block
duplicate_block = """        uv_cfg = uvicorn.Config(
            app,
            host=self.config.http_host,
            port=self.config.http_port,
            log_level=self.config.http_log_level,
            timeout_keep_alive=5,
        )
        self._web_server = uvicorn.Server(uv_cfg)"""

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# We expect to find this block twice. We want to remove one of them.
# content.count(duplicate_block) should be 2.

count = content.count(duplicate_block)
print(f"Found {count} occurrences of the duplicate block.")

if count >= 2:
    # Remove the last occurrence
    # We can split by the block and join back, keeping only the first one
    # Or just replace the first occurrence with itself and the second with empty string?
    # Easier: find the index of the second occurrence.
    
    first_idx = content.find(duplicate_block)
    second_idx = content.find(duplicate_block, first_idx + len(duplicate_block))
    
    if second_idx != -1:
        # Construct new content: everything up to second_idx, then skip the block, then everything after
        # But we need to handle the newline/indentation potentially.
        # The block string above includes indentation but not leading/trailing newlines.
        
        # Let's check if there's an extra newline between them.
        # In the file:
        # block 1
        # <newline>
        # block 2
        
        # If we remove block 2, we might leave extra empty lines. That's fine.
        
        new_content = content[:second_idx] + content[second_idx + len(duplicate_block):]
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Successfully removed duplicate initialization.")
    else:
        print("Could not find second occurrence.")
else:
    print("Not enough occurrences to remove.")
