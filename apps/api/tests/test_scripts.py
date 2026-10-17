from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from schemawatch_api.database import create_db_engine, create_session_factory, init_db
from schemawatch_api.models import Baseline, DriftEventModel, Endpoint
from scripts.export_openapi import export_openapi
from scripts.seed_demo import seed_demo_data
from sqlalchemy import select


def test_export_openapi_generates_valid_schema(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    result_path = export_openapi(target)

    assert result_path == target
    assert target.exists()

    with open(target, encoding="utf-8") as f:
        spec = json.load(f)

    assert "openapi" in spec
    assert "paths" in spec
    assert "/api/endpoints" in spec["paths"]
    assert "/api/events" in spec["paths"]
    assert "/healthz" in spec["paths"]
    assert spec["info"]["title"] == "schemawatch API"


def test_export_openapi_cli_runs_successfully(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "export_openapi.py"

    # Run as a subprocess
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "OpenAPI spec successfully exported" in proc.stdout


def test_seed_demo_data_creates_expected_entities(tmp_path: Path) -> None:
    db_file = tmp_path / "test_seed.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_db_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = seed_demo_data(session, learn_samples=5)
        assert result["endpoints"] == 4
        assert result["events"] == 4

        # Check endpoints
        endpoints = session.scalars(select(Endpoint)).all()
        assert len(endpoints) == 4
        vendors = {ep.vendor for ep in endpoints}
        assert vendors == {"stripe", "twilio", "sendgrid", "github"}

        # Check baselines
        baselines = session.scalars(select(Baseline)).all()
        assert len(baselines) == 4

        # Check events
        events = session.scalars(select(DriftEventModel)).all()
        assert len(events) == 4

        breaking_unack = [e for e in events if e.severity == "breaking" and not e.acknowledged]
        warning_unack = [e for e in events if e.severity == "warning" and not e.acknowledged]
        info_unack = [e for e in events if e.severity == "info" and not e.acknowledged]
        ack_events = [e for e in events if e.acknowledged]

        assert len(breaking_unack) == 1
        assert breaking_unack[0].vendor == "stripe"
        assert breaking_unack[0].kind == "type_changed"

        assert len(warning_unack) == 1
        assert warning_unack[0].vendor == "twilio"
        assert warning_unack[0].kind == "enum_changed"

        assert len(info_unack) == 1
        assert info_unack[0].vendor == "sendgrid"
        assert info_unack[0].kind == "field_added"

        assert len(ack_events) == 1
        assert ack_events[0].vendor == "github"
        assert ack_events[0].kind == "became_nullable"
        assert ack_events[0].acknowledged is True


def test_seed_demo_cli_skips_if_already_seeded(tmp_path: Path) -> None:
    db_file = tmp_path / "cli_seed.db"
    db_url = f"sqlite:///{db_file}"
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "seed_demo.py"

    env = dict(os.environ)
    env["SCHEMAWATCH_DATABASE_URL"] = db_url
    env["SCHEMAWATCH_DEV_MODE"] = "true"

    # First run seeds
    proc1 = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc1.returncode == 0
    assert "Successfully seeded 4 endpoints and 4 events" in proc1.stdout

    # Second run skips
    proc2 = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc2.returncode == 0
    assert "Database already contains data, skipping seed" in proc2.stdout
