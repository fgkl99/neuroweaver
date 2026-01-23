import json
from pathlib import Path
from jsonschema import Draft202012Validator

def test_feature_meta_schema_is_valid_json():
    p = Path("schemas/feature_meta.schema.json")
    assert p.exists()
    raw = p.read_text(encoding="utf-8").strip()
    assert raw, "feature_meta.schema.json is empty"
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
