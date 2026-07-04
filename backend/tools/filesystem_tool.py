import os
import aiofiles

ALLOWED_LOG_DIRS = [
    "./logs",
    "./data/logs",
    "C:/logs",
]

async def read_log_file(file_path: str) -> dict:
    """
    Reads a log file from the filesystem.
    Only allows reading from pre-approved directories for security.
    """
    try:
        # Security check — only read from allowed directories
        abs_path = os.path.abspath(file_path)
        allowed = any(
            abs_path.startswith(os.path.abspath(d))
            for d in ALLOWED_LOG_DIRS
        )

        if not allowed:
            return {
                "success": False,
                "error": f"Access denied. Only logs from approved directories allowed.",
                "content": ""
            }

        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "content": ""
            }

        async with aiofiles.open(abs_path, mode='r', encoding='utf-8') as f:
            content = await f.read()

        # Return last 3000 chars — most recent entries
        truncated = content[-3000:] if len(content) > 3000 else content

        return {
            "success": True,
            "file_path": file_path,
            "total_chars": len(content),
            "content": truncated,
            "truncated": len(content) > 3000
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": ""
        }