# CI/Publish Standardization Checklist

This checklist guides the standardization of CI/CD workflows and publishing scripts across the `kryten-*` ecosystem (e.g., `kryten-robot`, `kryten-userstats`, `kryten-shell`, etc.).

## Goals
1.  **Single Source of Truth (SSOT)**: Version number is defined *only* in `pyproject.toml`. No `VERSION` files.
2.  **Standardized CI**: GitHub Actions for linting (Ruff), formatting (Black), type checking (MyPy), and testing (Pytest).
3.  **Standardized Release**: GitHub Actions to create releases/tags automatically when `pyproject.toml` version changes.
4.  **Standardized Local Publish**: `publish.sh` (Bash) and `publish.ps1` (PowerShell) scripts for local building and publishing.

## Checklist per Microservice

### 1. Preparation
- [ ] **Access**: Ensure you have write access to the repository/directory.
- [ ] **Cleanup**: Remove `VERSION` file if it exists.
- [ ] **SSOT**: Verify `pyproject.toml` contains the correct `version = "X.Y.Z"`.
- [ ] **Manifest**: Update `MANIFEST.in` to remove `include VERSION` (if present).

### 2. Workflow Configuration (`.github/workflows/`)
- [ ] **Create `release.yml`**:
    - [ ] Trigger on `push` to `main` when `pyproject.toml` changes.
    - [ ] Extract version from `pyproject.toml`.
    - [ ] Check if tag exists.
    - [ ] Create Git tag and GitHub Release if tag is new.
- [ ] **Create `ci.yml`**:
    - [ ] Run on `push` and `pull_request`.
    - [ ] Install dependencies (uv/poetry).
    - [ ] Run `ruff check`, `black --check`, `mypy`, `pytest`.

### 3. Local Scripts
- [ ] **Create/Update `publish.sh`**:
    - [ ] Check `pyproject.toml` for version.
    - [ ] Support `--clean`, `--build`, `--testpypi`, `--publish` flags.
    - [ ] Use appropriate build tool (`uv` or `poetry`).
- [ ] **Create/Update `publish.ps1`**:
    - [ ] PowerShell equivalent of `publish.sh`.
    - [ ] Support same flags and logic.

### 4. Verification
- [ ] **Linting**: Run `ruff check .` and fix errors.
- [ ] **Formatting**: Run `black .` to ensure compliance.
- [ ] **Type Checking**: Run `mypy .` (fix critical errors, `ignore_missing_imports` if needed).
- [ ] **Tests**: Run `pytest` to ensure no regression.
- [ ] **Dry Run**: Run `./publish.sh --build` (or `.\publish.ps1 -Build`) to verify build process.

## Standardization Status

| Service | Status | Notes |
| :--- | :--- | :--- |
| `kryten-robot` | ✅ Complete | Reference implementation. Uses Poetry. |
| `kryten-userstats` | ✅ Complete | Standardized to UV. Verified tests. |
| `kryten-shell` | ⏳ Pending | |
| `kryten-llm` | ✅ Complete | Standardized to UV. Verified tests. |
| `kryten-cli` | ⏳ Pending | |
| `kryten-moderator` | ✅ Complete | Standardized to UV. Verified tests. |
| `kryten-playlist` | ✅ Complete | Standardized to UV. Verified tests. |
