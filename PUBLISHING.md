# Publishing to PyPI

This document describes how to publish the `aws-audit` package to PyPI.

## Prerequisites

1. **PyPI Account**: Create accounts on:
   - [Test PyPI](https://test.pypi.org/account/register/) (for testing)
   - [PyPI](https://pypi.org/account/register/) (for production)

2. **GitHub Repository Setup**:
   - Enable [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   - Configure repository secrets (if not using trusted publishing)

3. **Local Development Tools**:
   ```bash
   pip install build twine
   ```

## Automated Publishing (Recommended)

The project uses GitHub Actions for automated publishing.

### Method 1: Release Publishing (Production PyPI)

1. **Create a new release on GitHub**:
   ```bash
   # Create and push a version tag
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Create GitHub Release**:
   - Go to repository → Releases → "Draft a new release"
   - Choose the tag you just created
   - Add release notes
   - Click "Publish release"

3. **Automated workflow will**:
   - Build the package
   - Run tests and quality checks
   - Publish to PyPI
   - Upload distributions to GitHub Release

### Method 2: Manual Trigger (Test PyPI)

For testing before production release:

1. Go to Actions → "Publish to PyPI" → "Run workflow"
2. Select branch (usually `main`)
3. Check "Publish to Test PyPI"
4. Click "Run workflow"

The package will be published to https://test.pypi.org/project/aws-audit/

To install from Test PyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ aws-audit
```

## Manual Publishing (Alternative)

If you need to publish manually (not recommended for regular releases):

### Step 1: Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info
```

### Step 2: Update Version

Update version in `pyproject.toml`:
```toml
[project]
name = "aws-audit"
version = "1.0.1"  # Increment version
```

### Step 3: Build Package

```bash
# Build source distribution and wheel
python -m build

# Verify the build
ls dist/
# Should show:
#   aws_audit-1.0.1-py3-none-any.whl
#   aws-audit-1.0.1.tar.gz
```

### Step 4: Check Package

```bash
# Check package metadata and description
twine check dist/*
```

### Step 5: Upload to Test PyPI

```bash
# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ aws-audit==1.0.1
aws-audit --version
```

### Step 6: Upload to Production PyPI

```bash
# Upload to production PyPI
twine upload dist/*

# Verify
pip install aws-audit==1.0.1
aws-audit --version
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major version** (1.0.0 → 2.0.0): Breaking changes
- **Minor version** (1.0.0 → 1.1.0): New features, backward compatible
- **Patch version** (1.0.0 → 1.0.1): Bug fixes, backward compatible

### Pre-release Versions

For beta/alpha releases:
```
1.0.0a1  # Alpha release 1
1.0.0b1  # Beta release 1
1.0.0rc1 # Release candidate 1
```

## GitHub Trusted Publishing Setup

Trusted Publishing eliminates the need for API tokens.

### Step 1: Add Trusted Publisher on PyPI

1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in:
   - PyPI Project Name: `aws-audit`
   - Owner: `your-github-username`
   - Repository: `aws-baseline`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`

### Step 2: Create GitHub Environment

1. Go to repository → Settings → Environments
2. Create environment: `pypi`
3. Add protection rules (optional):
   - Required reviewers
   - Wait timer
   - Deployment branches: `main` only

### Step 3: Test Publishing

Create a test release to verify the setup works.

## Checklist Before Publishing

- [ ] All tests pass: `invoke test`
- [ ] Code quality checks pass: `invoke quality`
- [ ] Version number updated in `pyproject.toml`
- [ ] CHANGELOG updated with release notes
- [ ] README.md is up-to-date
- [ ] Documentation is complete
- [ ] No sensitive data in repository
- [ ] Package builds successfully: `python -m build`
- [ ] Package passes checks: `twine check dist/*`
- [ ] Tested installation from Test PyPI

## Post-Publishing

After successful PyPI publication:

1. **Verify Installation**:
   ```bash
   pip install aws-audit
   aws-audit --version
   ```

2. **Update Documentation**:
   - Update README badges
   - Update installation instructions
   - Announce on relevant channels

3. **Tag and Archive**:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

## Troubleshooting

### "File already exists" Error

PyPI doesn't allow re-uploading the same version. Solutions:
- Increment version number
- Delete the release from PyPI (only for mistakes)
- Use Test PyPI for testing

### Build Fails

```bash
# Clean and rebuild
rm -rf dist/ build/ *.egg-info
python -m build
```

### Upload Authentication Fails

For manual uploads:
```bash
# Generate API token from PyPI
# Store in ~/.pypirc:
[pypi]
username = __token__
password = pypi-...your-token...

[testpypi]
username = __token__
password = pypi-...your-test-token...
```

### Package Import Fails

Common issues:
- Missing `__init__.py` files
- Incorrect package structure in `pyproject.toml`
- Missing dependencies in `dependencies` list

## Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Semantic Versioning](https://semver.org/)
- [GitHub Actions for Python](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)

## Support

For publishing issues:
- PyPI: https://pypi.org/help/
- Test PyPI: https://test.pypi.org/help/
- GitHub Actions: Check workflow logs
