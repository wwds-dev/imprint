"""What a release kit will make, on which routes, and what it may cost (spec A1, A4, D2).

Qt-free. Slice 1 is the free path: every step runs on this Mac, the audiobook
is "Not included", and a paid route anywhere blocks the estimate with
"not in this version". The money side of A1 (job reservation, caps table)
arrives in slice 2.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from agents.manuscript.content_calendar import build_calendar
from agents.manuscript.quote_finder import (
    MAX_QUOTE_CHARS, MAX_QUOTES, WHOLE_TEXT_LIMIT, WINDOW_COUNT)
from services.providers import is_local


@dataclass(frozen=True)
class Stage:
    key: str
    ordinal: int
    label: str
    agent: str


STAGES: tuple[Stage, ...] = (
    Stage("epub", 1, "EPUB", "manuscript"),
    Stage("audiobook", 2, "Audiobook", "audiobook"),
    Stage("quotes", 3, "Quotes", "manuscript"),
    Stage("calendar", 4, "Calendar", "manuscript"),
    Stage("graphics", 5, "Quote graphics", "manuscript"),
    Stage("shorts", 6, "Shorts", "manuscript"),
    Stage("captions", 7, "Captions and CSV", "manuscript"),
    Stage("link", 8, "Link and report", "manuscript"),
)
STAGE_BY_KEY = {s.key: s for s in STAGES}

CALENDAR_WEEKS = 4                       # owner decision 2: 28 days
PLATFORMS = ("TikTok", "Instagram", "Pinterest")
CAPTION_SLOT_CHARS = 600                 # 280 × 2 JSON escaping + 40 for keys
CAPTION_OUTPUT_TOKENS = 8192

# Legal L1: the Shorts voice is a route value, never chosen from the
# environment. `system` = macOS `say`; `none` and `elevenlabs` come later.
SYSTEM_VOICE_ROUTE = "system"
DEFAULT_SHORTS_VOICE_ROUTE = SYSTEM_VOICE_ROUTE
DEFAULT_SYSTEM_VOICE = "Samantha"        # what MockVoiceProvider uses for "default"

LOCAL_NO_CHARGE = "local, no charge"

# Draft notice wording from docs/audit/one-click-release-legal-consult.md.
# The wording stays the owner's or a lawyer's; ids are recorded in plan_json.
NOTICES = {
    "N2": ("Apple's macOS licence limits its built-in voices to personal, "
           "non-commercial use. Decide before posting these Shorts publicly."),
    "N5": ("This kit contains AI-generated captions and quote choices. "
           "See the report."),
}


def is_local_route(provider: str) -> bool:
    """A route that makes no paid provider call: a local model runtime or
    the on-device voice."""
    return provider == SYSTEM_VOICE_ROUTE or is_local(provider)


@dataclass
class Route:
    provider: str = ""
    model: str = ""
    voice: str = ""


@dataclass
class KitPlan:
    project_id: str
    project_name: str
    version: int
    title: str
    byline: str
    source_sha256: str
    words: int
    characters: int
    output_dir: str
    quotes: Route = field(default_factory=Route)
    captions: Route = field(default_factory=Route)
    shorts: Route = field(default_factory=lambda: Route(
        DEFAULT_SHORTS_VOICE_ROUTE, "", DEFAULT_SYSTEM_VOICE))
    start_date: date = field(default_factory=date.today)
    platforms: list[str] = field(default_factory=lambda: list(PLATFORMS))
    weeks: int = CALENDAR_WEEKS
    project_instructions: str = ""

    def to_json(self) -> dict:
        data = asdict(self)
        data["start_date"] = self.start_date.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict) -> "KitPlan":
        data = dict(data)
        for name in ("quotes", "captions", "shorts"):
            data[name] = Route(**data.get(name, {}))
        data["start_date"] = date.fromisoformat(data["start_date"])
        data["platforms"] = list(data.get("platforms") or [])
        return cls(**data)

    def route_for(self, stage: str) -> Route:
        if stage in ("quotes", "captions", "shorts"):
            return getattr(self, stage)
        if stage == "audiobook":
            return Route()
        return Route("local", "", "")


@dataclass
class EstimateRow:
    stage: str
    label: str
    route: str
    basis: str
    maximum: str
    route_kind: str = "local"            # local · not_included
    notices: list[str] = field(default_factory=list)

    @property
    def accessible(self) -> str:
        return f"{self.label}, {self.route}, {self.maximum}"


@dataclass
class KitEstimate:
    rows: list[EstimateRow]
    blocked: list[tuple[str, str]]       # (stage, sentence)
    total_eur: float = 0.0
    slots: int = 0
    shorts: int = 0
    graphic_slots: int = 0

    @property
    def figure(self) -> str:
        if self.blocked:
            return "Cannot start"
        return "No charge"

    @property
    def caption(self) -> str:
        return "EVERY STEP RUNS ON THIS MAC"

    @property
    def start_label(self) -> str:
        return "Start"

    @property
    def can_start(self) -> bool:
        return not self.blocked

    def signature(self) -> tuple:
        """What the owner saw, compared again when Start is pressed."""
        return (tuple((r.stage, r.route, r.basis, r.maximum) for r in self.rows),
                tuple(self.blocked), round(self.total_eur, 6))

    def notices_shown(self) -> list[str]:
        return sorted({n for r in self.rows for n in r.notices})


def calendar_counts(plan: KitPlan) -> tuple[int, int, int]:
    """(slots, Short slots, graphic slots) for the plan's window and platforms."""
    slots = build_calendar(["q"], plan.weeks, plan.start_date, plan.platforms)
    shorts = sum(1 for s in slots if s.format == "short")
    return len(slots), shorts, len(slots) - shorts


def _route_text(route: Route) -> str:
    runtime = {"ollama": "Ollama", "lmstudio": "LM Studio"}.get(
        route.provider, route.provider)
    return f"{runtime} · {route.model}, on this Mac" if route.model else runtime


def estimate(plan: KitPlan) -> KitEstimate:
    """Slice 1: every row is local or not included; anything else blocks."""
    slots, shorts, graphic_slots = calendar_counts(plan)
    passages = 1 if plan.characters <= WHOLE_TEXT_LIMIT else WINDOW_COUNT
    blocked: list[tuple[str, str]] = []

    def text_row(stage: str, label: str, route: Route, basis: str) -> EstimateRow:
        if not route.provider or not route.model:
            blocked.append((stage, "no local model answered. Start Ollama or "
                                   "LM Studio, then press Check again."))
        elif not is_local(route.provider):
            blocked.append((stage, f"{label} uses {route.provider}, a paid "
                                   "route. This version runs local steps only."))
        return EstimateRow(stage, label, _route_text(route), basis,
                           LOCAL_NO_CHARGE)

    rows = [
        EstimateRow("epub", "EPUB", "EbookLib, on this Mac",
                    f"1 file from version {plan.version}", LOCAL_NO_CHARGE),
        EstimateRow("audiobook", "Audiobook", "Not included",
                    "Narration is always paid, and this screen cannot approve "
                    "paid steps yet. Narrate in Booth.", "—",
                    route_kind="not_included"),
        text_row("quotes", "Quotes", plan.quotes,
                 f"Up to {MAX_QUOTES} quotes from {passages} "
                 f"passage{'s' if passages != 1 else ''} across the whole "
                 f"book · one reply capped at {CAPTION_OUTPUT_TOKENS:,} tokens"),
        EstimateRow("calendar", "Calendar",
                    f"{plan.weeks} weeks ({plan.weeks * 7} days) from "
                    f"{plan.start_date.isoformat()}",
                    f"{slots} posts: {shorts} Shorts, {graphic_slots} graphic posts",
                    LOCAL_NO_CHARGE),
        EstimateRow("graphics", "Quote graphics", "On this Mac",
                    f"One per unique quote: up to {MAX_QUOTES}", LOCAL_NO_CHARGE),
    ]
    shorts_row = EstimateRow(
        "shorts", "Shorts",
        f"On-device voice (macOS) · {plan.shorts.voice or DEFAULT_SYSTEM_VOICE}",
        f"{shorts} Shorts, narration up to {MAX_QUOTE_CHARS} characters each",
        LOCAL_NO_CHARGE)
    if plan.shorts.provider == SYSTEM_VOICE_ROUTE:
        shorts_row.notices.append("N2")
    else:
        blocked.append(("shorts", "Shorts can use only the on-device voice in "
                                  "this version."))
    rows.append(shorts_row)
    rows.append(text_row(
        "captions", "Captions and CSV", plan.captions,
        f"{slots} captions in one request · reply capped at "
        f"{CAPTION_OUTPUT_TOKENS:,} tokens"))
    rows.append(EstimateRow("link", "Link and report", "On this Mac",
                            f"Every file linked to {plan.project_name}",
                            LOCAL_NO_CHARGE))
    if not plan.platforms:
        blocked.append(("calendar", "choose at least one platform for the "
                                    "calendar."))
    if not plan.title.strip() or not plan.byline.strip():
        blocked.append(("epub", f"Version {plan.version} has no title or "
                                "byline. Set them in the Project, then approve "
                                "a new version."))
    return KitEstimate(rows, blocked, 0.0, slots, shorts, graphic_slots)


def blocking_sentence(estimate_: KitEstimate) -> str:
    """The one "Cannot start:" line above the buttons (D2)."""
    if not estimate_.blocked:
        return ""
    _stage, reason = estimate_.blocked[0]
    return "Cannot start: " + reason[:1].upper() + reason[1:]


def safe_name(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_") or "release_kit"


def default_output_dir(base: Path, title: str, version: int,
                       today: date | None = None) -> Path:
    """A new folder `<Title>_v<version>_<date>` under `base`, never reused."""
    today = today or date.today()
    stem = f"{safe_name(title)}_v{version}_{today.isoformat()}"
    candidate = Path(base) / stem
    n = 2
    while candidate.exists():
        candidate = Path(base) / f"{stem}-{n}"
        n += 1
    return candidate


def output_dir_problem(path: Path | str) -> str:
    """Empty when the folder can be used; else the D2 "Cannot start" reason."""
    path = Path(path)
    if path.exists():
        if not path.is_dir():
            return f"Imprint cannot write to {path}."
        if any(path.iterdir()):
            return f"{path} already has files. Choose a new folder."
        return "" if os.access(path, os.W_OK) else f"Imprint cannot write to {path}."
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return "" if os.access(parent, os.W_OK) else f"Imprint cannot write to {path}."
