from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import schemawatch


def test_import_schemawatch_without_httpx_installed() -> None:
    """Proves 'import schemawatch' works without httpx installed in a subprocess."""
    core_path = Path(__file__).resolve().parent.parent

    # Run a fresh python process where httpx import is blocked via sys.modules['httpx'] = None
    code = (
        "import sys\n"
        "sys.modules['httpx'] = None\n"
        f"sys.path.insert(0, {str(core_path)!r})\n"
        "import schemawatch\n"
        "assert hasattr(schemawatch, 'Watchdog'), 'Watchdog should be present'\n"
        "assert hasattr(schemawatch, 'DriftEvent'), 'DriftEvent should be present'\n"
        "assert hasattr(schemawatch, 'Change'), 'Change should be present'\n"
        "assert hasattr(schemawatch, 'diff'), 'diff should be present'\n"
        "assert hasattr(schemawatch, 'infer_schema'), 'infer_schema should be present'\n"
        "assert hasattr(schemawatch, 'redact'), 'redact should be present'\n"
        "print('LAZY_IMPORT_SUCCESS')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Subprocess failed with stderr:\n{result.stderr}"
    assert "LAZY_IMPORT_SUCCESS" in result.stdout


def test_schemawatch_lazy_exports_and_dir() -> None:
    """Verify lazy __getattr__ exports and __dir__."""
    assert schemawatch.SlackAlert is not None
    assert schemawatch.create_httpx_hook is not None
    assert "SlackAlert" in dir(schemawatch)
    assert "create_httpx_hook" in dir(schemawatch)

    with pytest.raises(AttributeError):
        _ = schemawatch.non_existent_attribute
