import json
from pathlib import Path
from jsonschema import validate, Draft202012Validator

def test_bandpower_meta_validates_against_schema():
    schema_path = Path("schemas/feature_meta.schema.json")
    meta_path = Path("features/bandpower/meta.json")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    validate(instance=meta, schema=schema)
