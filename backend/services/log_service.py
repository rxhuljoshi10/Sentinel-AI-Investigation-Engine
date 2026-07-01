MAX_LOG_CHARS = 3000

def extract_log_content(raw_bytes: bytes) -> str:
    """
    Decodes raw file bytes and truncates to fit LLM context window.
    """
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = raw_bytes.decode("latin-1")

    content = content.strip()

    if len(content) > MAX_LOG_CHARS:
        content = content[-MAX_LOG_CHARS:]
        content = f"[Log truncated to last {MAX_LOG_CHARS} chars]\n\n" + content

    return content