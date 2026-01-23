from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import validate, Draft202012Validator

# Gemini SDK (pip install google-genai)
from google import genai


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def strict_parse_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Model returned empty text.")

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence line (``` or ```json)
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        # drop last fence line (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # First try pure JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end+1])


def main():
    root = Path(".")
    runs_dir = root / "runs"

    # Pick latest run folder (you can hardcode if you prefer)
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    run_dir = run_folders[-1]
    print(f"[INFO] Using run folder: {run_dir}")

    checks = load_json(run_dir / "checks.json")
    summary = load_json(run_dir / "data_summary.json")

    prompt_path = root / "prompts" / "prompt_001.txt"
    prompt_template = load_text(prompt_path)

    prompt = (
        prompt_template
        .replace("$CHECKS_JSON", json.dumps(checks, indent=2))
        .replace("$DATA_SUMMARY_JSON", json.dumps(summary, indent=2))
    )

    schema = load_json(root / "schemas" / "llm_data_assessment_v0.schema.json")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("Set GEMINI_API_KEY env var first.")

    client = genai.Client(api_key=api_key)

    # Choose a model you have access to; "gemini-2.0-flash" is usually available
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    resp = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            "temperature": 0.2,
            "max_output_tokens": 800,
        },
    )

    text = (resp.text or "").strip()
    print("\n=== RAW MODEL OUTPUT (first 500 chars) ===")
    print(text[:500])
    print("=== END RAW OUTPUT ===\n")

    if not text:
        raise RuntimeError("Empty response from model.")

    data = strict_parse_json(text)

    # Validate against schema
    Draft202012Validator.check_schema(schema)
    validate(instance=data, schema=schema)
    # Hard guardrail: ban connectivity for this project scope
    bad_terms = ["connectivity", "coherence", "plv", "pli", "wpli", "graph"]
    rec = " ".join([s.lower() for s in data.get("recommended_feature_families", [])])
    if any(t in rec for t in bad_terms):
        raise ValueError("Guardrail violation: connectivity recommended for wearable EEG scope.")


    out_path = run_dir / "llm_data_assessment.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()
