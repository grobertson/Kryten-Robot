# Kryten Ecosystem CI/CD Standardization Strategy

## 1. Goal
Standardize the build, release, and dependency management process across all `kryten-*` microservices to ensure consistency, reliability, and ease of maintenance.

## 2. Core Tooling
- **Dependency Management**: [uv](https://github.com/astral-sh/uv) (replaces Poetry).
- **Build Backend**: `hatchling` (standard PEP 621 compliant backend, managed via `uv`).
- **Linting/Formatting**: `ruff` (linting/imports), `black` (formatting), `mypy` (static type checking).
- **CI/CD**: GitHub Actions.
- **Versioning**: Semantic Versioning (SemVer) with `pyproject.toml` as the **Single Source of Truth (SSOT)**.

## 3. Standardization Requirements

### A. Repository Structure
- Remove `VERSION` file (if exists).
- Remove `poetry.lock` and `pyproject.toml` Poetry sections.
- Ensure `pyproject.toml` follows PEP 621 standards.
- Add `uv.lock` (managed by `uv`).

### B. Versioning (SSOT)
- The `version` field in `[project]` table of `pyproject.toml` is the authoritative source.
- No other files should hardcode the version (imports should use `importlib.metadata`).

### C. Build & Release Workflow
1. **Trigger**: Pushing a commit to `main` that changes the `version` in `pyproject.toml`.
2. **CI Process**:
   - Install dependencies with `uv sync`.
   - Run tests (`pytest`).
   - Run linters (`ruff`, `black`, `mypy`).
3. **Release Process** (GitHub Actions):
   - Read version from `pyproject.toml`.
   - Create Git tag (e.g., `v1.2.3`).
   - Create GitHub Release with auto-generated changelog.
   - (Optional) Publish to PyPI.

### D. Local Scripts
- `publish.sh` (Bash) and `publish.ps1` (PowerShell) for local building/publishing.
- Must use `uv build` and `uv publish`.

## 4. Migration Steps (per microservice)
1. **Initialize UV**: `uv init` (or convert existing `pyproject.toml`).
2. **Migrate Dependencies**: Move dependencies from Poetry/Pip format to standard `project.dependencies`.
3. **Clean Up**: Remove Poetry files, old build artifacts, and unused config.
4. **Update CI**: Replace GitHub Actions workflows with the standardized template.
5. **Add Scripts**: Add standardized `publish.sh` and `publish.ps1`.
6. **Verify**: Run full CI suite locally and verify `uv build`.
