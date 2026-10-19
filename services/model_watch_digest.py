"""What the Model updates tile says about video and image models.

`ModelWatch` remembers; this decides what to show and in which words, so the
tile (`ModelUpdatesCard.set_media`) only paints. One question drives it: will
the video or image route I am about to pay for still work, and is there a
newer one? The most urgent answer leads.

Rows, in order: an offered model a provider stopped listing, or a Seedance
path that is not answering; then shutdown dates, soonest first; then models a
provider lists that Imprint does not offer. Shutdown dates come only from
`media_catalog.MODELS` (`MediaModel.retires`); no date is written here.

Qt-free, so every line of copy is a plain unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from services import media_catalog
from services.media_catalog import human_date

# Shutdowns this close are warnings; further out they are a quiet line.
SHUTDOWN_WARNING_DAYS = 14
# A past shutdown is shown this long after its date, then dropped.
PAST_SHUTDOWN_DAYS = 14

_PROVIDER_LABELS = {name.casefold(): name for name in media_catalog.MEDIA_PROVIDERS}


@dataclass(frozen=True)
class MediaRow:
    kind: str            # removed | not_answering | shutdown | past | new
    text: str            # the sentence (for "new": the detail line)
    warning: bool = False
    accessible_name: str = ""
    provider_label: str = ""   # "new" rows: shown bold above the id
    model_id: str = ""         # "new" rows: shown elided, full in the name


@dataclass(frozen=True)
class MediaDigest:
    headline: str
    rows: tuple[MediaRow, ...] = ()
    warning_count: int = 0
    new_count: int = 0
    dismissable: bool = False  # new or removed media notices
    visible: bool = True


def provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider.casefold(), provider.title())


def _catalog_entry(provider: str, model_id: str):
    return next((m for m in media_catalog.MODELS
                 if m.provider.casefold() == provider.casefold()
                 and m.model_id == model_id), None)


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def group_label(labels: list[str]) -> str:
    """["Veo 3.1", "Veo 3.1 Fast", "Veo 3.1 Lite"] -> "Veo 3.1, Fast and Lite"."""
    if len(labels) == 1:
        return labels[0]
    base, rest = labels[0], labels[1:]
    if all(label.startswith(base + " ") for label in rest):
        return f"{base}, " + _join([label[len(base) + 1:] for label in rest])
    return _join(labels)


def _when(days: int) -> str:
    return "tomorrow" if days == 1 else f"in {days} days"


def _shutdown_rows(today: date) -> list[tuple[int, MediaRow, str]]:
    """(days left, row, headline) per group of models sharing a provider and
    a date; days left is negative for a date already passed."""
    groups: dict[tuple[str, str], list] = {}
    for model in media_catalog.MODELS:
        if model.retires:
            groups.setdefault((model.provider, model.retires), []).append(model)
    found = []
    for (_provider, retires), models in groups.items():
        days = (date.fromisoformat(retires) - today).days
        label = group_label([m.label for m in models])
        when = human_date(retires)
        if days <= 0:
            if -days >= PAST_SHUTDOWN_DAYS:
                continue
            text = (f"{label}: past its earliest shutdown date ({when}); "
                    "no longer offered in Video")
            found.append((days, MediaRow("past", text, accessible_name=text), ""))
            continue
        if days > SHUTDOWN_WARNING_DAYS:
            text = f"{label}: earliest shutdown {when}"
            found.append((days, MediaRow("shutdown", text, accessible_name=text), ""))
            continue
        text = f"{label}: earliest shutdown {when} — {_when(days)}"
        spoken = f"Warning: {label}, earliest shutdown {when}, {_when(days)}"
        if len(models) == 1:
            headline = f"{label} shuts down {_when(days)}"
        else:
            family = models[0].label.split()[0]
            headline = f"{len(models)} {family} models shut down {_when(days)}"
        found.append((days, MediaRow("shutdown", text, warning=True,
                                     accessible_name=spoken), headline))
    return found


def _probe_rows(watch) -> list[tuple[MediaRow, str]]:
    from services.higgsfield_client import SEEDANCE_ENDPOINTS
    models = []
    for probe in watch.probe_rows():
        model = next((name for name, paths in SEEDANCE_ENDPOINTS.items()
                      if probe.path in paths), "")
        if model and model not in models:
            models.append(model)
    rows = []
    for model in models:
        version = model.split("-", 1)[1] if "-" in model else model
        text = (f"Seedance {version}: Higgsfield's path is not answering. "
                "Renders on it will likely fail.")
        rows.append((MediaRow("not_answering", text, warning=True,
                              accessible_name=f"Warning: {text}"),
                     f"Seedance {version} path not answering"))
    return rows


def media_digest(watch, today: date | None = None) -> MediaDigest:
    """Order and word the video and image news for the tile."""
    today = today or date.today()

    urgent: list[tuple[MediaRow, str]] = []
    for removal in watch.removals("media"):
        provider = provider_label(removal.provider)
        entry = _catalog_entry(removal.provider, removal.model_id)
        label = entry.label if entry else removal.model_id
        text = (f"{label} ({removal.model_id}) is no longer listed by {provider}. "
                "Renders with it will fail; pick another model in Video.")
        urgent.append((MediaRow("removed", text, warning=True,
                                accessible_name=f"Warning: {text}"),
                       f"{label} is no longer listed"))
    urgent.extend(_probe_rows(watch))

    shutdowns = _shutdown_rows(today)
    upcoming = sorted((s for s in shutdowns if s[0] > 0), key=lambda s: s[0])
    past = sorted((s for s in shutdowns if s[0] <= 0), key=lambda s: s[0])

    new_rows = []
    pending = watch.pending_media()
    for notice in pending:
        provider = provider_label(notice.provider)
        offered = _catalog_entry(notice.provider, notice.model_id) is not None
        detail = (f"Already in Imprint's Video menus — listed by {provider}"
                  if offered else
                  f"Not in Imprint's Video menus yet — listed by {provider}")
        new_rows.append(MediaRow(
            "new", detail, accessible_name=f"New: {provider} {notice.model_id}. {detail}",
            provider_label=provider, model_id=notice.model_id))

    rows = ([row for row, _ in urgent] + [row for _, row, _ in upcoming]
            + [row for _, row, _ in past] + new_rows)
    soon = [(row, headline) for days, row, headline in upcoming if row.warning]
    warning_count = sum(1 for row in rows if row.warning)

    if urgent:
        headline = (urgent[0][1] if len(urgent) == 1 else
                    f"{len(urgent)} video or image warnings")
    elif soon:
        headline = soon[0][1]
    elif not watch.last_checked:
        headline = "Not checked yet"
    elif pending:
        headline = ("1 new video or image model" if len(pending) == 1 else
                    f"{len(pending)} new video or image models")
    else:
        headline = "No video or image changes"

    offered_dates = any(m.retires for m in media_catalog.offered_models(today.isoformat()))
    return MediaDigest(
        headline=headline, rows=tuple(rows), warning_count=warning_count,
        new_count=len(pending),
        # The Design's Dismiss: for new and removed models only. A "not
        # answering" row clears when a later probe answers.
        dismissable=bool(pending or watch.removals("media")),
        visible=bool(rows) or offered_dates)
