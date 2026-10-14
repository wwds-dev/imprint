"""
Imprint — Model updates: the video and image lane
=================================================
Type: unit (Qt-free rules, copy and clients) + window-level (the tile, the
scan, the Higgsfield gate), run headless with fakes for every client.

The tile's second question: will the video or image route I am about to pay
for still work, and is there a newer one? Each test here is one way that
answer could lie — a media id reaching a chat menu, a regional blip read as a
removal, a shutdown date that drifts from the catalog, or a path check that
spends money or calls a 5xx "gone". Spec: docs/specs/model-watch-media.md.

No test makes a network call: clients get fake sessions, and the window's
Higgsfield client is an injected fake.

Run with:  pytest tests/test_model_watch_media.py -v
"""

import json
import os
import sys
import threading
import types
from datetime import date
from pathlib import Path

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import media_catalog  # noqa: E402
from services.media_catalog import VEO_SHUTDOWN, VEO_SHUTDOWN_NOTE, human_date  # noqa: E402
from services.model_watch import (  # noqa: E402
    MediaListUnsupported, ModelWatch, is_chat_model, is_media_model,
)
from services.model_watch_digest import group_label, media_digest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class _DayClock:
    """ISO timestamps on a day the test sets; minutes tick within it."""

    def __init__(self, day="2026-10-14"):
        self.day = day
        self.ticks = 0

    def __call__(self):
        self.ticks += 1
        return f"{self.day}T10:{self.ticks % 60:02d}:00+00:00"


@pytest.fixture
def clock():
    return _DayClock()


@pytest.fixture
def watch(tmp_path, clock):
    return ModelWatch(tmp_path / "model_watch.json", clock=clock)


VEO = "veo-3.1-generate-preview"
GEMINI_MEDIA = [VEO, "veo-3.1-fast-generate-preview", "imagen-4.0-generate-001",
                "gemini-nano-banana-2.1"]


# ── M1, M2: the media lane announces, separately ────────────────────────────

def test_first_media_look_is_a_silent_baseline_even_with_a_chat_baseline(watch):
    watch.observe("gemini", ["gemini-3.1-pro-preview"])
    assert watch.observe_media("gemini", GEMINI_MEDIA) == []
    assert watch.has_media_baseline("gemini")
    assert watch.pending_media() == [] and watch.pending() == []


def test_a_new_media_id_reaches_pending_media_never_pending(watch):
    watch.observe("gemini", ["gemini-3.1-pro-preview"])
    watch.observe_media("gemini", GEMINI_MEDIA)
    news = watch.observe_media("gemini", GEMINI_MEDIA + ["veo-4.0-generate-preview"])
    assert [n.model_id for n in news] == ["veo-4.0-generate-preview"]
    assert [n.model_id for n in watch.pending_media()] == ["veo-4.0-generate-preview"]
    assert watch.pending() == []
    assert not watch.is_pending("gemini", "veo-4.0-generate-preview")


def test_qwen_media_ids_are_announced_in_their_lane(watch):
    watch.observe_media("qwen", ["wan3.0-video", "qwen-image-3.0"])
    watch.observe_media("qwen", ["wan3.0-video", "qwen-image-3.0", "wan3.5-video",
                                 "qwen-image-3.5"])
    assert sorted(n.model_id for n in watch.pending_media()) == [
        "qwen-image-3.5", "wan3.5-video"]


def test_a_dated_media_snapshot_is_not_news(watch):
    watch.observe_media("gemini", [VEO])
    assert watch.observe_media("gemini", [VEO, VEO + "-001"]) == []


def test_media_ids_never_enter_the_chat_lane(watch):
    watch.observe("gemini", ["gemini-3.1-pro-preview"])
    watch.observe("gemini", ["gemini-3.1-pro-preview", *GEMINI_MEDIA,
                             "gemini-omni-1.1-flash", "gemini-3-pro-image"])
    assert watch.pending() == []


def test_acknowledge_media_clears_only_the_media_lane(watch):
    watch.observe("qwen", ["qwen-plus"])
    watch.observe("qwen", ["qwen-plus", "qwen4-max"])
    watch.observe_media("qwen", ["wan3.0-video"])
    watch.observe_media("qwen", ["wan3.0-video", "wan3.5-video"])
    watch.acknowledge_media()
    assert watch.pending_media() == []
    assert [n.model_id for n in watch.pending()] == ["qwen4-max"]
    watch.acknowledge()
    assert watch.observe_media("qwen", ["wan3.0-video", "wan3.5-video"]) == []


# ── M3: removals ────────────────────────────────────────────────────────────

def _baseline_then(watch, clock, *looks, tracked=(VEO,)):
    watch.observe_media("gemini", [VEO, "imagen-4.0-generate-001"], tracked=tracked)
    for day, ids in looks:
        clock.day = day
        watch.observe_media("gemini", ids, tracked=tracked)


def test_two_absences_on_two_days_confirm_one_removal(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]))
    removals = watch.removals("media")
    assert [(r.provider, r.model_id) for r in removals] == [("gemini", VEO)]
    clock.day = "2026-10-17"
    watch.observe_media("gemini", ["imagen-4.0-generate-001"], tracked=(VEO,))
    assert len(watch.removals("media")) == 1        # one notice, not one a day


def test_one_absence_is_not_a_removal(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]))
    assert watch.removals() == []


def test_two_absences_on_the_same_day_are_one(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-15", ["imagen-4.0-generate-001"]))
    assert watch.removals() == []
    clock.day = "2026-10-16"
    watch.observe_media("gemini", ["imagen-4.0-generate-001"], tracked=(VEO,))
    assert len(watch.removals()) == 1


def test_an_empty_list_is_never_an_absence(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", []), ("2026-10-16", []))
    assert watch.removals() == []


def test_a_model_never_listed_cannot_be_removed(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]),
                   tracked=("veo-9-never-listed",))
    assert watch.removals() == []


def test_without_tracked_ids_nothing_is_counted(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]), tracked=())
    assert watch.removals() == []


def test_a_listed_snapshot_counts_as_present(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", [VEO + "-001"]),
                   ("2026-10-16", [VEO + "-001"]))
    assert watch.removals() == []


def test_reappearing_drops_the_removal_and_resets_the_count(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]),
                   ("2026-10-17", [VEO, "imagen-4.0-generate-001"]))
    assert watch.removals() == []
    clock.day = "2026-10-18"
    watch.observe_media("gemini", ["imagen-4.0-generate-001"], tracked=(VEO,))
    assert watch.removals() == []                   # counting starts over


def test_a_dismissed_removal_is_not_raised_again(watch, clock):
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]))
    watch.acknowledge_media()
    clock.day = "2026-10-17"
    watch.observe_media("gemini", ["imagen-4.0-generate-001"], tracked=(VEO,))
    assert watch.removals() == []


def test_a_selected_chat_model_removal_and_its_dismissal(watch, clock):
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    for day in ("2026-10-15", "2026-10-16"):
        clock.day = day
        watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    assert [(r.kind, r.model_id) for r in watch.removals()] == [("chat", "qwen-plus")]
    assert watch.removals("media") == []
    watch.acknowledge([("qwen", "anything")])       # pairs touch only pending
    assert len(watch.removals("chat")) == 1
    watch.acknowledge()
    assert watch.removals() == []


def test_a_panel_fetch_never_counts_an_absence(watch, clock):
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    for day in ("2026-10-15", "2026-10-16"):
        clock.day = day
        watch.observe("qwen", ["qwen3.8-max"])      # no tracked: a panel fetch
    assert watch.removals() == []


# ── review fix round 1 (docs/audit/model-watch-media-*.md) ──────────────────

OMNI = "gemini-omni-1.1-flash"


def test_upgrade_no_false_removal_for_a_selected_id_now_classed_media(tmp_path):
    """CR P2-1: before this change Omni counted as chat, so a v1 file holds it
    in the chat lane's last_live and an agent may still have it selected.
    Google still lists it; it must not read as removed."""
    path = tmp_path / "model_watch.json"
    path.write_text(json.dumps({"version": 1, "providers": {"gemini": {
        "baseline_at": "2026-10-01T00:00:00+00:00",
        "seen": ["gemini-3.1-pro-preview", OMNI],
        "last_live": ["gemini-3.1-pro-preview", OMNI],
        "listed_at": "2026-10-01T00:00:00+00:00"}}, "pending": []}),
        encoding="utf-8")
    clock = _DayClock("2026-10-14")
    watch = ModelWatch(path, clock=clock)
    for day in ("2026-10-14", "2026-10-15", "2026-10-16"):
        clock.day = day
        watch.observe("gemini", ["gemini-3.1-pro-preview", OMNI], tracked=(OMNI,))
    assert watch.removals() == []


def test_a_model_listed_while_untracked_starts_its_count_again(watch, clock):
    """CR P2-2: absent once while selected, then listed while nobody had it
    selected, then one blip months later: that is one absence, not two."""
    clock.day = "2026-10-01"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    clock.day = "2026-10-02"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))      # miss 1
    clock.day = "2026-10-03"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=())     # present
    clock.day = "2026-12-01"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    assert watch.removals() == []
    clock.day = "2026-12-02"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    assert [r.model_id for r in watch.removals()] == ["qwen-plus"]


def test_an_untracked_absence_forgets_the_count_before_it_is_tracked_again(
        watch, clock):
    """QA N2: tracked and missed once, then missing while nobody had it
    selected, then selected again and missing: one new absence is not a
    removal (the untracked scan forgot the first count)."""
    clock.day = "2026-10-01"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    clock.day = "2026-10-02"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))      # miss 1
    clock.day = "2026-10-03"
    watch.observe("qwen", ["qwen3.8-max"], tracked=())                  # untracked
    clock.day = "2026-10-04"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))      # one new miss
    assert watch.removals() == []


def test_a_panel_fetch_listing_the_model_also_resets_the_count(watch, clock):
    clock.day = "2026-10-01"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    clock.day = "2026-10-02"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"])                 # a panel
    clock.day = "2026-10-03"
    watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    assert watch.removals() == []


def test_a_removal_drops_when_the_model_returns_even_untracked(watch, clock):
    """CR P3-2: the Design says the notice drops on its own."""
    clock.day = "2026-10-01"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"], tracked=("qwen-plus",))
    for day in ("2026-10-02", "2026-10-03"):
        clock.day = day
        watch.observe("qwen", ["qwen3.8-max"], tracked=("qwen-plus",))
    assert len(watch.removals("chat")) == 1
    clock.day = "2026-10-04"
    watch.observe("qwen", ["qwen3.8-max", "qwen-plus"])      # nobody on it now
    assert watch.removals() == []


def test_hostile_or_huge_lists_are_bounded(watch):
    """Sec P3-1/P3-2: markup and over-long ids never reach the state or the
    tile, one list adds at most MAX_LISTED_IDS, pending_media is capped."""
    from services.model_watch import MAX_LISTED_IDS, MAX_PENDING_MEDIA, valid_model_id
    assert not valid_model_id('<span style="color:red">veo</span>')
    assert not valid_model_id("veo-" + "x" * 200) and valid_model_id("wan3.0-video")
    watch.observe_media("qwen", ["wan3.0-video"])
    flood = [f"wan-{i:05d}" for i in range(MAX_LISTED_IDS + 500)]
    watch.observe_media("qwen", ["wan3.0-video", '<b>wan</b>', "wan-" + "y" * 300,
                                 *flood])
    record = json.loads(watch.path.read_text())["media"]["qwen"]
    assert len(record["last_live"]) == MAX_LISTED_IDS
    assert all(valid_model_id(m) for m in record["seen"])
    assert len(watch.pending_media()) == MAX_PENDING_MEDIA


def test_the_pending_media_cap_keeps_the_newest(watch):
    """QA N5: past MAX_PENDING_MEDIA, the oldest notices go, not the newest."""
    from services.model_watch import MAX_PENDING_MEDIA
    watch.observe_media("qwen", ["wan3.0-video"])
    ids = [f"wan{i:03d}-video" for i in range(MAX_PENDING_MEDIA + 5)]
    for model in ids:                       # one new model per look, in order
        watch.observe_media("qwen", ["wan3.0-video", model])
    kept = {n.model_id for n in watch.pending_media()}
    assert kept == set(ids[-MAX_PENDING_MEDIA:])


@pytest.mark.parametrize("lane, tracked_id, flood_prefix", [
    ("media", "wan3.0-video", "wan-"),      # "wan-…" sorts before "wan3…"
    ("chat", "qwen-plus", "qwen-"),         # "qwen-0…" sorts before "qwen-p…"
])
def test_a_tracked_id_past_the_cap_is_still_present(watch, clock, lane,
                                                    tracked_id, flood_prefix):
    """CR P3-B: presence is read from every valid id, the cap bounds only
    what is stored, so a list of 2,001 ids cannot remove the last one."""
    from services.model_watch import MAX_LISTED_IDS
    observe = watch.observe_media if lane == "media" else watch.observe
    tracked = (tracked_id,)
    clock.day = "2026-10-01"
    observe("qwen", [tracked_id], tracked=tracked)
    flood = [f"{flood_prefix}{i:05d}" for i in range(MAX_LISTED_IDS)]
    assert sorted([*flood, tracked_id])[-1] == tracked_id    # past the cap
    for day in ("2026-10-02", "2026-10-03", "2026-10-04"):
        clock.day = day
        observe("qwen", [*flood, tracked_id], tracked=tracked)
    assert watch.removals() == []
    key = "media" if lane == "media" else "providers"
    record = json.loads(watch.path.read_text())[key]["qwen"]
    assert len(record["last_live"]) <= MAX_LISTED_IDS
    assert record["missing"] == {}


def test_the_probe_runs_at_most_once_a_day_and_forgets_unprobed_paths(watch, clock):
    """Sec P2-1, CR P3-5."""
    assert not watch.probed_today()
    watch.observe_probe("/bytedance/seedance-1.9/text-to-video", "missing")
    watch.mark_probed([T25])
    assert watch.probed_today()
    assert watch.probe_rows() == []          # a path no longer probed is gone
    clock.day = "2026-10-15"
    assert not watch.probed_today()


def test_only_new_or_removed_media_show_the_dismiss(watch):
    """QA D7: a "not answering" row clears when a probe answers; the Design
    gives the media Dismiss to new and removed models only."""
    watch.observe_probe(T25, "missing")
    digest = _digest(watch, "2026-10-14")
    assert any(r.kind == "not_answering" for r in digest.rows)
    assert not digest.dismissable


def test_qwen_pages_on_without_a_total(qwen, monkeypatch):
    """CR P3-3: a page without `total` that is full may have a successor."""
    monkeypatch.setattr(qwen, "MEDIA_PAGE_SIZE", 1)
    session = _GetSession(
        _Resp(data={"output": {"models": [{"model": "wan3.0-video",
                                           "capabilities": ["VG"]}]}}),
        _Resp(data={"output": {"models": [{"model": "qwen-image-3.0",
                                           "capabilities": ["IG"]}]}}),
        _Resp(data={"output": {"models": []}}))
    monkeypatch.setattr(qwen, "_media_session", lambda: session)
    assert qwen.list_media_models_live() == ["qwen-image-3.0", "wan3.0-video"]
    assert len(session.calls) == 3


def test_qwen_never_sends_the_key_over_plain_http(monkeypatch):
    """Sec P3-3."""
    from services import qwen_client
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("DASHSCOPE_VIDEO_BASE_URL", "http://example.com/api/v1")
    wrapper = qwen_client.QwenClientWrapper()
    session = _GetSession()
    monkeypatch.setattr(wrapper, "_media_session", lambda: session)
    with pytest.raises(RuntimeError, match="not https"):
        wrapper.list_media_models_live()
    assert session.calls == []
    monkeypatch.setenv("DASHSCOPE_VIDEO_BASE_URL", "http://localhost:8080/api/v1")
    local = qwen_client.QwenClientWrapper()
    session = _GetSession(_Resp(data=_page([], 0)))
    monkeypatch.setattr(local, "_media_session", lambda: session)
    assert local.list_media_models_live() == []
    assert len(session.calls) == 1


# ── M6 and the ADR: an old file keeps everything ────────────────────────────

def test_a_v1_file_loads_with_its_chat_state_and_a_silent_first_media_look(tmp_path):
    path = tmp_path / "model_watch.json"
    path.write_text(json.dumps({
        "version": 1,
        "providers": {"gemini": {"baseline_at": "2026-10-01T00:00:00+00:00",
                                 "seen": ["gemini-3.1-pro-preview"],
                                 "last_live": ["gemini-3.1-pro-preview"],
                                 "listed_at": "2026-10-01T00:00:00+00:00"}},
        "pending": [{"provider": "gemini", "model_id": "gemini-3.1-pro-preview",
                     "first_seen": "2026-10-02T00:00:00+00:00"}],
    }), encoding="utf-8")
    watch = ModelWatch(path, clock=_DayClock())
    assert watch.has_baseline("gemini")
    assert [n.model_id for n in watch.pending()] == ["gemini-3.1-pro-preview"]
    assert watch.last_checked is None
    assert watch.observe_media("gemini", GEMINI_MEDIA) == []
    assert watch.pending_media() == []
    # The chat notice survived the media look and the save.
    assert [n.model_id for n in ModelWatch(path).pending()] == ["gemini-3.1-pro-preview"]


def test_an_older_build_round_trips_the_media_keys(tmp_path):
    path = tmp_path / "model_watch.json"
    watch = ModelWatch(path, clock=_DayClock())
    watch.observe_media("qwen", ["wan3.0-video"])
    watch.observe_media("qwen", ["wan3.0-video", "wan3.5-video"])
    watch.observe_probe("/bytedance/seedance-2.5/text-to-video", "missing")

    # The build before this change: version check, three setdefaults, and a
    # save of the whole dict (model_watch.py at d0ce9a1).
    old = json.loads(path.read_text(encoding="utf-8"))
    assert old.get("version") == 1
    for key, value in (("providers", {}), ("pending", []), ("last_checked", None)):
        old.setdefault(key, value)
    path.write_text(json.dumps(old, indent=2, sort_keys=True), encoding="utf-8")

    again = ModelWatch(path)
    assert [n.model_id for n in again.pending_media()] == ["wan3.5-video"]
    assert [p.path for p in again.probe_rows()] == [
        "/bytedance/seedance-2.5/text-to-video"]
    assert ModelWatch.VERSION == 1


# ── probes ─────────────────────────────────────────────────────────────────

T25 = "/bytedance/seedance-2.5/text-to-video"


def test_a_missing_path_is_a_row_until_it_answers(watch):
    watch.observe_probe(T25, "missing")
    assert [p.path for p in watch.probe_rows()] == [T25]
    watch.observe_probe(T25, "answering")
    assert watch.probe_rows() == []


def test_clear_probes_forgets_every_answer(watch):
    watch.observe_probe(T25, "missing")
    watch.clear_probes()
    assert watch.probe_rows() == []
    assert json.loads(watch.path.read_text())["probes"] == {}


def test_unreachable_is_never_stored(watch):
    watch.observe_probe(T25, "missing")
    watch.observe_probe(T25, "unreachable")
    assert [p.status for p in watch.probe_rows()] == ["missing"]
    watch.observe_probe("/bytedance/seedance-2.0/text-to-video", "unreachable")
    assert len(watch.probe_rows()) == 1


def test_a_dismissed_probe_row_returns_only_when_the_answer_changes(watch):
    watch.observe_probe(T25, "missing")
    watch.acknowledge_media()
    watch.observe_probe(T25, "missing")
    assert watch.probe_rows() == []
    watch.observe_probe(T25, "answering")
    watch.observe_probe(T25, "missing")
    assert [p.path for p in watch.probe_rows()] == [T25]


# ── the classifier ─────────────────────────────────────────────────────────

def test_no_offered_media_id_is_a_chat_model():
    ids = [m.model_id for m in media_catalog.MODELS]
    assert "gemini-nano-banana-2.1" in ids and "gemini-omni-1.1-flash" in ids
    assert [i for i in ids if is_chat_model(i)] == []
    assert all(is_media_model(i) for i in ids)
    assert is_media_model("imagen-4.0-generate-001") and is_media_model("wan3.5-video")
    assert not is_media_model("qwen3.8-max") and not is_media_model("")
    assert is_chat_model("gemini-3.1-pro-preview") and is_chat_model("qwen-plus")


def test_the_ranking_drops_every_offered_media_id():
    from services.recommendations.catalog import text_candidates
    ids = [m.model_id for m in media_catalog.MODELS]
    found = {c.model_id for c in text_candidates(
        ["gemini"], {"gemini": ["gemini-3.1-pro-preview", *ids]})}
    assert found == {"gemini-3.1-pro-preview"}


# ── M4: shutdown dates, one source ─────────────────────────────────────────

def _digest(watch, day):
    return media_digest(watch, date.fromisoformat(day))


def test_the_veo_previews_are_one_row_eight_days_out(watch):
    digest = _digest(watch, "2026-10-14")
    shutdown = [r for r in digest.rows if r.kind == "shutdown"]
    assert [r.text for r in shutdown] == [
        "Veo 3.1, Fast and Lite: earliest shutdown 22 October 2026 — in 8 days"]
    assert shutdown[0].warning
    assert shutdown[0].accessible_name == (
        "Warning: Veo 3.1, Fast and Lite, earliest shutdown 22 October 2026, in 8 days")
    assert digest.headline == "3 Veo models shut down in 8 days"
    assert digest.warning_count == 1 and digest.visible


def test_the_day_before_says_tomorrow(watch):
    digest = _digest(watch, "2026-10-21")
    assert digest.rows[0].text.endswith("— tomorrow")
    assert digest.headline == "3 Veo models shut down tomorrow"


def test_fourteen_days_out_is_a_warning_and_fifteen_is_not(watch):
    at14 = _digest(watch, "2026-10-08")
    assert at14.rows[0].warning and at14.warning_count == 1
    assert at14.rows[0].text.endswith("— in 14 days")
    at15 = _digest(watch, "2026-10-07")
    assert at15.rows[0].text == "Veo 3.1, Fast and Lite: earliest shutdown 22 October 2026"
    assert not at15.rows[0].warning and at15.warning_count == 0
    assert at15.headline == "Not checked yet"


def test_a_past_date_shows_for_fourteen_days_then_drops(watch):
    on = _digest(watch, "2026-10-22")
    assert on.rows[0].kind == "past" and not on.rows[0].warning
    assert on.rows[0].text == ("Veo 3.1, Fast and Lite: past its earliest shutdown "
                               "date (22 October 2026); no longer offered in Video")
    assert _digest(watch, "2026-11-04").rows[0].kind == "past"
    late = _digest(watch, "2026-11-05")
    assert [r for r in late.rows if r.kind == "past"] == []
    assert not late.visible                 # nothing to say, no date ahead


def test_a_single_model_headline_and_the_label_grouping():
    assert group_label(["Veo 3.1"]) == "Veo 3.1"
    assert group_label(["Veo 3.1", "Veo 3.1 Fast", "Veo 3.1 Lite"]) == \
        "Veo 3.1, Fast and Lite"
    assert group_label(["Wan 3.0", "Qwen Image"]) == "Wan 3.0 and Qwen Image"


def test_the_veo_note_is_built_from_the_one_date():
    assert human_date(VEO_SHUTDOWN) in VEO_SHUTDOWN_NOTE
    assert "earliest" in VEO_SHUTDOWN_NOTE
    assert VEO_SHUTDOWN_NOTE == ("Google may shut this preview down from 22 October "
                                 "2026 (earliest date); Gemini Omni is its replacement.")


def test_the_shutdown_date_is_written_only_in_the_catalog():
    """Measure 4: one source. Any other module holding the date would drift."""
    hits = []
    skip = {"tests", "build", "dist", "_to_delete"}
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in skip or rel.parts[0].startswith("."):
            continue
        if "2026-10-22" in path.read_text(encoding="utf-8", errors="ignore"):
            hits.append(str(rel))
    assert hits == ["services/media_catalog.py"]


# ── the rest of the copy ───────────────────────────────────────────────────

def test_urgent_rows_lead_and_name_the_fix(watch, clock):
    watch.last_checked or watch.mark_checked()
    _baseline_then(watch, clock, ("2026-10-15", ["imagen-4.0-generate-001"]),
                   ("2026-10-16", ["imagen-4.0-generate-001"]))
    digest = _digest(watch, "2026-10-16")
    assert digest.rows[0].kind == "removed"
    assert digest.rows[0].text == (
        "Veo 3.1 (veo-3.1-generate-preview) is no longer listed by Gemini. "
        "Renders with it will fail; pick another model in Video.")
    assert digest.headline == "Veo 3.1 is no longer listed"
    assert digest.rows[1].kind == "shutdown"
    assert digest.dismissable and digest.warning_count == 2

    watch.observe_probe(T25, "missing")
    watch.observe_probe("/bytedance/seedance-2.5/image-to-video", "missing")
    digest = _digest(watch, "2026-10-16")
    probe = [r for r in digest.rows if r.kind == "not_answering"]
    assert [r.text for r in probe] == [      # one row per model, not per path
        "Seedance 2.5: Higgsfield's path is not answering. Renders on it will "
        "likely fail."]
    assert digest.headline == "2 video or image warnings"


def test_new_rows_and_headlines(watch):
    assert _digest(watch, "2026-11-30").headline == "Not checked yet"
    watch.observe_media("qwen", ["wan3.0-video"])
    assert _digest(watch, "2026-11-30").headline == "No video or image changes"
    watch.observe_media("qwen", ["wan3.0-video", "wan3.5-video"])
    digest = _digest(watch, "2026-11-30")
    assert digest.headline == "1 new video or image model"
    new = digest.rows[-1]
    assert (new.kind, new.provider_label, new.model_id) == ("new", "Qwen", "wan3.5-video")
    assert new.text == "Not in Imprint's Video menus yet — listed by Qwen"
    assert digest.dismissable and digest.new_count == 1
    # The shutdown rows stay after a dismiss; only the news goes.
    watch.acknowledge_media()
    after = _digest(watch, "2026-10-14")
    assert not after.dismissable
    assert [r.kind for r in after.rows] == ["shutdown"]


# ── clients ────────────────────────────────────────────────────────────────

def test_gemini_media_list_is_unfiltered_by_generate_content():
    from services.gemini_client import GeminiClientWrapper
    def model(name, actions):
        return types.SimpleNamespace(name=f"models/{name}", supported_actions=actions)

    listing = [model("gemini-3.1-pro-preview", ["generateContent"]),
               model(VEO, ["predictLongRunning"]),
               model("imagen-4.0-generate-001", ["predict"]),
               model("gemini-3-pro-image", ["generateContent"]),
               model("text-embedding-004", ["embedContent"])]
    wrapper = GeminiClientWrapper.__new__(GeminiClientWrapper)
    wrapper.client = types.SimpleNamespace(
        models=types.SimpleNamespace(list=lambda: iter(listing)))
    assert wrapper.list_media_models_live() == [
        "gemini-3-pro-image", "imagen-4.0-generate-001", VEO]
    wrapper.client = None
    assert wrapper.list_media_models_live() == []


class _Resp:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code = status
        self._data = data
        self._bad = bad_json
        self.headers = {}

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class _GetSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def post(self, *a, **k):            # pragma: no cover - must never happen
        raise AssertionError("the media list never POSTs")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True


@pytest.fixture
def qwen(monkeypatch):
    from services import qwen_client
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("DASHSCOPE_VIDEO_BASE_URL", raising=False)
    return qwen_client.QwenClientWrapper()


def _page(models, total, page=1):
    return {"output": {"models": models, "total": total, "page_no": page,
                       "page_size": 100}}


def _host(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc


def test_qwen_media_list_pages_and_keeps_ig_and_vg(qwen, monkeypatch):
    from services import qwen_client
    monkeypatch.setattr(qwen, "MEDIA_PAGE_SIZE", 2)
    session = _GetSession(
        _Resp(data=_page([{"model": "qwen-image-3.0-pro", "capabilities": ["IG"]},
                          {"model": "qwen3.8-max", "capabilities": ["TG"]}], 3)),
        _Resp(data=_page([{"model": "wan3.0-video", "capabilities": ["VG", "TG"]}], 3, 2)))
    monkeypatch.setattr(qwen, "_media_session", lambda: session)
    assert qwen.list_media_models_live() == ["qwen-image-3.0-pro", "wan3.0-video"]
    assert session.closed
    assert [kw["params"]["page_no"] for _u, kw in session.calls] == [1, 2]
    for url, kwargs in session.calls:
        assert _host(url) == _host(qwen_client.video_base_url())
        assert url.endswith("/api/v1/models")
        assert kwargs["timeout"] > 0


@pytest.mark.parametrize("response", [_Resp(404), _Resp(405), _Resp(data={"x": 1}),
                                      _Resp(bad_json=True)])
def test_qwen_media_list_not_served_is_unsupported(qwen, response, monkeypatch):
    from services import qwen_client
    session = _GetSession(response)
    monkeypatch.setattr(qwen, "_media_session", lambda: session)
    with pytest.raises(MediaListUnsupported):
        qwen.list_media_models_live()
    assert _host(session.calls[0][0]) == _host(qwen_client.video_base_url())


@pytest.mark.parametrize("status", [401, 500])
def test_qwen_media_list_other_failures_raise(qwen, status, monkeypatch):
    session = _GetSession(_Resp(status))
    monkeypatch.setattr(qwen, "_media_session", lambda: session)
    with pytest.raises(requests.HTTPError):
        qwen.list_media_models_live()


def test_qwen_media_list_without_a_key_calls_nothing(monkeypatch):
    from services import qwen_client
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    wrapper = qwen_client.QwenClientWrapper()
    monkeypatch.setattr(requests.Session, "get", lambda *a, **k: pytest.fail("network"))
    assert wrapper.list_media_models_live() == []


# ── M5: the Higgsfield probe ───────────────────────────────────────────────

class _PostSession:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def get(self, *a, **k):             # pragma: no cover - must never happen
        raise AssertionError("the probe never GETs")


@pytest.mark.parametrize("result, status", [
    (_Resp(200, {}), "answering"), (_Resp(400), "answering"),
    (_Resp(422), "answering"), (_Resp(404), "missing"),
    (_Resp(401), "unreachable"), (_Resp(403), "unreachable"),
    (_Resp(429), "unreachable"), (_Resp(500), "unreachable"),
    (_Resp(503), "unreachable"),
    (requests.Timeout("slow"), "unreachable"),
    (requests.ConnectionError("down"), "unreachable"),
])
def test_probe_maps_each_answer(result, status):
    from urllib.parse import urlparse
    from services.higgsfield_client import PROBE_TIMEOUT_SECONDS, HiggsfieldClient
    client = HiggsfieldClient(key_id="kid", key_secret="secret")
    client._session = session = _PostSession(result)
    assert client.probe_endpoint(T25) == status
    assert len(session.calls) == 1                   # no retry
    url, kwargs = session.calls[0]
    assert urlparse(url).path.startswith("/estimate/")
    assert urlparse(url).path == "/estimate" + T25
    assert "upload" not in url
    assert kwargs["timeout"] == PROBE_TIMEOUT_SECONDS == 15
    assert kwargs["json"] == {"duration": 4, "prompt": "status check"}


def test_probe_without_a_key_sends_nothing():
    from services.higgsfield_client import HiggsfieldClient
    client = HiggsfieldClient(key_id="", key_secret="")
    client._session = session = _PostSession(_Resp(200))
    with pytest.raises(RuntimeError):
        client.probe_endpoint(T25)
    assert session.calls == []


# ── the worker ─────────────────────────────────────────────────────────────

class _Media:
    def __init__(self, result):
        self.result = result

    def list_media_models_live(self):
        if isinstance(self.result, Exception):
            raise self.result
        return list(self.result)


def test_the_worker_lists_then_probes_one_at_a_time(app):
    from ui.workers import ModelScanWorker
    # Signals reach these lambdas queued, in the order they were emitted;
    # the probes themselves run on the worker's thread.
    events, started = [], []
    busy = threading.Lock()
    overlaps = []

    def probe(path):
        if not busy.acquire(blocking=False):
            overlaps.append(path)
            return "answering"
        try:
            started.append(path)
            return "missing" if path.endswith("image-to-video") else "answering"
        finally:
            busy.release()

    class _Chat:
        def list_models_live(self):
            return ["qwen-plus"]

    worker = ModelScanWorker(
        {"qwen": _Chat()},
        media_clients={"gemini": _Media([VEO]),
                       "qwen": _Media(MediaListUnsupported("no")),
                       "kimi": _Media(RuntimeError("boom"))},
        probe=probe, probe_paths=(("seedance-2.5", T25),
                                  ("seedance-2.5", "/bytedance/seedance-2.5/image-to-video")))
    worker.provider_listed.connect(lambda *a: events.append(("chat",) + a))
    worker.media_listed.connect(lambda *a: events.append(("media",) + a))
    worker.path_probed.connect(lambda *a: events.append(("probed",) + a))
    worker.start()
    assert worker.wait(5000)
    for _ in range(10):
        app.processEvents()
    kinds = [e[0] for e in events]
    assert kinds == ["chat", "media", "media", "media", "probed", "probed"]
    assert len(started) == 2
    assert ("media", "gemini", [VEO], "") in events
    assert ("media", "qwen", [], "unsupported") in events
    assert ("media", "kimi", [], "boom") in events
    assert ("probed", "seedance-2.5", "/bytedance/seedance-2.5/image-to-video",
            "missing") in events
    assert overlaps == []


def test_the_worker_with_defaults_behaves_as_before(app):
    from ui.workers import ModelScanWorker

    class _Chat:
        def list_models_live(self):
            return ["qwen-plus"]

    worker = ModelScanWorker({"qwen": _Chat()})
    seen = []
    worker.media_listed.connect(lambda *a: seen.append(a))
    worker.path_probed.connect(lambda *a: seen.append(a))
    worker.start()
    assert worker.wait(5000)
    for _ in range(10):         # queued signals land only when events run
        app.processEvents()
    assert seen == []


# ── the window ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(app):
    from PySide6.QtWidgets import QMessageBox
    import main

    saved = (QMessageBox.warning, QMessageBox.question, QMessageBox.information)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    # The window schedules its own Model updates check a few seconds after
    # start. Left pending, it fires inside whichever test is pumping events
    # then and runs a second scan on that test's fakes (seen under random
    # order). Run it now, on the window's real keyless clients, and let it end.
    delay = main.MODEL_CHECK_DELAY_MS
    main.MODEL_CHECK_DELAY_MS = 0
    try:
        w = main.GodAI()
        w.show()
        for _ in range(10):
            app.processEvents()
        if w.model_scan_worker is not None:
            assert w.model_scan_worker.wait(5000)
        for _ in range(10):
            app.processEvents()
        yield w
    finally:
        main.MODEL_CHECK_DELAY_MS = delay
        QMessageBox.warning, QMessageBox.question, QMessageBox.information = saved


class _FakeHiggsfield:
    """Records every call; no network. Renders fail the test outright."""

    def __init__(self, configured=True, answers=None):
        self.configured = configured
        self.answers = dict(answers or {})
        self.probed = []

    def probe_endpoint(self, path):
        self.probed.append(path)
        return self.answers.get(path, "answering")

    def generate_video(self, *a, **k):     # pragma: no cover - must not run
        raise AssertionError("a probe must never render")

    generate_prepared = prepare_video = upload_file = generate_video


class _KeyedMedia:
    """A keyed Gemini/Qwen stand-in for the media lane only."""

    KNOWN_MODELS = ["x"]

    def __init__(self, media):
        self.media = media
        self.client = object()

    @staticmethod
    def key_available():
        return True

    def list_models_live(self):
        return ["gemini-3.1-pro-preview"]

    list_models = list_models_live

    def list_media_models_live(self):
        if isinstance(self.media, Exception):
            raise self.media
        return list(self.media)


@pytest.fixture
def media_window(app, window, tmp_path, monkeypatch):
    import main
    window.model_watch = ModelWatch(tmp_path / "model_watch.json", clock=_DayClock())
    monkeypatch.setattr(main, "WATCHED_PROVIDERS", ())
    monkeypatch.setattr(window, "_media_today", lambda: date(2026, 10, 14))
    monkeypatch.setattr(window, "session_budget_eur", 1000.0)
    monkeypatch.setattr(window, "daily_budget_eur", 1000.0)
    fake = _FakeHiggsfield()
    monkeypatch.setattr(window, "_higgsfield_factory", lambda: fake)
    monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", True)
    window.allow_higgsfield_checkbox.setChecked(True)
    window.higgs = fake
    yield window
    del window.higgs
    window.allow_higgsfield_checkbox.setChecked(False)
    window._model_scan_failed = {}
    window._model_scan_probe = ""
    window.model_watch.acknowledge()
    window.model_watch.acknowledge_media()
    window.refresh_model_updates()


def _scan(app, window):
    window.check_for_new_models()
    worker = window.model_scan_worker
    if worker is not None:
        assert worker.wait(5000)
    for _ in range(10):
        app.processEvents()


def test_the_probe_gate_says_why_and_probes_nothing(app, media_window, monkeypatch):
    window, fake = media_window, media_window.higgs
    monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", False)
    assert window._higgsfield_probe_allowed() == "off"
    _scan(app, window)
    assert "Seedance paths not checked: the Higgsfield check is off." in \
        window.model_updates_card.skipped_label.text()
    assert "confirmed to cost nothing" in window.model_updates_card.skipped_label.toolTip()

    monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", True)
    window.allow_higgsfield_checkbox.setChecked(False)
    assert window._higgsfield_probe_allowed() == "not_permitted"
    _scan(app, window)
    assert "the Higgsfield chip under Paid media is off." in \
        window.model_updates_card.skipped_label.text()

    fake.configured = False
    window.allow_higgsfield_checkbox.setChecked(True)
    assert window._higgsfield_probe_allowed() == "no_key"
    _scan(app, window)
    assert "No key, not checked: Higgsfield" in \
        window.model_updates_card.skipped_label.text()
    assert fake.probed == []


def test_the_guard_refusing_stops_the_probe(app, media_window, monkeypatch):
    window = media_window
    monkeypatch.setattr(window, "session_budget_eur", 0.0)
    monkeypatch.setattr(window, "session_cost_total", 1.0)
    assert window._higgsfield_probe_allowed() == "refused"
    _scan(app, window)
    assert window.higgs.probed == []


def test_with_everything_on_each_offered_seedance_path_is_probed_once(
        app, media_window):
    window, fake = media_window, media_window.higgs
    assert window._higgsfield_probe_allowed() == "ok"
    fake.answers = {"/bytedance/seedance-2.0/image-to-video": "missing",
                    "/bytedance/seedance-2.5/text-to-video": "unreachable"}
    _scan(app, window)
    assert sorted(fake.probed) == sorted([
        "/bytedance/seedance-2.5/text-to-video", "/bytedance/seedance-2.5/image-to-video",
        "/bytedance/seedance-2.0/text-to-video", "/bytedance/seedance-2.0/image-to-video"])
    assert not any("lite" in path for path in fake.probed)
    card = window.model_updates_card
    texts = [r.accessibleName() for r in card.media_rows]
    assert "Warning: Seedance 2.0: Higgsfield's path is not answering. Renders on " \
        "it will likely fail." in texts
    assert not any("Seedance 2.5" in t for t in texts)       # unreachable ≠ gone
    assert "Could not reach: Higgsfield (Seedance paths)" in card.skipped_label.text()


def test_a_media_result_leaves_every_chat_menu_and_the_cache_alone(app, media_window):
    import main
    window = media_window

    def snapshot():
        boxes = {}
        for agent, (_p, model_attr) in main.AGENT_SETUP_WIDGETS.items():
            box = window._find_control(model_attr)
            if box is not None:
                boxes[agent] = [box.itemText(i) for i in range(box.count())]
        return boxes, {k: list(v) for k, v in window.model_list_cache.items()}

    before = snapshot()
    window._on_media_scan_listed("gemini", [VEO, "imagen-4.0-generate-001"], "")
    window._on_media_scan_listed("gemini", [VEO, "imagen-4.0-generate-001",
                                            "veo-4.0-generate-preview"], "")
    window._on_media_scan_listed("qwen", ["qwen-image-3.0", "wan3.0-video"], "")
    window._on_media_scan_listed("qwen", ["qwen-image-3.0", "wan3.0-video",
                                          "qwen-image-3.5"], "")
    for _ in range(6):
        app.processEvents()
    assert snapshot() == before
    assert window.model_watch.pending() == []
    assert len(window.model_watch.pending_media()) == 2


def test_chat_lists_no_longer_put_media_ids_in_the_cache(app, media_window):
    window = media_window
    saved = window.model_list_cache.get("qwen")
    try:
        window._on_model_scan_listed(
            "qwen", ["qwen-plus", "qwen-image-3.0", "wan2.7-t2v"], "")
        assert window.model_list_cache["qwen"] == ["qwen-plus"]
        window.model_list_cache.pop("qwen", None)
        window._on_models_listed("qwen", ["qwen3.8-max", "qwen-image-3.0-pro"], "")
        assert window.model_list_cache["qwen"] == ["qwen3.8-max"]
    finally:
        window.model_list_cache.pop("qwen", None)
        if saved is not None:
            window.model_list_cache["qwen"] = saved


def test_the_qwen_fallback_is_silent_and_a_gemini_failure_is_named(app, media_window):
    window = media_window
    window._model_scan_failed = {}
    window._on_media_scan_listed("qwen", [], "unsupported")
    assert window._model_scan_failed == {}
    assert not window.model_watch.has_media_baseline("qwen")
    window._on_media_scan_listed("gemini", [], "HTTP 503")
    assert "Could not reach: Gemini (video and image list)" in \
        window.model_updates_card.skipped_label.text()
    assert not window.model_watch.has_media_baseline("gemini")


def test_the_scan_runs_the_media_lane_from_keyed_clients(app, media_window, monkeypatch):
    window = media_window
    monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", False)
    monkeypatch.setattr(window, "gemini", _KeyedMedia([VEO, "imagen-4.0-generate-001"]))
    import main
    monkeypatch.setattr(main, "WATCHED_PROVIDERS", ("gemini",))
    saved = window.model_list_cache.get("gemini")
    try:
        _scan(app, window)
        assert window.model_watch.has_media_baseline("gemini")
        window.gemini.media.append("veo-4.0-generate-preview")
        _scan(app, window)
        assert [n.model_id for n in window.model_watch.pending_media()] == [
            "veo-4.0-generate-preview"]
        assert "veo-4.0-generate-preview" not in window.model_list_cache.get("gemini", [])
    finally:
        window.model_list_cache.pop("gemini", None)
        if saved is not None:
            window.model_list_cache["gemini"] = saved


def test_the_tile_shows_the_media_section_and_dismisses_it(app, media_window):
    window = media_window
    card = window.model_updates_card
    window.model_watch.observe_media("qwen", ["wan3.0-video"])
    window.model_watch.observe_media("qwen", ["wan3.0-video", "wan3.5-video"])
    window.refresh_model_updates()
    assert card.media_box.isVisibleTo(card)
    assert card.media_title.text() == "VIDEO AND IMAGE"
    assert card.media_box.accessibleName() == "Video and image"
    assert card.media_headline.text() == "3 Veo models shut down in 8 days"
    assert window.model_updates_section._title == "Model updates · 1 new · 1 warning"
    names = [r.accessibleName() for r in card.media_rows]
    assert names[0] == ("Warning: Veo 3.1, Fast and Lite, earliest shutdown "
                        "22 October 2026, in 8 days")
    assert any("wan3.5-video" in n for n in names)
    assert card.media_dismiss_btn.isVisibleTo(card)
    assert card.media_dismiss_btn.accessibleName() == "Dismiss video and image notices"
    assert card.accessibleName() == (
        "New AI models and video and image changes from configured providers")
    # Media rows are not focusable; the media Dismiss comes before Check now.
    from PySide6.QtCore import Qt
    assert all(r.focusPolicy() == Qt.FocusPolicy.NoFocus for r in card.media_rows)
    chain, widget = [], card.media_dismiss_btn
    for _ in range(40):
        widget = widget.nextInFocusChain()
        chain.append(widget)
        if widget is card.check_btn:
            break
    assert card.check_btn in chain

    card.media_dismiss_btn.click()
    for _ in range(4):
        app.processEvents()
    assert window.model_watch.pending_media() == []
    assert not card.media_dismiss_btn.isVisibleTo(card)
    assert [r.accessibleName() for r in card.media_rows] == [names[0]]  # dates stay
    assert window.model_updates_section._title == "Model updates · 1 warning"


def test_a_removed_selected_chat_model_leads_the_chat_section(app, media_window):
    window = media_window
    clock = window.model_watch.clock
    window.model_watch.observe("qwen", ["qwen3.8-max", "qwen-plus"],
                               tracked=("qwen-plus",))
    for day in ("2026-10-15", "2026-10-16"):
        clock.day = day
        window.model_watch.observe("qwen", ["qwen3.8-max", "qwen4-max"],
                                   tracked=("qwen-plus",))
    window.refresh_model_updates()
    card = window.model_updates_card
    first = card.rows[0]
    assert first.notice.removed and first.mark is None
    assert first.accessibleName().startswith("Warning: Qwen no longer lists qwen-plus")
    assert card.marked() == []
    assert card.headline.text() == "1 new model"
    assert "2 warnings" in window.model_updates_section._title
    window.dismiss_new_models()
    assert window.model_watch.removals("chat") == []
    assert not any(r.notice.removed for r in card.rows)


def test_the_scan_passes_the_selected_chat_models_as_tracked(app, media_window,
                                                             monkeypatch):
    window = media_window
    seen = {}
    real = window.model_watch.observe

    def spy(provider, models, *, tracked=()):
        seen[provider] = tuple(tracked)
        return real(provider, models, tracked=tracked)

    monkeypatch.setattr(window.model_watch, "observe", spy)
    monkeypatch.setattr(window, "_selected_chat_models",
                        lambda provider: ("qwen3.8-max",))
    import main
    monkeypatch.setattr(main, "WATCHED_PROVIDERS", ("qwen",))
    monkeypatch.setattr(window, "qwen", types.SimpleNamespace(
        key_available=lambda: True, client=object()))
    saved = window.model_list_cache.get("qwen")
    try:
        window._on_model_scan_listed("qwen", ["qwen3.8-max"], "")
    finally:
        window.model_list_cache.pop("qwen", None)
        if saved is not None:
            window.model_list_cache["qwen"] = saved
    assert seen["qwen"] == ("qwen3.8-max",)


# ── review fix round 1: window ─────────────────────────────────────────────

@pytest.mark.parametrize("setting", ["missing", "false", 0, "true"])
def test_the_probe_is_off_unless_the_setting_is_json_true(
        app, media_window, monkeypatch, setting):
    """QA P1 / Sec P3-4: with a key, the chip on and budgets fine, the probe
    still sends nothing unless settings.json holds a real `true`."""
    window, fake = media_window, media_window.higgs
    if setting == "missing":
        monkeypatch.delitem(window.settings, "model_watch_probe_higgsfield")
    else:
        monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", setting)
    assert fake.configured and window.allow_higgsfield_checkbox.isChecked()
    assert window._higgsfield_probe_allowed() == "off"
    _scan(app, window)
    assert fake.probed == []


@pytest.mark.parametrize("gate", ["off", "not_permitted", "no_key", "refused"])
def test_a_not_answering_row_clears_once_the_probe_may_not_run(
        app, media_window, monkeypatch, gate):
    """CR P3-A: a stored "not answering" row has no Dismiss and clears only
    on a later answer, so a scan that may not probe forgets it."""
    window, fake = media_window, media_window.higgs
    fake.answers = {"/bytedance/seedance-2.0/image-to-video": "missing"}
    _scan(app, window)
    card = window.model_updates_card
    assert any("not answering" in r.accessibleName() for r in card.media_rows)

    window.model_watch.clock.day = "2026-10-15"
    if gate == "off":
        monkeypatch.setitem(window.settings, "model_watch_probe_higgsfield", False)
    elif gate == "not_permitted":
        window.allow_higgsfield_checkbox.setChecked(False)
    elif gate == "no_key":
        fake.configured = False
    else:
        monkeypatch.setattr(window, "session_budget_eur", 0.0)
        monkeypatch.setattr(window, "session_cost_total", 1.0)
    assert window._higgsfield_probe_allowed() == gate
    _scan(app, window)
    assert window.model_watch.probe_rows() == []
    assert not any("not answering" in r.accessibleName() for r in card.media_rows)
    assert len(fake.probed) == 4                    # the gated scan probed nothing


def test_a_second_scan_the_same_day_does_not_probe_again(app, media_window):
    window, fake = media_window, media_window.higgs
    _scan(app, window)
    assert len(fake.probed) == 4
    _scan(app, window)
    assert len(fake.probed) == 4
    window.model_watch.clock.day = "2026-10-15"
    _scan(app, window)
    assert len(fake.probed) == 8


def test_a_failed_save_on_dismiss_is_noted_not_raised(app, media_window, monkeypatch):
    """CR P3-7."""
    window = media_window
    noted = []
    monkeypatch.setattr(window, "_note_failure", lambda ctx, exc, *a: noted.append(ctx))

    def broken(*a, **k):
        raise OSError("disk full")
    with monkeypatch.context() as patch:     # undone before the fixture's teardown
        patch.setattr(window.model_watch, "acknowledge_media", broken)
        patch.setattr(window.model_watch, "acknowledge", broken)
        window.dismiss_media_notices()
        window.dismiss_new_models()
    assert noted == ["model updates: save", "model updates: save"]


@pytest.fixture
def owned(app):
    """Widgets a test builds on its own, destroyed before the test ends.

    A parentless card left to Python's garbage collector, with the
    deleteLater() of its replaced rows still queued, left a dangling widget
    that a later window's `app.allWidgets()` walk crashed on (segfault in
    ui/widgets.py install_dropdown_system, --randomly-seed=28367). Delete
    them now, on this thread, while nothing is walking the widget list.
    """
    import gc
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent
    widgets = []
    yield widgets.append
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    for widget in widgets:
        if shiboken6.isValid(widget):
            shiboken6.delete(widget)
    widgets.clear()
    gc.collect()
    app.processEvents()


def test_the_chat_overflow_line_does_not_call_removals_new(app, owned):
    """CR P3-1."""
    from ui.status_cards import ModelNotice, ModelUpdatesCard
    card = ModelUpdatesCard()
    owned(card)
    card.set_notices([ModelNotice("Qwen", f"qwen-old-{i}", provider="qwen",
                                  removed=True) for i in range(7)])
    texts = [w.text() for w in card.findChildren(type(card.headline))]
    assert "+2 more notices" in texts
    assert not any("marked NEW" in t for t in texts)
    card.set_notices([ModelNotice("Qwen", f"qwen-new-{i}", provider="qwen")
                      for i in range(7)])
    texts = [w.text() for w in card.findChildren(type(card.headline))]
    assert "+2 more — all are in the model menus, marked NEW." in texts


def test_rail_labels_never_render_markup(app, owned):
    """Sec P3-1: provider-sent text is shown as text."""
    from PySide6.QtCore import Qt
    from ui.status_cards import ElidedLabel, _label
    label, elided = _label("<b>x</b>", "RailDetail"), ElidedLabel("<b>x</b>")
    owned(label)
    owned(elided)
    assert label.textFormat() == Qt.TextFormat.PlainText
    assert elided.textFormat() == Qt.TextFormat.PlainText
