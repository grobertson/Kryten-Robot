# Publishing Kryten-Robot to PyPI

This guide covers building and publishing kryten-robot to PyPI.

> **🤖 Automated Publishing Available!**
> 
> Kryten-Robot now supports automated PyPI publishing via GitHub Actions.
> Simply update the `VERSION` file and push to `main` - the rest happens automatically!
> 
> See [AUTOMATED_PUBLISHING.md](AUTOMATED_PUBLISHING.md) for details.

## Publishing Methods

### Method 1: Automated (Recommended)

1. Update version files:
   ```bash
   echo "0.5.2" > VERSION
   # Also update pyproject.toml line 3
   ```

2. Commit and push:
   ```bash
   git add VERSION pyproject.toml
   git commit -m "Bump version to 0.5.2"
   git push origin main
   ```

3. GitHub Actions will:
   - Create a GitHub Release automatically
   - Build and publish to PyPI
   - Takes ~2-3 minutes total

4. Verify at https://pypi.org/project/kryten-robot/

See [AUTOMATED_PUBLISHING.md](AUTOMATED_PUBLISHING.md) for troubleshooting.

### Method 2: Manual (Fallback)

Use this method if automation fails or for local testing.

## Prerequisites (Manual Publishing)

1. **Poetry** installed:
   ```bash
   pip install poetry
   ```

2. **PyPI Account**: Register at https://pypi.org/account/register/

3. **PyPI API Token**: 
   - Go to https://pypi.org/manage/account/token/
   - Create a new API token with "Upload packages" scope
   - Save the token securely

## Build Process (Manual)

### 1. Update Version

Edit `VERSION` file and `pyproject.toml`:
```bash
echo "0.5.1" > VERSION
# Also update version in pyproject.toml [tool.poetry] section
```

### 2. Clean Previous Builds

```bash
# PowerShell
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# Bash
rm -rf dist build *.egg-info
```

### 3. Build Package

```bash
uv build
```

This creates:
- `dist/kryten_robot-0.5.1-py3-none-any.whl` (wheel distribution)
- `dist/kryten-robot-0.5.1.tar.gz` (source distribution)

### 4. Verify Build

```bash
# Check package contents
tar -tzf dist/kryten-robot-0.5.1.tar.gz

# Test local installation
pip install dist/kryten_robot-0.5.1-py3-none-any.whl
```

## Publishing to PyPI

### Configure Poetry with PyPI Token

```bash
poetry config pypi-token.pypi YOUR-API-TOKEN-HERE
```

### Test Upload (PyPI Test Server)

First, test on TestPyPI:

```bash
# Configure TestPyPI repository
poetry config repositories.testpypi https://test.pypi.org/legacy/

# Get TestPyPI token from https://test.pypi.org/manage/account/token/
poetry config pypi-token.testpypi YOUR-TEST-TOKEN-HERE

# Upload to TestPyPI
uv publish -r testpypi

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ kryten-robot
```

### Production Upload

Once tested, upload to production PyPI:

```bash
uv publish
```

Or build and publish in one command:

```bash
uv publish --build
```

## Verify Publication

1. **Check PyPI Page**: https://pypi.org/project/kryten-robot/

2. **Install from PyPI**:
   ```bash
   pip install kryten-robot
   ```

3. **Verify version**:
   ```bash
   python -c "import kryten; print(kryten.__version__)"
   ```

4. **Test command**:
   ```bash
   kryten-robot --help
   ```

## Version Updates

For subsequent releases:

1. Update `VERSION` file
2. Update `CHANGELOG` in README.md
3. Commit changes:
   ```bash
   git add VERSION README.md pyproject.toml
   git commit -m "Release v0.5.1"
   git tag v0.5.1
   git push origin main --tags
   ```
4. Build and publish:
   ```bash
   uv publish --build
   ```

## Automation with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Poetry
        run: |
          pip install poetry
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
        run: uv publish
```

Store PyPI token in GitHub repository secrets as `PYPI_TOKEN`.

## Troubleshooting

### "File already exists" Error

PyPI doesn't allow re-uploading the same version. Increment version number:
```bash
echo "0.5.1" > VERSION
```

### Import Errors After Installation

Verify package structure:
```bash
uv build
tar -tzf dist/kryten-robot-0.5.0.tar.gz | grep __init__.py
```

Should show:
```
kryten-robot-0.5.0/kryten/__init__.py
```

### Missing Dependencies

Ensure all dependencies are in `pyproject.toml`:
```toml
[tool.poetry.dependencies]
python = "^3.11"
nats-py = ">=2.9.0"
python-socketio = {extras = ["asyncio-client"], version = ">=5.11.0"}
# ... etc
```

## Distribution Checklist

Before publishing:

- [ ] VERSION file updated
- [ ] README.md changelog updated
- [ ] All tests passing (`pytest`)
- [ ] Code formatted (`black kryten/`)
- [ ] Linting clean (`ruff check kryten/`)
- [ ] Type checking clean (`mypy kryten/`)
- [ ] Git committed and tagged
- [ ] Built successfully (`uv build`)
- [ ] Tested local install
- [ ] Tested on TestPyPI (optional but recommended)

## Manual Upload (Alternative)

If not using Poetry, use twine:

```bash
# Install twine
pip install twine

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

## Quick Reference

```bash
# Complete release workflow
echo "0.5.0" > VERSION
uv build
uv publish --dry-run  # Preview
uv publish            # Actual upload

# Upgrade kryten-robot everywhere
pip install --upgrade kryten-robot
```

## Support

For issues with packaging or publication:
- Check Poetry docs: https://python-poetry.org/docs/
- Check PyPI docs: https://packaging.python.org/
- Open issue: https://github.com/grobertson/kryten-robot/issues
