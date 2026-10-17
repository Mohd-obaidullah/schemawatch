from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from schemawatch.diff import diff
from schemawatch.infer import infer_schema, merge

# Strategy for recursive JSON-like data
json_primitives = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)

json_data = st.recursive(
    json_primitives,
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(min_size=1, max_size=10), children, max_size=5)
    ),
    max_leaves=15,
)


@given(json_data)
@settings(max_examples=500)
def test_payload_never_drifts_from_itself(payload: Any) -> None:
    """Property test: A payload never drifts from a baseline built from itself."""
    schema = infer_schema(payload)
    changes = diff(schema, schema)
    assert changes == []


@given(json_data, json_data)
@settings(max_examples=500)
def test_merge_is_commutative(payload_a: Any, payload_b: Any) -> None:
    """Property test: merge(A, B) == merge(B, A)."""
    schema_a = infer_schema(payload_a)
    schema_b = infer_schema(payload_b)

    merged_ab = merge(schema_a, schema_b)
    merged_ba = merge(schema_b, schema_a)

    assert merged_ab == merged_ba


@given(json_data, json_data, json_data)
@settings(max_examples=500)
def test_merge_is_associative(payload_a: Any, payload_b: Any, payload_c: Any) -> None:
    """Property test: merge(merge(A, B), C) == merge(A, merge(B, C))."""
    schema_a = infer_schema(payload_a)
    schema_b = infer_schema(payload_b)
    schema_c = infer_schema(payload_c)

    left = merge(merge(schema_a, schema_b), schema_c)
    right = merge(schema_a, merge(schema_b, schema_c))

    assert left == right
