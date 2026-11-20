"""AI-use facts per kit output (legal L2, L5, N4; spec A4).

Slice 1 is a recorder only (owner decision, Architect gate 7): the facts go
into each item's `ai_json`, a `provenance.json` sidecar in the output folder,
the report's "AI used in this kit" section and the CSV's "AI used" column.
Embedded marking (ID3/MP4 tags, OPF meta, PNG tEXt, C2PA) waits for lawyer
trigger T1; nothing here writes into an output file.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.release_kit import ledger

SIDECAR = "provenance.json"


def _model_name(stage_row: dict) -> str:
    runtime = {"ollama": "Ollama", "lmstudio": "LM Studio"}.get(
        stage_row.get("provider", ""), stage_row.get("provider", ""))
    model = stage_row.get("model", "")
    return f"{model} ({runtime}, on this Mac)" if model else runtime


def ai_facts(stage_row: dict, *, quote_model: str = "") -> dict:
    """Facts only, no judgement on whether a label is required."""
    key = stage_row["stage"]
    if key == "quotes":
        return {"ai": True, "what": "quotes chosen by a model from your text",
                "provider": stage_row["provider"], "model": stage_row["model"],
                "words": "yours, verbatim"}
    if key == "captions":
        return {"ai": True, "what": "captions written by a model",
                "provider": stage_row["provider"], "model": stage_row["model"]}
    if key == "shorts":
        return {"ai": None, "what": "synthetic voice",
                "route": stage_row["provider"], "voice": stage_row["voice"],
                "engine": "macOS say" if stage_row["provider"] == "system"
                else stage_row["provider"],
                "quote_chosen_by": quote_model}
    if key == "graphics":
        return {"ai": False, "what": "made on this Mac without an AI model",
                "quote_chosen_by": quote_model}
    return {"ai": False, "what": "made on this Mac without an AI model"}


def csv_ai_cell(slot_format: str, shorts_row: dict, captions_row: dict,
                captioned: bool = True) -> str:
    """Legal L5: a factual per-slot cell; the owner sets platform labels."""
    parts = []
    if slot_format == "short":
        parts.append(f"voice: synthetic (macOS {shorts_row.get('voice') or 'say'})")
    parts.append(f"caption: written by {_model_name(captions_row)}"
                 if captioned else "caption: none")
    return "; ".join(parts)


def write_sidecar(job_id: str) -> Path | None:
    """Rewrite `provenance.json` from the ledger alone."""
    job = ledger.get_job(job_id)
    if not job or not job["output_dir"]:
        return None
    outputs = [
        {"path": row["output_path"], "kind": row["output_kind"],
         "sha256": row["output_sha256"], "stage": row["stage"],
         "item": row["item_key"], "ai": row["ai"]}
        for row in ledger.done_outputs(job_id)
        if Path(row["output_path"]).name != SIDECAR]
    data = {
        "release_kit": job_id,
        "project": job["project_id"],
        "approved_version": job["version"],
        "source_sha256": job["source_sha256"],
        "note": ("Facts recorded by Imprint. No AI marking is embedded in "
                 "these files."),
        "outputs": outputs,
    }
    path = Path(job["output_dir"]) / SIDECAR
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path
