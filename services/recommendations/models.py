"""Data contracts shared by agents, the ranker and the GUI.

The engine deliberately receives plain immutable values.  It can therefore be
tested without Qt, provider SDKs or network access, and the GUI never has to
reverse-engineer meaning from colours or display strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class AgentProfile:
    key: str
    label: str
    task_tags: tuple[str, ...]
    quality_weight: float = 0.40
    reliability_weight: float = 0.20
    cost_weight: float = 0.15
    speed_weight: float = 0.10
    context_weight: float = 0.10
    privacy_weight: float = 0.05
    provider_affinity: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    provider: str
    model_id: str
    label: str
    modality: str = "text"
    kind: str = "text"
    task_fit: Mapping[str, float] = field(default_factory=dict)
    quality: float = 0.65
    reliability: float = 0.70
    cost_efficiency: float = 0.60
    speed: float = 0.60
    context: float = 0.65
    privacy: float = 0.0
    available: bool | None = None
    retired: bool = False
    aspects: tuple[str, ...] = ()
    durations: tuple[int, ...] = ()
    estimated_cost: float | None = None
    # Quality per task tag where public ratings rate this kind of work on its
    # own (coding, creative writing...); a tag not listed is scored on
    # `quality`. `quality_evidence` says what each rated figure rests on, by
    # tag ("general" for `quality` itself), and `quality_credit` is the credit
    # the ratings' licence requires wherever one is shown.
    task_quality: Mapping[str, float] = field(default_factory=dict)
    quality_evidence: Mapping[str, str] = field(default_factory=dict)
    quality_credit: str = ""


@dataclass(frozen=True)
class RecommendationContext:
    agent: str
    modality: str = "text"
    task: str = ""
    selected_provider: str | None = None
    required_kind: str | None = None
    aspect: str | None = None
    duration: int | None = None
    budget_remaining: float | None = None
    priority: str = "balanced"  # balanced | quality | cost | speed | privacy


@dataclass(frozen=True)
class RecommendationResult:
    candidate: Candidate
    score: float
    confidence: str
    reason: str
    fallback: bool = False
    # Winner's score minus the runner-up's. 0 is a tie, decided only by the
    # deterministic order of ids — which must never be reported as a win:
    # "qwen4" sorting after "qwen3.8" is not evidence.
    margin: float = 0.0

    @property
    def badge(self) -> str:
        return "BEST FIT"
