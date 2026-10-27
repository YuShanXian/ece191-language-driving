"""Validate parser outputs before they become executable stages."""

import json, math
from pathlib import Path

SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text())


def validate(value, schema=SCHEMA, path="plan"):
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "number": lambda v: type(v) in (int, float) and math.isfinite(v),
        "integer": lambda v: type(v) is int,
        "boolean": lambda v: type(v) is bool,
        "null": lambda v: v is None,
    }
    if kinds and not any(checks[k](value) for k in kinds):
        raise ValueError(path + ": invalid value type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(path + ": unknown value")
    if isinstance(value, dict):
        fields = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            raise ValueError(path + ": missing field")
        if schema.get("additionalProperties") is False and any(k not in fields for k in value):
            raise ValueError(path + ": unknown field")
        for key, item in value.items():
            if key in fields:
                validate(item, fields[key], path + "." + key)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ValueError(path + ": too many items")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), path + f"[{i}]")
    elif type(value) in (int, float):
        if not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
            raise ValueError(path + ": out of range")


def validate_stage(value):
    schema = SCHEMA["properties"]["stages"]["items"]
    schema = {
        **schema,
        "properties": {
            **schema["properties"],
            "speed_delta_mps": {"type": "number", "minimum": 0, "maximum": 15},
        },
    }
    validate(value, schema, "stage")
