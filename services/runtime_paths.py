"""Central path resolution for Imprint.

In development (running `python main.py`) every path resolves to the project
root exactly as before — behaviour is unchanged.

When frozen by PyInstaller (`sys.frozen` is set) the app bundle is read-only,
so writable state (SQLite DB, saved chats, logs, editable config, .env) is
redirected to  ~/Library/Application Support/Imprint/  and seeded from
the read-only copies bundled inside the .app on first launch.

Both main.py and services/database.py import from here so they always agree on
where the writable data lives.

APP_NAME decides that directory, so it must differ from Sentinel AI's — the two
apps are separate forks and sharing the name would mean sharing state.

The app was called "Create & Publish" until it was renamed to Imprint. Changing
APP_NAME moves the writable directory, which would have stranded the existing
database, saved chats and — worst — the .env holding the API keys. See
adopt_previous_app_dir().
"""
import os
import sys
import shutil
from pathlib import Path

APP_NAME = "Imprint"

# Directories this app used to write to, newest first. Only ever read from, to
# carry state forward across a rename.
PREVIOUS_APP_NAMES = ("Create & Publish",)


# Set when the last adoption attempt failed and the old directory is still in
# place. user_data_base() then keeps using it for this run, so the keys in its
# .env still work and no blank directory is seeded to block a retry next launch.
ADOPT_FALLBACK: Path | None = None


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def resource_base() -> Path:
    """Read-only bundled resources (README.md, config defaults, assets).

    Frozen: PyInstaller extracts datas next to the executable and exposes the
    root via sys._MEIPASS. Dev: the project root.
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def adopt_previous_app_dir() -> Path | None:
    """Carry a previous name's data directory forward, once.

    Renaming the app moves ~/Library/Application Support/<APP_NAME>/, and the
    user's API keys live in a .env in there — so a rename without this looks
    exactly like "the app forgot everything and lost my keys".

    Renames rather than copies, so there is one directory afterwards and no
    question about which is authoritative. Does nothing if the new directory
    already has content, so it can never overwrite newer state.
    """
    global ADOPT_FALLBACK
    ADOPT_FALLBACK = None
    if not is_frozen():
        return None
    support = Path.home() / "Library" / "Application Support"
    target = support / APP_NAME
    if target.exists() and any(target.iterdir()):
        return None
    for previous in PREVIOUS_APP_NAMES:
        source = support / previous
        if source.is_dir() and any(source.iterdir()):
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                # One atomic step; on POSIX it replaces an empty target dir.
                os.replace(source, target)
            except OSError as exc:
                # Never let a failed carry-forward stop the app starting, and
                # never fall through to a blank directory: that would populate
                # the target and make every later launch skip the adoption.
                print(f"[Paths] Could not adopt {source} -> {target}: {exc}; "
                      f"using {source} for this run, will retry next launch")
                ADOPT_FALLBACK = source
                return None
            return target
    return None


def user_data_base() -> Path:
    """Writable base directory.

    Frozen: ~/Library/Application Support/Imprint  (created if missing).
    Dev:    the project root, so `python main.py` keeps writing in-place.
    """
    if is_frozen():
        adopt_previous_app_dir()
        if ADOPT_FALLBACK is not None and ADOPT_FALLBACK.is_dir():
            return ADOPT_FALLBACK
        d = Path.home() / "Library" / "Application Support" / APP_NAME
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).resolve().parent.parent


def ensure_seeded() -> None:
    """On first frozen launch, copy the bundled read-only defaults into the
    writable user-data directory so the rest of the app can read AND write them.
    No-op in development."""
    if not is_frozen():
        return

    ub = user_data_base()
    rb = resource_base()

    # Seed editable config/ (settings.json is written at runtime).
    dst_config = ub / "config"
    if not dst_config.exists():
        src_config = rb / "config"
        if src_config.exists():
            shutil.copytree(src_config, dst_config)
        else:
            dst_config.mkdir(parents=True, exist_ok=True)

    # Ensure writable data directories exist.
    (ub / "data").mkdir(exist_ok=True)
    (ub / "data" / "chats").mkdir(exist_ok=True)
    (ub / "data" / "logs").mkdir(exist_ok=True)

    # Seed a .env template so the user has one place to paste API keys.
    env_file = ub / ".env"
    if not env_file.exists():
        example = rb / ".env.example"
        if example.exists():
            shutil.copy(example, env_file)
            try:
                env_file.chmod(0o600)
            except OSError:
                print(f"[Paths] Could not restrict {env_file} to 0600")
        else:
            # Created 0600 from the start rather than chmod-ed afterwards.
            fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(
                    "OPENAI_API_KEY=\n"
                    "DEEPSEEK_API_KEY=\n"
                    "KIMI_API_KEY=\n"
                    "GOOGLE_API_KEY=\n"
                    "ANTHROPIC_API_KEY=\n"
                    "DASHSCOPE_API_KEY=\n"
                )
