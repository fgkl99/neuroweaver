from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import validate, Draft202012Validator

from google import genai
from google.genai.errors import ClientError


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def parse_json_with_fences(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Model returned empty text.")

    # Strip markdown fences ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract first {...}
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in model output.")
        return json.loads(text[start:end + 1])


def fallback_feature_plan(summary: dict, assessor: dict) -> dict:
    """
    Deterministic feature plan for wearable low-density EEG.
    No LLM needed. This is intentional robustness.
    """
    ch = summary["channels"]
    bands = assessor.get("usable_bands", [])
    duration = float(summary.get("duration_sec", 0.0))
    conf_in = float(assessor.get("confidence", 0.1))

    feats = []

    # Safe defaults for short recordings
    window_sec = 2.0
    stride_sec = 1.0

    # Bandpower: only if alpha is usable (as per auditor)
    if "alpha" in bands:
        # Posterior alpha: O1/O2 then P3/P4
        for c in ["O1", "O2", "P3", "P4"]:
            if c in ch:
                feats.append({
                    "name": f"bandpower_alpha_{c.lower()}",
                    "family": "bandpower",
                    "channel_scope": "single_channel",
                    "params": {
                        "channel": c,
                        "band_hz": [8, 12],
                        "window_sec": window_sec,
                        "stride_sec": stride_sec
                    },
                    "rationale": "Posterior alpha bandpower is plausible with O1/O2 montage under wearable constraints."
                })

        # Frontal asymmetry (simple, common)
        if "F3" in ch and "F4" in ch:
            feats.append({
                "name": "alpha_asymmetry_f3_f4",
                "family": "bandpower",
                "channel_scope": "pair_lr",
                "params": {
                    "channels": ["F3", "F4"],
                    "band_hz": [8, 12],
                    "formula": "log(F4)-log(F3)",
                    "window_sec": window_sec,
                    "stride_sec": stride_sec
                },
                "rationale": "Frontal alpha asymmetry is a simple low-density feature; robust compared to complex spatial methods."
            })

    # Time-domain statistics: robust even in noisy wearable signals
    for c in ["F3", "F4", "C3", "C4", "O1", "O2"]:
        if c in ch:
            feats.append({
                "name": f"rms_{c.lower()}",
                "family": "time_domain",
                "channel_scope": "single_channel",
                "params": {
                    "channel": c,
                    "window_sec": window_sec,
                    "stride_sec": stride_sec
                },
                "rationale": "RMS is a robust amplitude feature; works with low SNR and low channel count."
            })

    # Spectral entropy: compact measure of spectral flatness/complexity
    for c in ["O1", "O2"]:
        if c in ch:
            feats.append({
                "name": f"spectral_entropy_{c.lower()}",
                "family": "spectral_entropy",
                "channel_scope": "single_channel",
                "params": {
                    "channel": c,
                    "band_hz": [4, 30],
                    "window_sec": window_sec,
                    "stride_sec": stride_sec
                },
                "rationale": "Spectral entropy summarizes spectral distribution and is implementable without heavy modeling."
            })

    # Keep it tight
    feats = feats[:12]

    notes = []
    if duration < 10:
        notes.append("Very short recording: plan is illustrative only; confidence is low.")
    notes.append("Connectivity features are intentionally excluded for wearable low-density EEG.")

    return {
        "recording_id": summary["recording_id"],
        "features": feats,
        "notes": notes,
        "confidence": min(conf_in, 0.2)
    }


def main():
    root = Path(".")
    runs_dir = root / "runs"
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    run_dir = run_folders[-1]
    print(f"[INFO] Using run folder: {run_dir}")

    summary = load_json(run_dir / "data_summary.json")
    assessor = load_json(run_dir / "llm_data_assessment.json")

    schema_path = root / "schemas" / "feature_plan_v0.schema.json"
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)

    # Build prompt (LLM optional)
    prompt_path = root / "prompts" / "prompt_002.txt"
    prompt_template = load_text(prompt_path)
    prompt = (
        prompt_template
        .replace("$DATA_SUMMARY_JSON", json.dumps(summary, indent=2))
        .replace("$LLM_DATA_ASSESSMENT_JSON", json.dumps(assessor, indent=2))
    )

    data = None

    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 600,  # reduce load
                    "response_mime_type": "application/json",
                },
            )
            data = parse_json_with_fences(resp.text or "")
            validate(instance=data, schema=schema)

            # Hard guardrail: ban connectivity in case it sneaks in
            joined = json.dumps(data).lower()
            for bad in ["connectivity", "coherence", "plv", "graph"]:
                if bad in joined:
                    raise ValueError(f"Guardrail violation: '{bad}' appeared in feature plan.")

            print("[OK] LLM feature plan generated.")
        except ClientError as e:
            # Quota / rate limit fallback
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("[WARN] 429 RESOURCE_EXHAUSTED. Falling back to deterministic plan.")
                data = fallback_feature_plan(summary, assessor)
                validate(instance=data, schema=schema)
            else:
                raise
        except Exception as e:
            print(f"[WARN] LLM step failed ({e}). Falling back to deterministic plan.")
            data = fallback_feature_plan(summary, assessor)
            validate(instance=data, schema=schema)
    else:
        print("[WARN] GEMINI_API_KEY not set. Using deterministic fallback plan.")
        data = fallback_feature_plan(summary, assessor)
        validate(instance=data, schema=schema)

    out_path = run_dir / "feature_plan.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()
