"""Routing phase 1 — the provider registry and a second local provider.

One rule: a provider is local because its spec says so, never because its name
is the string "ollama". LM Studio is the second local provider that proves it
— free, private, no permission, no paid-request dialog — while it stays
unrated, so the ranker never picks it over rated models by itself.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.recommendation_profiles import profile_for
from services import pricing_catalog, providers
from services.recommendations import (
    Candidate, RecommendationContext, RecommendationEngine,
)
from services.recommendations.catalog import (
    provider_configured, text_candidate,
)
from services.registry import Registry
from services.validator import Validator

GB = 1e9


def test_lmstudio_is_listed_beside_ollama_in_the_price_table_providers():
    assert pricing_catalog.PROVIDER_LABELS["lmstudio"] == "LM Studio"
    assert "lmstudio" in pricing_catalog.TEXT_PROVIDERS


# ── candidates: free, private, unrated ─────────────────────────────────────

def test_a_lmstudio_candidate_is_priced_zero_and_scored_private():
    item = text_candidate("lmstudio", "dolphin3.0-llama3.1-8b")
    assert item.privacy == 1.0
    assert item.price_per_1m == 0.0
    cloud = text_candidate("openai", "gpt-4o")
    assert cloud.privacy < 1.0


def test_lmstudio_gets_the_same_priors_as_ollama():
    a = text_candidate("ollama", "x-14b")
    b = text_candidate("lmstudio", "x-14b")
    assert (a.quality, a.speed, a.cost_efficiency, a.privacy) \
        == (b.quality, b.speed, b.cost_efficiency, b.privacy)


def test_a_local_provider_is_not_available_until_the_app_has_seen_its_models():
    # No API key to check; the window promotes it once a live list exists.
    assert provider_configured("lmstudio") is False
    assert provider_configured("local") is True


def _rated(provider, model, rating, price, **extra):
    values = dict(
        provider=provider, model_id=model, label=model,
        task_fit={"general": .8}, quality=.8, reliability=.8,
        cost_efficiency=.55, speed=.7, context=.7, available=True,
        ratings={"general": rating} if rating is not None else {},
        price_per_1m=price)
    values.update(extra)
    return Candidate(**values)


def test_an_unrated_lmstudio_model_never_beats_rated_models():
    chat = profile_for("chat")
    result = RecommendationEngine().recommend(chat, [
        _rated("lmstudio", "dolphin3.0-llama3.1-8b", None, 0.0, privacy=1.0),
        _rated("openai", "gpt-4o", 1400, 5.0),
        _rated("anthropic", "claude-sonnet-5-5", 1395, 6.0),
    ], RecommendationContext(agent="chat"))
    assert result.basis == "rating"
    assert result.candidate.provider != "lmstudio"


def test_a_rated_free_local_model_inside_the_band_wins_on_price():
    chat = profile_for("chat")
    result = RecommendationEngine().recommend(chat, [
        _rated("lmstudio", "tuned", 1395, 0.0, privacy=1.0, cost_efficiency=1.0),
        _rated("openai", "gpt-4o", 1400, 5.0),
    ], RecommendationContext(agent="chat"))
    assert result.candidate.provider == "lmstudio"       # a known price of zero


def test_a_zero_price_cloud_model_is_still_unknown_not_free():
    chat = profile_for("chat")
    result = RecommendationEngine().recommend(chat, [
        _rated("openai", "mystery", 1400, 0.0),
        _rated("anthropic", "claude-sonnet-5-5", 1395, 6.0),
    ], RecommendationContext(agent="chat"))
    assert result.candidate.model_id == "claude-sonnet-5-5"


# ── validation and the registry's allow-lists ──────────────────────────────

class _Registry:
    def __getattr__(self, name):
        if name.startswith(("is_", "agent_allows", "tool_allows")):
            return lambda *a: True
        return lambda *a: None


def _validate(provider):
    perms = {f"allow_{p}": False for p in providers.CLOUD_PROVIDERS}
    return Validator(_Registry()).validate(
        agent_name="chat", tool_name="General Chat", provider=provider,
        api_permissions=perms, session_cost=0.0, session_budget=0.0,
        daily_cost=0.0, daily_budget=0.0, estimated_cost=99.0)


def test_a_local_provider_needs_no_permission_and_ignores_every_budget():
    for name in providers.LOCAL_PROVIDERS:
        assert _validate(name).allowed, name
    assert not _validate("openai").allowed


def _reg(agent, tool=None):
    reg = Registry.__new__(Registry)
    reg.get_agent = lambda name: agent if name == "a" else None
    reg.get_tool = lambda name: tool if name == "t" else None
    return reg


def test_an_agent_allowed_ollama_may_use_lmstudio_too():
    reg = _reg({"allowed_providers": ["ollama", "openai"]})
    assert reg.agent_allows_provider("a", "lmstudio")
    assert not reg.agent_allows_provider("a", "gemini")


def test_a_cloud_only_agent_still_refuses_local_providers():
    reg = _reg({"allowed_providers": ["openai", "gemini"]})
    assert not reg.agent_allows_provider("a", "lmstudio")


# ── running, resolving and fitting ─────────────────────────────────────────

def test_run_backend_dispatches_lmstudio_to_its_client_and_fit_checks_it():
    import main
    asked, calls = [], []

    class LM:
        def stream_chat(self, messages, model):
            calls.append(model); yield "tok"

    def assess(model, provider="ollama", **kw):
        asked.append((model, provider)); return None

    stub = SimpleNamespace(lmstudio=LM(), assess_local_model=assess)
    out = main.GodAI.run_backend(stub, "lmstudio", "m", [], "x")
    assert list(out) == ["tok"] and asked == [("m", "lmstudio")] and calls == ["m"]


def test_run_backend_refuses_an_unknown_backend():
    import main
    window_cls = main.GodAI
    with pytest.raises(RuntimeError, match="No compatible backend"):
        window_cls.run_backend(SimpleNamespace(), "legacy-provider", "m", [], "p")


def test_assess_local_model_reads_lmstudio_sizes(monkeypatch):
    import main
    import psutil
    window_cls = main.GodAI
    stub = SimpleNamespace(lmstudio=SimpleNamespace(model_size_bytes=lambda m: 15 * GB),
                           ollama=SimpleNamespace(model_size_bytes=lambda m: None))
    monkeypatch.setattr(psutil, "virtual_memory",
                        lambda: SimpleNamespace(total=24 * GB, available=9 * GB))
    verdict = window_cls.assess_local_model(stub, "dsr1-32b", "lmstudio")
    assert verdict["level"] == "tight" and "free right now" in verdict["message"]
    assert window_cls.assess_local_model(
        SimpleNamespace(lmstudio=SimpleNamespace(model_size_bytes=lambda m: None)),
        "unknown", "lmstudio") is None


def test_there_is_no_provider_name_comparison_left_in_the_app():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in [root / "main.py", *root.glob("services/**/*.py"), *root.glob("ui/**/*.py")]:
        if path.name in {"providers.py", "lmstudio_client.py"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if '== "ollama"' in line or '!= "ollama"' in line:
                offenders.append(f"{path.relative_to(root)}:{number}: {line.strip()}")
    # Ollama-only features keep the literal: the Muse Glimmer pull button and
    # the published-size fallback.
    allowed = ('if published_gb is None or provider != "ollama":',
               'if self.provider_box.currentText() == "ollama":',
               'details=details if provider == "ollama" else None)',
               'if not models and provider == "ollama":',
               'if kind == "ollama":',
               'if provider == "ollama":')
    stray = [o for o in offenders if not o.endswith(allowed)]
    assert not stray, "\n".join(stray)


def test_every_agent_panel_that_offers_ollama_offers_lmstudio_too():
    root = Path(__file__).resolve().parents[1]
    for path in root.glob("agents/*/panel.py"):
        text = path.read_text(encoding="utf-8")
        assert ('"ollama"' in text) == ('"lmstudio"' in text), path.name


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.skipif(not (Path.home() / ".lmstudio" / "models").is_dir(),
                    reason="LM Studio has no models folder on this machine")
def test_every_uncensored_download_on_this_machine_is_tagged_and_no_other():
    from services import lmstudio_client
    for model in lmstudio_client.scan_disk():
        text = f"{model['name']} {Path(model['path']).name}"
        tag = providers.uncensored_tag(text, model["publisher"])
        looks_uncensored = any(w in text.casefold()
                               for w in ("abliterat", "dolphin", "uncensor"))
        assert bool(tag) == looks_uncensored, text


# ── the pickers tag uncensored models ──────────────────────────────────────

def _amber_pixels(widget) -> int:
    image = widget.grab().toImage()
    count = 0
    for x in range(0, image.width()):
        for y in range(0, image.height()):
            c = image.pixelColor(x, y)
            if c.red() > 170 and 110 < c.green() < 200 and c.blue() < 110:
                count += 1
    return count


def test_the_closed_picker_paints_a_tag_for_an_abliterated_model_only(qapp):
    from PySide6.QtWidgets import QComboBox
    from ui.widgets import polish_combo
    combo = QComboBox()
    combo.resize(320, 34)
    combo.addItems(["deepseek-r1:8b", "DeepSeek-R1-Distill-Qwen-14B-abliterated"])
    polish_combo(combo)
    combo.show()
    plain = _amber_pixels(combo)
    combo.setCurrentIndex(1)
    assert _amber_pixels(combo) > plain + 40
    combo.close()


def test_the_popup_row_of_an_uncensored_model_is_wider_and_has_a_note(qapp):
    from PySide6.QtCore import QModelIndex
    from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem
    from ui import widgets
    combo = QComboBox()
    combo.addItems(["llama3.1:8b", "dolphin3.0-llama3.1-8b"])
    delegate = widgets.DropdownItemDelegate(combo)
    option = QStyleOptionViewItem()
    plain = delegate.sizeHint(option, combo.model().index(0, 0)).width()
    tagged = delegate.sizeHint(option, combo.model().index(1, 0)).width()
    assert tagged - plain > widgets.TAG_WIDTH - 40
    assert "not to refuse" in widgets.TAG_NOTES["uncensored"]
    assert "refusal behaviour was removed" in widgets.TAG_NOTES["abliterated"]
