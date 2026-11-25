"""Voice profiles and persona bibles for creator accounts.

Two records that answer "who is this account", kept out of the agent module so
the prompt builder stays about prompts and this stays about storage.

**Voice** is the quality lever. A model asked to write "a caption for a gym
photoset" writes the median internet caption. The same model, given five of the
creator's own posts plus their tone, emoji habits and typical length, writes
something recognisably theirs. Samples do most of the work — the rules mainly
stop it drifting.

**Character** is the consistency lever. The bible is what keeps a written
character the same between sessions, including a locked seed and reference
images so the visuals stay on-model rather than being a different character
every render. It is stored for any account that has one; there is no account
type gating it.
"""

from __future__ import annotations

from datetime import datetime

from services.database import get_connection

# How many samples are worth sending. Beyond a handful the marginal value drops
# and the prompt just gets expensive.
MAX_SAMPLES = 6

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Voice ────────────────────────────────────────────────────────────────────
def load_voice(account_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM creator_voice WHERE account_id = ?",
            (account_id,)).fetchone()
    return dict(row) if row else {}


def save_voice(account_id: int, **fields) -> None:
    allowed = ("samples", "tone", "emoji_style", "banned_words",
               "typical_length", "notes")
    values = {k: (fields.get(k) or "") for k in allowed}
    with get_connection() as conn:
        conn.execute(f"""
            INSERT INTO creator_voice
              (account_id, {", ".join(allowed)}, updated_at)
            VALUES (?, {", ".join("?" * len(allowed))}, ?)
            ON CONFLICT(account_id) DO UPDATE SET
              {", ".join(f"{k}=excluded.{k}" for k in allowed)},
              updated_at=excluded.updated_at
        """, (account_id, *[values[k] for k in allowed], _now()))
        conn.commit()


def voice_block(account_id: int) -> str:
    """The voice half of a prompt, or "" when nothing is recorded.

    Samples come last and are the longest part, because they are what the model
    actually imitates — the rules above them only constrain the drift.
    """
    voice = load_voice(account_id)
    if not voice:
        return ""

    lines: list[str] = []
    if voice.get("tone"):
        lines.append(f"Tone: {voice['tone']}")
    if voice.get("typical_length"):
        lines.append(f"Typical length: {voice['typical_length']}")
    if voice.get("emoji_style"):
        lines.append(f"Emoji: {voice['emoji_style']}")
    if voice.get("banned_words"):
        lines.append(
            f"Never use these words or phrases: {voice['banned_words']}")
    if voice.get("notes"):
        lines.append(f"Other notes: {voice['notes']}")

    samples = [s.strip() for s in (voice.get("samples") or "").splitlines()
               if s.strip()][:MAX_SAMPLES]
    if samples:
        lines.append("")
        lines.append(
            "Here is how this account actually writes. Match the rhythm, "
            "vocabulary and punctuation — not the subject matter:")
        lines += [f"  — {s}" for s in samples]

    if not lines:
        return ""
    return "VOICE\n" + "\n".join(lines)


# ── Persona ──────────────────────────────────────────────────────────────────
def load_persona(account_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM creator_persona WHERE account_id = ?",
            (account_id,)).fetchone()
    return dict(row) if row else {}


def save_persona(account_id: int, **fields) -> None:
    allowed = ("appearance", "backstory", "personality", "boundaries",
               "reference_images")
    # A field the caller does not pass keeps its stored value. The panel saves
    # only the fields it edits, and reference_images has no editor yet — the
    # old dict comprehension replaced every omitted field with "", which wiped
    # reference_images on every save. Passing a field explicitly (even as "")
    # still overwrites it.
    existing = load_persona(account_id)
    values = {
        k: (fields[k] if k in fields else existing.get(k)) or ""
        for k in allowed
    }
    seed = fields["seed"] if "seed" in fields else existing.get("seed")
    with get_connection() as conn:
        conn.execute(f"""
            INSERT INTO creator_persona
              (account_id, {", ".join(allowed)}, seed, updated_at)
            VALUES (?, {", ".join("?" * len(allowed))}, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
              {", ".join(f"{k}=excluded.{k}" for k in allowed)},
              seed=excluded.seed,
              updated_at=excluded.updated_at
        """, (account_id, *[values[k] for k in allowed], seed, _now()))
        conn.commit()


def persona_block(account_id: int) -> str:
    """The character bible, as prompt text."""
    persona = load_persona(account_id)
    if not persona:
        return ""
    lines = []
    for key, label in (("appearance", "Appearance"),
                       ("backstory", "Backstory"),
                       ("personality", "Personality"),
                       ("boundaries", "Never does or says")):
        if persona.get(key):
            lines.append(f"{label}: {persona[key]}")
    if not lines:
        return ""
    return ("CHARACTER — this is a written character, not a real person. "
            "Keep it consistent with the following:\n" + "\n".join(lines))


def persona_seed(account_id: int) -> int | None:
    """The locked generation seed, so visuals stay the same character."""
    return (load_persona(account_id) or {}).get("seed")


def reference_images(account_id: int) -> list[str]:
    raw = (load_persona(account_id) or {}).get("reference_images") or ""
    return [line.strip() for line in raw.splitlines() if line.strip()]


# ── Whose photos ─────────────────────────────────────────────────────────────
# Beside the reference photos the user says whose they are (spec
# reference-photo-consent, owner's option A′ of 2026-11-24). The answer is kept
# in the account's existing `account_type` column: "own" (me), "persona" (a
# made-up character) or "managed" (someone else), with that person's name and
# the date they agreed in `consent_holder` / `consent_date`. This records what
# the user says; it checks nothing about the photos themselves.
PHOTO_SUBJECTS = (
    ("own", "Me"),
    ("persona", "A made-up character"),
    ("managed", "Someone else"),
)
# None is an account dict without the column (the table's default is 'own');
# any other value, the empty string included, needs a record.
NO_RECORD_NEEDED = ("own", "persona", None)
PHOTO_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def photo_path_problem(path: str) -> str:
    """Why this line is not a photo that may be sent, or "".

    Every teaser route reads the listed file and sends its bytes, so a stray
    line (a pasted `.env`, a key file, a symlink named like a photo) would go
    to the provider. Only an absolute path to a regular, non-symlinked file
    with an image suffix and image bytes passes.
    """
    from pathlib import Path
    p = Path(path)
    if not p.is_absolute():
        return "not a full path"
    if p.is_symlink():
        return "a link, not the photo itself"
    if not p.is_file():
        return "no such file"
    if p.suffix.lower() not in PHOTO_SUFFIXES:
        return "not a PNG, JPEG or WebP file"
    try:
        with p.open("rb") as handle:
            head = handle.read(12)
    except OSError:
        return "cannot be read"
    if not (head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8\xff")
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")):
        return "not an image"
    return ""


def consent_date_problem(text: str) -> str:
    """Why the date they agreed is not usable, or ""."""
    from datetime import date
    text = (text or "").strip()
    if not text:
        return "missing"
    try:
        agreed = date.fromisoformat(text)
    except ValueError:
        return "not a year-month-day date"
    if agreed > date.today():
        return "in the future"
    return ""


def photo_consent_refusal(account: dict, references: list) -> str:
    """Why the photos may not be sent, or "" when they may.

    Only someone else's photos need a record: their name and the date they
    agreed, as a past or present year-month-day date. A value no build writes
    counts as someone else, so a hand edit or a typo fails closed. No photos,
    nothing to refuse.
    """
    if not references:
        return ""
    account = account or {}
    if account.get("account_type") in NO_RECORD_NEEDED:
        return ""
    missing = []
    if not str(account.get("consent_holder") or "").strip():
        missing.append("their name")
    # Parsed here too: a hand-edited or old row is not trusted to be a date.
    if consent_date_problem(str(account.get("consent_date") or "")):
        missing.append("the date they agreed")
    if not missing:
        return ""
    return (
        f"Not sent: consent record missing ({' and '.join(missing)}).\n\n"
        "These reference photos are marked as showing someone else. Fill in "
        "who agreed and when under Voice → Reference photos before a teaser "
        "sends them. Nothing was sent or charged.")
