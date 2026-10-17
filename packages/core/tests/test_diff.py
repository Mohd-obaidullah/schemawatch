from __future__ import annotations

from schemawatch.diff import Change, diff
from schemawatch.infer import DYNAMIC_KEY_WILDCARD, SchemaNode, infer_schema, merge
from schemawatch.severity import (
    KIND_BECAME_NULLABLE,
    KIND_FIELD_ADDED,
    KIND_FIELD_MISSING,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)


def test_diff_identical_payloads() -> None:
    baseline = infer_schema({"id": 1, "name": "Payco"})
    observed = infer_schema({"id": 2, "name": "Payco"})
    changes = diff(baseline, observed)
    assert changes == []


def test_diff_type_changed_breaking() -> None:
    baseline = infer_schema({"user_id": 123})
    observed = infer_schema({"user_id": "usr_123"})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.path == "$.user_id"
    assert ch.field == "$.user_id"
    assert ch.kind == KIND_TYPE_CHANGED
    assert ch.severity == SEVERITY_BREAKING
    assert ch.was == "integer"
    assert ch.now == "string"


def test_diff_became_nullable_breaking() -> None:
    baseline = infer_schema({"status": "active"})
    observed = infer_schema({"status": None})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.path == "$.status"
    assert ch.kind == KIND_BECAME_NULLABLE
    assert ch.severity == SEVERITY_BREAKING


def test_diff_integer_compatible_with_number() -> None:
    # Baseline expected a number (float)
    baseline = infer_schema({"amount": 49.99})
    assert "number" in baseline.properties["amount"].types

    # Observed an integer (49) -> integer is compatible with number
    observed = infer_schema({"amount": 50})
    changes = diff(baseline, observed)
    assert changes == []


def test_diff_number_not_compatible_with_strict_integer() -> None:
    # Baseline only had integer
    baseline = infer_schema({"count": 5})
    # Observed a float -> type_changed
    observed = infer_schema({"count": 5.5})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    assert changes[0].kind == KIND_TYPE_CHANGED
    assert changes[0].severity == SEVERITY_BREAKING


def test_diff_required_field_missing_breaking() -> None:
    baseline = infer_schema({"user_id": 1, "amount": 100})
    # Amount missing
    observed = infer_schema({"user_id": 1})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.path == "$.amount"
    assert ch.kind == KIND_FIELD_MISSING
    assert ch.severity == SEVERITY_BREAKING
    assert ch.was == "present"
    assert ch.now == "missing"


def test_diff_optional_field_missing_info() -> None:
    # Build baseline where 'discount' is optional
    sample_1 = infer_schema({"user_id": 1, "discount": 10})
    sample_2 = infer_schema({"user_id": 2})
    baseline = merge(sample_1, sample_2)
    assert "discount" not in baseline.required
    assert "discount" in baseline.properties

    # Observed payload without 'discount'
    observed = infer_schema({"user_id": 3})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.path == "$.discount"
    assert ch.kind == KIND_FIELD_MISSING
    assert ch.severity == SEVERITY_INFO


def test_diff_field_added_info() -> None:
    baseline = infer_schema({"user_id": 1})
    observed = infer_schema({"user_id": 1, "meta": "extra"})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.path == "$.meta"
    assert ch.kind == KIND_FIELD_ADDED
    assert ch.severity == SEVERITY_INFO


def test_diff_does_not_descend_on_type_mismatch() -> None:
    # Baseline has a complex object
    baseline = infer_schema({"data": {"user": {"id": 1, "email": "a@b.com"}}})
    # Observed has a string at $.data
    observed = infer_schema({"data": "service unavailable"})
    changes = diff(baseline, observed)
    # Should only report type_changed for $.data, not child missing fields
    assert len(changes) == 1
    assert changes[0].path == "$.data"
    assert changes[0].kind == KIND_TYPE_CHANGED


def test_diff_array_items() -> None:
    baseline = infer_schema({"items": [{"id": 1, "price": 10.0}]})
    observed = infer_schema({"items": [{"id": "bad_id", "price": 10.0}]})
    changes = diff(baseline, observed)
    assert len(changes) == 1
    assert changes[0].path == "$.items[*].id"
    assert changes[0].kind == KIND_TYPE_CHANGED


def test_change_to_dict_and_message() -> None:
    ch = Change(
        path="$.user_id",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="integer",
        now="string",
        detail="type mismatch",
    )
    d = ch.to_dict()
    assert d["field"] == "$.user_id"
    assert d["kind"] == KIND_TYPE_CHANGED
    assert ch.message == "type mismatch"


def test_diff_object_transition_to_map() -> None:
    # Baseline was normal object
    baseline = infer_schema({"id": 1, "name": "foo"})
    # Observed became a map
    observed = SchemaNode(
        types={"object"},
        properties={DYNAMIC_KEY_WILDCARD: SchemaNode(types={"string"})},
    )

    changes = diff(baseline, observed)
    assert any(c.kind == "field_missing" and c.field == "$.id" for c in changes)
    assert any(c.kind == "field_added" and c.field == "$.*" for c in changes)


def test_drift_event_to_dict_and_highest_severity() -> None:
    from schemawatch.diff import DriftEvent

    ch_info = Change(path="$.a", kind=KIND_FIELD_ADDED, severity=SEVERITY_INFO)
    ch_warn = Change(path="$.b", kind="enum_changed", severity=SEVERITY_WARNING)
    ch_break = Change(path="$.c", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)

    # Info only
    event_info = DriftEvent(vendor="v", endpoint="/e", changes=(ch_info,))
    assert event_info.highest_severity == SEVERITY_INFO

    # Warning + Info -> highest is warning
    event_warn = DriftEvent(vendor="v", endpoint="/e", changes=(ch_info, ch_warn))
    assert isinstance(event_warn.changes, tuple)
    assert event_warn.highest_severity == SEVERITY_WARNING

    # Breaking + Warning + Info -> highest is breaking
    event_break = DriftEvent(
        vendor="payco",
        endpoint="/v1",
        changes=(ch_info, ch_warn, ch_break),
        detected_at=123456789.0,
    )
    assert event_break.highest_severity == SEVERITY_BREAKING

    d = event_break.to_dict()
    assert d["vendor"] == "payco"
    assert d["endpoint"] == "/v1"
    assert d["highest_severity"] == "breaking"
    assert d["detected_at"] == 123456789.0
    assert len(d["changes"]) == 3


def test_diff_object_with_literal_asterisk_key_does_not_drift_from_itself() -> None:
    payload = {"0": None, "*": False}
    schema = infer_schema(payload)
    changes = diff(schema, schema)
    assert changes == []
