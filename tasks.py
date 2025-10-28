"""Invoke tasks for aws-baseline project."""

from invoke import task


@task
def test(c, verbose=False, coverage=True):
    """Run all tests with coverage.

    Args:
        verbose: Show verbose output
        coverage: Generate coverage report
    """
    cmd = "pytest"
    if verbose:
        cmd += " -v"
    if coverage:
        cmd += " --cov=src --cov-report=term-missing --cov-report=html"
    c.run(cmd)


@task
def test_unit(c, verbose=False):
    """Run unit tests only.

    Args:
        verbose: Show verbose output
    """
    cmd = "pytest tests/unit"
    if verbose:
        cmd += " -v"
    c.run(cmd)


@task
def test_integration(c, verbose=False):
    """Run integration tests only.

    Args:
        verbose: Show verbose output
    """
    cmd = "pytest tests/integration"
    if verbose:
        cmd += " -v"
    c.run(cmd)


@task
def format(c, check=False):
    """Format code with black.

    Args:
        check: Only check formatting without making changes
    """
    cmd = "black src/ tests/"
    if check:
        cmd += " --check"
    c.run(cmd)


@task
def lint(c, fix=False):
    """Lint code with ruff.

    Args:
        fix: Automatically fix issues
    """
    cmd = "ruff check src/ tests/"
    if fix:
        cmd += " --fix"
    c.run(cmd)


@task
def typecheck(c):
    """Run type checking with mypy."""
    c.run("mypy src/")


@task
def quality(c, fix=False):
    """Run all code quality checks (format, lint, typecheck).

    Args:
        fix: Automatically fix issues where possible
    """
    print("🎨 Running formatter...")
    format(c, check=not fix)

    print("\n🔍 Running linter...")
    lint(c, fix=fix)

    print("\n📊 Running type checker...")
    typecheck(c)

    print("\n✅ All quality checks complete!")


@task
def clean(c):
    """Clean build artifacts and cache files."""
    patterns = [
        "build/",
        "dist/",
        "*.egg-info",
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        ".pytest_cache/",
        ".coverage",
        "htmlcov/",
        ".mypy_cache/",
        ".ruff_cache/",
    ]

    for pattern in patterns:
        c.run(f"rm -rf {pattern}", warn=True)

    print("✅ Cleaned build artifacts and cache files")


@task
def build(c):
    """Build the package."""
    clean(c)
    c.run("python -m build")
    print("✅ Package built successfully")


@task
def install(c, dev=False):
    """Install the package.

    Args:
        dev: Install development dependencies
    """
    if dev:
        c.run("pip install -e '.[dev]'")
        print("✅ Installed package with development dependencies")
    else:
        c.run("pip install -e .")
        print("✅ Installed package")


@task
def install_invoke(c):
    """Install invoke for task automation."""
    c.run("pip install invoke")
    print("✅ Invoke installed")


@task
def version(c):
    """Display package version."""
    c.run("python -c \"import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])\"")


@task(pre=[quality, test])
def ci(c):
    """Run all CI checks (quality + tests)."""
    print("\n✅ All CI checks passed!")


@task
def coverage_report(c):
    """Generate and open HTML coverage report."""
    c.run("pytest --cov=src --cov-report=html")
    c.run("open htmlcov/index.html", warn=True)
    print("✅ Coverage report generated")


@task
def docs(c):
    """Generate documentation (placeholder for future implementation)."""
    print("📚 Documentation generation not yet implemented")
    print("   Available documentation:")
    print("   - README.md")
    print("   - specs/001-aws-baseline-snapshot/quickstart.md")
    print("   - specs/002-inventory-management/quickstart.md")
