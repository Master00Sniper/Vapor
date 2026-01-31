# utils/logging.py
# Shared logging functionality for Vapor application

import os
import time
from utils.constants import DEBUG_LOG_FILE, MAX_LOG_SIZE


def log(message, category="INFO"):
    """
    Print timestamped log message with category and write to log file.

    Args:
        message: The message to log
        category: Category label (e.g., INFO, ERROR, STEAM, TEMP, etc.)
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{category}] {message}"

    # Print to console (if available)
    try:
        print(formatted)
    except (OSError, ValueError):
        # Handle case where console has been freed
        pass

    # Also write to log file
    try:
        # Check if log file is too large and truncate if needed
        if os.path.exists(DEBUG_LOG_FILE):
            if os.path.getsize(DEBUG_LOG_FILE) > MAX_LOG_SIZE:
                # Keep last 1000 lines
                with open(DEBUG_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-1000:]
                with open(DEBUG_LOG_FILE, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{formatted}\n")
    except Exception:
        pass
