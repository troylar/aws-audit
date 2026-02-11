"""Tests for pattern data models (T005 + T006)."""

from __future__ import annotations

import pytest

from src.patterns.models import (
    ComparisonReport,
    ExpectViolation,
    GuardrailViolationRef,
    Pattern,
    PatternMatch,
    PatternResource,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_resource_dict() -> dict:
    return {
        "type": "lambda:function",
        "count": 3,
        "description": "Backend API handlers",
        "expect": {"runtime": "python3.11", "memory": ">= 256"},
    }


@pytest.fixture
def sample_resource(sample_resource_dict: dict) -> PatternResource:
    return PatternResource.from_dict(sample_resource_dict)


@pytest.fixture
def minimal_resource_dict() -> dict:
    return {"type": "s3:bucket", "count": 1}


@pytest.fixture
def sample_pattern_dict(sample_resource_dict: dict) -> dict:
    return {
        "name": "serverless-api",
        "description": "Standard serverless API pattern",
        "version": 2,
        "tags": ["serverless", "api"],
        "owner": "platform-team",
        "resources": [
            sample_resource_dict,
            {"type": "apigateway:rest-api", "count": 1},
        ],
        "guardrails": ["encryption-at-rest", "logging-enabled"],
        "source_snapshot": "snap-20260101",
        "source_account": "123456789012",
    }


@pytest.fixture
def sample_pattern(sample_pattern_dict: dict) -> Pattern:
    return Pattern.from_dict(sample_pattern_dict)


# ===========================================================================
# T005: PatternResource and Pattern dataclasses
# ===========================================================================


class TestPatternResource:
    """Tests for PatternResource dataclass."""

    def test_construction_all_fields(self) -> None:
        """PatternResource can be constructed with all fields."""
        r = PatternResource(
            type="lambda:function",
            count=3,
            description="Backend handlers",
            expect={"runtime": "python3.11"},
        )
        assert r.type == "lambda:function"
        assert r.count == 3
        assert r.description == "Backend handlers"
        assert r.expect == {"runtime": "python3.11"}

    def test_default_description_is_empty(self) -> None:
        """Description defaults to empty string."""
        r = PatternResource(type="s3:bucket", count=1)
        assert r.description == ""

    def test_default_expect_is_empty_dict(self) -> None:
        """Expect defaults to empty dict."""
        r = PatternResource(type="s3:bucket", count=1)
        assert r.expect == {}

    def test_type_is_string(self) -> None:
        """PatternResource.type is a string."""
        r = PatternResource(type="ec2:instance", count=1)
        assert isinstance(r.type, str)

    def test_count_is_int(self) -> None:
        """PatternResource.count is an int."""
        r = PatternResource(type="ec2:instance", count=5)
        assert isinstance(r.count, int)

    def test_to_dict_all_fields(self, sample_resource: PatternResource) -> None:
        """to_dict includes all non-empty fields."""
        d = sample_resource.to_dict()
        assert d["type"] == "lambda:function"
        assert d["count"] == 3
        assert d["description"] == "Backend API handlers"
        assert d["expect"] == {"runtime": "python3.11", "memory": ">= 256"}

    def test_to_dict_minimal(self) -> None:
        """to_dict omits empty description and expect."""
        r = PatternResource(type="s3:bucket", count=1)
        d = r.to_dict()
        assert d == {"type": "s3:bucket", "count": 1}
        assert "description" not in d
        assert "expect" not in d

    def test_from_dict_all_fields(self, sample_resource_dict: dict) -> None:
        """from_dict parses all fields correctly."""
        r = PatternResource.from_dict(sample_resource_dict)
        assert r.type == "lambda:function"
        assert r.count == 3
        assert r.description == "Backend API handlers"
        assert r.expect == {"runtime": "python3.11", "memory": ">= 256"}

    def test_from_dict_minimal(self, minimal_resource_dict: dict) -> None:
        """from_dict fills defaults for missing optional fields."""
        r = PatternResource.from_dict(minimal_resource_dict)
        assert r.type == "s3:bucket"
        assert r.count == 1
        assert r.description == ""
        assert r.expect == {}

    def test_from_dict_defaults_count_to_1(self) -> None:
        """from_dict defaults count to 1 when omitted."""
        r = PatternResource.from_dict({"type": "rds:instance"})
        assert r.count == 1

    def test_round_trip(self, sample_resource: PatternResource) -> None:
        """from_dict(to_dict()) produces an equivalent object."""
        d = sample_resource.to_dict()
        rebuilt = PatternResource.from_dict(d)
        assert rebuilt.type == sample_resource.type
        assert rebuilt.count == sample_resource.count
        assert rebuilt.description == sample_resource.description
        assert rebuilt.expect == sample_resource.expect

    def test_round_trip_minimal(self) -> None:
        """Round-trip works for a minimal resource (no optional fields)."""
        original = PatternResource(type="s3:bucket", count=2)
        rebuilt = PatternResource.from_dict(original.to_dict())
        assert rebuilt.type == original.type
        assert rebuilt.count == original.count
        assert rebuilt.description == ""
        assert rebuilt.expect == {}

    def test_to_dict_returns_new_expect_dict(self, sample_resource: PatternResource) -> None:
        """to_dict returns a copy of expect, not the original reference."""
        d = sample_resource.to_dict()
        d["expect"]["new_key"] = "value"
        assert "new_key" not in sample_resource.expect


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_construction_all_fields(self) -> None:
        """Pattern can be constructed with all fields."""
        res = PatternResource(type="s3:bucket", count=1)
        p = Pattern(
            name="my-pattern",
            description="A test pattern",
            version=3,
            tags=["web", "prod"],
            owner="team-alpha",
            resources=[res],
            guardrails=["encryption-at-rest"],
            source_snapshot="snap-001",
            source_account="111222333444",
        )
        assert p.name == "my-pattern"
        assert p.description == "A test pattern"
        assert p.version == 3
        assert p.tags == ["web", "prod"]
        assert p.owner == "team-alpha"
        assert len(p.resources) == 1
        assert p.guardrails == ["encryption-at-rest"]
        assert p.source_snapshot == "snap-001"
        assert p.source_account == "111222333444"

    def test_default_guardrails_empty(self) -> None:
        """Guardrails defaults to empty list."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        assert p.guardrails == []

    def test_default_source_snapshot_none(self) -> None:
        """source_snapshot defaults to None."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        assert p.source_snapshot is None

    def test_default_source_account_none(self) -> None:
        """source_account defaults to None."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        assert p.source_account is None

    def test_tags_is_list_of_strings(self, sample_pattern: Pattern) -> None:
        """Pattern.tags is a list of strings."""
        assert isinstance(sample_pattern.tags, list)
        assert all(isinstance(t, str) for t in sample_pattern.tags)

    def test_resources_is_list_of_pattern_resource(self, sample_pattern: Pattern) -> None:
        """Pattern.resources is a list of PatternResource."""
        assert isinstance(sample_pattern.resources, list)
        assert all(isinstance(r, PatternResource) for r in sample_pattern.resources)

    def test_to_dict_full(self, sample_pattern: Pattern) -> None:
        """to_dict includes all populated fields."""
        d = sample_pattern.to_dict()
        assert d["name"] == "serverless-api"
        assert d["description"] == "Standard serverless API pattern"
        assert d["version"] == 2
        assert d["tags"] == ["serverless", "api"]
        assert d["owner"] == "platform-team"
        assert len(d["resources"]) == 2
        assert d["guardrails"] == ["encryption-at-rest", "logging-enabled"]
        assert d["source_snapshot"] == "snap-20260101"
        assert d["source_account"] == "123456789012"

    def test_to_dict_omits_empty_guardrails(self) -> None:
        """to_dict omits guardrails when empty."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        d = p.to_dict()
        assert "guardrails" not in d

    def test_to_dict_omits_none_source_snapshot(self) -> None:
        """to_dict omits source_snapshot when None."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        d = p.to_dict()
        assert "source_snapshot" not in d

    def test_to_dict_omits_none_source_account(self) -> None:
        """to_dict omits source_account when None."""
        p = Pattern(
            name="x",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[],
        )
        d = p.to_dict()
        assert "source_account" not in d

    def test_from_dict_full(self, sample_pattern_dict: dict) -> None:
        """from_dict parses all fields from a complete dict."""
        p = Pattern.from_dict(sample_pattern_dict)
        assert p.name == "serverless-api"
        assert p.version == 2
        assert p.guardrails == ["encryption-at-rest", "logging-enabled"]
        assert p.source_snapshot == "snap-20260101"
        assert p.source_account == "123456789012"
        assert len(p.resources) == 2

    def test_from_dict_minimal(self) -> None:
        """from_dict fills defaults for all optional fields."""
        d = {
            "name": "simple",
            "description": "A simple pattern",
        }
        p = Pattern.from_dict(d)
        assert p.name == "simple"
        assert p.description == "A simple pattern"
        assert p.version == 1
        assert p.tags == []
        assert p.owner == ""
        assert p.resources == []
        assert p.guardrails == []
        assert p.source_snapshot is None
        assert p.source_account is None

    def test_round_trip(self, sample_pattern: Pattern) -> None:
        """from_dict(to_dict()) produces an equivalent object."""
        d = sample_pattern.to_dict()
        rebuilt = Pattern.from_dict(d)
        assert rebuilt.name == sample_pattern.name
        assert rebuilt.description == sample_pattern.description
        assert rebuilt.version == sample_pattern.version
        assert rebuilt.tags == sample_pattern.tags
        assert rebuilt.owner == sample_pattern.owner
        assert rebuilt.guardrails == sample_pattern.guardrails
        assert rebuilt.source_snapshot == sample_pattern.source_snapshot
        assert rebuilt.source_account == sample_pattern.source_account
        assert len(rebuilt.resources) == len(sample_pattern.resources)
        for orig, copy in zip(sample_pattern.resources, rebuilt.resources):
            assert orig.type == copy.type
            assert orig.count == copy.count

    def test_round_trip_minimal(self) -> None:
        """Round-trip works for a minimal pattern."""
        original = Pattern(
            name="bare",
            description="bare bones",
            version=1,
            tags=[],
            owner="",
            resources=[],
        )
        rebuilt = Pattern.from_dict(original.to_dict())
        assert rebuilt.name == original.name
        assert rebuilt.resources == []
        assert rebuilt.guardrails == []
        assert rebuilt.source_snapshot is None

    def test_to_dict_returns_new_tags_list(self, sample_pattern: Pattern) -> None:
        """to_dict returns a copy of tags, not the original reference."""
        d = sample_pattern.to_dict()
        d["tags"].append("injected")
        assert "injected" not in sample_pattern.tags

    def test_to_dict_returns_new_guardrails_list(self, sample_pattern: Pattern) -> None:
        """to_dict returns a copy of guardrails, not the original reference."""
        d = sample_pattern.to_dict()
        d["guardrails"].append("injected")
        assert "injected" not in sample_pattern.guardrails


# ===========================================================================
# T006: ExpectViolation, GuardrailViolationRef, PatternMatch, ComparisonReport
# ===========================================================================


class TestExpectViolation:
    """Tests for ExpectViolation dataclass."""

    def test_construction(self) -> None:
        """ExpectViolation can be constructed with all required fields."""
        v = ExpectViolation(
            resource_type="lambda:function",
            resource_name="my-func",
            config_key="runtime",
            actual_value="python3.9",
            expected_value="python3.11",
        )
        assert v.resource_type == "lambda:function"
        assert v.resource_name == "my-func"
        assert v.config_key == "runtime"
        assert v.actual_value == "python3.9"
        assert v.expected_value == "python3.11"

    def test_actual_value_can_be_any_type(self) -> None:
        """actual_value accepts any type (int, bool, None, dict, etc.)."""
        for val in [42, True, None, {"nested": "dict"}, [1, 2]]:
            v = ExpectViolation(
                resource_type="t",
                resource_name="n",
                config_key="k",
                actual_value=val,
                expected_value="expected",
            )
            assert v.actual_value == val


class TestGuardrailViolationRef:
    """Tests for GuardrailViolationRef dataclass."""

    def test_construction(self) -> None:
        """GuardrailViolationRef can be constructed with all required fields."""
        g = GuardrailViolationRef(
            guardrail_name="encryption-at-rest",
            resource_type="s3:bucket",
            resource_name="my-bucket",
            detail="Bucket is not encrypted",
        )
        assert g.guardrail_name == "encryption-at-rest"
        assert g.resource_type == "s3:bucket"
        assert g.resource_name == "my-bucket"
        assert g.detail == "Bucket is not encrypted"


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""

    @pytest.fixture
    def base_pattern(self) -> Pattern:
        return Pattern(
            name="test",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )

    def test_construction_all_fields(self, base_pattern: Pattern) -> None:
        """PatternMatch can be constructed with all required fields."""
        m = PatternMatch(
            pattern=base_pattern,
            score=0.85,
            aligned={"s3:bucket": (1, 1)},
            missing={"rds:instance": 2},
            extra={"ec2:instance": 3},
            expect_violations=[],
            guardrail_violations=[],
        )
        assert m.pattern is base_pattern
        assert m.score == 0.85
        assert m.aligned == {"s3:bucket": (1, 1)}
        assert m.missing == {"rds:instance": 2}
        assert m.extra == {"ec2:instance": 3}
        assert m.expect_violations == []
        assert m.guardrail_violations == []

    def test_guidance_defaults_to_none(self, base_pattern: Pattern) -> None:
        """PatternMatch.guidance defaults to None."""
        m = PatternMatch(
            pattern=base_pattern,
            score=1.0,
            aligned={},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        assert m.guidance is None

    def test_guidance_can_be_string(self, base_pattern: Pattern) -> None:
        """PatternMatch.guidance accepts a string value."""
        m = PatternMatch(
            pattern=base_pattern,
            score=0.5,
            aligned={},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
            guidance="Add an RDS instance to match the pattern.",
        )
        assert m.guidance == "Add an RDS instance to match the pattern."

    def test_with_violations(self, base_pattern: Pattern) -> None:
        """PatternMatch holds expect and guardrail violations."""
        ev = ExpectViolation(
            resource_type="lambda:function",
            resource_name="fn1",
            config_key="runtime",
            actual_value="python3.9",
            expected_value="python3.11",
        )
        gv = GuardrailViolationRef(
            guardrail_name="encryption",
            resource_type="s3:bucket",
            resource_name="b1",
            detail="not encrypted",
        )
        m = PatternMatch(
            pattern=base_pattern,
            score=0.75,
            aligned={},
            missing={},
            extra={},
            expect_violations=[ev],
            guardrail_violations=[gv],
        )
        assert len(m.expect_violations) == 1
        assert len(m.guardrail_violations) == 1
        assert m.expect_violations[0].config_key == "runtime"
        assert m.guardrail_violations[0].guardrail_name == "encryption"


class TestComparisonReport:
    """Tests for ComparisonReport dataclass."""

    def test_construction_required_fields(self) -> None:
        """ComparisonReport can be constructed with required fields only."""
        r = ComparisonReport(
            snapshot_name="snap-20260101",
            matches=[],
            threshold=0.25,
        )
        assert r.snapshot_name == "snap-20260101"
        assert r.matches == []
        assert r.threshold == 0.25

    def test_empty_matches_list(self) -> None:
        """ComparisonReport with empty matches list."""
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.5,
        )
        assert len(r.matches) == 0

    def test_coverage_summary_defaults_to_none(self) -> None:
        """coverage_summary defaults to None."""
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
        )
        assert r.coverage_summary is None

    def test_coverage_summary_accepts_string(self) -> None:
        """coverage_summary can be set to a string."""
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
            coverage_summary="80% of resources are covered.",
        )
        assert r.coverage_summary == "80% of resources are covered."

    def test_unaccounted_types_defaults_to_empty_dict(self) -> None:
        """unaccounted_types defaults to empty dict."""
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
        )
        assert r.unaccounted_types == {}

    def test_unaccounted_types_with_data(self) -> None:
        """ComparisonReport can hold unaccounted resource types."""
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
            unaccounted_types={"ec2:instance": 5, "sqs:queue": 2},
        )
        assert r.unaccounted_types == {"ec2:instance": 5, "sqs:queue": 2}

    def test_with_matches(self) -> None:
        """ComparisonReport holds a list of PatternMatch objects."""
        p = Pattern(
            name="p1",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )
        match = PatternMatch(
            pattern=p,
            score=0.9,
            aligned={"s3:bucket": (1, 1)},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        r = ComparisonReport(
            snapshot_name="snap",
            matches=[match],
            threshold=0.25,
        )
        assert len(r.matches) == 1
        assert r.matches[0].score == 0.9
        assert r.matches[0].pattern.name == "p1"
