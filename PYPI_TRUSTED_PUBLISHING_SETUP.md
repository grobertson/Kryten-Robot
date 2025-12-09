# PyPI Trusted Publishing Setup

This guide explains how to set up PyPI Trusted Publishing for Kryten-Robot. This only needs to be done once by the repository maintainer.

## What is Trusted Publishing?

Trusted Publishing is a secure way to publish packages to PyPI without using API tokens. Instead of managing tokens, PyPI trusts GitHub Actions workflows to publish packages directly.

**Benefits:**
- ✅ No API tokens to manage or rotate
- ✅ More secure than tokens
- ✅ Automatic verification by GitHub
- ✅ Limited to specific workflows
- ✅ Cannot be leaked or misused

## Prerequisites

- PyPI account with owner/maintainer access to `kryten-robot` project
- GitHub repository with `publish-pypi.yml` workflow

## Setup Steps

### 1. Log in to PyPI

Go to https://pypi.org/ and log in with your account.

### 2. Navigate to Project Settings

Go to: https://pypi.org/manage/project/kryten-robot/settings/publishing/

Or:
1. Go to https://pypi.org/project/kryten-robot/
2. Click "Manage project"
3. Click "Publishing" in the left sidebar

### 3. Add Trusted Publisher

Scroll to the "Trusted publishers" section and click "Add a new publisher".

Fill in the form:

| Field | Value |
|-------|-------|
| **PyPI Project Name** | `kryten-robot` |
| **Owner** | `grobertson` |
| **Repository name** | `kryten-robot` |
| **Workflow name** | `publish-pypi.yml` |
| **Environment name** | `pypi` |

Click "Add".

### 4. Verify Configuration

You should see the trusted publisher listed:

```
GitHub Actions workflow publish-pypi.yml in grobertson/kryten-robot targeting the pypi environment
```

## Testing the Setup

### Test Locally First

Before triggering the automation, verify the package builds correctly:

```bash
cd kryten-robot
poetry build
ls -lh dist/
```

You should see:
- `kryten_robot-X.Y.Z-py3-none-any.whl`
- `kryten_robot-X.Y.Z.tar.gz`

### Trigger a Test Release

1. Update VERSION file:
   ```bash
   echo "0.5.1" > VERSION
   ```

2. Update pyproject.toml version (line 3)

3. Commit and push to main:
   ```bash
   git add VERSION pyproject.toml
   git commit -m "Test release v0.5.1"
   git push origin main
   ```

4. Watch GitHub Actions:
   - Go to https://github.com/grobertson/kryten-robot/actions
   - You should see "Release Automation" workflow running
   - After it completes, "Publish Python Package to PyPI" should run
   - Total time: ~2-3 minutes

5. Verify on PyPI:
   - Go to https://pypi.org/project/kryten-robot/
   - You should see version 0.5.1 (or your test version)

6. Test installation:
   ```bash
   pip install --upgrade kryten-robot
   python -c "import kryten; print(kryten.__version__)"
   ```

## Troubleshooting

### "Trusted publishing exchange failure"

**Cause:** Trusted publisher configuration doesn't match the workflow.

**Solution:**
1. Verify all fields on PyPI match exactly:
   - Owner: `grobertson`
   - Repository: `kryten-robot`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`
2. Ensure the workflow file exists in `.github/workflows/publish-pypi.yml`
3. Check the environment is named `pypi` in the workflow file

### Workflow runs but doesn't publish

**Cause:** The workflow might be waiting for environment approval.

**Solution:**
1. Go to https://github.com/grobertson/kryten-robot/settings/environments
2. Click on `pypi` environment
3. Check if "Required reviewers" is enabled
4. Either disable it or approve the deployment

### "Project does not exist"

**Cause:** PyPI project name doesn't match.

**Solution:**
1. Verify project exists: https://pypi.org/project/kryten-robot/
2. Ensure `name = "kryten-robot"` in `pyproject.toml` matches exactly
3. Check for typos or case differences

### Package not found after publishing

**Cause:** PyPI might be caching or indexing.

**Solution:**
1. Wait 2-3 minutes for PyPI to index
2. Clear pip cache: `pip cache purge`
3. Try again: `pip install --upgrade --no-cache-dir kryten-robot`

## Environment Protection (Optional)

You can add protection rules to the `pypi` environment for extra safety:

1. Go to https://github.com/grobertson/kryten-robot/settings/environments
2. Click on `pypi` environment (or create it if it doesn't exist)
3. Configure protection rules:
   - **Required reviewers**: Require approval before publishing
   - **Wait timer**: Add a delay before publishing
   - **Deployment branches**: Limit to `main` branch only

Example configuration:
```yaml
Required reviewers: [grobertson]
Wait timer: 5 minutes
Deployment branches: Selected branches only (main)
```

This adds an extra approval step before publishing to PyPI.

## Disabling Trusted Publishing

If you need to revert to token-based publishing:

### 1. Remove Trusted Publisher

1. Go to https://pypi.org/manage/project/kryten-robot/settings/publishing/
2. Find the trusted publisher
3. Click "Remove"

### 2. Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: "Kryten-Robot Manual Publishing"
4. Scope: "Project: kryten-robot"
5. Click "Add token"
6. Copy the token (starts with `pypi-`)

### 3. Configure Token

```bash
poetry config pypi-token.pypi pypi-YOUR-TOKEN-HERE
```

### 4. Disable Automated Workflow

Rename or delete `.github/workflows/publish-pypi.yml`.

## Additional Resources

- [PyPI Trusted Publishers Documentation](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions OpenID Connect](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Poetry Publishing Documentation](https://python-poetry.org/docs/repositories/#configuring-credentials)

## Support

If you encounter issues:

1. Check workflow logs: https://github.com/grobertson/kryten-robot/actions
2. Check PyPI project settings: https://pypi.org/manage/project/kryten-robot/
3. Open an issue: https://github.com/grobertson/kryten-robot/issues
