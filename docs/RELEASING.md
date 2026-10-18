# Releasing SchemaWatch to PyPI

This guide documents the step-by-step process for publishing `schemawatch-core` and `schemawatch-api` to PyPI using PyPI Trusted Publishing (OIDC). No long-lived API tokens or passwords are stored in the GitHub repository.

---

## 1. Initial One-Time Setup: PyPI Trusted Publishing (OIDC)

PyPI supports OpenID Connect (OIDC) to exchange short-lived tokens directly with GitHub Actions.

### A. Configure TestPyPI (for dry-run verification)
1. Log into [test.pypi.org](https://test.pypi.org/).
2. Navigate to **Account settings** > **Publishing**.
3. Under **Add a publisher**, choose **GitHub**.
4. Configure publisher for **`schemawatch-core`**:
   - **PyPI Project Name**: `schemawatch-core`
   - **Owner**: `Mohd-obaidullah`
   - **Repository name**: `schemawatch`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `testpypi`
5. Repeat for **`schemawatch-api`**:
   - **PyPI Project Name**: `schemawatch-api`
   - Same owner, repo, workflow name (`publish.yml`), and environment (`testpypi`).

### B. Configure Production PyPI
1. Log into [pypi.org](https://pypi.org/).
2. Navigate to **Account settings** > **Publishing**.
3. Under **Add a publisher**, choose **GitHub**.
4. Configure publisher for **`schemawatch-core`**:
   - **PyPI Project Name**: `schemawatch-core`
   - **Owner**: `Mohd-obaidullah`
   - **Repository name**: `schemawatch`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
5. Repeat for **`schemawatch-api`**:
   - **PyPI Project Name**: `schemawatch-api`
   - Same owner, repo, workflow name (`publish.yml`), and environment (`pypi`).

---

## 2. GitHub Environments Setup

1. In your GitHub repository (`Mohd-obaidullah/schemawatch`), go to **Settings** > **Environments**.
2. Click **New environment** and create:
   - Name: `testpypi`
   - (Optional) Configure environment protection rules if desired.
3. Click **New environment** and create:
   - Name: `pypi`
   - (Optional) Add required reviewers for production release protection.

---

## 3. Pre-Release Verification Checklist

Before creating a release, run the local verification gate:

```bash
# 1. Clean hypothesis cache
rm -rf .hypothesis

# 2. Run full test suite with coverage gate (>= 90%)
uv run pytest --cov

# 3. Code formatting and linting
uv run ruff format --check .
uv run ruff check .

# 4. Strict typecheck on packages/core
uv run mypy packages/core

# 5. Frontend lint, typecheck, test, and build
(cd apps/web && npm run lint && npm run typecheck && npm run test && npm run build)

# 6. Verify demo script
uv run python examples/demo.py

# 7. Build wheel & sdist archives
uv build --package schemawatch-core
uv build --package schemawatch-api

# 8. Check distributions with twine
uvx twine check dist/*
```

Verify that version numbers in `packages/core/pyproject.toml`, `apps/api/pyproject.toml`, and `CHANGELOG.md` are aligned (e.g. `0.1.0`).

---

## 4. Triggering the Release

1. Commit and push all changes to the `main` branch.
2. Go to **GitHub** > **Releases** > **Draft a new release**.
3. Fill in:
   - **Tag**: `v0.1.0` (select `Create new tag: v0.1.0 on publish`)
   - **Target**: `main`
   - **Title**: `v0.1.0 - SchemaWatch 0.1.0 Release`
   - **Description**: Copy the section from `CHANGELOG.md`.
4. Click **Publish release**.

---

## 5. Automated Publication Flow

Once published, GitHub Actions triggers `.github/workflows/publish.yml`:
1. **`build`**: Checks out repository, installs `uv`, builds both `schemawatch-core` and `schemawatch-api` wheels and source distributions, and validates them with `twine check`.
2. **`test-publish`**: Publishes to TestPyPI via OIDC token exchange (`pypa/gh-action-pypi-publish`).
3. **`pypi-publish`**: Publishes both packages to production PyPI via OIDC token exchange.

---

## 6. Verification After Release

Verify the release in a clean environment:

```bash
# In a new virtual environment
pip install schemawatch-core
pip install "schemawatch-core[httpx]"
pip install schemawatch-api

python -c "import schemawatch; import schemawatch_api; print('SchemaWatch successfully installed!')"
```
