from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from schemawatch_api.__main__ import main


def test_cli_refused_no_token() -> None:
    """Starting python -m schemawatch_api without token fails fast with exit 1 and no traceback."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SCHEMAWATCH_")}
    env["SCHEMAWATCH_DEV_MODE"] = "false"
    env["SCHEMAWATCH_API_TOKEN"] = ""

    result = subprocess.run(
        [sys.executable, "-m", "schemawatch_api"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "ERROR: SCHEMAWATCH_API_TOKEN is required" in result.stderr
    assert "placeholder 'your-random-secure-token-here'" in result.stderr
    assert 'python -c "import secrets; print(secrets.token_urlsafe(32))"' in result.stderr
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


def test_cli_refused_empty_token() -> None:
    """Starting python -m schemawatch_api with empty token exits with code 1 and no traceback."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SCHEMAWATCH_")}
    env["SCHEMAWATCH_DEV_MODE"] = "false"
    env["SCHEMAWATCH_API_TOKEN"] = "   "

    result = subprocess.run(
        [sys.executable, "-m", "schemawatch_api"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "ERROR: SCHEMAWATCH_API_TOKEN is required" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_refused_placeholder_token() -> None:
    """Starting python -m schemawatch_api with placeholder token exits with 1 and no traceback."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SCHEMAWATCH_")}
    env["SCHEMAWATCH_DEV_MODE"] = "false"
    env["SCHEMAWATCH_API_TOKEN"] = "your-random-secure-token-here"

    result = subprocess.run(
        [sys.executable, "-m", "schemawatch_api"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "placeholder 'your-random-secure-token-here'" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_valid_token_startup() -> None:
    """Starting with a valid token proceeds to uvicorn.run."""
    with (
        patch.dict(
            os.environ,
            {
                "SCHEMAWATCH_API_TOKEN": "valid-secret-token-32-characters-abc",
                "SCHEMAWATCH_DEV_MODE": "false",
            },
        ),
        patch("sys.argv", ["schemawatch_api", "--host", "127.0.0.1", "--port", "8000"]),
        patch("uvicorn.run") as mock_uvicorn,
    ):
        main()
        mock_uvicorn.assert_called_once_with(
            "schemawatch_api.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=8000,
            reload=False,
        )


def test_cli_dev_mode_startup() -> None:
    """Starting with DEV_MODE=true bypasses token requirement."""
    with (
        patch.dict(
            os.environ,
            {"SCHEMAWATCH_DEV_MODE": "true", "SCHEMAWATCH_API_TOKEN": ""},
        ),
        patch("sys.argv", ["schemawatch_api", "--dev"]),
        patch("uvicorn.run") as mock_uvicorn,
    ):
        main()
        mock_uvicorn.assert_called_once_with(
            "schemawatch_api.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=8000,
            reload=True,
        )


def test_docker_entrypoint_exits_nonzero_when_token_missing() -> None:
    """The entrypoint script must exit non-zero with the clear message when the token is missing."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    entrypoint_path = repo_root / "scripts" / "docker-entrypoint.sh"

    sh_path = shutil.which("sh")
    if sh_path:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "SCHEMAWATCH_DEV_MODE": "false",
            "SCHEMAWATCH_API_TOKEN": "",
        }
        res = subprocess.run(
            [sh_path, str(entrypoint_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 1
        assert "ERROR: SCHEMAWATCH_API_TOKEN is not set" in res.stderr
        assert 'python -c "import secrets; print(secrets.token_urlsafe(32))"' in res.stderr
        return

    docker_path = shutil.which("docker")
    if docker_path:
        res = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "SCHEMAWATCH_DEV_MODE=false",
                "-e",
                "SCHEMAWATCH_API_TOKEN=",
                "api-schemawatch",
            ],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 1
        assert "ERROR: SCHEMAWATCH_API_TOKEN is not set" in res.stderr
        assert 'python -c "import secrets; print(secrets.token_urlsafe(32))"' in res.stderr
        return

    pytest.skip("Neither sh nor docker is available in this test environment")
