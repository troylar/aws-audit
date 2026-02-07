# Publishing to PyPI

## Automated Publishing (Recommended)

The project uses GitHub Actions for automated publishing.

### Release Publishing (Production PyPI)

1. **Create and push a version tag:**

    ```bash
    git tag v1.0.0
    git push origin v1.0.0
    ```

2. **Create GitHub Release:**
    - Go to repository > Releases > "Draft a new release"
    - Choose the tag you just created
    - Add release notes
    - Click "Publish release"

3. **Automated workflow will:**
    - Build the package
    - Run tests and quality checks
    - Publish to PyPI
    - Upload distributions to GitHub Release

### Manual Trigger (Test PyPI)

For testing before production release:

1. Go to Actions > "Publish to PyPI" > "Run workflow"
2. Select branch (usually `main`)
3. Check "Publish to Test PyPI"
4. Click "Run workflow"

Install from Test PyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ aws-inventory-manager
```

## Manual Publishing

If you need to publish manually:

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Update version in pyproject.toml

# Build
python -m build

# Check
twine check dist/*

# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Upload to production PyPI
twine upload dist/*
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0 > 2.0.0): Breaking changes
- **Minor** (1.0.0 > 1.1.0): New features, backward compatible
- **Patch** (1.0.0 > 1.0.1): Bug fixes, backward compatible

## Checklist Before Publishing

- [ ] All tests pass: `invoke test`
- [ ] Code quality checks pass: `invoke quality`
- [ ] Version number updated in `pyproject.toml`
- [ ] CHANGELOG updated with release notes
- [ ] README.md is up-to-date
- [ ] No sensitive data in repository
- [ ] Package builds successfully: `python -m build`
- [ ] Package passes checks: `twine check dist/*`
- [ ] Tested installation from Test PyPI

## Troubleshooting

### "File already exists" Error

PyPI doesn't allow re-uploading the same version. Increment the version number.

### Build Fails

```bash
rm -rf dist/ build/ *.egg-info
python -m build
```

### Upload Authentication Fails

For manual uploads, generate an API token from PyPI and store in `~/.pypirc`.
