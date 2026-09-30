"""The audiobook library, and where the listener stopped.

The Narrator converts an ebook into one merged MP3 per book and writes it to
the configured output folder. Until now the app forgot about it the moment the
conversion finished — the file existed and nothing in the tool could find it,
list it, or play it.

Local resume position is keyed by file path. When Google Drive storage is
selected, each audiobook gets a JSON record in the chosen synced folder so
the listening position and saved marks can travel with the library.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.database import get_connection, get_setting, save_setting

AUDIO_SUFFIXES = {".mp3", ".m4a", ".m4b", ".wav", ".aac", ".flac", ".ogg"}

# Past this, treat the book as finished rather than resuming three seconds
# before the end and immediately stopping.
FINISHED_FRACTION = 0.99
PROGRESS_MODE_KEY = "audiobook_progress_mode"
PROGRESS_FOLDER_KEY = "audiobook_progress_folder"
PROGRESS_DIR = "Imprint Progress"


@dataclass
class Audiobook:
    path: Path
    title: str
    size_bytes: int
    position_ms: int = 0
    duration_ms: int = 0
    finished: bool = False
    last_played: str = ""

    @property
    def progress(self) -> float:
        if not self.duration_ms:
            return 0.0
        return min(1.0, self.position_ms / self.duration_ms)

    @property
    def started(self) -> bool:
        return self.position_ms > 0 and not self.finished


@dataclass(frozen=True)
class ChapterMark:
    title: str
    position_ms: int
    source: str  # embedded | saved


def progress_storage() -> tuple[str, Path | None]:
    """Return the selected store and the synced folder, when selected."""
    mode = get_setting(PROGRESS_MODE_KEY, "local")
    folder = get_setting(PROGRESS_FOLDER_KEY, "")
    return ("drive" if mode == "drive" else "local",
            Path(folder).expanduser() if folder else None)


def _shared_record_path(path: Path, folder: Path | None = None) -> Path:
    folder = folder or progress_storage()[1]
    if folder is None or not folder.is_dir():
        raise FileNotFoundError("The selected audiobook Google Drive folder is unavailable.")
    media = Path(path)
    # The same audio file can be under different local paths on another Mac or
    # in a phone player. Keep machine-specific paths out of the shared ID.
    identity = media.name
    size = media.stat().st_size if media.exists() else 0
    digest = hashlib.sha256(f"{identity}\n{size}".encode()).hexdigest()
    return folder / PROGRESS_DIR / f"{digest}.json"


def _read_shared(path: Path, folder: Path | None = None) -> dict | None:
    record_path = _shared_record_path(path, folder)
    if not record_path.exists():
        return None
    data = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"Invalid Imprint progress file: {record_path}")
    return data


def _write_shared(path: Path, data: dict, folder: Path | None = None) -> None:
    record_path = _shared_record_path(path, folder)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "file_name": Path(path).name, **data}
    temporary = record_path.with_name(f".{record_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        temporary.replace(record_path)
    finally:
        temporary.unlink(missing_ok=True)


def _local_progress(path: Path) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM audiobook_progress WHERE path = ?", (str(path),)
        ).fetchone()
    return dict(row) if row else None


def _local_marks(path: Path) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT title, position_ms, created_at FROM audiobook_marks "
            "WHERE path = ? ORDER BY position_ms", (str(path),)
        ).fetchall()
    return [dict(row) for row in rows]


def configure_progress_storage(mode: str, folder: Path | None,
                               books: list[Path]) -> None:
    """Switch stores, copying each visible book only if the target is empty."""
    if mode not in {"local", "drive"}:
        raise ValueError("Unknown audiobook progress storage mode")
    if mode == "drive":
        if folder is None or not Path(folder).is_dir():
            raise FileNotFoundError("Choose an existing Google Drive audiobook folder.")
        folder = Path(folder).expanduser()
        current_mode, current_folder = progress_storage()
        if (current_mode == "drive" and current_folder is not None and
                not current_folder.is_dir()):
            raise FileNotFoundError(
                "Reconnect the previous Google Drive audiobook folder before "
                "changing folders, so current progress can be copied.")
        for path in books:
            if _read_shared(path, folder) is not None:
                continue
            data = (_read_shared(path, current_folder)
                    if current_mode == "drive" and current_folder is not None
                    and current_folder.is_dir() else None)
            if data is None:
                row = _local_progress(path)
                marks = _local_marks(path)
                if row or marks:
                    data = {
                        "title": (row or {}).get("title", ""),
                        "position_ms": (row or {}).get("position_ms", 0),
                        "duration_ms": (row or {}).get("duration_ms", 0),
                        "finished": bool((row or {}).get("finished", 0)),
                        "last_played": (row or {}).get("last_played", ""),
                        "marks": marks,
                    }
            if data is not None:
                _write_shared(path, data, folder)
        save_setting(PROGRESS_FOLDER_KEY, str(folder))
    else:
        current_mode, current_folder = progress_storage()
        if current_mode == "drive" and (current_folder is None or
                                        not current_folder.is_dir()):
            raise FileNotFoundError(
                "Reconnect the Google Drive audiobook folder before switching "
                "to local storage, so current progress can be copied.")
        if current_folder is not None and current_folder.is_dir():
            for path in books:
                data = _read_shared(path, current_folder)
                if data is None:
                    continue
                with get_connection() as conn:
                    conn.execute("""
                        INSERT INTO audiobook_progress
                          (path, title, position_ms, duration_ms, finished, last_played)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT(path) DO UPDATE SET
                          title=excluded.title, position_ms=excluded.position_ms,
                          duration_ms=excluded.duration_ms, finished=excluded.finished,
                          last_played=excluded.last_played
                    """, (str(path), data.get("title", ""),
                          int(data.get("position_ms", 0)),
                          int(data.get("duration_ms", 0)),
                          int(bool(data.get("finished", False))),
                          data.get("last_played", "")))
                    conn.execute("DELETE FROM audiobook_marks WHERE path = ?",
                                 (str(path),))
                    for mark in data.get("marks", []):
                        conn.execute("""
                            INSERT INTO audiobook_marks
                              (path, position_ms, title, created_at)
                            VALUES (?,?,?,?)
                        """, (str(path), int(mark["position_ms"]), mark["title"],
                              mark.get("created_at", "")))
                    conn.commit()
    save_setting(PROGRESS_MODE_KEY, mode)


def embedded_chapters(path: Path) -> list[ChapterMark]:
    """Read actual chapter timestamps from the audio container, if present."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=10, check=True,
        )
        raw = json.loads(result.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    chapters = []
    for index, row in enumerate(raw.get("chapters") or [], start=1):
        try:
            position = max(0, int(float(row["start_time"]) * 1000))
        except (KeyError, TypeError, ValueError):
            continue
        title = (row.get("tags") or {}).get("title") or f"Chapter {index}"
        chapters.append(ChapterMark(str(title), position, "embedded"))
    return chapters


def saved_marks(path: Path) -> list[ChapterMark]:
    mode, _ = progress_storage()
    if mode == "drive":
        rows = (_read_shared(path) or {}).get("marks", [])
    else:
        rows = _local_marks(path)
    return [ChapterMark(row["title"], int(row["position_ms"]), "saved")
            for row in rows]


def save_mark(path: Path, position_ms: int, title: str) -> None:
    if position_ms < 0 or not title.strip():
        raise ValueError("A mark needs a non-negative position and a title.")
    if progress_storage()[0] == "drive":
        data = _read_shared(path) or {}
        marks = [mark for mark in data.get("marks", [])
                 if int(mark["position_ms"]) != int(position_ms)]
        marks.append({"position_ms": int(position_ms), "title": title.strip(),
                      "created_at": datetime.now().isoformat(timespec="seconds")})
        data["marks"] = sorted(marks, key=lambda mark: mark["position_ms"])
        _write_shared(path, data)
        return
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO audiobook_marks (path, position_ms, title, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path, position_ms) DO UPDATE SET title = excluded.title
        """, (str(path), int(position_ms), title.strip(),
              datetime.now().isoformat(timespec="seconds")))
        conn.commit()


def delete_mark(path: Path, position_ms: int) -> None:
    if progress_storage()[0] == "drive":
        data = _read_shared(path) or {}
        data["marks"] = [mark for mark in data.get("marks", [])
                         if int(mark["position_ms"]) != int(position_ms)]
        _write_shared(path, data)
        return
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM audiobook_marks WHERE path = ? AND position_ms = ?",
            (str(path), int(position_ms)))
        conn.commit()


def scan(folder: Path) -> list[Audiobook]:
    """Every audio file in the folder, with any saved progress attached.

    Recursive, because the converter can be pointed at a per-book subfolder.
    """
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return []

    mode, progress_folder = progress_storage()
    if mode == "drive" and (progress_folder is None or
                            not progress_folder.is_dir()):
        raise FileNotFoundError(
            "The selected audiobook Google Drive folder is unavailable.")
    saved = _all_progress() if mode == "local" else {}
    books: list[Audiobook] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_SUFFIXES:
            continue
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue    # vanished between rglob and stat; skip, not crash
        row = (saved.get(str(path), {}) if mode == "local" else
               (_read_shared(path) or _local_progress(path) or {}))
        books.append(Audiobook(
            path=path,
            title=row.get("title") or path.stem.replace("_", " "),
            size_bytes=size_bytes,
            position_ms=row.get("position_ms", 0),
            duration_ms=row.get("duration_ms", 0),
            finished=bool(row.get("finished", 0)),
            last_played=row.get("last_played", ""),
        ))
    return books


def _all_progress() -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM audiobook_progress").fetchall()
    return {row["path"]: dict(row) for row in rows}


def load_position(path: Path) -> int:
    """Where to resume, in milliseconds. 0 for a book that is new or finished."""
    row = ((_read_shared(path) or _local_progress(path))
           if progress_storage()[0] == "drive" else _local_progress(path))
    if not row or row["finished"]:
        return 0
    return int(row["position_ms"] or 0)


def save_position(path: Path, position_ms: int, duration_ms: int = 0,
                  title: str = "") -> None:
    """Record the playhead.

    A book played to the end is marked finished rather than left parked at the
    last second, so the next play starts from the beginning instead of
    resuming and stopping immediately.
    """
    position_ms = max(0, int(position_ms))
    duration_ms = max(0, int(duration_ms))
    if progress_storage()[0] == "drive":
        data = _read_shared(path) or {}
        effective_duration = duration_ms or int(data.get("duration_ms", 0))
        data.update({
            "title": title or data.get("title", ""),
            "position_ms": position_ms,
            "duration_ms": effective_duration,
            "finished": bool(effective_duration and
                             position_ms >= effective_duration * FINISHED_FRACTION),
            "last_played": datetime.now().isoformat(timespec="seconds"),
        })
        _write_shared(path, data)
        return
    finished = bool(duration_ms and position_ms >= duration_ms * FINISHED_FRACTION)
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO audiobook_progress
              (path, title, position_ms, duration_ms, finished, last_played)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
              title=CASE WHEN excluded.title != '' THEN excluded.title
                         ELSE audiobook_progress.title END,
              position_ms=excluded.position_ms,
              duration_ms=CASE WHEN excluded.duration_ms > 0
                               THEN excluded.duration_ms
                               ELSE audiobook_progress.duration_ms END,
              finished=excluded.finished,
              last_played=excluded.last_played
        """, (str(path), title, position_ms, duration_ms, int(finished),
              datetime.now().isoformat(timespec="seconds")))
        conn.commit()


def mark_unfinished(path: Path) -> None:
    """Reset a finished book so it plays from the start again."""
    if progress_storage()[0] == "drive":
        data = _read_shared(path) or {}
        data.update({"position_ms": 0, "finished": False})
        _write_shared(path, data)
        return
    with get_connection() as conn:
        conn.execute(
            "UPDATE audiobook_progress SET finished = 0, position_ms = 0 "
            "WHERE path = ?", (str(path),))
        conn.commit()


def format_time(ms: int) -> str:
    """h:mm:ss, or m:ss for anything under an hour."""
    if ms <= 0:
        return "0:00"
    seconds = int(ms // 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def probe_duration_ms(path: Path) -> int:
    """Duration via ffprobe, or 0 when it is unavailable.

    Only used to show a length before the file has ever been played — once
    QMediaPlayer has loaded it, its own duration is authoritative and cheaper.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=20)
        return int(float(result.stdout.strip()) * 1000)
    except Exception:
        return 0
