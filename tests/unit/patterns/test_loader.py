"""Tests for pattern loading and validation (T007 + T008)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, List

import pytest
import yaml

from src.patterns.models import Pattern, PatternResource

try:
    from src.patterns.loader import (
        delete_pattern,
        get_library_path,
        list_pattern_versions,
        load_library,
        load_pattern,
        save_pattern,
        validate_pattern,
    )
except ImportError:
    pytest.skip(
        "loader functions not yet implemented",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_YAML = dedent("""\
    name: serverless-api
    description: Standard serverless API pattern
    version: 1
    tags:
      - serverless
      - api
    owner: platform-team
    resources:
      - type: "lambda:function"
        count: 3
        description: Backend API handlers
        expect:
          runtime: python3.11
          memory: ">= 256"
      - type: "apigateway:rest-api"
        count: 1
    guardrails:
      - encryption-at-rest
    source_snapshot: snap-20260101
    source_account: "123456789012"
""")

MINIMAL_YAML = dedent("""\
    name: minimal
    description: A minimal pattern
    version: 1
    tags: []
    owner: someone
    resources:
      - type: "s3:bucket"
        count: 1
""")


@pytest.fixture
def valid_yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "serverless-api-v1.yaml"
    p.write_text(VALID_YAML)
    return p


@pytest.fixture
def minimal_yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "minimal-v1.yaml"
    p.write_text(MINIMAL_YAML)
    return p


@pytest.fixture
def sample_pattern() -> Pattern:
    return Pattern(
        name="serverless-api",
        description="Standard serverless API pattern",
        version=2,
        tags=["serverless", "api"],
        owner="platform-team",
        resources=[
            PatternResource(
                type="lambda:function",
                count=3,
                description="Backend API handlers",
                expect={"runtime": "python3.11"},
            ),
            PatternResource(type="apigateway:rest-api", count=1),
        ],
        guardrails=["encryption-at-rest"],
        source_snapshot="snap-20260101",
        source_account="123456789012",
    )


@pytest.fixture
def valid_pattern() -> Pattern:
    """A pattern that passes all validation rules."""
    return Pattern(
        name="valid",
        description="A valid pattern",
        version=1,
        tags=["test"],
        owner="owner",
        resources=[
            PatternResource(
                type="lambda:function",
                count=2,
                expect={"runtime": "python3.11", "memory.size": ">= 256"},
            ),
        ],
        guardrails=["encryption-at-rest"],
    )


@pytest.fixture
def library_dir(tmp_path: Path) -> Path:
    """Create a library directory with several pattern files."""
    patterns = [
        {
            "name": "web-app",
            "description": "Web application",
            "version": 1,
            "tags": ["web"],
            "owner": "team-a",
            "resources": [{"type": "ec2:instance", "count": 2}],
        },
        {
            "name": "web-app",
            "description": "Web application v2",
            "version": 2,
            "tags": ["web"],
            "owner": "team-a",
            "resources": [
                {"type": "ec2:instance", "count": 2},
                {"type": "rds:instance", "count": 1},
            ],
        },
        {
            "name": "data-pipeline",
            "description": "Data pipeline",
            "version": 1,
            "tags": ["data"],
            "owner": "team-b",
            "resources": [{"type": "lambda:function", "count": 5}],
        },
    ]
    for p in patterns:
        filepath = tmp_path / f"{p['name']}-v{p['version']}.yaml"
        filepath.write_text(yaml.dump(p, default_flow_style=False))
    return tmp_path


# ===========================================================================
# T007: load_pattern, load_library, validate_pattern, save_pattern
# ===========================================================================


class TestLoadPattern:
    """Tests for load_pattern()."""

    def test_valid_yaml_returns_pattern(self, valid_yaml_file: Path) -> None:
        """load_pattern() with a valid YAML file returns a Pattern object."""
        pattern = load_pattern(valid_yaml_file)
        assert isinstance(pattern, Pattern)
        assert pattern.name == "serverless-api"
        assert pattern.version == 1
        assert len(pattern.resources) == 2
        assert pattern.resources[0].type == "lambda:function"
        assert pattern.resources[0].count == 3
        assert pattern.guardrails == ["encryption-at-rest"]
        assert pattern.source_snapshot == "snap-20260101"

    def test_minimal_yaml_returns_pattern(self, minimal_yaml_file: Path) -> None:
        """load_pattern() with minimal fields returns a Pattern."""
        pattern = load_pattern(minimal_yaml_file)
        assert pattern.name == "minimal"
        assert pattern.description == "A minimal pattern"
        assert len(pattern.resources) == 1

    def test_invalid_yaml_syntax_raises(self, tmp_path: Path) -> None:
        """load_pattern() raises ValueError on malformed YAML."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("name: test\n  bad indent:\n- broken: {[")
        with pytest.raises(ValueError):
            load_pattern(bad_file)

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        """load_pattern() raises ValueError when 'name' is missing."""
        content = dedent("""\
            description: No name pattern
            version: 1
            tags: []
            owner: someone
            resources:
              - type: "s3:bucket"
                count: 1
        """)
        f = tmp_path / "noname.yaml"
        f.write_text(content)
        with pytest.raises(ValueError):
            load_pattern(f)

    def test_missing_description_raises(self, tmp_path: Path) -> None:
        """load_pattern() raises ValueError when 'description' is missing."""
        content = dedent("""\
            name: nodesc
            version: 1
            tags: []
            owner: someone
            resources:
              - type: "s3:bucket"
                count: 1
        """)
        f = tmp_path / "nodesc.yaml"
        f.write_text(content)
        with pytest.raises(ValueError):
            load_pattern(f)


class TestValidatePattern:
    """Tests for validate_pattern()."""

    def test_valid_pattern_no_errors(self, valid_pattern: Pattern) -> None:
        """validate_pattern() returns empty list for a valid pattern."""
        errors = validate_pattern(valid_pattern)
        assert errors == []

    def test_empty_resources_returns_error(self) -> None:
        """validate_pattern() returns an error when resources list is empty."""
        p = Pattern(
            name="no-resources",
            description="Empty resources",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1
        assert any("resource" in e.lower() for e in errors)

    def test_invalid_type_no_colon_returns_error(self) -> None:
        """validate_pattern() returns error when type has no colon separator."""
        p = Pattern(
            name="bad-type",
            description="Type without colon",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="lambdafunction", count=1)],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1
        assert any(":" in e or "type" in e.lower() or "format" in e.lower() for e in errors)

    def test_count_less_than_1_returns_error(self) -> None:
        """validate_pattern() returns error when count < 1."""
        p = Pattern(
            name="bad-count",
            description="Zero count",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=0)],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1
        assert any("count" in e.lower() for e in errors)

    def test_negative_count_returns_error(self) -> None:
        """validate_pattern() returns error when count is negative."""
        p = Pattern(
            name="neg-count",
            description="Negative count",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=-1)],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1
        assert any("count" in e.lower() for e in errors)

    def test_expect_key_leading_dot_returns_error(self) -> None:
        """validate_pattern() returns error for expect key with leading dot."""
        p = Pattern(
            name="bad-key",
            description="Leading dot",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={".runtime": "python3.11"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1

    def test_expect_key_trailing_dot_returns_error(self) -> None:
        """validate_pattern() returns error for expect key with trailing dot."""
        p = Pattern(
            name="bad-key",
            description="Trailing dot",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"runtime.": "python3.11"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1

    def test_expect_key_non_alphanumeric_returns_error(self) -> None:
        """validate_pattern() returns error for expect key with invalid chars."""
        p = Pattern(
            name="bad-key",
            description="Special chars",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"run time!": "python3.11"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1

    def test_expect_valid_dotted_path_accepted(self) -> None:
        """validate_pattern() accepts valid dotted-path expect keys."""
        p = Pattern(
            name="ok-key",
            description="Valid keys",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"config.runtime.version": "python3.11"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert errors == []

    def test_expect_value_invalid_operator_returns_error(self) -> None:
        """validate_pattern() returns error for invalid operator prefix."""
        p = Pattern(
            name="bad-op",
            description="Invalid operator",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"memory": ">> 256"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert len(errors) >= 1

    def test_expect_value_valid_operators_accepted(self) -> None:
        """validate_pattern() accepts all valid operator prefixes."""
        for op in [">=", "<=", ">", "<", "!="]:
            p = Pattern(
                name="ok-op",
                description="Valid op",
                version=1,
                tags=[],
                owner="o",
                resources=[
                    PatternResource(
                        type="lambda:function",
                        count=1,
                        expect={"memory": f"{op} 256"},
                    ),
                ],
            )
            errors = validate_pattern(p)
            assert errors == [], f"Unexpected error for operator '{op}': {errors}"

    def test_expect_value_exact_match_accepted(self) -> None:
        """validate_pattern() accepts plain string values (exact match)."""
        p = Pattern(
            name="exact",
            description="Exact match",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"runtime": "python3.11"},
                ),
            ],
        )
        errors = validate_pattern(p)
        assert errors == []

    def test_expect_overlap_with_guardrail_returns_warning(self) -> None:
        """validate_pattern() returns a warning (not error) for expect/guardrail overlap."""
        p = Pattern(
            name="overlap",
            description="Overlap test",
            version=1,
            tags=[],
            owner="o",
            resources=[
                PatternResource(
                    type="s3:bucket",
                    count=1,
                    expect={"encryption": "AES256"},
                ),
            ],
            guardrails=["encryption-at-rest"],
        )
        result = validate_pattern(p)
        has_warning = any("guardrail" in s.lower() for s in result)
        assert has_warning, f"Expected a warning about guardrail overlap, got: {result}"


class TestSavePattern:
    """Tests for save_pattern()."""

    def test_saves_to_correct_filename(self, tmp_path: Path, sample_pattern: Pattern) -> None:
        """save_pattern() writes to {name}-v{version}.yaml."""
        save_pattern(sample_pattern, tmp_path)
        expected_file = tmp_path / "serverless-api-v2.yaml"
        assert expected_file.exists()

    def test_saved_file_is_valid_yaml(self, tmp_path: Path, sample_pattern: Pattern) -> None:
        """save_pattern() writes valid, parseable YAML."""
        save_pattern(sample_pattern, tmp_path)
        filepath = tmp_path / "serverless-api-v2.yaml"
        data = yaml.safe_load(filepath.read_text())
        assert data["name"] == "serverless-api"
        assert data["version"] == 2

    def test_save_then_load_round_trip(self, tmp_path: Path, sample_pattern: Pattern) -> None:
        """Saving then loading a pattern preserves all fields."""
        save_pattern(sample_pattern, tmp_path)
        filepath = tmp_path / "serverless-api-v2.yaml"
        loaded = load_pattern(filepath)
        assert loaded.name == sample_pattern.name
        assert loaded.version == sample_pattern.version
        assert loaded.description == sample_pattern.description
        assert len(loaded.resources) == len(sample_pattern.resources)
        assert loaded.guardrails == sample_pattern.guardrails


class TestLoadLibrary:
    """Tests for load_library()."""

    def test_loads_all_patterns(self, library_dir: Path) -> None:
        """load_library() returns all patterns from a directory."""
        patterns = load_library(library_dir)
        assert len(patterns) == 3

    def test_returns_pattern_objects(self, library_dir: Path) -> None:
        """load_library() returns Pattern instances."""
        patterns = load_library(library_dir)
        assert all(isinstance(p, Pattern) for p in patterns)

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """load_library() returns an empty list for empty directory."""
        patterns = load_library(tmp_path)
        assert patterns == []

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """load_library() skips files without .yaml/.yml extension."""
        (tmp_path / "readme.txt").write_text("not a pattern")
        (tmp_path / "pattern-v1.yaml").write_text(
            yaml.dump(
                {
                    "name": "pattern",
                    "description": "A pattern",
                    "version": 1,
                    "tags": [],
                    "owner": "o",
                    "resources": [{"type": "s3:bucket", "count": 1}],
                }
            )
        )
        patterns = load_library(tmp_path)
        assert len(patterns) == 1


# ===========================================================================
# T008: list_pattern_versions, delete_pattern, get_library_path
# ===========================================================================


class TestListPatternVersions:
    """Tests for list_pattern_versions()."""

    def test_returns_all_versions_sorted(self, library_dir: Path) -> None:
        """list_pattern_versions() returns versions sorted ascending."""
        versions = list_pattern_versions("web-app", library_dir)
        assert versions == [1, 2]

    def test_single_version(self, library_dir: Path) -> None:
        """list_pattern_versions() works for a pattern with one version."""
        versions = list_pattern_versions("data-pipeline", library_dir)
        assert versions == [1]

    def test_nonexistent_pattern_returns_empty(self, library_dir: Path) -> None:
        """list_pattern_versions() returns empty list for unknown pattern."""
        versions = list_pattern_versions("nonexistent", library_dir)
        assert versions == []


class TestDeletePattern:
    """Tests for delete_pattern()."""

    def test_deletes_specific_version(self, library_dir: Path) -> None:
        """delete_pattern() removes a specific version file."""
        result = delete_pattern("web-app", library_dir, version=1)
        assert result is True
        assert not (library_dir / "web-app-v1.yaml").exists()
        assert (library_dir / "web-app-v2.yaml").exists()

    def test_deletes_all_versions_when_no_version(self, library_dir: Path) -> None:
        """delete_pattern() deletes all versions when version is None."""
        result = delete_pattern("web-app", library_dir)
        assert result is True
        assert not (library_dir / "web-app-v1.yaml").exists()
        assert not (library_dir / "web-app-v2.yaml").exists()

    def test_returns_false_for_nonexistent_pattern(self, library_dir: Path) -> None:
        """delete_pattern() returns False when pattern is not found."""
        result = delete_pattern("nonexistent", library_dir)
        assert result is False

    def test_returns_false_for_nonexistent_version(self, library_dir: Path) -> None:
        """delete_pattern() returns False for a version that doesn't exist."""
        result = delete_pattern("web-app", library_dir, version=99)
        assert result is False

    def test_does_not_affect_other_patterns(self, library_dir: Path) -> None:
        """delete_pattern() only removes matching files."""
        delete_pattern("web-app", library_dir)
        assert (library_dir / "data-pipeline-v1.yaml").exists()


class TestGetLibraryPath:
    """Tests for get_library_path()."""

    def test_uses_custom_path(self, tmp_path: Path) -> None:
        """get_library_path() returns the custom path when provided."""
        result = get_library_path(custom_path=str(tmp_path))
        assert Path(result) == tmp_path

    def test_falls_back_to_env_var(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """get_library_path() uses env var when no custom path."""
        env_path = str(tmp_path / "env-lib")
        monkeypatch.setenv("AWS_PATTERN_LIBRARY_PATH", env_path)
        result = get_library_path()
        assert result == env_path

    def test_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_library_path() returns a default when no custom path or env var."""
        monkeypatch.delenv("AWS_PATTERN_LIBRARY_PATH", raising=False)
        result = get_library_path()
        assert isinstance(result, str)
        assert len(result) > 0
