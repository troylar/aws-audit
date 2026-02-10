"""Tests for pattern report formatting (T029 + T041)."""

from __future__ import annotations

import json

import pytest

from src.patterns.models import (
    ComparisonReport,
    ExpectViolation,
    GuardrailViolationRef,
    Pattern,
    PatternMatch,
    PatternResource,
)
from src.patterns.reporter import (
    format_compliance_report,
    format_json_report,
    format_pattern_detail,
    format_pattern_list,
    format_terminal_report,
)


@pytest.fixture
def sample_pattern() -> Pattern:
    return Pattern(
        name="serverless-api",
        description="Standard serverless API",
        version=1,
        tags=["serverless", "api"],
        owner="platform-team",
        resources=[
            PatternResource(
                type="lambda:function",
                count=2,
                description="API handlers",
                expect={"Runtime": "python3.12"},
            ),
            PatternResource(type="apigateway:rest-api", count=1),
        ],
        guardrails=["encryption-at-rest"],
    )


@pytest.fixture
def second_pattern() -> Pattern:
    return Pattern(
        name="data-pipeline",
        description="Batch data pipeline",
        version=1,
        tags=["data"],
        owner="team-b",
        resources=[
            PatternResource(type="lambda:function", count=3),
            PatternResource(type="sqs:queue", count=1),
        ],
    )


@pytest.fixture
def single_match(sample_pattern: Pattern) -> PatternMatch:
    return PatternMatch(
        pattern=sample_pattern,
        score=0.78,
        aligned={"lambda:function": (2, 2), "apigateway:rest-api": (1, 1)},
        missing={"cloudwatch:alarm": 3},
        extra={"sqs:queue": 1},
        expect_violations=[
            ExpectViolation(
                resource_type="lambda:function",
                resource_name="my-func",
                config_key="Runtime",
                actual_value="python3.9",
                expected_value="python3.12",
            ),
        ],
        guardrail_violations=[
            GuardrailViolationRef(
                guardrail_name="encryption-at-rest",
                resource_type="dynamodb:table",
                resource_name="my-table",
                detail="SSEDescription.Status = DISABLED",
            ),
        ],
        guidance="Switch to python3.12 and enable encryption.",
    )


# ===========================================================================
# T041: format_pattern_list and format_pattern_detail
# ===========================================================================


class TestFormatPatternList:
    def test_table_output(self, sample_pattern: Pattern, second_pattern: Pattern) -> None:
        result = format_pattern_list([sample_pattern, second_pattern])
        assert "serverless-api" in result
        assert "data-pipeline" in result
        assert "Pattern Library" in result

    def test_json_output(self, sample_pattern: Pattern) -> None:
        result = format_pattern_list([sample_pattern], as_json=True)
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "serverless-api"
        assert data[0]["resource_count"] == 2
        assert data[0]["tags"] == ["serverless", "api"]

    def test_empty_library(self) -> None:
        result = format_pattern_list([])
        assert "No patterns found" in result

    def test_tag_display(self, sample_pattern: Pattern) -> None:
        result = format_pattern_list([sample_pattern])
        assert "serverless" in result
        assert "api" in result


class TestFormatPatternDetail:
    def test_shows_all_fields(self, sample_pattern: Pattern) -> None:
        result = format_pattern_detail(sample_pattern)
        assert "serverless-api" in result
        assert "v1" in result
        assert "Standard serverless API" in result
        assert "platform-team" in result
        assert "serverless" in result
        assert "encryption-at-rest" in result
        assert "lambda:function" in result
        assert "count: 2" in result
        assert "Runtime" in result

    def test_json_output(self, sample_pattern: Pattern) -> None:
        result = format_pattern_detail(sample_pattern, as_json=True)
        data = json.loads(result)
        assert data["name"] == "serverless-api"
        assert len(data["resources"]) == 2

    def test_no_guardrails(self) -> None:
        p = Pattern(
            name="simple",
            description="No guardrails",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )
        result = format_pattern_detail(p)
        assert "Guardrails" not in result


# ===========================================================================
# T029: format_terminal_report and format_json_report
# ===========================================================================


class TestFormatTerminalReport:
    def test_single_match(self, single_match: PatternMatch) -> None:
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[single_match],
            threshold=0.25,
            unaccounted_types={},
        )
        result = format_terminal_report(report)
        assert "Combined Coverage" in result
        assert "serverless-api" in result
        assert "78%" in result
        assert "Aligned" in result
        assert "Missing" in result
        assert "Design-choice violations" in result
        assert "Guardrail violations" in result
        assert "Guidance" in result

    def test_multiple_matches(
        self,
        sample_pattern: Pattern,
        second_pattern: Pattern,
    ) -> None:
        match1 = PatternMatch(
            pattern=sample_pattern,
            score=0.75,
            aligned={"lambda:function": (2, 2)},
            missing={"apigateway:rest-api": 1},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        match2 = PatternMatch(
            pattern=second_pattern,
            score=0.50,
            aligned={"sqs:queue": (1, 1)},
            missing={"lambda:function": 3},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[match1, match2],
            threshold=0.25,
            unaccounted_types={"ec2:instance": 5},
        )
        result = format_terminal_report(report)
        assert "serverless-api" in result
        assert "data-pipeline" in result
        assert "2 pattern(s) matched" in result
        assert "ec2:instance" in result

    def test_no_matches(self) -> None:
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[],
            threshold=0.25,
        )
        result = format_terminal_report(report)
        assert "No patterns matched" in result
        assert "25%" in result

    def test_violations_formatting(self, single_match: PatternMatch) -> None:
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[single_match],
            threshold=0.25,
        )
        result = format_terminal_report(report)
        assert "Runtime" in result
        assert "python3.9" in result
        assert "python3.12" in result
        assert "encryption-at-rest" in result
        assert "SSEDescription.Status" in result

    def test_coverage_summary(self) -> None:
        p = Pattern(
            name="test",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )
        match = PatternMatch(
            pattern=p,
            score=1.0,
            aligned={"s3:bucket": (1, 1)},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[match],
            threshold=0.25,
            coverage_summary="Full coverage achieved.",
        )
        result = format_terminal_report(report)
        assert "Coverage Summary" in result
        assert "Full coverage achieved" in result


class TestFormatJsonReport:
    def test_single_match(self, single_match: PatternMatch) -> None:
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[single_match],
            threshold=0.25,
            unaccounted_types={"sqs:queue": 1},
        )
        result = format_json_report(report)
        assert result["snapshot_name"] == "snap-1"
        assert result["threshold"] == 0.25
        assert len(result["matches"]) == 1
        m = result["matches"][0]
        assert m["pattern_name"] == "serverless-api"
        assert m["score"] == 0.78
        assert len(m["expect_violations"]) == 1
        assert len(m["guardrail_violations"]) == 1
        assert m["guidance"] == "Switch to python3.12 and enable encryption."
        assert result["unaccounted_types"] == {"sqs:queue": 1}

    def test_no_guidance_omitted(self) -> None:
        p = Pattern(
            name="test",
            description="d",
            version=1,
            tags=[],
            owner="o",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )
        match = PatternMatch(
            pattern=p,
            score=1.0,
            aligned={},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[match],
            threshold=0.25,
        )
        result = format_json_report(report)
        assert "guidance" not in result["matches"][0]

    def test_empty_report(self) -> None:
        report = ComparisonReport(
            snapshot_name="snap-1",
            matches=[],
            threshold=0.5,
        )
        result = format_json_report(report)
        assert result["matches"] == []
        assert result["snapshot_name"] == "snap-1"
        assert result["threshold"] == 0.5


# ===========================================================================
# format_compliance_report
# ===========================================================================


class TestFormatComplianceReport:
    def test_terminal_output(self) -> None:
        data = {
            "total_snapshots": 2,
            "snapshots": [
                {
                    "snapshot_name": "snap-1",
                    "match_count": 2,
                    "top_pattern": "serverless-api",
                    "top_score": 0.9,
                },
                {
                    "snapshot_name": "snap-2",
                    "match_count": 0,
                    "top_pattern": None,
                    "top_score": 0.0,
                },
            ],
            "pattern_adoption": {"serverless-api": 1},
            "accounts_with_no_matches": ["snap-2"],
        }
        result = format_compliance_report(data)
        assert "Compliance Report (2 snapshots)" in result
        assert "snap-1" in result
        assert "snap-2" in result
        assert "serverless-api" in result
        assert "Accounts with no matches" in result
        assert "Pattern adoption" in result

    def test_json_output(self) -> None:
        data = {
            "total_snapshots": 1,
            "snapshots": [
                {
                    "snapshot_name": "snap-1",
                    "match_count": 1,
                    "top_pattern": "test",
                    "top_score": 0.8,
                },
            ],
            "pattern_adoption": {"test": 1},
            "accounts_with_no_matches": [],
        }
        result = format_compliance_report(data, as_json=True)
        parsed = json.loads(result)
        assert parsed["total_snapshots"] == 1
        assert len(parsed["snapshots"]) == 1
        assert parsed["pattern_adoption"]["test"] == 1

    def test_error_snapshot_in_terminal(self) -> None:
        data = {
            "total_snapshots": 1,
            "snapshots": [
                {
                    "snapshot_name": "bad-snap",
                    "error": "Snapshot not found",
                },
            ],
            "pattern_adoption": {},
            "accounts_with_no_matches": [],
        }
        result = format_compliance_report(data)
        assert "bad-snap" in result
        assert "ERROR" in result
        assert "Snapshot not found" in result
