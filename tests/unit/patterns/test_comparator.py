"""Tests for pattern comparison engine."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.patterns.comparator import (
    _NOT_FOUND,
    compare_snapshot,
    compliance_report,
    compute_coverage,
    evaluate_expect_value,
    evaluate_expects,
    evaluate_pattern_guardrails,
    resolve_config_path,
    score_pattern,
)
from src.patterns.models import (
    ComparisonReport,
    Pattern,
    PatternMatch,
    PatternResource,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pattern(
    name: str = "test-pattern",
    resources: list | None = None,
    guardrails: list | None = None,
) -> Pattern:
    if resources is None:
        resources = []
    return Pattern(
        name=name,
        description="Test pattern",
        version=1,
        tags=["test"],
        owner="test-team",
        resources=resources,
        guardrails=guardrails or [],
    )


def _make_resource(
    resource_type: str = "lambda:function",
    name: str = "my-function",
    arn: str = "arn:aws:lambda:us-east-1:123456789012:function:my-function",
    raw_config: dict | None = None,
) -> MagicMock:
    resource = MagicMock()
    resource.resource_type = resource_type
    resource.name = name
    resource.arn = arn
    resource.raw_config = raw_config
    return resource


# ---------------------------------------------------------------------------
# T022: resolve_config_path + evaluate_expect_value
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    def test_simple_key(self) -> None:
        config = {"Runtime": "python3.12"}
        assert resolve_config_path(config, "Runtime") == "python3.12"

    def test_nested_dotted_path(self) -> None:
        config = {"SSEDescription": {"Status": "ENABLED"}}
        assert resolve_config_path(config, "SSEDescription.Status") == "ENABLED"

    def test_deeply_nested(self) -> None:
        config = {"a": {"b": {"c": {"d": 42}}}}
        assert resolve_config_path(config, "a.b.c.d") == 42

    def test_missing_key_returns_sentinel(self) -> None:
        config = {"Runtime": "python3.12"}
        assert resolve_config_path(config, "MissingKey") is _NOT_FOUND

    def test_missing_nested_key_returns_sentinel(self) -> None:
        config = {"SSEDescription": {"Status": "ENABLED"}}
        assert resolve_config_path(config, "SSEDescription.MissingNested") is _NOT_FOUND

    def test_partial_path_not_dict_returns_sentinel(self) -> None:
        config = {"Runtime": "python3.12"}
        assert resolve_config_path(config, "Runtime.SubKey") is _NOT_FOUND

    def test_empty_dict(self) -> None:
        assert resolve_config_path({}, "any.key") is _NOT_FOUND

    def test_value_is_zero(self) -> None:
        config = {"Timeout": 0}
        assert resolve_config_path(config, "Timeout") == 0

    def test_value_is_false(self) -> None:
        config = {"Enabled": False}
        assert resolve_config_path(config, "Enabled") is False

    def test_value_is_none(self) -> None:
        config = {"Value": None}
        assert resolve_config_path(config, "Value") is None


class TestEvaluateExpectValue:
    def test_exact_match_string(self) -> None:
        assert evaluate_expect_value("python3.12", "python3.12") is True

    def test_exact_match_string_fail(self) -> None:
        assert evaluate_expect_value("python3.11", "python3.12") is False

    def test_exact_match_coerces_int_to_str(self) -> None:
        assert evaluate_expect_value(30, "30") is True

    def test_exact_match_coerces_bool_to_str(self) -> None:
        assert evaluate_expect_value(True, "True") is True

    def test_gte_numeric(self) -> None:
        assert evaluate_expect_value(256, ">= 128") is True

    def test_gte_exact_boundary(self) -> None:
        assert evaluate_expect_value(128, ">= 128") is True

    def test_gte_below(self) -> None:
        assert evaluate_expect_value(64, ">= 128") is False

    def test_lte_numeric(self) -> None:
        assert evaluate_expect_value(64, "<= 128") is True

    def test_lte_above(self) -> None:
        assert evaluate_expect_value(256, "<= 128") is False

    def test_gt_numeric(self) -> None:
        assert evaluate_expect_value(129, "> 128") is True

    def test_gt_exact_boundary(self) -> None:
        assert evaluate_expect_value(128, "> 128") is False

    def test_lt_numeric(self) -> None:
        assert evaluate_expect_value(127, "< 128") is True

    def test_lt_exact_boundary(self) -> None:
        assert evaluate_expect_value(128, "< 128") is False

    def test_neq_numeric(self) -> None:
        assert evaluate_expect_value(64, "!= 128") is True

    def test_neq_same_value(self) -> None:
        assert evaluate_expect_value(128, "!= 128") is False

    def test_operator_with_non_numeric_actual_returns_false(self) -> None:
        assert evaluate_expect_value("not-a-number", ">= 128") is False

    def test_operator_with_float_values(self) -> None:
        assert evaluate_expect_value(3.14, ">= 3.0") is True


# ---------------------------------------------------------------------------
# T023: score_pattern
# ---------------------------------------------------------------------------


class TestScorePattern:
    def test_full_match(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=2),
                PatternResource(type="dynamodb:table", count=1),
            ]
        )
        snapshot_types = {
            "lambda:function": 2,
            "dynamodb:table": 1,
        }
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 1.0
        assert aligned == {
            "lambda:function": (2, 2),
            "dynamodb:table": (1, 1),
        }
        assert missing == {}
        assert extra == {}

    def test_partial_match(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=1),
                PatternResource(type="dynamodb:table", count=1),
                PatternResource(type="sqs:queue", count=1),
            ]
        )
        snapshot_types = {"lambda:function": 3}
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == pytest.approx(1.0 / 3.0)
        assert "lambda:function" in aligned
        assert "dynamodb:table" in missing
        assert "sqs:queue" in missing

    def test_no_match(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=1),
                PatternResource(type="dynamodb:table", count=1),
            ]
        )
        snapshot_types = {"ec2:instance": 5, "rds:instance": 2}
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 0.0
        assert aligned == {}
        assert len(missing) == 2
        assert "ec2:instance" in extra
        assert "rds:instance" in extra

    def test_count_mismatch_still_aligned(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=3),
            ]
        )
        snapshot_types = {"lambda:function": 1}
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 1.0
        assert aligned == {"lambda:function": (1, 3)}

    def test_extra_snapshot_types(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=1),
            ]
        )
        snapshot_types = {
            "lambda:function": 1,
            "ec2:instance": 3,
            "s3:bucket": 2,
        }
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 1.0
        assert extra == {"ec2:instance": 3, "s3:bucket": 2}

    def test_empty_pattern_zero_score(self) -> None:
        pattern = _make_pattern(resources=[])
        snapshot_types = {"lambda:function": 5}
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 0.0

    def test_duplicate_resource_types_aggregated(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=2),
                PatternResource(type="lambda:function", count=3),
            ]
        )
        snapshot_types = {"lambda:function": 4}
        score, aligned, missing, extra = score_pattern(pattern, snapshot_types)
        assert score == 1.0
        assert aligned == {"lambda:function": (4, 5)}


# ---------------------------------------------------------------------------
# T024: evaluate_expects
# ---------------------------------------------------------------------------


class TestEvaluateExpects:
    def test_single_resource_all_pass(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"Runtime": "python3.12", "Timeout": "30"},
                ),
            ]
        )
        resource = _make_resource(
            raw_config={"Runtime": "python3.12", "Timeout": 30},
        )
        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert violations == []

    def test_single_resource_violation(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"Runtime": "python3.12"},
                ),
            ]
        )
        resource = _make_resource(
            raw_config={"Runtime": "python3.9"},
        )
        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert len(violations) == 1
        assert violations[0].resource_type == "lambda:function"
        assert violations[0].config_key == "Runtime"
        assert violations[0].actual_value == "python3.9"
        assert violations[0].expected_value == "python3.12"

    def test_multiple_instances_per_instance_reporting(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=3,
                    expect={"Runtime": "python3.12"},
                ),
            ]
        )
        fn1 = _make_resource(name="fn-good", raw_config={"Runtime": "python3.12"})
        fn2 = _make_resource(name="fn-bad1", raw_config={"Runtime": "python3.9"})
        fn3 = _make_resource(name="fn-bad2", raw_config={"Runtime": "nodejs18.x"})

        violations = evaluate_expects(pattern, {"lambda:function": [fn1, fn2, fn3]})
        assert len(violations) == 2
        violated_names = {v.resource_name for v in violations}
        assert violated_names == {"fn-bad1", "fn-bad2"}

    def test_missing_raw_config_skips_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"Runtime": "python3.12"},
                ),
            ]
        )
        resource = _make_resource(raw_config=None)

        with caplog.at_level(logging.WARNING, logger="src.patterns.comparator"):
            violations = evaluate_expects(pattern, {"lambda:function": [resource]})

        assert violations == []
        assert "no raw_config" in caplog.text

    def test_missing_config_path_creates_violation(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"NonExistent.Path": "expected-value"},
                ),
            ]
        )
        resource = _make_resource(raw_config={"Runtime": "python3.12"})

        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert len(violations) == 1
        assert violations[0].config_key == "NonExistent.Path"
        assert violations[0].actual_value is None

    def test_nested_expect_key(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="dynamodb:table",
                    count=1,
                    expect={"SSEDescription.Status": "ENABLED"},
                ),
            ]
        )
        resource = _make_resource(
            resource_type="dynamodb:table",
            name="my-table",
            raw_config={"SSEDescription": {"Status": "ENABLED"}},
        )
        violations = evaluate_expects(pattern, {"dynamodb:table": [resource]})
        assert violations == []

    def test_operator_expect_passes(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"MemorySize": ">= 128"},
                ),
            ]
        )
        resource = _make_resource(raw_config={"MemorySize": 256})
        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert violations == []

    def test_operator_expect_fails(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"MemorySize": ">= 512"},
                ),
            ]
        )
        resource = _make_resource(raw_config={"MemorySize": 128})
        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert len(violations) == 1
        assert violations[0].actual_value == 128
        assert violations[0].expected_value == ">= 512"

    def test_no_expect_fields_no_violations(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(type="lambda:function", count=1),
            ]
        )
        resource = _make_resource(raw_config={"Runtime": "python3.12"})
        violations = evaluate_expects(pattern, {"lambda:function": [resource]})
        assert violations == []

    def test_no_matching_resources_in_snapshot(self) -> None:
        pattern = _make_pattern(
            resources=[
                PatternResource(
                    type="lambda:function",
                    count=1,
                    expect={"Runtime": "python3.12"},
                ),
            ]
        )
        violations = evaluate_expects(pattern, {"ec2:instance": [_make_resource()]})
        assert violations == []


# ---------------------------------------------------------------------------
# T025: evaluate_pattern_guardrails
# ---------------------------------------------------------------------------


class TestEvaluatePatternGuardrails:
    def test_no_guardrails_returns_empty(self) -> None:
        pattern = _make_pattern(guardrails=[])
        result = evaluate_pattern_guardrails(pattern, {})
        assert result == []

    @patch("src.guardrails.evaluator.GuardrailEvaluator", autospec=True)
    @patch("src.guardrails.loader.load_builtin_guardrails")
    def test_referenced_guardrail_found_with_violations(
        self,
        mock_load_builtins: MagicMock,
        mock_evaluator_cls: MagicMock,
    ) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            Severity,
        )

        mock_guardrail = MagicMock()
        mock_guardrail.id = "GR-ENC-001"
        mock_load_builtins.return_value = [mock_guardrail]

        mock_evaluation = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="Encryption check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.FAIL,
            failure_reason="Encryption not enabled",
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_resource.return_value = [mock_evaluation]
        mock_evaluator_cls.return_value = mock_evaluator

        pattern = _make_pattern(guardrails=["GR-ENC-001"])
        resource = _make_resource(resource_type="s3:bucket", name="my-bucket")

        violations = evaluate_pattern_guardrails(pattern, {"s3:bucket": [resource]})

        assert len(violations) == 1
        assert violations[0].guardrail_name == "GR-ENC-001"
        assert violations[0].resource_name == "my-bucket"
        assert violations[0].detail == "Encryption not enabled"

    @patch("src.guardrails.loader.load_builtin_guardrails")
    def test_referenced_guardrail_not_found_logs_warning(
        self,
        mock_load_builtins: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_load_builtins.return_value = []

        pattern = _make_pattern(guardrails=["GR-NONEXISTENT-001"])

        with caplog.at_level(logging.WARNING, logger="src.patterns.comparator"):
            violations = evaluate_pattern_guardrails(pattern, {})

        assert violations == []
        assert "GR-NONEXISTENT-001" in caplog.text
        assert "not found" in caplog.text

    @patch("src.guardrails.evaluator.GuardrailEvaluator", autospec=True)
    @patch("src.guardrails.loader.load_builtin_guardrails")
    def test_passing_guardrail_no_violations(
        self,
        mock_load_builtins: MagicMock,
        mock_evaluator_cls: MagicMock,
    ) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            Severity,
        )

        mock_guardrail = MagicMock()
        mock_guardrail.id = "GR-ENC-001"
        mock_load_builtins.return_value = [mock_guardrail]

        mock_evaluation = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="Encryption check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.PASS,
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_resource.return_value = [mock_evaluation]
        mock_evaluator_cls.return_value = mock_evaluator

        pattern = _make_pattern(guardrails=["GR-ENC-001"])
        resource = _make_resource(resource_type="s3:bucket", name="my-bucket")

        violations = evaluate_pattern_guardrails(pattern, {"s3:bucket": [resource]})
        assert violations == []

    @patch("src.guardrails.loader.load_policy")
    @patch("src.guardrails.evaluator.GuardrailEvaluator", autospec=True)
    @patch("src.guardrails.loader.load_builtin_guardrails")
    def test_custom_policy_path_loads_additional_guardrails(
        self,
        mock_load_builtins: MagicMock,
        mock_evaluator_cls: MagicMock,
        mock_load_policy: MagicMock,
    ) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            Severity,
        )

        mock_load_builtins.return_value = []

        custom_guardrail = MagicMock()
        custom_guardrail.id = "GR-CUSTOM-001"
        mock_policy = MagicMock()
        mock_policy.guardrails = [custom_guardrail]
        mock_load_policy.return_value = mock_policy

        mock_evaluation = GuardrailEvaluation(
            guardrail_id="GR-CUSTOM-001",
            guardrail_short_description="Custom check",
            severity=Severity.MEDIUM,
            action=Action.WARN,
            resource_type="lambda:function",
            resource_name="my-fn",
            resource_arn="arn:aws:lambda:us-east-1:123456789012:function:my-fn",
            result=EvaluationResult.FAIL,
            failure_reason="Custom rule failed",
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_resource.return_value = [mock_evaluation]
        mock_evaluator_cls.return_value = mock_evaluator

        pattern = _make_pattern(guardrails=["GR-CUSTOM-001"])
        resource = _make_resource()

        violations = evaluate_pattern_guardrails(
            pattern,
            {"lambda:function": [resource]},
            guardrails_policy_path="/path/to/policy.yaml",
        )

        mock_load_policy.assert_called_once_with("/path/to/policy.yaml")
        assert len(violations) == 1
        assert violations[0].guardrail_name == "GR-CUSTOM-001"


# ---------------------------------------------------------------------------
# T026: compare_snapshot
# ---------------------------------------------------------------------------


class TestCompareSnapshot:
    @patch("src.snapshot.storage.SnapshotStorage")
    @patch("src.patterns.comparator.load_library")
    def test_full_flow_multiple_patterns(
        self,
        mock_load_lib: MagicMock,
        mock_storage_cls: MagicMock,
    ) -> None:
        r1 = _make_resource(
            resource_type="lambda:function",
            name="fn1",
            raw_config={"Runtime": "python3.12"},
        )
        r2 = _make_resource(
            resource_type="dynamodb:table",
            name="table1",
            raw_config={"SSEDescription": {"Status": "ENABLED"}},
        )
        r3 = _make_resource(
            resource_type="ec2:instance",
            name="server1",
            raw_config={},
        )

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [r1, r2, r3]
        mock_storage.load_snapshot.return_value = mock_snapshot

        high_match = _make_pattern(
            name="serverless-api",
            resources=[
                PatternResource(type="lambda:function", count=1),
                PatternResource(type="dynamodb:table", count=1),
            ],
        )
        low_match = _make_pattern(
            name="compute-heavy",
            resources=[
                PatternResource(type="ec2:instance", count=1),
                PatternResource(type="rds:instance", count=1),
                PatternResource(type="elasticache:cluster", count=1),
            ],
        )
        mock_load_lib.return_value = [high_match, low_match]

        report = compare_snapshot("test-snap", "/lib/path", threshold=0.25)

        assert isinstance(report, ComparisonReport)
        assert report.snapshot_name == "test-snap"
        assert report.threshold == 0.25
        assert len(report.matches) == 2
        assert report.matches[0].pattern.name == "serverless-api"
        assert report.matches[0].score == 1.0
        assert report.matches[1].pattern.name == "compute-heavy"
        assert report.matches[1].score == pytest.approx(1.0 / 3.0)

    @patch("src.snapshot.storage.SnapshotStorage")
    @patch("src.patterns.comparator.load_library")
    def test_threshold_filtering(
        self,
        mock_load_lib: MagicMock,
        mock_storage_cls: MagicMock,
    ) -> None:
        r1 = _make_resource(resource_type="lambda:function", name="fn1", raw_config={})

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [r1]
        mock_storage.load_snapshot.return_value = mock_snapshot

        good_pattern = _make_pattern(
            name="good",
            resources=[PatternResource(type="lambda:function", count=1)],
        )
        bad_pattern = _make_pattern(
            name="bad",
            resources=[
                PatternResource(type="rds:instance", count=1),
                PatternResource(type="ec2:instance", count=1),
                PatternResource(type="ecs:service", count=1),
                PatternResource(type="elasticache:cluster", count=1),
            ],
        )
        mock_load_lib.return_value = [good_pattern, bad_pattern]

        report = compare_snapshot("snap", "/lib", threshold=0.5)

        assert len(report.matches) == 1
        assert report.matches[0].pattern.name == "good"

    @patch("src.snapshot.storage.SnapshotStorage")
    @patch("src.patterns.comparator.load_pattern")
    def test_target_single_pattern(
        self,
        mock_load_pat: MagicMock,
        mock_storage_cls: MagicMock,
    ) -> None:
        r1 = _make_resource(resource_type="lambda:function", name="fn1", raw_config={})

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [r1]
        mock_storage.load_snapshot.return_value = mock_snapshot

        target = _make_pattern(
            name="specific",
            resources=[PatternResource(type="lambda:function", count=1)],
        )
        mock_load_pat.return_value = target

        report = compare_snapshot("snap", "/lib", target_pattern="/patterns/specific.yaml")

        mock_load_pat.assert_called_once_with("/patterns/specific.yaml")
        assert len(report.matches) == 1
        assert report.matches[0].pattern.name == "specific"

    @patch("src.snapshot.storage.SnapshotStorage")
    @patch("src.patterns.comparator.load_library")
    def test_sorted_by_score_descending(
        self,
        mock_load_lib: MagicMock,
        mock_storage_cls: MagicMock,
    ) -> None:
        r1 = _make_resource(resource_type="lambda:function", name="fn1", raw_config={})
        r2 = _make_resource(resource_type="dynamodb:table", name="tbl1", raw_config={})
        r3 = _make_resource(resource_type="sqs:queue", name="q1", raw_config={})

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [r1, r2, r3]
        mock_storage.load_snapshot.return_value = mock_snapshot

        p1 = _make_pattern(
            name="one-of-three",
            resources=[
                PatternResource(type="lambda:function", count=1),
                PatternResource(type="rds:instance", count=1),
                PatternResource(type="ec2:instance", count=1),
            ],
        )
        p2 = _make_pattern(
            name="two-of-two",
            resources=[
                PatternResource(type="lambda:function", count=1),
                PatternResource(type="dynamodb:table", count=1),
            ],
        )
        mock_load_lib.return_value = [p1, p2]

        report = compare_snapshot("snap", "/lib", threshold=0.25)
        assert report.matches[0].pattern.name == "two-of-two"
        assert report.matches[0].score == 1.0
        assert report.matches[1].pattern.name == "one-of-three"

    @patch("src.snapshot.storage.SnapshotStorage")
    @patch("src.patterns.comparator.load_library")
    def test_no_matches_produces_empty_report(
        self,
        mock_load_lib: MagicMock,
        mock_storage_cls: MagicMock,
    ) -> None:
        r1 = _make_resource(resource_type="ec2:instance", name="i-1", raw_config={})

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [r1]
        mock_storage.load_snapshot.return_value = mock_snapshot

        pattern = _make_pattern(
            name="no-overlap",
            resources=[PatternResource(type="lambda:function", count=1)],
        )
        mock_load_lib.return_value = [pattern]

        report = compare_snapshot("snap", "/lib", threshold=0.5)
        assert report.matches == []
        assert report.unaccounted_types == {"ec2:instance": 1}


# ---------------------------------------------------------------------------
# T027: compute_coverage
# ---------------------------------------------------------------------------


class TestComputeCoverage:
    def test_all_covered(self) -> None:
        match = PatternMatch(
            pattern=_make_pattern(),
            score=1.0,
            aligned={"lambda:function": (2, 2), "dynamodb:table": (1, 1)},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        snapshot_types = {"lambda:function": 2, "dynamodb:table": 1}
        unaccounted = compute_coverage([match], snapshot_types)
        assert unaccounted == {}

    def test_partially_covered(self) -> None:
        match = PatternMatch(
            pattern=_make_pattern(),
            score=0.5,
            aligned={"lambda:function": (2, 2)},
            missing={"dynamodb:table": 1},
            extra={"ec2:instance": 3},
            expect_violations=[],
            guardrail_violations=[],
        )
        snapshot_types = {
            "lambda:function": 2,
            "ec2:instance": 3,
            "s3:bucket": 5,
        }
        unaccounted = compute_coverage([match], snapshot_types)
        assert unaccounted == {"ec2:instance": 3, "s3:bucket": 5}

    def test_no_matches_all_unaccounted(self) -> None:
        snapshot_types = {
            "lambda:function": 2,
            "ec2:instance": 3,
        }
        unaccounted = compute_coverage([], snapshot_types)
        assert unaccounted == snapshot_types

    def test_multiple_matches_union_coverage(self) -> None:
        match1 = PatternMatch(
            pattern=_make_pattern(name="p1"),
            score=0.5,
            aligned={"lambda:function": (1, 1)},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        match2 = PatternMatch(
            pattern=_make_pattern(name="p2"),
            score=0.5,
            aligned={"dynamodb:table": (1, 1)},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        snapshot_types = {
            "lambda:function": 1,
            "dynamodb:table": 1,
            "ec2:instance": 2,
        }
        unaccounted = compute_coverage([match1, match2], snapshot_types)
        assert unaccounted == {"ec2:instance": 2}

    def test_empty_snapshot_types(self) -> None:
        match = PatternMatch(
            pattern=_make_pattern(),
            score=1.0,
            aligned={},
            missing={},
            extra={},
            expect_violations=[],
            guardrail_violations=[],
        )
        unaccounted = compute_coverage([match], {})
        assert unaccounted == {}


# ---------------------------------------------------------------------------
# compliance_report
# ---------------------------------------------------------------------------


class TestComplianceReport:
    @patch("src.patterns.comparator.compare_snapshot")
    def test_multiple_snapshots(self, mock_compare: MagicMock) -> None:
        pattern_a = _make_pattern(name="pattern-a")
        pattern_b = _make_pattern(name="pattern-b")

        report_1 = ComparisonReport(
            snapshot_name="snap-1",
            matches=[
                PatternMatch(
                    pattern=pattern_a,
                    score=0.9,
                    aligned={"lambda:function": (1, 1)},
                    missing={},
                    extra={},
                    expect_violations=[],
                    guardrail_violations=[],
                ),
            ],
            threshold=0.25,
        )
        report_2 = ComparisonReport(
            snapshot_name="snap-2",
            matches=[
                PatternMatch(
                    pattern=pattern_b,
                    score=0.7,
                    aligned={"s3:bucket": (1, 1)},
                    missing={},
                    extra={},
                    expect_violations=[],
                    guardrail_violations=[],
                ),
            ],
            threshold=0.25,
        )
        mock_compare.side_effect = [report_1, report_2]

        result = compliance_report(
            snapshot_names=["snap-1", "snap-2"],
            library_path="/lib",
        )

        assert result["total_snapshots"] == 2
        assert len(result["snapshots"]) == 2
        assert result["snapshots"][0]["snapshot_name"] == "snap-1"
        assert result["snapshots"][0]["match_count"] == 1
        assert result["snapshots"][0]["top_pattern"] == "pattern-a"
        assert result["snapshots"][1]["top_pattern"] == "pattern-b"
        assert result["accounts_with_no_matches"] == []

    @patch("src.patterns.comparator.compare_snapshot")
    def test_no_matches_tracked(self, mock_compare: MagicMock) -> None:
        report = ComparisonReport(
            snapshot_name="empty-snap",
            matches=[],
            threshold=0.25,
        )
        mock_compare.return_value = report

        result = compliance_report(
            snapshot_names=["empty-snap"],
            library_path="/lib",
        )

        assert result["accounts_with_no_matches"] == ["empty-snap"]
        assert result["snapshots"][0]["match_count"] == 0
        assert result["snapshots"][0]["top_pattern"] is None
        assert result["snapshots"][0]["top_score"] == 0.0

    @patch("src.patterns.comparator.compare_snapshot")
    def test_pattern_adoption_counts(self, mock_compare: MagicMock) -> None:
        shared_pattern = _make_pattern(name="shared")

        report_1 = ComparisonReport(
            snapshot_name="snap-1",
            matches=[
                PatternMatch(
                    pattern=shared_pattern,
                    score=0.8,
                    aligned={"lambda:function": (1, 1)},
                    missing={},
                    extra={},
                    expect_violations=[],
                    guardrail_violations=[],
                ),
            ],
            threshold=0.25,
        )
        report_2 = ComparisonReport(
            snapshot_name="snap-2",
            matches=[
                PatternMatch(
                    pattern=shared_pattern,
                    score=0.6,
                    aligned={"lambda:function": (2, 2)},
                    missing={},
                    extra={},
                    expect_violations=[],
                    guardrail_violations=[],
                ),
            ],
            threshold=0.25,
        )
        mock_compare.side_effect = [report_1, report_2]

        result = compliance_report(
            snapshot_names=["snap-1", "snap-2"],
            library_path="/lib",
        )

        assert result["pattern_adoption"]["shared"] == 2

    @patch("src.patterns.comparator.compare_snapshot")
    def test_error_handling(self, mock_compare: MagicMock) -> None:
        mock_compare.side_effect = FileNotFoundError("Snapshot 'bad' not found")

        result = compliance_report(
            snapshot_names=["bad"],
            library_path="/lib",
        )

        assert len(result["snapshots"]) == 1
        assert "error" in result["snapshots"][0]
        assert "not found" in result["snapshots"][0]["error"]
