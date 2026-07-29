# core/schema_utils.py
"""
JSON Schema conversion helpers.

entity_schema_v2.json is written in Gemini-style JSON Schema (uppercase
type names: "OBJECT", "ARRAY", "STRING", ...). OpenAI Structured Outputs and
Anthropic tool input_schema both expect standard lowercase JSON Schema types;
OpenAI's strict mode additionally requires `additionalProperties: false` on
every object and every property listed in `required` (fields that were
originally optional become nullable instead).
"""

_TYPE_MAP = {
    "OBJECT": "object",
    "ARRAY": "array",
    "STRING": "string",
    "NUMBER": "number",
    "INTEGER": "integer",
    "BOOLEAN": "boolean",
}


def lowercase_schema_types(schema):
    """Recursively return a copy of schema with uppercase type names lowercased."""
    if isinstance(schema, dict):
        result = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, str) and value in _TYPE_MAP:
                result[key] = _TYPE_MAP[value]
            else:
                result[key] = lowercase_schema_types(value)
        return result
    if isinstance(schema, list):
        return [lowercase_schema_types(item) for item in schema]
    return schema


def _make_nullable(prop_schema):
    prop_type = prop_schema.get("type")
    if isinstance(prop_type, list):
        if "null" not in prop_type:
            prop_type.append("null")
    elif prop_type is not None:
        prop_schema["type"] = [prop_type, "null"]
    if "enum" in prop_schema and None not in prop_schema["enum"]:
        prop_schema["enum"] = prop_schema["enum"] + [None]


def _make_strict(node):
    if isinstance(node, dict):
        node = {key: _make_strict(value) for key, value in node.items()}
        if node.get("type") == "object" and "properties" in node:
            original_required = set(node.get("required", []))
            properties = node["properties"]
            for prop_name, prop_schema in properties.items():
                if prop_name not in original_required:
                    _make_nullable(prop_schema)
            node["required"] = list(properties.keys())
            node["additionalProperties"] = False
        return node
    if isinstance(node, list):
        return [_make_strict(item) for item in node]
    return node


def to_openai_strict_schema(schema: dict) -> dict:
    """
    Convert a Gemini-style schema into an OpenAI Structured Outputs
    strict-mode schema: lowercase types, additionalProperties: false on every
    object, and every property listed in `required` (fields not originally
    required become nullable via a ["type", "null"] union).
    """
    return _make_strict(lowercase_schema_types(schema))


def to_anthropic_tool_schema(schema: dict) -> dict:
    """Convert a Gemini-style schema into an Anthropic tool input_schema (lowercase types)."""
    return lowercase_schema_types(schema)


__all__ = ["lowercase_schema_types", "to_openai_strict_schema", "to_anthropic_tool_schema"]
