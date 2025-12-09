# Automated PyPI Publishing

Kryten-Robot uses GitHub Actions to automatically publish to PyPI when a new release is created.

## How It Works

The automation follows this workflow:

```
VERSION file update → Push to main → GitHub Release → PyPI Publish
```

### Step 1: Version Update Triggers Release

When you push a commit that changes the `VERSION` file to the `main` branch:

1. GitHub Actions workflow `.github/workflows/release.yml` is triggered
2. The workflow reads the new version from `VERSION` file
3. Creates a git tag (e.g., `v0.5.1`)
4. Generates changelog from recent commits
5. Creates a GitHub Release

### Step 2: Release Triggers PyPI Publish

When a GitHub Release is published:

1. GitHub Actions workflow `.github/workflows/publish-pypi.yml` is triggered
2. The workflow uses Poetry to build the package
3. Publishes to PyPI using trusted publishing (no token needed)
4. Package becomes available at https://pypi.org/project/kryten-robot/

## Trusted Publishing (No Tokens Required)

Kryten-Robot uses PyPI's [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) which eliminates the need to manage API tokens. This is more secure and easier to maintain.

### Initial Setup (One Time)

The repository maintainer needs to configure trusted publishing on PyPI:

1. Go to https://pypi.org/manage/project/kryten-robot/settings/publishing/
2. Add a new trusted publisher:
   - **PyPI Project Name**: `kryten-robot`
   - **Owner**: `grobertson` (or your GitHub username)
   - **Repository name**: `kryten-robot`
   - **Workflow name**: `publish-pypi.yml`
   - **Environment name**: `pypi`

That's it! No API tokens to create, rotate, or manage.

## Publishing a New Version

### Automated Method (Recommended)

1. **Update version files:**
   ```bash
   echo "0.5.2" > VERSION
   # Also update pyproject.toml line 3
   ```

2. **Commit and push to main:**
   ```bash
   git add VERSION pyproject.toml
   git commit -m "Bump version to 0.5.2"
   git push origin main
   ```

3. **Wait for automation:**
   - Release workflow creates GitHub Release (~30 seconds)
   - PyPI workflow publishes package (~1-2 minutes)
   - Check https://pypi.org/project/kryten-robot/ for new version

### Manual Method (Fallback)

If you need to publish manually or test locally:

```bash
# Using the publish script
./publish.ps1 -Clean -Build -Publish

# Or using Poetry directly
poetry config pypi-token.pypi YOUR-TOKEN
poetry build
poetry publish
```

## Monitoring the Workflow

### View Workflow Runs

Go to: https://github.com/grobertson/kryten-robot/actions

You'll see two workflows:
- **Release Automation** - Creates GitHub releases
- **Publish Python Package to PyPI** - Publishes to PyPI

### Check Logs

Click on any workflow run to see detailed logs:
- Build step shows package creation
- Publish step confirms upload to PyPI
- Any errors will appear in the logs

### Verify Publication

After the workflow completes:

1. **Check PyPI page:**
   https://pypi.org/project/kryten-robot/

2. **Test installation:**
   ```bash
   pip install --upgrade kryten-robot
   python -c "import kryten; print(kryten.__version__)"
   ```

## Workflow Files

### `.github/workflows/release.yml`

Creates GitHub releases when VERSION file changes on main branch.

**Triggers:**
- Push to main branch with VERSION file changes
- Manual workflow dispatch

**Actions:**
- Reads VERSION file
- Creates git tag
- Generates changelog
- Creates GitHub Release

### `.github/workflows/publish-pypi.yml`

Publishes to PyPI when a GitHub release is published.

**Triggers:**
- GitHub Release published

**Actions:**
- Installs Poetry
- Builds package with Poetry
- Uploads to PyPI using trusted publishing

## Troubleshooting

### Release Not Created

**Problem:** Pushed VERSION change but no release was created.

**Solutions:**
1. Check workflow run at https://github.com/grobertson/kryten-robot/actions
2. Ensure VERSION file is in root directory
3. Verify you pushed to `main` branch
4. Check that tag doesn't already exist: `git tag -l`

### PyPI Publish Failed

**Problem:** Release created but package not on PyPI.

**Solutions:**
1. Check publish workflow logs for errors
2. Verify trusted publishing is configured on PyPI
3. Ensure environment name is `pypi` in workflow
4. Check PyPI project settings

### Version Already Exists

**Problem:** PyPI rejects upload because version exists.

**Solution:**
- Cannot re-upload same version to PyPI
- Increment version number and push again
- PyPI versions are immutable by design

### Authentication Failed

**Problem:** "Trusted publishing exchange failure"

**Solutions:**
1. Verify trusted publisher is configured on PyPI
2. Check repository owner and name match exactly
3. Ensure workflow name is `publish-pypi.yml`
4. Verify environment name is `pypi`

## Security Considerations

### Why Trusted Publishing is Better

Traditional approach (API tokens):
- ❌ Tokens can be leaked in logs
- ❌ Need to rotate regularly
- ❌ Stored in GitHub secrets
- ❌ Can be misused if compromised

Trusted publishing:
- ✅ No tokens to manage
- ✅ GitHub verifies workflow identity
- ✅ Limited to specific workflow
- ✅ Automatic rotation by GitHub
- ✅ More secure by design

### Environment Protection

The `pypi` environment can be protected with:
- Required reviewers before deployment
- Wait timer before deployment
- Deployment branches restriction

To configure: https://github.com/grobertson/kryten-robot/settings/environments

## Best Practices

### Before Publishing

1. **Test locally first:**
   ```bash
   poetry build
   pip install dist/kryten_robot-*.whl
   # Test the package
   ```

2. **Update all version references:**
   - `VERSION` file
   - `pyproject.toml` (line 3)
   - `install.sh` (header comment)
   - `publish.ps1` (header comment)
   - `publish.sh` (header comment)

3. **Update documentation:**
   - `RELEASE_NOTES.md`
   - `CHANGELOG.md` (if exists)

4. **Commit with clear message:**
   ```bash
   git commit -m "Release v0.5.2: Added new features"
   ```

### After Publishing

1. **Verify on PyPI:**
   - Check package page
   - Verify version number
   - Test pip install

2. **Test installation:**
   ```bash
   # In a clean environment
   python -m venv test-env
   source test-env/bin/activate
   pip install kryten-robot
   kryten-robot --version
   ```

3. **Announce release:**
   - Update project README
   - Notify users
   - Post in relevant channels

## Disabling Automation

If you need to disable automatic publishing:

### Disable Release Creation

Edit `.github/workflows/release.yml`:
```yaml
on:
  # push:  # Comment out the push trigger
  #   branches:
  #     - main
  #   paths:
  #     - 'VERSION'
  workflow_dispatch:  # Keep manual trigger
```

### Disable PyPI Publishing

Edit `.github/workflows/publish-pypi.yml`:
```yaml
on:
  # release:  # Comment out the release trigger
  #   types: [published]
  workflow_dispatch:  # Add manual trigger
```

Or simply delete/rename the workflow file.

## Manual Publishing

If automation fails or you need manual control:

```bash
# 1. Configure token (first time)
poetry config pypi-token.pypi YOUR-TOKEN

# 2. Clean and build
rm -rf dist build *.egg-info
poetry build

# 3. Publish
poetry publish
```

Or use the helper scripts:
```bash
./publish.sh --clean --build --publish
```

## References

- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions - Publishing Python Packages](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python#publishing-to-package-registries)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [PyPI Kryten-Robot Page](https://pypi.org/project/kryten-robot/)
