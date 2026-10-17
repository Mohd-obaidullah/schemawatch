from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemawatch.redact import (
    DEFAULT_MAX_ARRAY_LENGTH,
    DEFAULT_MAX_OBJECT_KEYS,
    is_dynamic_map,
)


@dataclass
class SchemaNode:
    """Represents an inferred or merged schema node."""

    types: set[str] = field(default_factory=set)
    properties: dict[str, SchemaNode] = field(default_factory=dict)
    required: set[str] = field(default_factory=set)
    items: SchemaNode | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the SchemaNode into a JSON-serializable dictionary."""
        result: dict[str, Any] = {
            "types": sorted(self.types),
        }
        if self.properties:
            result["properties"] = {k: v.to_dict() for k, v in sorted(self.properties.items())}
        if self.required:
            result["required"] = sorted(self.required)
        if self.items is not None:
            result["items"] = self.items.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaNode:
        """Construct a SchemaNode from a dictionary representation."""
        node = cls(types=set(data.get("types", [])))
        if "properties" in data:
            node.properties = {k: cls.from_dict(v) for k, v in data["properties"].items()}
        if "required" in data:
            node.required = set(data["required"])
        if "items" in data and data["items"] is not None:
            node.items = cls.from_dict(data["items"])
        return node

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SchemaNode):
            return False
        return (
            self.types == other.types
            and self.properties == other.properties
            and self.required == other.required
            and self.items == other.items
        )


def infer_schema(
    value: Any,
    *,
    max_array_length: int = DEFAULT_MAX_ARRAY_LENGTH,
    max_object_keys: int = DEFAULT_MAX_OBJECT_KEYS,
    current_depth: int = 0,
    max_depth: int = 32,
) -> SchemaNode:
    """Infer the schema shape from a Python/JSON value.

    Types recognized: null, boolean, integer, number, string, array, object.
    Booleans are checked before integers because bool is a subclass of int in Python.

    Args:
        value: The JSON value to infer a schema for.
        max_array_length: Maximum number of array elements to inspect.
        max_object_keys: Maximum number of object keys before treating as a wildcard map.
        current_depth: Current recursion depth.
        max_depth: Maximum recursion depth allowed before truncation.

    Returns:
        SchemaNode describing the type and nested structure.
    """
    if current_depth > max_depth:
        if isinstance(value, dict):
            return SchemaNode(types={"object"})
        return SchemaNode(types={"string"})

    if value is None:
        return SchemaNode(types={"null"})

    # Check bool before int, as bool is a subclass of int
    if isinstance(value, bool):
        return SchemaNode(types={"boolean"})
    if isinstance(value, int):
        return SchemaNode(types={"integer"})
    if isinstance(value, float):
        return SchemaNode(types={"number"})
    if isinstance(value, str):
        return SchemaNode(types={"string"})
    if isinstance(value, dict):
        if is_dynamic_map(value.keys(), max_keys=max_object_keys):
            merged_val: SchemaNode | None = None
            for v in value.values():
                val_node = infer_schema(
                    v,
                    max_array_length=max_array_length,
                    max_object_keys=max_object_keys,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                )
                merged_val = merge(merged_val, val_node) if merged_val is not None else val_node
            fallback = SchemaNode(types={"null"})
            item_node = merged_val if merged_val is not None else fallback
            return SchemaNode(
                types={"object"},
                properties={"*": item_node},
                required={"*"},
            )
        properties: dict[str, SchemaNode] = {}
        required: set[str] = set()
        for k, v in value.items():
            k_str = str(k)
            properties[k_str] = infer_schema(
                v,
                max_array_length=max_array_length,
                max_object_keys=max_object_keys,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            )
            required.add(k_str)
        return SchemaNode(types={"object"}, properties=properties, required=required)
    if isinstance(value, (list, tuple)):
        truncated = value[:max_array_length]
        if not truncated:
            return SchemaNode(types={"array"}, items=None)
        item_schema = infer_schema(
            truncated[0],
            max_array_length=max_array_length,
            max_object_keys=max_object_keys,
            current_depth=current_depth + 1,
            max_depth=max_depth,
        )
        for elem in truncated[1:]:
            item_schema = merge(
                item_schema,
                infer_schema(
                    elem,
                    max_array_length=max_array_length,
                    max_object_keys=max_object_keys,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                ),
            )
        return SchemaNode(types={"array"}, items=item_schema)

    return SchemaNode(types={"string"})


def merge(node_a: SchemaNode, node_b: SchemaNode) -> SchemaNode:
    """Merge two schema nodes into a unified schema.

    - Types are unioned.
    - Properties are merged across object nodes.
    - Required fields are the intersection of required fields (only fields present
      in all samples remain required).
    - Array item schemas are merged recursively.
    - Order-independent (commutative and associative).
    """
    merged_types = node_a.types | node_b.types

    # Merge properties
    merged_properties: dict[str, SchemaNode] = {}
    all_prop_keys = node_a.properties.keys() | node_b.properties.keys()
    for prop in all_prop_keys:
        if prop in node_a.properties and prop in node_b.properties:
            merged_properties[prop] = merge(node_a.properties[prop], node_b.properties[prop])
        elif prop in node_a.properties:
            merged_properties[prop] = node_a.properties[prop]
        else:
            merged_properties[prop] = node_b.properties[prop]

    # Required fields is the intersection across samples
    merged_required = node_a.required & node_b.required

    # Merge array items
    merged_items: SchemaNode | None = None
    if node_a.items is not None and node_b.items is not None:
        merged_items = merge(node_a.items, node_b.items)
    elif node_a.items is not None:
        merged_items = node_a.items
    elif node_b.items is not None:
        merged_items = node_b.items

    return SchemaNode(
        types=merged_types,
        properties=merged_properties,
        required=merged_required,
        items=merged_items,
    )
