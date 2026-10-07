from __future__ import annotations
import os
import requests
from typing import Optional
from .base import VoiceProvider, VoiceConfig

_BASE_URL = "https://api.elevenlabs.io/v1"
# eleven_turbo_v2_5 is deprecated; eleven_flash_v2_5 replaces it at the same
# price (elevenlabs.io/docs/overview/models, checked 2026-10-07).
DEFAULT_MODEL = "eleven_flash_v2_5"
# voice_settings.speed accepts 0.7-1.2 (1.0 is normal); the API rejects values
# outside it rather than clamping.
SPEED_RANGE = (0.7, 1.2)


class ElevenLabsProvider(VoiceProvider):
    """
    ElevenLabs text-to-speech.
    Requires ELEVENLABS_API_KEY environment variable.
    Docs: https://docs.elevenlabs.io/api-reference
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model = model
        if not self._api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")

    @property
    def name(self) -> str:
        return "elevenlabs"

    def _headers(self) -> dict:
        return {"xi-api-key": self._api_key, "Content-Type": "application/json"}

    def list_voices(self, max_pages: int = 10) -> list[dict]:
        """Every voice on the account, from the current paginated endpoint.

        GET /v1/voices is legacy and stops working once a workspace holds more
        than 500 voices (elevenlabs.io/docs, checked 2026-10-07); /v2/voices
        pages 100 at a time.
        """
        voices: list[dict] = []
        token = None
        for _page in range(max_pages):
            params = {"page_size": 100, "include_total_count": "false"}
            if token:
                params["next_page_token"] = token
            r = requests.get("https://api.elevenlabs.io/v2/voices",
                             headers=self._headers(), params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            voices += [
                {"id": v["voice_id"], "name": v["name"],
                 "preview_url": v.get("preview_url")}
                for v in data.get("voices", [])
            ]
            token = data.get("next_page_token")
            if not data.get("has_more") or not token:
                break
        return voices

    def synthesize(
        self,
        text: str,
        output_path: str,
        config: Optional[VoiceConfig] = None,
    ) -> str:
        cfg = config or VoiceConfig()
        voice_id = cfg.voice_id if cfg.voice_id != "default" else "21m00Tcm4TlvDq8ikWAM"  # Rachel

        low, high = SPEED_RANGE
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": cfg.stability,
                "similarity_boost": cfg.similarity_boost,
                # The field is `speed`; `speaking_rate` was never an API
                # field, so every speed setting was silently ignored.
                "speed": min(high, max(low, float(cfg.speaking_rate))),
            },
        }

        r = requests.post(
            f"{_BASE_URL}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
            json=payload,
            headers={**self._headers(), "Accept": "audio/mpeg"},
            timeout=120,
        )
        r.raise_for_status()

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(r.content)

        return output_path
