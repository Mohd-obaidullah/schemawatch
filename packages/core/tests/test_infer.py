from __future__ import annotations

from schemawatch.infer import DYNAMIC_KEY_WILDCARD, SchemaNode, infer_schema, merge


def test_infer_primitives() -> None:
    assert infer_schema(None).types == {"null"}
    assert infer_schema(True).types == {"boolean"}
    assert infer_schema(False).types == {"boolean"}
    assert infer_schema(42).types == {"integer"}
    assert infer_schema(3.14).types == {"number"}
    assert infer_schema("hello").types == {"string"}


def test_infer_bool_before_int() -> None:
    node = infer_schema(True)
    assert node.types == {"boolean"}
    assert "integer" not in node.types


def test_infer_object() -> None:
    obj = {"id": 1, "name": "Alice", "active": True}
    node = infer_schema(obj)
    assert node.types == {"object"}
    assert node.required == {"id", "name", "active"}
    assert node.properties["id"].types == {"integer"}
    assert node.properties["name"].types == {"string"}
    assert node.properties["active"].types == {"boolean"}


def test_infer_array() -> None:
    empty_arr = infer_schema([])
    assert empty_arr.types == {"array"}
    assert empty_arr.items is None

    homog_arr = infer_schema([1, 2, 3])
    assert homog_arr.types == {"array"}
    assert homog_arr.items is not None
    assert homog_arr.items.types == {"integer"}

    hetero_arr = infer_schema([1, "text", 2.5])
    assert hetero_arr.types == {"array"}
    assert hetero_arr.items is not None
    assert hetero_arr.items.types == {"integer", "string", "number"}


def test_schema_node_dict_roundtrip() -> None:
    node = infer_schema(
        {
            "user": {"id": 100, "tags": ["admin", "dev"]},
            "score": 9.5,
        }
    )
    as_dict = node.to_dict()
    restored = SchemaNode.from_dict(as_dict)
    assert restored == node


def test_merge_unions_types() -> None:
    node_a = infer_schema(10)
    node_b = infer_schema("test")
    merged = merge(node_a, node_b)
    assert merged.types == {"integer", "string"}


def test_merge_required_fields_intersection() -> None:
    # Sample 1 has required {a, b}
    node_1 = infer_schema({"a": 1, "b": "foo"})
    # Sample 2 has required {a, c} (b is omitted, c is added)
    node_2 = infer_schema({"a": 2, "c": True})

    merged = merge(node_1, node_2)
    assert merged.types == {"object"}
    assert merged.required == {"a"}  # Only 'a' was present in both
    assert set(merged.properties.keys()) == {"a", "b", "c"}
    assert merged.properties["a"].types == {"integer"}
    assert merged.properties["b"].types == {"string"}
    assert merged.properties["c"].types == {"boolean"}


def test_merge_mixed_object_and_non_object() -> None:
    # Sample 1 is an object
    node_obj = infer_schema({"user_id": 100, "role": "admin"})
    # Sample 2 is null
    node_null = infer_schema(None)

    merged = merge(node_obj, node_null)
    assert merged.types == {"object", "null"}
    assert "user_id" in merged.properties
    assert merged.required == set()  # Not present in null sample, so not required


def test_merge_arrays() -> None:
    node_1 = infer_schema([1, 2])
    node_2 = infer_schema(["a", "b"])
    merged = merge(node_1, node_2)
    assert merged.types == {"array"}
    assert merged.items is not None
    assert merged.items.types == {"integer", "string"}


def test_schema_node_eq_with_non_node() -> None:
    node = SchemaNode(types={"string"})
    assert node != "not a node"
    assert node != 123


def test_infer_schema_unknown_object_fallback() -> None:
    node = infer_schema(object())
    assert node.types == {"string"}


def test_infer_schema_large_object_treated_as_map() -> None:
    large_dict = {f"k_{i}": i * 10 for i in range(60)}
    node = infer_schema(large_dict)
    assert node.types == {"object"}
    assert node.is_map
    assert DYNAMIC_KEY_WILDCARD in node.properties
    assert node.properties[DYNAMIC_KEY_WILDCARD].types == {"integer"}
    assert node.required == {DYNAMIC_KEY_WILDCARD}

    # Serialization preserves '*' key and marks is_map
    serialized = node.to_dict()
    assert serialized.get("is_map") is True
    assert "*" in serialized["properties"]
    assert serialized["properties"]["*"]["types"] == ["integer"]

    # Deserialization restores DYNAMIC_KEY_WILDCARD
    restored = SchemaNode.from_dict(serialized)
    assert restored == node
    assert restored.is_map
    assert DYNAMIC_KEY_WILDCARD in restored.properties


def test_legacy_baseline_deserialization_compatibility() -> None:
    """Ensure existing persisted baselines without 'is_map' flag still load as dynamic maps."""
    legacy_data = {
        "types": ["object"],
        "properties": {"*": {"types": ["string"]}},
        "required": ["*"],
    }
    node = SchemaNode.from_dict(legacy_data)
    assert node.is_map
    assert DYNAMIC_KEY_WILDCARD in node.properties
    assert node.properties[DYNAMIC_KEY_WILDCARD].types == {"string"}
    assert node.required == {DYNAMIC_KEY_WILDCARD}
