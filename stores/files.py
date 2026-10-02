"""Write scrape artifacts even when the working directory is not writable."""

import logging
import os
import shutil

logger = logging.getLogger("stores")


def safe_write_file(filename, content, mode="w"):
    try:
        with open(filename, mode, encoding="utf-8") as handle:
            handle.write(content)
        logger.info("Successfully wrote to file: %s", filename)
        return True
    except (IOError, PermissionError) as exc:
        logger.error("Permission error writing to %s: %s", filename, exc)
        try:
            tmp_filename = os.path.join("/tmp", os.path.basename(filename))
            with open(tmp_filename, mode, encoding="utf-8") as handle:
                handle.write(content)
            logger.info("Wrote to alternate location: %s", tmp_filename)
            try:
                shutil.copy(tmp_filename, filename)
                logger.info("Copied from %s to %s", tmp_filename, filename)
                return True
            except Exception as copy_error:
                logger.error("Couldn't copy from temp to original: %s", copy_error)
                return False
        except Exception as tmp_error:
            logger.error("Could not write to temp location either: %s", tmp_error)
            return False
