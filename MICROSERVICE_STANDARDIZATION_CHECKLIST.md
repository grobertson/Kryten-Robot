# Microservice Standardization Checklist

Copy this checklist for each `kryten-*` microservice migration.

## Target Service: ____________________

### 1. Preparation & Cleanup
- [ ] **Remove Poetry**: Delete `poetry.lock`.
- [ ] **Remove Version File**: Delete `VERSION` file if it exists.
- [ ] **Clean Config**: Remove `[tool.poetry]` sections from `pyproject.toml`.
- [ ] **Clean Build Artifacts**: Remove `dist/`, `build/`, `*.egg-info`.

### 2. UV Migration
- [ ] **Install UV**: Ensure `uv` is installed locally.
- [ ] **Initialize/Update `pyproject.toml`**:
  - [ ] Set `build-system` to `hatchling`.
  - [ ] Define `[project]` table (name, version, description, authors, etc.).
  - [ ] Define `dependencies` list.
  - [ ] Define `[project.scripts]` (if applicable).
- [ ] **Generate Lockfile**: Run `uv lock` (creates `uv.lock`).
- [ ] **Sync Environment**: Run `uv sync`.

### 3. Single Source of Truth (SSOT)
- [ ] **Verify Version**: Ensure `version = "X.Y.Z"` is present in `[project]` table of `pyproject.toml`.
- [ ] **Update Code**: Ensure `__init__.py` or `__main__.py` uses `importlib.metadata` to get version (or minimal hardcoding if strictly necessary, but prefer SSOT).

### 4. CI/CD Workflows (GitHub Actions)
- [ ] **Create/Update `.github/workflows/release.yml`**:
  - [ ] Trigger on `push` to `main` when `pyproject.toml` changes.
  - [ ] Use `uv` for installation (`astral-sh/setup-uv`).
  - [ ] Build using `uv build`.
  - [ ] Publish/Release steps.
- [ ] **Create/Update `.github/workflows/ci.yml`**:
  - [ ] Trigger on PRs and pushes.
  - [ ] Use `uv` to run tests/linting.

### 5. Local Scripts
- [ ] **Add `publish.sh`**: Standardized Bash script using `uv`.
- [ ] **Add `publish.ps1`**: Standardized PowerShell script using `uv`.
- [ ] **Make Executable**: `chmod +x publish.sh` (if on Linux/Mac).

### 6. Verification
- [ ] **Local Build**: Run `uv build` -> Success?
- [ ] **Local Tests**: Run `uv run pytest` -> Success?
- [ ] **Linting**: Run `uv run ruff check .` and `uv run black --check .` -> Success?
- [ ] **Dry Run Publish**: Run `./publish.ps1` (or `.sh`) with build flags.

### 7. Finalize
- [ ] **Commit Changes**: `git add . && git commit -m "chore: migrate to uv and standardize CI/CD"`
- [ ] **Push**: `git push origin main`
