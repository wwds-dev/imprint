"""Small shared rules for Drive paths and Imprint progress sidecars."""

import hashlib
from pathlib import PurePosixPath


ALLOWED_EXTENSIONS = {".epub", ".pdf", ".txt", ".mobi"}


def ebook_parts(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or path.startswith("/") or "\\" in path or len(path) > 1000:
        raise ValueError("Choose a supported ebook inside My Drive/ebooks.")
    parts = PurePosixPath(path).parts
    if (not parts or len(parts) > 12 or any(part in (".", "..", "") for part in parts)
            or PurePosixPath(path).suffix.lower() not in ALLOWED_EXTENSIONS):
        raise ValueError("Choose a supported ebook inside My Drive/ebooks.")
    return parts


def progress_filename(name: str, size: int | str) -> str:
    digest = hashlib.sha256(f"{name}\n{size}".encode()).hexdigest()
    return f"{digest}.json"


def updated_progress(current: dict, name: str, position_ms: int,
                     duration_ms: int, title: str, timestamp: str) -> dict:
    """Keep Imprint's saved marks while advancing its shared playhead."""
    position = max(0, int(position_ms))
    duration = max(0, int(duration_ms)) or max(0, int(current.get("duration_ms", 0)))
    return {**current, "version": 1, "file_name": name,
            "title": title[:200], "position_ms": position,
            "duration_ms": duration,
            "finished": bool(duration and position >= duration * 0.99),
            "last_played": timestamp}
