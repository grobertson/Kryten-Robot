# PyPI Publishing Checklist

Use this checklist before publishing a new version to PyPI.

> **🤖 Automated Publishing**
> 
> Kryten-Robot supports automated publishing! After completing the pre-release checklist,
> simply push to main and GitHub Actions will handle the rest.
> 
> See [AUTOMATED_PUBLISHING.md](AUTOMATED_PUBLISHING.md) for details.

## Publishing Options

### Option A: Automated (Recommended)

1. Complete pre-release checklist below
2. Push to main branch
3. GitHub Actions automatically:
   - Creates GitHub Release
   - Builds package
   - Publishes to PyPI
4. Verify publication

### Option B: Manual

Use this checklist for manual publishing or troubleshooting.

## Pre-Release Checklist

### 1. Version Update
- [ ] Update `VERSION` file with new version number
- [ ] Update `version` in `pyproject.toml` (line 3)
- [ ] Update version in `install.sh` header comment (line 2)
- [ ] Update version in `publish.ps1` header comment (line 2)
- [ ] Update version in `publish.sh` header comment (line 2)

### 2. Documentation
- [ ] Update `RELEASE_NOTES.md` with changes
- [ ] Update `README.md` if needed
- [ ] Update `CHANGELOG.md` if it exists
- [ ] Review all documentation for accuracy

### 3. Code Quality
- [ ] Run tests: `pytest`
- [ ] Check for type errors: `mypy kryten/`
- [ ] Format code: `black kryten/`
- [ ] Lint code: `ruff kryten/`
- [ ] Fix any startup banner issues

### 4. Configuration
- [ ] Remove any `config.json` from `kryten/` directory
- [ ] Verify `.gitignore` excludes config files
- [ ] Verify `pyproject.toml` excludes config files
- [ ] Ensure `config.example.json` is up to date

### 5. Git
- [ ] Commit all changes
- [ ] Tag release: `git tag v0.5.1`
- [ ] Push commits: `git push`
- [ ] Push tags: `git push --tags`

## Build and Test

### 1. Clean Build
```powershell
# PowerShell
.\publish.ps1 -Clean -Build

# Or manually
Remove-Item -Recurse -Force dist, build, *.egg-info
poetry build
```

```bash
# Bash
./publish.sh --clean --build

# Or manually
rm -rf dist build *.egg-info
poetry build
```

### 2. Verify Package Contents
```bash
# Check tarball contents
tar -tzf dist/kryten_robot-X.Y.Z.tar.gz

# Verify exclusions
tar -tzf dist/kryten_robot-X.Y.Z.tar.gz | grep -E "config\.json|logs/"
# Should return nothing

# Verify inclusions
tar -tzf dist/kryten_robot-X.Y.Z.tar.gz | grep -E "(install\.sh|systemd/|INSTALL\.md)"
# Should show files
```

### 3. Test Local Installation
```bash
# Create test environment
python -m venv test-env
source test-env/bin/activate  # Linux/Mac
# or
test-env\Scripts\activate     # Windows

# Install from wheel
pip install dist/kryten_robot-X.Y.Z-py3-none-any.whl

# Verify installation
kryten-robot --help
python -m kryten --help

# Test run (requires config and NATS)
kryten-robot config.json

# Cleanup
deactivate
rm -rf test-env
```

## Publish to TestPyPI (Optional but Recommended)

### 1. Configure TestPyPI
```bash
# First time only
poetry config pypi-token.testpypi YOUR-TEST-TOKEN
```

### 2. Upload to TestPyPI
```powershell
# PowerShell
.\publish.ps1 -TestPyPI

# Or manually
poetry publish -r testpypi
```

```bash
# Bash
./publish.sh --testpypi

# Or manually
poetry publish -r testpypi
```

### 3. Test Installation from TestPyPI
```bash
pip install --index-url https://test.pypi.org/simple/ kryten-robot
```

### 4. Verify
- [ ] Check TestPyPI page: https://test.pypi.org/project/kryten-robot/
- [ ] Test installation works
- [ ] Test running the package

## Publish to Production PyPI

### 1. Configure PyPI
```bash
# First time only
poetry config pypi-token.pypi YOUR-PRODUCTION-TOKEN
```

### 2. Final Verification
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Git commits pushed and tagged
- [ ] TestPyPI installation verified (if tested)

### 3. Publish
```powershell
# PowerShell
.\publish.ps1 -Publish

# Or manually
poetry publish
```

```bash
# Bash
./publish.sh --publish

# Or manually
poetry publish
```

### 4. Verify Production Release
- [ ] Check PyPI page: https://pypi.org/project/kryten-robot/
- [ ] Test installation: `pip install kryten-robot`
- [ ] Test upgrade: `pip install --upgrade kryten-robot`
- [ ] Verify version: `kryten-robot --version` or `python -m kryten --version`

## Post-Release

### 1. GitHub Release
- [ ] Create GitHub release at: https://github.com/grobertson/kryten-robot/releases/new
- [ ] Use tag created earlier (e.g., v0.5.1)
- [ ] Copy release notes from `RELEASE_NOTES.md`
- [ ] Attach built artifacts (optional)

### 2. Announcements
- [ ] Update project README if needed
- [ ] Notify users of new version
- [ ] Update any deployment documentation

### 3. Verify Deployments
- [ ] Test systemd installation on clean Linux system
- [ ] Test pip upgrade on existing installations
- [ ] Verify health endpoints work
- [ ] Check logs for issues

## Troubleshooting

### Poetry Can't Find Python
```bash
# Use system Python directly
python -m poetry build
```

### Wrong Virtual Environment Detected
```bash
# Deactivate current venv
deactivate

# Use system Python
python -m poetry build
```

### Config Files in Package
```bash
# Remove from kryten/ directory
rm kryten/config.json kryten/config-*.json

# Verify exclusion in pyproject.toml
# Look for: exclude = ["config.json", "config-*.json", ...]

# Rebuild
poetry build
```

### Upload Failed - Version Already Exists
- Cannot re-upload same version to PyPI
- Must increment version number
- Delete dist/ and rebuild with new version

### Authentication Failed
```bash
# Verify token is set
poetry config pypi-token.pypi --show

# Set/update token
poetry config pypi-token.pypi YOUR-TOKEN
```

## Quick Reference

### Version Locations
- `VERSION` - Main version file
- `pyproject.toml` - line 3
- `install.sh` - line 2
- `publish.ps1` - line 2
- `publish.sh` - line 2

### Key Commands
```bash
# Clean
rm -rf dist build *.egg-info

# Build
poetry build

# Test publish
poetry publish -r testpypi

# Production publish
poetry publish

# View package contents
tar -tzf dist/kryten_robot-X.Y.Z.tar.gz
```

### Important Files
- `pyproject.toml` - Package configuration
- `MANIFEST.in` - Additional files to include (legacy, Poetry uses pyproject.toml)
- `.gitignore` - Files to exclude from git
- `README.md` - Main documentation (shown on PyPI)
- `LICENSE` - License file (shown on PyPI)
