file_path = r"d:\Devel\kryten-playlist\kryten_playlist\service.py"

old_str = """        if self._catalog_refresh_task is not None:
            logger.debug("Cancelling catalog refresh task")
            self._catalog_refresh_task.cancel()
            with contextlib.suppress(Exception):
                await self._catalog_refresh_task
            logger.debug("Catalog refresh task cancelled")"""

new_str = """        if self._catalog_refresh_task is not None:
            logger.debug("Cancelling catalog refresh task")
            self._catalog_refresh_task.cancel()
            try:
                await asyncio.wait_for(self._catalog_refresh_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("Catalog refresh task timed out or cancelled")
            except Exception as e:
                logger.error(f"Error waiting for catalog refresh task: {e}")
            logger.debug("Catalog refresh task cancelled")"""

with open(file_path, encoding="utf-8") as f:
    content = f.read()

if old_str in content:
    new_content = content.replace(old_str, new_str)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully patched service.py")
else:
    print("Could not find target string in service.py")
